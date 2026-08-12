"""Our own diary: working hours, minus what is already booked.

Chosen over Calendly for now, and it is not a placeholder. A slot offered here
is a slot genuinely free, because it is computed from the firm's working hours
with existing appointments and the length of the job taken out of it. The stub
it replaces invented times and reserved nothing, which is why forty three
conversations produced zero bookings and no way to tell.

Calendly becomes one more implementation of this same interface when the client
sends their details. Nothing above this file changes.

Two rules that come from the trade rather than from software:

* A job has to *finish* inside the working day, so the last start depends on how
  long the service takes. A two hour job cannot start at half past four.
* A slot has to be far enough away that somebody could actually get there, which
  is why there is a lead time.
"""

import logging
from datetime import datetime, time, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.calendly.base import Booking, CalendarProvider, Slot

logger = logging.getLogger("booking")


class LocalCalendar(CalendarProvider):
    """Availability from our own database."""

    #: Not a stub. These are real slots against a real diary.
    is_stub = False

    def __init__(self, db: Session | None = None):
        # The session is handed in per request by the booking service, because a
        # provider built once at import time must not hold a connection open.
        self.db = db

    def _busy(self, since: datetime, until: datetime) -> list[tuple[datetime, datetime]]:
        """Everything already promised, held or booked.

        An expired hold is not busy. That is what lets an abandoned conversation
        give its slot back without anybody tidying up.
        """
        if self.db is None:
            return []
        rows = self.db.execute(text("""
            SELECT starts_at, ends_at
            FROM appointments
            WHERE status IN ('held', 'booked', 'rescheduled')
              AND ends_at > :since AND starts_at < :until
              AND (status <> 'held' OR hold_expires_at > UTC_TIMESTAMP())
        """), {"since": since, "until": until}).fetchall()
        return [(r[0], r[1]) for r in rows]

    def free_slots(self, service_id: int, duration_minutes: int,
                   days_ahead: int = 14) -> list[Slot]:
        now = datetime.utcnow()
        earliest = now + timedelta(hours=settings.BOOKING_LEAD_HOURS)
        until = now + timedelta(days=days_ahead)

        busy = self._busy(now, until)
        duration = timedelta(minutes=max(15, duration_minutes))

        out: list[Slot] = []
        for day in range(days_ahead + 1):
            date = (now + timedelta(days=day)).date()
            if date.weekday() >= 5 and not settings.BOOKING_WEEKENDS:
                continue

            cursor = datetime.combine(date, time(hour=settings.BOOKING_OPEN_HOUR))
            closes = datetime.combine(date, time(hour=settings.BOOKING_CLOSE_HOUR))

            while cursor + duration <= closes:
                start, end = cursor, cursor + duration
                if start >= earliest and not any(
                    start < b_end and end > b_start for b_start, b_end in busy
                ):
                    out.append(Slot(starts_at=start, ends_at=end))
                cursor += timedelta(minutes=settings.BOOKING_SLOT_STEP_MINUTES)

        logger.info(
            f"[BOOKING] {len(out)} slot(s) free for service {service_id} "
            f"over {days_ahead} days, {len(busy)} already taken"
        )
        return out

    def book(self, slot: Slot, *, name: str, email: str, phone: str,
             address: str, notes: str) -> Booking:
        """Nothing to call. The appointment row is the booking.

        With an outside calendar this is where the visit gets created in their
        system. Here our own table is the record, so the reference points back
        at the slot and the booking service writes the row.
        """
        ref = f"local-{slot.starts_at:%Y%m%d-%H%M}"
        return Booking(ref=ref, invitee_ref=ref, starts_at=slot.starts_at,
                       ends_at=slot.ends_at)

    def cancel(self, booking_ref: str, reason: str = "") -> None:
        # The booking service marks the appointment cancelled, which is the
        # whole of it while we hold the diary ourselves.
        return None
