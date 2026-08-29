from sqlalchemy import Column, Integer, ForeignKey, Enum, Numeric, Text, JSON, DateTime, Date, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Job(Base):
    """A booked visit.

    The grocery system already carried a delivery date and a time label, chosen
    at checkout. A plumbing visit needs exactly the same two fields, so they are
    kept under their own names here rather than invented again.
    """

    __tablename__ = "jobs"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    customer_id  = Column(Integer, ForeignKey("customers.id"), nullable=False)
    # Who is doing the work, and on which of their offerings. The offering is
    # kept so a later price change does not rewrite what somebody was quoted.
    provider_id         = Column(Integer, ForeignKey("providers.id"))
    provider_service_id = Column(Integer, ForeignKey("provider_services.id"))
    # The problem this job came from, in the customer's own words. See
    # models/service_request.py for why that is a separate record.
    service_request_id  = Column(Integer, ForeignKey("service_requests.id"))
    # Stored rather than read from configuration when displaying, so a historic
    # booking still reads in the currency it was agreed in.
    currency = Column(String(8))
    status       = Column(
        Enum("pending", "confirmed", "scheduled", "completed", "cancelled"),
        nullable=False,
        default="pending",
    )
    total_amount = Column(Numeric(10, 2), nullable=False, default=0)
    # What the customer added for the provider on top of the price. The whole
    # of it is theirs. `total_amount` above is price + tip, because that is what
    # api/payments.py charges; this column is how anyone tells the two apart
    # afterwards.
    #
    # Like `payment_method` below, it does NOT reach the client's system, so the
    # tip is also written into `notes`. See job_service.note_with_tip.
    tip_amount   = Column(Numeric(10, 2), nullable=False, default=0)
    items_json   = Column(JSON)          # list of order line items stored inline
    notes        = Column(Text)
    # The slot the customer chose. Nullable only because a job can be taken by
    # phone and scheduled afterwards.
    appointment_date = Column(Date)
    appointment_time = Column(String(20))  # label, e.g. "9:00 AM"
    access_notes  = Column(Text)         # how to get in, where the stopcock is
    # Supplied by the client so a double-clicked checkout, a retry or a replayed
    # request returns the original order instead of creating a second one. NULL
    # is allowed, and MySQL permits many NULLs in a unique index, so orders
    # placed without a key still work. The unique index is added by
    # sql/payments_setup.sql, since create_all cannot alter an existing table.
    idempotency_key = Column(String(64), unique=True)
    # How the customer is paying: "cod", "stripe" or "paypal". Nullable, because
    # orders placed before this existed have none.
    #
    # This column does NOT reach the client's system: sync_to_remote intersects
    # the columns present on both sides, so anything he has not added is dropped
    # silently. A cash order that looked confirmed with no sign money was still
    # owed would be a real problem for whoever delivers it, so the method is
    # also written into `notes`, which does sync. This column exists for the
    # admin page, where querying a real field beats parsing free text.
    payment_method = Column(String(20))
    # Separate from `status`, which is the booking's own lifecycle. A visit can
    # be scheduled and unpaid, scheduled and paid, or cancelled after being
    # paid, and one column cannot say both. "cod" means it will be settled on
    # the day, which is neither paid nor a debt we are chasing.
    payment_status = Column(String(20), default="unpaid")
    created_at   = Column(DateTime, server_default=func.now())

    customer = relationship("Customer", back_populates="orders")
