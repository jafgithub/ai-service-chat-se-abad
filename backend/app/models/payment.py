from sqlalchemy import (
    Column, BigInteger, Integer, String, Numeric, Text, DateTime, UniqueConstraint, Index
)
from sqlalchemy.sql import func

from app.db.database import Base

# SQLite only auto-increments a plain INTEGER PRIMARY KEY. Keeps BIGINT on
# MySQL, which is what production runs, and lets the tests use SQLite.
_AUTO_PK = BigInteger().with_variant(Integer, "sqlite")


class Payment(Base):
    """One attempt to collect money for an order.

    An order can have several: a shopper who abandons Stripe and comes back
    through PayPal leaves two rows, only one of which ever reaches "paid".
    The order's own status is what the rest of the app reads; this table is the
    audit trail and the thing that makes webhooks safe to replay.
    """

    __tablename__ = "payments"

    id       = Column(_AUTO_PK, primary_key=True, autoincrement=True)
    order_id = Column(Integer, nullable=False)

    provider     = Column(String(20), nullable=False)    # "stripe" | "paypal"
    # The provider's id for the checkout itself, used to find this row again when
    # a webhook arrives carrying nothing but that id.
    provider_ref = Column(String(255))

    # The id of the webhook event already applied to this payment. Unique, so a
    # replayed delivery cannot confirm an order or decrement stock a second time.
    # Both providers retry until they get a 2xx, so replays are normal traffic,
    # not an attack.
    provider_event_id = Column(String(255))

    status   = Column(String(20), nullable=False, default="pending")  # pending|paid|failed|cancelled
    amount   = Column(Numeric(10, 2), nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="USD")

    error_message = Column(Text)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("provider_event_id", name="uq_payments_event"),
        Index("ix_payments_order", "order_id"),
        Index("ix_payments_ref", "provider", "provider_ref"),
    )
