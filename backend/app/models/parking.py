"""A resident's parking pass, and the QR code that proves it.

One row per pass. The QR carries a token and nothing else: no name, no
registration, no unit number, because a QR code is a picture anybody can
photograph off a windscreen and read. Everything about the pass is looked up
from the token on our side, by somebody authorised to ask.

The token is also why a pass cannot be invented. It is 32 random hex characters
from `secrets`, not a sequence, so knowing one tells you nothing about the next
and guessing one is not worth attempting.
"""

from datetime import datetime

from sqlalchemy import (Column, DateTime, ForeignKey, Index, Integer, String,
                        Text)
from sqlalchemy.orm import relationship

from app.db.database import Base

#: Waiting to be used, in use, finished, or timed out.
ISSUED = "issued"
EXPIRED = "expired"


class ParkingPass(Base):
    """A pass to park in a community, issued to one logged in resident."""

    __tablename__ = "parking_passes"

    id = Column(Integer, primary_key=True, index=True)

    #: Who it belongs to. A pass is personal: the client asked that a resident
    #: be registered and signed in before one is issued, so that the office can
    #: always say whose vehicle is on the property.
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True, index=True)

    community = Column(String(80), nullable=False, index=True)
    vehicle_registration = Column(String(32), nullable=False)
    vehicle_description = Column(String(120), nullable=True)
    visiting = Column(String(120), nullable=True)

    #: What the QR encodes. Unique so a duplicate can never be issued, indexed
    #: because every scan at the gate looks a pass up by it.
    token = Column(String(64), nullable=False, unique=True, index=True)

    status = Column(String(20), nullable=False, default=ISSUED, index=True)
    issued_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    #: The end of the permitted stay. Serenity's own form allows five days.
    expires_at = Column(DateTime, nullable=False, index=True)
    #: Set when the vehicle leaves. From that moment the pass is spent, whatever
    #: `expires_at` says: the client asked for it to expire on the way out, and
    #: a pass that still works after the car has gone is a pass somebody can
    #: hand to a friend.
    exited_at = Column(DateTime, nullable=True)

    notes = Column(Text, nullable=True)

    account = relationship("Account")
    customer = relationship("Customer")

    def is_live(self, now: datetime | None = None) -> bool:
        now = now or datetime.utcnow()
        return (self.status == ISSUED
                and self.exited_at is None
                and self.expires_at > now)

    def state(self, now: datetime | None = None) -> str:
        """What to tell a person, rather than what is in the column.

        Three ways a pass stops working and they are not the same thing: the
        car left, the time ran out, or the office cancelled it. Somebody at a
        barrier needs to know which.
        """
        now = now or datetime.utcnow()
        if self.exited_at is not None:
            return "used"
        if self.status == EXPIRED:
            return "cancelled"
        if self.expires_at <= now:
            return "expired"
        return "valid"


Index("ix_parking_account_status", ParkingPass.account_id, ParkingPass.status)
