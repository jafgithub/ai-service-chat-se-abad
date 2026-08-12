"""Starting a payment, and hearing back about it.

Two endpoints. `/checkout` turns a pending order into a provider session and
hands back a URL for the browser to visit. `/webhook/{provider}` is how we learn
what happened, because the shopper's browser returning to the success page is
not proof of anything: they can close the tab, or forge the redirect.

Everything money-related is decided by the webhook, never by the redirect.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.job import Job
from app.models.payment import Payment
from app.services import job_service, payments
from app.services.emails import send_order_emails
from app.services.booking_notify import send_payment_receipt
from app.models.appointment import Appointment

logger = logging.getLogger("payments")

router = APIRouter(prefix="/payments", tags=["payments"])


class CheckoutRequest(BaseModel):
    order_id: int
    provider: str
    # Where the provider sends the browser afterwards. Optional so the server
    # falls back to its own configured frontend URL.
    success_url: str | None = None
    cancel_url: str | None = None


class CheckoutResponse(BaseModel):
    url: str
    provider: str
    provider_ref: str


@router.get("/providers")
def list_providers():
    """Which methods the checkout should offer. Empty when payments are off."""
    if not settings.PAYMENTS_ENABLED:
        return {"enabled": False, "providers": []}
    return {"enabled": True, "providers": payments.available()}


def _checkout_description(db: Session, order: Job) -> str:
    """The line the payment provider shows on its own page."""
    booked = db.query(Appointment).filter(Appointment.job_id == order.id).first()
    if booked is None:
        return f"{settings.SHOP_NAME} order #{order.id}"

    items = order.items_json or []
    what = (items[0].get("name") if items else None) or "Service"
    return f"{what}, {booked.starts_at:%-d %b %-I:%M %p} (BK-{order.id:05d})"


@router.post("/checkout", response_model=CheckoutResponse)
def start_checkout(payload: CheckoutRequest, db: Session = Depends(get_db)):
    if not settings.PAYMENTS_ENABLED:
        raise HTTPException(status_code=503, detail="Payments are not enabled.")

    order = db.query(Job).filter(Job.id == payload.order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if order.payment_method == "cod" or order.payment_status == "cod":
        raise HTTPException(
            status_code=409, detail="This one is being settled in cash on the day.",
        )
    if order.payment_status == "paid":
        # Paying again would take the money twice.
        raise HTTPException(status_code=409, detail="This has already been paid for.")

    # A booking and a shop order reach this point in different states, and the
    # test has to allow both. A shop order waits at "pending" and is confirmed
    # by the payment. A booking is "scheduled" the moment it is made, because
    # the slot is genuinely taken whether or not the money has arrived, so its
    # status says nothing about payment; `payment_status` does, and it was
    # checked above.
    is_booking = order.payment_status in ("unpaid", "paid")
    if not is_booking and order.status != "pending":
        raise HTTPException(status_code=409, detail=f"Job is already {order.status}.")
    if order.status == "cancelled":
        raise HTTPException(status_code=409, detail="That booking was cancelled.")

    try:
        provider = payments.get(payload.provider)
    except payments.PaymentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not provider.is_configured():
        raise HTTPException(
            status_code=503,
            detail=f"{payload.provider} is not configured on the server.",
        )

    base = (settings.FRONTEND_URL or "").rstrip("/")
    try:
        session = provider.create_checkout(
            order_id=order.id,
            amount=float(order.total_amount),
            currency=settings.PAYMENT_CURRENCY,
            # What the customer reads on the payment page. A booking is named
            # by its reference and what was booked, not by "order #21": the
            # reference is what they were given a moment ago and what they will
            # quote if anything goes wrong.
            description=_checkout_description(db, order),
            success_url=payload.success_url or f"{base}/chat?paid={order.id}",
            cancel_url=payload.cancel_url or f"{base}/chat?cancelled={order.id}",
        )
    except payments.PaymentError as exc:
        # Explicit, because the global handler in main.py would otherwise turn
        # this into an unhelpful 500.
        raise HTTPException(status_code=502, detail=str(exc))

    db.add(Payment(
        order_id=order.id,
        provider=provider.name,
        provider_ref=session.provider_ref,
        status="pending",
        amount=order.total_amount,
        currency=settings.PAYMENT_CURRENCY,
    ))
    db.commit()

    return CheckoutResponse(
        url=session.url, provider=provider.name, provider_ref=session.provider_ref,
    )


@router.post("/webhook/{provider_name}")
async def webhook(
    provider_name: str,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Apply a provider's verdict to an order.

    Always returns 200 once the signature checks out, even for events we ignore.
    A non-2xx makes both providers retry for days, and retrying will not help
    with an event type we simply do not handle.
    """
    # Raw bytes, not the parsed body: Stripe signs the exact payload, so
    # re-serialising it would fail verification.
    raw = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    try:
        provider = payments.get(provider_name)
        event = provider.parse_webhook(raw, headers)
    except payments.PaymentError as exc:
        # 400, so an unsigned or forged call is rejected and not retried.
        logger.warning(f"[PAY] {provider_name} webhook rejected: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))

    logger.info(
        f"[PAY] {provider_name} event {event.raw_type} "
        f"ref={event.provider_ref} -> {event.status}"
    )

    if event.status == "ignored":
        return {"received": True, "handled": False, "reason": "event not handled"}

    payment = db.query(Payment).filter(
        Payment.provider == provider.name,
        Payment.provider_ref == event.provider_ref,
    ).first()
    if payment is None:
        # Not ours, or from before this deploy. Acknowledge so they stop retrying.
        logger.warning(f"[PAY] no payment row for {provider.name} ref {event.provider_ref}")
        return {"received": True, "handled": False, "reason": "unknown payment"}

    # Has this exact delivery already been applied? Ask before writing, because
    # storing the same event id back onto the same row is not a uniqueness
    # violation and would sail straight through the IntegrityError below.
    if event.event_id:
        already = db.query(Payment).filter(
            Payment.provider_event_id == event.event_id
        ).first()
        if already is not None:
            logger.info(f"[PAY] event {event.event_id} already applied, ignoring replay")
            return {"received": True, "handled": False, "reason": "duplicate event"}

    # Claim it. The unique column is the backstop for two deliveries arriving at
    # once, where both got past the check above.
    try:
        payment.provider_event_id = event.event_id
        db.flush()
    except IntegrityError:
        db.rollback()
        logger.info(f"[PAY] event {event.event_id} claimed concurrently, ignoring replay")
        return {"received": True, "handled": False, "reason": "duplicate event"}

    order = db.query(Job).filter(Job.id == payment.order_id).first()
    if order is None:
        db.commit()
        return {"received": True, "handled": False, "reason": "order missing"}

    # PayPal approval moves no money: it has to be captured, and the capture
    # sends its own COMPLETED event which is what actually confirms the order.
    if event.status == "approved":
        captured = provider.capture(event.provider_ref)
        db.commit()
        return {"received": True, "handled": True, "captured": captured}

    if event.status == "paid":
        payment.status = "paid"
        order.payment_status = "paid"

        # A booking is already scheduled and already has its confirmation email.
        # Running the shop's path over it would set the status to "confirmed",
        # wiping the booking's own lifecycle, and send an order confirmation
        # listing a delivery slot for a visit. So the two are told apart by
        # whether an appointment exists.
        appointment = (
            db.query(Appointment).filter(Appointment.job_id == order.id).first()
        )
        if appointment is not None:
            logger.info(f"[PAY] booking BK-{order.id:05d} paid by {provider.name}")
            background.add_task(send_payment_receipt, appointment.id)
        elif job_service.confirm_order(db, order):
            # Outside the request: SMTP is slow, and the provider is waiting on
            # this response to decide whether to retry.
            background.add_task(send_order_emails, order.id)

        db.commit()
        return {"received": True, "handled": True, "order_status": order.status}

    # failed or cancelled.
    payment.status = event.status

    # A booking keeps its slot. Somebody who abandons a card page has still
    # agreed a time with a business that has written it in the diary, and
    # cancelling their appointment because the card was declined would be a
    # surprising and expensive thing to do on their behalf. It simply stays
    # unpaid, and they can pay again or settle on the day.
    if db.query(Appointment).filter(Appointment.job_id == order.id).first() is not None:
        logger.info(
            f"[PAY] booking BK-{order.id:05d} payment {event.status}; "
            "the appointment stands and is still unpaid"
        )
        db.commit()
        return {"received": True, "handled": True, "order_status": order.status}

    job_service.cancel_order(db, order, reason=f"{provider.name} {event.raw_type}")
    db.commit()
    return {"received": True, "handled": True, "order_status": order.status}
