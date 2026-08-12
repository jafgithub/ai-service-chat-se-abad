"""Choosing which diary to talk to.

Same shape as the grocery system's provider selection, so the switch between a
demonstration and the real thing is one line of configuration.
"""

import logging

from app.core.config import settings
from app.services.calendly.base import (  # noqa: F401
    Booking, CalendarError, CalendarProvider, Slot,
)
from app.services.calendly.calendly_provider import CalendlyCalendar
from app.services.calendly.local_provider import LocalCalendar
from app.services.calendly.stub_provider import StubCalendar

logger = logging.getLogger("booking")

_cached: CalendarProvider | None = None
_cached_for: str | None = None


def current(db=None, provider_id=None) -> CalendarProvider:
    """The calendar in use, built once.

    Falls back to the stub rather than failing when Calendly is selected but has
    no token: a missing token is a setup mistake, and a system that still runs
    and says its slots are examples is easier to diagnose than one that will not
    start.
    """
    global _cached, _cached_for

    choice = (settings.CALENDAR_PROVIDER or "stub").strip().lower()
    if choice == "calendly" and not settings.CALENDLY_TOKEN:
        logger.warning("[BOOKING] CALENDAR_PROVIDER=calendly but no token; using examples")
        choice = "stub"

    # The local diary reads the appointments table, so it is built per request
    # with that request's session rather than cached holding a connection.
    if choice == "local":
        return LocalCalendar(db, provider_id)

    if _cached is not None and _cached_for == choice:
        return _cached

    _cached = CalendlyCalendar() if choice == "calendly" else StubCalendar()
    _cached_for = choice
    logger.info(f"[BOOKING] calendar provider: {choice}")
    return _cached
