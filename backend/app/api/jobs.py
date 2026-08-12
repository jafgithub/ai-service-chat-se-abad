from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.job import Job
from app.schemas.order import (
    PlaceOrderRequest, PlaceOrderResponse, OrderItemOut, OrderItemIn,
)
from app.services import cart_service, job_service
from app.services.emails import send_order_emails
from app.services.job_service import OrderError

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _response_for(order: Job) -> PlaceOrderResponse:
    """Build the response from a stored order, so a repeated request with the
    same idempotency key returns exactly what the first one did."""
    items = order.items_json or []
    subtotal = round(sum(float(i.get("subtotal", 0)) for i in items), 2)
    total    = float(order.total_amount)
    return PlaceOrderResponse(
        order_id=order.id,
        customer_id=order.customer_id,
        total_amount=total,
        subtotal=subtotal,
        tax=round(total - subtotal, 2),
        status=order.status,
        items=[
            OrderItemOut(
                product_id=d["product_id"],
                product_name=d["product_name"],
                quantity=d["quantity"],
                unit=d.get("unit", "unit"),
                unit_price=d["unit_price"],
                subtotal=d["subtotal"],
            )
            for d in items
        ],
        delivery_date=order.delivery_date,
        delivery_time=order.delivery_time,
        delivery_notes=order.delivery_notes,
        payment_method=order.payment_method,
    )


@router.get("/by-key/{idempotency_key}", response_model=PlaceOrderResponse)
def get_order_by_key(idempotency_key: str, db: Session = Depends(get_db)):
    """Look up an order the caller already placed.

    This exists for the return trip from Stripe or PayPal. The provider sends
    the shopper back to `/chat?paid={order_id}`, and the page has to show them
    what they just bought.

    It is deliberately keyed on the idempotency key rather than the order id.
    The key is a UUID the browser generated for that one checkout, so it is
    unguessable and the shopper is the only one holding it; `GET /orders/{id}`
    would let anyone walk the integers and read other people's names, addresses
    and baskets.

    404 for anything not found, with no distinction between "no such key" and
    "malformed", so this cannot be used as an oracle.
    """
    # A real key is a UUID. Reject short strings before touching the database.
    if len(idempotency_key) < 16:
        raise HTTPException(status_code=404, detail="Job not found.")

    order = job_service.find_by_idempotency_key(db, idempotency_key)
    if order is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _response_for(order)


@router.post("", response_model=PlaceOrderResponse)
def place_order(
    payload: PlaceOrderRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Place an order.

    With payments on, the order is created `pending` and stays that way until a
    provider webhook confirms it: the shopper is then sent to `/payments/checkout`.
    With payments off it is confirmed immediately, which is how this endpoint
    behaved before payment existed.

    Stock is reserved here either way. Reserving at payment time instead would
    mean discovering the last unit was gone *after* taking the money.
    """
    # A repeat of a request we already handled returns the original order rather
    # than making a second one. Covers double clicks, retries and replays.
    existing = job_service.find_by_idempotency_key(db, payload.idempotency_key)
    if existing is not None:
        return _response_for(existing)

    customer = job_service.upsert_customer(db, payload.customer)

    # Prefer explicit items (back-compat); otherwise build from the session cart.
    session = None
    order_items = list(payload.items or [])
    if not order_items and payload.session_id:
        session = cart_service.get_or_create_session(db, payload.session_id)
        cart = cart_service.serialize_cart(db, session)
        order_items = [
            OrderItemIn(product_id=li["item_id"], quantity=li["quantity"])
            for li in cart["items"]
        ]

    if not order_items:
        raise HTTPException(status_code=400, detail="Your cart is empty.")

    try:
        item_details, subtotal_amount = job_service.build_line_items(db, order_items)
    except OrderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    tax_amount, grand_total = job_service.totals_for(subtotal_amount)

    # Whether money is taken before the order counts is now a per-order
    # question, not a global one: cash on delivery confirms immediately, a card
    # or PayPal order waits for the provider's webhook.
    method = payload.payment_method
    pay_first = method != "cod" and settings.PAYMENTS_ENABLED

    # Refuse rather than quietly confirm. If cash is switched off and we let
    # this through, the order would be marked confirmed with nobody having paid
    # and nobody told to collect.
    if method == "cod" and not settings.COD_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Cash on delivery is not available. Please choose a payment method.",
        )
    if method != "cod" and not settings.PAYMENTS_ENABLED:
        raise HTTPException(
            status_code=400, detail="Online payment is unavailable right now.",
        )

    order = job_service.create_order(
        db, customer, item_details, grand_total,
        status="pending" if pay_first else "confirmed",
        notes=job_service.note_with_payment_method(payload.notes, method),
        delivery_date=payload.delivery_date,
        delivery_time=payload.delivery_time,
        delivery_notes=payload.delivery_notes,
        idempotency_key=payload.idempotency_key,
        payment_method=method,
    )

    # The order owns these items now, so the cart must not be reusable.
    if session is not None:
        cart_service.clear(db, session)

    db.commit()
    db.refresh(order)

    # Only when nothing is being charged. Otherwise the webhook sends them, once
    # the money has actually arrived.
    if not pay_first:
        background.add_task(send_order_emails, order.id)

    return _response_for(order)
