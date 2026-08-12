"""Invented slots, so the whole system works before anybody has bought a plan.

Deliberately plausible but obviously fake: working hours only, weekdays only,
and nothing in the next two hours, because no plumber takes a booking for
twenty minutes' time through a web form. The interface tells the customer these
are examples, the same way the grocery system labels sample products, because a
convincing fake is harder to spot than an obvious one and does more damage.
"""

from datetime import datetime, timedelta

from app.services.calendly.base import Booking, CalendarProvider, Slot

# A plumber's day. Slots start on the hour and the last one starts at four, so
# a two hour job still finishes inside the working day.
FIRST_HOUR = 8
LAST_START_HOUR = 16
# Nothing sooner than this, so the diary never offers a slot nobody could reach.
LEAD_TIME_HOURS = 2


class StubCalendar(CalendarProvider):

    is_stub = True

    def free_slots(self, service_id: int, duration_minutes: int,
                   days_ahead: int = 14) -> list[Slot]:
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        earliest = now + timedelta(hours=LEAD_TIME_HOURS)

        # Long jobs occupy more of the day, so fewer of them fit. Rounded up:
        # ninety minutes takes two hours out of a diary that works in hours.
        span = max(1, -(-duration_minutes // 60))

        out: list[Slot] = []
        for day in range(days_ahead + 1):
            date = (now + timedelta(days=day)).date()
            if date.weekday() >= 5:          # a weekend, which costs extra
                continue
            for hour in range(FIRST_HOUR, LAST_START_HOUR + 1):
                start = datetime.combine(date, datetime.min.time()) + timedelta(hours=hour)
                if start < earliest:
                    continue
                if hour + span > LAST_START_HOUR + 1:
                    continue
                # Thin them out so the day looks worked rather than empty.
                if (day + hour) % 3 == 0:
                    continue
                out.append(Slot(starts_at=start,
                                ends_at=start + timedelta(minutes=duration_minutes)))
        return out

    def book(self, slot: Slot, *, name: str, email: str, phone: str,
             address: str, notes: str) -> Booking:
        # A reference that could not be mistaken for a real one.
        ref = f"stub-{slot.starts_at:%Y%m%d-%H%M}"
        return Booking(ref=ref, invitee_ref=f"{ref}-invitee",
                       starts_at=slot.starts_at, ends_at=slot.ends_at)

    def cancel(self, booking_ref: str, reason: str = "") -> None:
        return None
