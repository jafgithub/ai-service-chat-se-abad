from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Enum, Text, Index,
)
from sqlalchemy.sql import func

from app.db.database import Base


class Appointment(Base):
    """When a job is happening, and what the calendar thinks about it.

    Kept apart from `jobs` rather than folded into it, for one reason: a visit
    gets moved. Holding the arrangement separately means a job can be rescheduled
    without losing what was originally agreed, and a cancelled visit does not
    delete the job it belonged to.

    Calendly owns the diary. This table is our copy of what it says, so the
    office can see the day without waiting on somebody else's API, and so a
    Calendly outage does not take the shop offline. `calendly_uri` is the thread
    back to the original, and it is what the webhook arrives quoting.
    """

    __tablename__ = "appointments"

    id     = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)

    starts_at = Column(DateTime, nullable=False)
    ends_at   = Column(DateTime, nullable=False)

    # Which of the firm's people is attending. Nullable because a one person
    # firm has nobody to choose between.
    technician_id = Column(Integer)

    status = Column(
        Enum("held", "booked", "rescheduled", "cancelled", "completed"),
        nullable=False,
        default="held",
    )

    # A slot is held while the customer finishes the conversation, so two people
    # cannot take the same hour. Past this moment the hold means nothing and the
    # slot is offered again. See services/booking.py.
    hold_expires_at = Column(DateTime)

    # Calendly's own identifiers. `calendly_uri` identifies the scheduled event
    # and is what their webhook quotes; `calendly_invitee_uri` identifies the
    # person, and is what a cancellation quotes.
    calendly_uri         = Column(String(255))
    calendly_invitee_uri = Column(String(255))
    # Their reason, when they tell us one.
    cancel_reason = Column(Text)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # The office screen reads the day, over and over.
        Index("ix_appointment_day", "starts_at"),
        # The webhook arrives knowing only Calendly's identifier.
        Index("ix_appointment_calendly", "calendly_uri"),
    )
