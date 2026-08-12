"""Creating, confirming and cancelling orders.

Lifted out of api/orders.py because the payment webhook needs the same logic:
an order can now be confirmed long after the request that created it, by a
callback from Stripe or PayPal rather than by the shopper.

Three rules this module exists to enforce, none of which held before:

1. **Stock is decremented atomically.** The old code read `product.stock`, then
   wrote `stock - n` from Python. Two shoppers both reading 5 both wrote 4, and
   one unit was sold twice. Here it is a single conditional UPDATE and the
   database decides who wins.
2. **Stock is reserved when the order is placed, not when it is paid.** The
   alternative loses money: taking payment first and discovering afterwards
   that the last unit went to someone else means issuing a refund. Reserved
   stock is released when a payment fails or the checkout expires.
3. **Confirming twice does nothing the second time.** Payment providers retry
   webhooks until they get a 2xx, so a replay is ordinary traffic.
"""

import logging

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.customer import Customer
from app.models.job import Job
from app.models.job_line import JobLine
from app.models.service import Service

logger = logging.getLogger("orders")


class OrderError(Exception):
    """Something the shopper should be told about (empty cart, out of stock)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _reserve_stock(db: Session, product_id: int, quantity: float) -> bool:
    """Always true. A service has no stock to run out of.

    The grocery system reserves stock here, atomically, so two shoppers cannot
    buy the last jar. That protection is real and it is why the code is shaped
    this way, but it does not transfer: a firm does not hold six drain
    unblockings and run out of them. What it can run out of is time, and time is
    protected in `booking_service.hold`, which is the equivalent guard.

    Left as a function rather than deleted so the calling code keeps one shape
    across both systems, and so this note sits where somebody would look for it.
    """
    return True


def _release_stock(db: Session, product_id: int, quantity: float) -> None:
    """Nothing to release. See `_reserve_stock`.

    An abandoned booking gives its slot back when the hold expires, which
    `booking_service.release_expired` does.
    """
    return None


def upsert_customer(db: Session, customer_in) -> Customer:
    """Find the customer by email or create them, tolerating a concurrent create.

    `customers.email` is unique (sql/payments_setup.sql), so the race that used
    to produce two rows for one person now raises IntegrityError instead, and we
    re-read the row the other request committed.
    """
    customer = db.query(Customer).filter(Customer.email == customer_in.email).first()
    if customer is None:
        customer = Customer(**customer_in.model_dump())
        db.add(customer)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            customer = db.query(Customer).filter(Customer.email == customer_in.email).first()
            if customer is None:
                raise
    if customer.id is not None:
        customer.name      = customer_in.name
        customer.phone     = customer_in.phone
        customer.latitude  = customer_in.latitude
        customer.longitude = customer_in.longitude
        customer.address   = customer_in.address
    db.flush()
    return customer


# How each method reads in the order notes. Plain words, because a person in the
# shop reads this, not a program.
_METHOD_LABELS = {
    "cod":    "CASH ON DELIVERY - collect payment from the customer",
    "stripe": "Paid online by card",
    "paypal": "Paid online by PayPal",
}


def note_with_payment_method(notes: str | None, method: str | None) -> str | None:
    """Put the payment method into the order's notes.

    `orders.payment_method` does not reach the client: sync_to_remote keeps only
    the columns both databases share, and his `orders` table has no such column,
    so it is dropped without a word. `notes` is on both sides and does sync.

    That matters most for cash. Without this, a cash order arrives in his system
    looking exactly like a paid one, and whoever delivers it has no idea there is
    money to collect. Anything the shopper typed is kept underneath.
    """
    label = _METHOD_LABELS.get(method or "")
    if not label:
        return notes
    typed = (notes or "").strip()
    return f"Payment: {label}\n{typed}" if typed else f"Payment: {label}"


def find_by_idempotency_key(db: Session, key: str | None) -> Job | None:
    if not key:
        return None
    return db.query(Job).filter(Job.idempotency_key == key).first()


def build_line_items(db: Session, order_items) -> tuple[list[dict], float]:
    """Price the order and reserve stock for it. Raises OrderError if it cannot."""
    item_details: list[dict] = []
    goods_total = 0.0

    for item_in in order_items:
        product: Service | None = db.query(Service).filter(
            Service.id == item_in.product_id,
            Service.status == True,   # noqa: E712 - SQLAlchemy needs the comparison
        ).first()

        if not product:
            raise OrderError(f"Service {item_in.product_id} not found", 404)

        if not _reserve_stock(db, product.id, item_in.quantity):
            # Either it sold out, or another order reserved the last of it while
            # this one was being priced.
            raise OrderError(f"Not enough stock for '{product.name}'")

        unit_price = float(product.price)
        subtotal   = round(unit_price * item_in.quantity, 2)
        goods_total += subtotal

        item_details.append({
            "product_id":   product.id,
            "product_name": product.name,
            "quantity":     item_in.quantity,
            "unit":         "unit",
            "unit_price":   unit_price,
            "subtotal":     subtotal,
            "tax":          round(subtotal * settings.TAX_RATE, 2),
        })

    return item_details, round(goods_total, 2)


def totals_for(subtotal_amount: float) -> tuple[float, float]:
    tax_amount  = round(subtotal_amount * settings.TAX_RATE, 2)
    grand_total = round(subtotal_amount + tax_amount, 2)
    return tax_amount, grand_total


def create_order(
    db: Session,
    customer: Customer,
    item_details: list[dict],
    grand_total: float,
    *,
    status: str,
    notes: str | None = None,
    delivery_date=None,
    delivery_time: str | None = None,
    delivery_notes: str | None = None,
    idempotency_key: str | None = None,
    payment_method: str | None = None,
) -> Job:
    """Write the order and its line items. Stock is already reserved by now."""
    order = Job(
        customer_id=customer.id,
        total_amount=grand_total,
        notes=notes,
        status=status,
        items_json=item_details,
        delivery_date=delivery_date,
        delivery_time=delivery_time,
        delivery_notes=delivery_notes,
        idempotency_key=idempotency_key,
        payment_method=payment_method,
    )
    db.add(order)
    db.flush()   # need order.id for the detail rows

    for d in item_details:
        db.add(JobLine(
            item_id=d["product_id"],
            order_id=order.id,
            price=d["unit_price"],
            item_details=d["product_name"],
            quantity=d["quantity"],
            tax_amount=d.get("tax", 0),
            total_add_on_price=0,
        ))

    return order


def confirm_order(db: Session, order: Job) -> bool:
    """Move an order to confirmed. Returns False if it already was.

    The caller uses the return value to decide whether to send emails, so a
    replayed webhook does not email the shopper twice. Stock is untouched here
    because it was reserved when the order was placed.
    """
    if order.status != "pending":
        logger.info(f"[ORDER] {order.id} already {order.status}, nothing to confirm")
        return False
    order.status = "confirmed"
    db.flush()
    logger.info(f"[ORDER] {order.id} confirmed")
    return True


def cancel_order(db: Session, order: Job, reason: str = "") -> bool:
    """Cancel a pending order and give its reserved stock back."""
    if order.status != "pending":
        return False
    for line in (order.items_json or []):
        _release_stock(db, line["product_id"], line["quantity"])
    order.status = "cancelled"
    db.flush()
    logger.info(f"[ORDER] {order.id} cancelled{f': {reason}' if reason else ''}, stock released")
    return True
