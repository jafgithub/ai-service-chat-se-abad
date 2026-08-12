"""What a calendar has to be able to do, and the shape of a free slot.

Written as an interface with two implementations, the same way the grocery
system handles its search provider. That pattern earned its keep there: the
whole application can be built, demonstrated and tested before anybody has paid
for an account, and switching to the real thing is one line of configuration
rather than a rewrite.

    CALENDAR_PROVIDER=stub       invented slots, no account, no cost
    CALENDAR_PROVIDER=calendly   the firm's real diary
"""

from dataclasses import dataclass
from datetime import datetime


class CalendarError(Exception):
    """The calendar could not be reached, or refused. The message is shown."""


@dataclass(frozen=True)
class Slot:
    """One bookable hour, as the customer will see it."""

    starts_at: datetime
    ends_at: datetime
    #: What the calendar calls this slot, and what booking it needs back.
    #: Empty for the stub, which has nothing to refer to.
    ref: str = ""

    @property
    def label(self) -> str:
        """"Tuesday 9:00 AM". What a person reads, not what a machine stores."""
        return self.starts_at.strftime("%A %-d %B, %-I:%M %p")


@dataclass(frozen=True)
class Booking:
    """A slot that has been taken."""

    ref: str
    invitee_ref: str
    starts_at: datetime
    ends_at: datetime
    #: Where the customer can reschedule or cancel it themselves, if the
    #: calendar offers such a page. Worth passing on: it is the cheapest way to
    #: stop a customer ringing the office to move a visit.
    manage_url: str = ""


class CalendarProvider:
    """The two questions a booking assistant has to ask a diary."""

    #: True when the provider makes its slots up. The interface says so out
    #: loud, exactly as the grocery system labels sample products, because a
    #: convincing fake is worse than an obvious one.
    is_stub: bool = False

    def free_slots(self, service_id: int, duration_minutes: int,
                   days_ahead: int = 14) -> list[Slot]:
        raise NotImplementedError

    def book(self, slot: Slot, *, name: str, email: str, phone: str,
             address: str, notes: str) -> Booking:
        raise NotImplementedError

    def cancel(self, booking_ref: str, reason: str = "") -> None:
        raise NotImplementedError
