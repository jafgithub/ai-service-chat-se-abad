"""The firm's real Calendly diary.

Two things about Calendly shape this code and are worth knowing before reading
it.

Their API lists *available times* for an event type, and creates a booking
through a scheduling link rather than by writing to a calendar directly. So
"book this slot" is not one call, and the honest way to model it is: we hold the
slot on our side, send the customer's details, and treat their scheduled event
as the record of truth once it exists.

Changes made inside Calendly, by the plumber on their phone, only reach us by
webhook. Without one the office is working from a diary that quietly disagrees
with the plumber's. Webhooks are not on the free plan, which makes the plan a
requirement rather than a preference.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings
from app.services.calendly.base import Booking, CalendarError, CalendarProvider, Slot

logger = logging.getLogger("booking")

API = "https://api.calendly.com"
TIMEOUT = 20


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.CALENDLY_TOKEN}",
        "Content-Type": "application/json",
    }


def _parse(when: str) -> datetime:
    """Calendly returns ISO 8601 in UTC, with a trailing Z."""
    return datetime.fromisoformat(when.replace("Z", "+00:00"))


class CalendlyCalendar(CalendarProvider):

    is_stub = False

    def _event_type(self, service_id: int) -> str:
        """Which Calendly event type a service books against.

        One event type per service is the arrangement that makes the durations
        right without us having to enforce them: Calendly already knows a boiler
        service takes two hours. Until the firm has set those up, everything
        falls back to a single default event type, which is enough to book with
        and wrong only about length.
        """
        mapping = settings.calendly_event_types()
        return mapping.get(str(service_id)) or settings.CALENDLY_DEFAULT_EVENT_TYPE

    def free_slots(self, service_id: int, duration_minutes: int,
                   days_ahead: int = 14) -> list[Slot]:
        event_type = self._event_type(service_id)
        if not event_type:
            raise CalendarError("No calendar has been set up for this service yet.")

        start = datetime.now(timezone.utc)
        # Calendly refuses a range longer than a week per call, so the caller's
        # fortnight is asked for a week at a time.
        out: list[Slot] = []
        for offset in range(0, days_ahead, 7):
            window_start = start + timedelta(days=offset)
            window_end = min(window_start + timedelta(days=7),
                             start + timedelta(days=days_ahead))
            out.extend(self._window(event_type, window_start, window_end,
                                    duration_minutes))
        return out

    def _window(self, event_type: str, start: datetime, end: datetime,
                duration_minutes: int) -> list[Slot]:
        try:
            resp = httpx.get(
                f"{API}/event_type_available_times",
                params={
                    "event_type": event_type,
                    "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end_time": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                headers=_headers(),
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(f"[BOOKING] Calendly refused: {type(exc).__name__}")
            raise CalendarError("We could not reach the calendar just now.") from exc

        slots: list[Slot] = []
        for row in resp.json().get("collection", []):
            if row.get("status") != "available":
                continue
            when = row.get("start_time")
            if not when:
                continue
            begins = _parse(when)
            slots.append(Slot(
                starts_at=begins,
                ends_at=begins + timedelta(minutes=duration_minutes),
                # Their scheduling URL for this exact time. It is what a booking
                # is made against, so it has to travel with the slot.
                ref=row.get("scheduling_url", ""),
            ))
        return slots

    def book(self, slot: Slot, *, name: str, email: str, phone: str,
             address: str, notes: str) -> Booking:
        """Take the slot.

        Calendly does not offer a plain "create a booking" call on their public
        API; a booking is made through the scheduling link for that time. So the
        customer's details are carried on the link, the customer confirms, and
        their webhook tells us the event exists.

        Returning the link rather than a completed booking is deliberate. It
        would be easy to pretend here and mark the job confirmed, and the office
        would then have visits in the system that are not in the diary.
        """
        if not slot.ref:
            raise CalendarError("That time is no longer available.")

        params = {
            "name": name,
            "email": email,
            "a1": phone,
            "a2": address,
            "a3": notes,
        }
        query = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}"
                         for k, v in params.items() if v)
        return Booking(
            ref=slot.ref,
            invitee_ref="",
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
            manage_url=f"{slot.ref}?{query}" if query else slot.ref,
        )

    def cancel(self, booking_ref: str, reason: str = "") -> None:
        try:
            resp = httpx.post(
                f"{booking_ref}/cancellation",
                json={"reason": reason or "Cancelled by the customer"},
                headers=_headers(),
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(f"[BOOKING] cancel failed: {type(exc).__name__}")
            raise CalendarError("We could not cancel that just now.") from exc
