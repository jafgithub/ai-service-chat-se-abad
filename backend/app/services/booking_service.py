"""Holding a slot, taking it, and hearing when it changes.

The hold is the part worth explaining. Between a customer seeing a time and
confirming it there is a conversation, a phone number to type and an address to
check, which is a minute or two. Without a hold, two customers who both liked
Tuesday at nine both get told they have it, and the office finds out when the
plumber does.

So a slot is written down as `held` with an expiry, checked against on the way
in, and swept when it lapses. A hold is not a promise from the calendar, which
is why it is short: it is a promise from us, that we will not offer the same
hour to somebody else while this customer finishes typing.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.job import Job
from app.models.service import Service
from app.services import calendly
from app.services.calendly import CalendarError, Slot

logger = logging.getLogger("booking")


class BookingError(Exception):
    """Something a customer needs told, in words they can act on."""


def _now() -> datetime:
    # Naive UTC throughout, matching the rest of the system's timestamps.
    return datetime.utcnow()


def available_slots(db: Session, service: Service, days_ahead: int = 14) -> list[Slot]:
    """Free times for a service, minus anything we are already holding."""
    provider = calendly.current(db)
    duration = int(service.duration_minutes or 60)

    try:
        slots = provider.free_slots(service.id, duration, days_ahead=days_ahead)
    except CalendarError as exc:
        raise BookingError(str(exc)) from exc

    taken = _taken_starts(db)
    return [s for s in slots if s.starts_at.replace(tzinfo=None) not in taken]


def _taken_starts(db: Session) -> set[datetime]:
    """Start times we have already promised to somebody.

    Live holds and real bookings both count. An expired hold does not, which is
    what makes an abandoned conversation give its slot back without anybody
    having to tidy up.
    """
    rows = (
        db.query(Appointment.starts_at)
        .filter(
            Appointment.status.in_(("held", "booked", "rescheduled")),
            or_(
                Appointment.status != "held",
                and_(Appointment.status == "held",
                     Appointment.hold_expires_at > _now()),
            ),
        )
        .all()
    )
    return {r[0] for r in rows}


def hold(db: Session, job: Job, slot: Slot) -> Appointment:
    """Reserve a slot for as long as it takes to finish the conversation."""
    starts = slot.starts_at.replace(tzinfo=None)
    if starts in _taken_starts(db):
        raise BookingError("Somebody just took that time. Please choose another.")

    appointment = Appointment(
        job_id=job.id,
        starts_at=starts,
        ends_at=slot.ends_at.replace(tzinfo=None),
        status="held",
        hold_expires_at=_now() + timedelta(minutes=settings.BOOKING_HOLD_MINUTES),
        calendly_uri=slot.ref or None,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    logger.info(f"[BOOKING] held {starts:%Y-%m-%d %H:%M} for job {job.id}")
    return appointment


def confirm(db: Session, appointment: Appointment, *, name: str, email: str,
            phone: str, address: str, notes: str = "") -> Appointment:
    """Turn a hold into a booking in the calendar."""
    if appointment.status not in ("held", "booked"):
        raise BookingError("That appointment is no longer open.")
    if appointment.status == "held" and appointment.hold_expires_at and \
            appointment.hold_expires_at < _now():
        raise BookingError("That time was released while you were deciding.")

    slot = Slot(starts_at=appointment.starts_at, ends_at=appointment.ends_at,
                ref=appointment.calendly_uri or "")
    try:
        booking = calendly.current(db).book(
            slot, name=name, email=email, phone=phone, address=address, notes=notes,
        )
    except CalendarError as exc:
        raise BookingError(str(exc)) from exc

    appointment.status = "booked"
    appointment.calendly_uri = booking.ref or appointment.calendly_uri
    appointment.calendly_invitee_uri = booking.invitee_ref or None
    appointment.hold_expires_at = None
    db.commit()
    db.refresh(appointment)
    logger.info(f"[BOOKING] confirmed {appointment.starts_at:%Y-%m-%d %H:%M}")
    return appointment


def release_expired(db: Session) -> int:
    """Give back slots nobody came back for. Cheap, and safe to call often."""
    stale = (
        db.query(Appointment)
        .filter(Appointment.status == "held",
                Appointment.hold_expires_at < _now())
        .all()
    )
    for appointment in stale:
        appointment.status = "cancelled"
        appointment.cancel_reason = "The hold expired before it was confirmed."
    if stale:
        db.commit()
        logger.info(f"[BOOKING] released {len(stale)} expired hold(s)")
    return len(stale)


def apply_calendar_change(db: Session, *, calendly_uri: str, event: str,
                          starts_at: datetime | None = None,
                          ends_at: datetime | None = None,
                          reason: str = "") -> Appointment | None:
    """What the webhook does.

    The plumber moves a visit on their phone and the office has to know. Without
    this the two diaries drift apart quietly, and the first sign is a customer
    ringing about a plumber who is somewhere else.
    """
    appointment = (
        db.query(Appointment)
        .filter(Appointment.calendly_uri == calendly_uri)
        .order_by(Appointment.id.desc())
        .first()
    )
    if appointment is None:
        logger.info(f"[BOOKING] webhook for an appointment we do not hold: {calendly_uri[:60]}")
        return None

    if event == "invitee.canceled":
        appointment.status = "cancelled"
        appointment.cancel_reason = reason or "Cancelled in the calendar."
        job = db.query(Job).filter(Job.id == appointment.job_id).first()
        if job is not None:
            job.status = "cancelled"
    elif starts_at is not None:
        appointment.starts_at = starts_at
        if ends_at is not None:
            appointment.ends_at = ends_at
        appointment.status = "rescheduled"

    db.commit()
    db.refresh(appointment)
    logger.info(f"[BOOKING] {event} applied to appointment {appointment.id}")
    return appointment
