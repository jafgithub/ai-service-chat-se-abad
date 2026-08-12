"""Sending the order emails, outside the request that caused them.

They used to be sent inline, after the commit, with no SMTP timeout: a slow
relay held a worker open on an order that already existed, and the shopper
watched a spinner for something that had already succeeded.

Run as a FastAPI background task, so this opens its own session. The request's
session is closed by `get_db`'s `finally` before background tasks run, and
touching it here would raise. That is also why this takes an order id rather
than an Job: the object would be detached.
"""

import logging

from app.db.database import SessionLocal
from app.models.customer import Customer
from app.models.job import Job
from app.services.email_service import (
    send_customer_confirmation, send_order_notification,
)

logger = logging.getLogger("orders")


def send_order_emails(order_id: int) -> None:
    """Notify the shop and the customer. Never raises: a failed email must not
    take down the caller, and by this point the order is already placed."""
    db = SessionLocal()
    try:
        order = db.query(Job).filter(Job.id == order_id).first()
        if order is None:
            logger.warning(f"[EMAIL] order {order_id} vanished before emails were sent")
            return

        customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
        if customer is None:
            logger.warning(f"[EMAIL] order {order_id} has no customer row")
            return

        items = order.items_json or []
        subtotal = round(sum(float(i.get("subtotal", 0)) for i in items), 2)
        total    = float(order.total_amount)
        # Derived rather than stored: total already includes tax, and deriving it
        # keeps the emails consistent with whatever the order was actually charged.
        tax      = round(total - subtotal, 2)

        address = customer.address or (
            f"Lat {customer.latitude}, Lng {customer.longitude}"
            if customer.latitude else "Not provided"
        )

        try:
            send_order_notification(
                customer_name=customer.name,
                customer_email=customer.email,
                customer_phone=customer.phone or "",
                customer_address=address,
                order_id=order.id,
                items=items,
                subtotal=subtotal,
                tax=tax,
                total=total,
                delivery_date=order.delivery_date,
                delivery_time=order.delivery_time,
                delivery_notes=order.delivery_notes,
                payment_method=order.payment_method,
            )
        except Exception as exc:  # noqa: BLE001 - best effort, order already placed
            logger.warning(f"[EMAIL] shop notification failed for order {order.id}: {exc}")

        try:
            send_customer_confirmation(
                customer_email=customer.email,
                customer_name=customer.name,
                order_id=order.id,
                items=items,
                subtotal=subtotal,
                tax=tax,
                total=total,
                delivery_date=order.delivery_date,
                delivery_time=order.delivery_time,
                delivery_notes=order.delivery_notes,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[EMAIL] customer confirmation failed for order {order.id}: {exc}")

        logger.info(f"[EMAIL] order {order.id} emails attempted")
    finally:
        db.close()
