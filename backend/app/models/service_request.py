"""What the customer actually asked for, in their own words.

Kept apart from `jobs` on purpose, and this is the distinction that matters:

* A **service request** is a problem. "There is water coming through the ceiling
  in the back bedroom." It exists the moment somebody describes it, belongs to
  them, and may never become anything else. Most enquiries do not.
* A **job** is work that has been arranged with a particular business at a
  particular time.

Folding the two together, which is what the shop's order table was doing, loses
every request that did not turn into a booking. Those are the interesting ones:
they are the ones nobody could serve, the areas with no cover, and the searches
that found nothing.

Also deliberately not the conversation. The chat transcript is a record of how
somebody was helped and is a poor record of what they need: it is long, it
contains the assistant's guesses, and its shape changes whenever the prompt
does. The request stores the problem and what it was matched to; the transcript
stays where it is.
"""

from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.sql import func

from app.db.database import Base


class ServiceRequest(Base):
    """A customer's problem, and what became of it."""

    __tablename__ = "service_requests"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)

    #: Their words, untouched. Never overwritten by what we matched it to.
    description = Column(Text, nullable=False)

    #: Where the work is, when it differs from the address on the account.
    address  = Column(Text)
    postcode = Column(String(20))
    #: Their own sense of how bad it is. Not the same as a service being marked
    #: as emergency work, which is the firm's judgement rather than theirs.
    urgency = Column(Enum("whenever", "this_week", "urgent"),
                     nullable=False, default="whenever")

    #: What the matching engine made of it. Nullable, because a request that
    #: matched nothing is worth keeping: that is the gap in what is offered.
    service_id = Column(Integer, ForeignKey("services.id"))
    #: Who they chose, once they chose. Nullable for the same reason.
    provider_id = Column(Integer, ForeignKey("providers.id"))
    #: The booking it became, if it became one.
    job_id = Column(Integer, ForeignKey("jobs.id"))

    status = Column(
        Enum("open", "matched", "booked", "unserved", "closed"),
        nullable=False,
        default="open",
    )
    #: Why nothing came of it, when nothing did: no cover in the area, no
    #: provider offering it, or the customer simply did not come back.
    outcome_note = Column(Text)

    #: The conversation it came from, so the two can be read together without
    #: one being stored inside the other.
    session_id = Column(String(64))

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_request_customer", "customer_id", "created_at"),
        # The office question: what are people asking for that we cannot serve?
        Index("ix_request_status", "status"),
    )
