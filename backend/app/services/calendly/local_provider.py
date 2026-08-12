"""One business's diary: its hours, minus its own commitments.

There is no platform calendar. Availability is always a question about a
particular provider, because two firms working the same trade keep different
hours, take different lengths of time over the same job, and are busy at
different moments. Asking "is Tuesday at nine free" without naming who is
meaningless.

What gets subtracted from a provider's working hours:

* their own appointments, held or booked
* their own closures: holidays, a training afternoon, a van off the road
* the length of *this* job, since a two hour visit cannot start at half past
  four in a day that ends at five

Holds count as busy while they are alive and stop counting the moment they
expire, which is what lets an abandoned conversation give its hour back with
nothing having to sweep up.

Calendly replaces this file and nothing above it when the client sends their
details.
"""

import logging
from datetime import datetime, time, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.calendly.base import Booking, CalendarError, CalendarProvider, Slot

logger = logging.getLogger("booking")


class LocalCalendar(CalendarProvider):
    """Availability from our own database, for one provider at a time."""

    #: Real slots against a real diary.
    is_stub = False

    def __init__(self, db: Session | None = None, provider_id: int | None = None):
        # Both are handed in per request. A provider built once at import time
        # would hold a connection open and, worse, would have to be told whose
        # diary it was on every call anyway.
        self.db = db
        self.provider_id = provider_id

    # ── what the provider has already promised ───────────────────────────────

    @staticmethod
    def _as_time(value) -> time | None:
        """A MySQL TIME comes back as a timedelta, not a time.

        MySQL returns TIME as "duration since midnight", which is right for a
        column that can hold 838 hours and wrong for opening hours. SQLite
        returns a string. Passing either to datetime.combine raises, and because
        the diary is read inside a try in discovery, the whole thing failed
        silently: every provider showed "no availability" and nothing looked
        broken.
        """
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, timedelta):
            seconds = int(value.total_seconds())
            return time(hour=(seconds // 3600) % 24,
                        minute=(seconds // 60) % 60,
                        second=seconds % 60)
        if isinstance(value, str):
            # SQLite hands back "08:00:00" or "08:00:00.000000". Different
            # driver, same trap: three databases, three representations of the
            # same column, and only one of them is a time.
            head = value.strip().split(".")[0]
            parts = head.split(":")
            try:
                numbers = [int(p) for p in parts[:3]]
            except ValueError:
                return None
            while len(numbers) < 3:
                numbers.append(0)
            hour, minute, second = numbers
            if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
                return None
            return time(hour=hour, minute=minute, second=second)
        return None

    def _working_hours(self, weekday: int) -> list[tuple[time, time]]:
        """Open periods for one weekday. Empty means closed that day."""
        if self.db is None or self.provider_id is None:
            return []
        rows = self.db.execute(text("""
            SELECT opens_at, closes_at
            FROM provider_availability
            WHERE provider_id = :p AND weekday = :d
            ORDER BY opens_at
        """), {"p": self.provider_id, "d": weekday}).fetchall()

        out: list[tuple[time, time]] = []
        for opens, closes in rows:
            start, end = self._as_time(opens), self._as_time(closes)
            if start is not None and end is not None and end > start:
                out.append((start, end))
        return out

    def _commitments(self, since: datetime, until: datetime) -> list[tuple[datetime, datetime]]:
        """Appointments and closures, as busy periods.

        Both are subtracted the same way, because from the diary's point of view
        a holiday and a booked job are the same thing: the provider is not
        available.
        """
        if self.db is None or self.provider_id is None:
            return []

        booked = self.db.execute(text("""
            SELECT starts_at, ends_at
            FROM appointments
            WHERE provider_id = :p
              AND status IN ('held', 'booked', 'rescheduled')
              AND ends_at > :since AND starts_at < :until
              AND (status <> 'held' OR hold_expires_at > UTC_TIMESTAMP())
        """), {"p": self.provider_id, "since": since, "until": until}).fetchall()

        closed = self.db.execute(text("""
            SELECT starts_at, ends_at
            FROM provider_time_off
            WHERE provider_id = :p AND ends_at > :since AND starts_at < :until
        """), {"p": self.provider_id, "since": since, "until": until}).fetchall()

        out: list[tuple[datetime, datetime]] = []
        for start, end in list(booked) + list(closed):
            start, end = self._as_datetime(start), self._as_datetime(end)
            if start is not None and end is not None:
                out.append((start, end))
        return out

    @staticmethod
    def _as_datetime(value) -> datetime | None:
        """Same trap as `_as_time`, one level down.

        A DATETIME comes back as a datetime from MySQL and as a string from
        SQLite. Comparing a string against a datetime raises, and comparing two
        strings quietly compares them alphabetically, which is worse: it looks
        like it works right up until a date crosses a boundary.
        """
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            text_value = value.strip().replace("T", " ")
            for shape in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                          "%Y-%m-%d %H:%M"):
                try:
                    return datetime.strptime(text_value, shape)
                except ValueError:
                    continue
        return None

    # ── the diary ────────────────────────────────────────────────────────────

    def free_slots(self, service_id: int, duration_minutes: int,
                   days_ahead: int = 14) -> list[Slot]:
        if self.provider_id is None:
            raise CalendarError("A provider has to be chosen before times can be shown.")

        now = datetime.utcnow()
        earliest = now + timedelta(hours=settings.BOOKING_LEAD_HOURS)
        until = now + timedelta(days=days_ahead)

        busy = self._commitments(now, until)
        duration = timedelta(minutes=max(15, duration_minutes))
        step = timedelta(minutes=settings.BOOKING_SLOT_STEP_MINUTES)

        out: list[Slot] = []
        for day in range(days_ahead + 1):
            date = (now + timedelta(days=day)).date()
            for opens, closes in self._working_hours(date.weekday()):
                cursor = datetime.combine(date, opens)
                day_closes = datetime.combine(date, closes)

                # The job has to finish before they shut, so the last start
                # depends on how long this particular job takes.
                while cursor + duration <= day_closes:
                    start, end = cursor, cursor + duration
                    if start >= earliest and not any(
                        start < b_end and end > b_start for b_start, b_end in busy
                    ):
                        out.append(Slot(starts_at=start, ends_at=end))
                    cursor += step

        logger.info(
            f"[BOOKING] provider {self.provider_id}: {len(out)} slot(s) free for "
            f"service {service_id} ({duration_minutes} min), {len(busy)} commitment(s)"
        )
        return out

    def next_free(self, service_id: int, duration_minutes: int,
                  days_ahead: int = 14) -> datetime | None:
        """The soonest they could attend, or None.

        Used for ranking, where all that is needed is the first slot. Kept
        separate so ordering a list of providers does not build every slot for
        every one of them.
        """
        slots = self.free_slots(service_id, duration_minutes, days_ahead=days_ahead)
        return slots[0].starts_at if slots else None

    def book(self, slot: Slot, *, name: str, email: str, phone: str,
             address: str, notes: str) -> Booking:
        """Nothing external to call: the appointment row is the booking."""
        ref = f"local-{self.provider_id}-{slot.starts_at:%Y%m%d-%H%M}"
        return Booking(ref=ref, invitee_ref=ref, starts_at=slot.starts_at,
                       ends_at=slot.ends_at)

    def cancel(self, booking_ref: str, reason: str = "") -> None:
        # The booking service marks the appointment cancelled, which is the
        # whole of it while we hold the diary ourselves.
        return None
