"""Free times, taking one, and hearing when the calendar changes.

This is the step that replaces the shopping basket. Everything either side of
it, understanding what was asked for and confirming what was agreed, is the
machinery the grocery system already uses.
"""

import hashlib
import hmac
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.appointment import Appointment
from app.models.job import Job
from app.models.service import Service
from app.schemas.order import CustomerIn
from app.services import booking_service, calendly, job_service

logger = logging.getLogger("booking")

router = APIRouter(prefix="/booking", tags=["booking"])


class SlotOut(BaseModel):
    starts_at: datetime
    ends_at: datetime
    label: str
    ref: str = ""


class AvailabilityOut(BaseModel):
    service_id: int
    service_name: str
    duration_minutes: int
    #: True when these times are invented. The interface says so to the
    #: customer, because a convincing fake is worse than an obvious one.
    sample: bool
    slots: list[SlotOut]


class HoldIn(BaseModel):
    job_id: int
    starts_at: datetime
    ref: str = ""


class ConfirmIn(BaseModel):
    appointment_id: int
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=5, max_length=40)
    address: str = Field(min_length=3, max_length=400)
    notes: str = Field(default="", max_length=2000)


class AppointmentOut(BaseModel):
    id: int
    job_id: int
    starts_at: datetime
    ends_at: datetime
    status: str
    label: str


def _out(appointment: Appointment) -> AppointmentOut:
    return AppointmentOut(
        id=appointment.id,
        job_id=appointment.job_id,
        starts_at=appointment.starts_at,
        ends_at=appointment.ends_at,
        status=appointment.status,
        label=appointment.starts_at.strftime("%A %-d %B, %-I:%M %p"),
    )


@router.get("/availability", response_model=AvailabilityOut,
            summary="Free times for a service")
def availability(
    service_id: int = Query(..., ge=1),
    days_ahead: int = Query(0, ge=0, le=60),
    db: Session = Depends(get_db),
):
    service = db.query(Service).filter(Service.id == service_id).first()
    if service is None:
        raise HTTPException(status_code=404, detail="We do not offer that service.")

    # Cheap, and it means an abandoned conversation gives its slot back without
    # anything having to run on a timer.
    booking_service.release_expired(db)

    try:
        slots = booking_service.available_slots(
            db, service, days_ahead=days_ahead or settings.BOOKING_DAYS_AHEAD,
        )
    except booking_service.BookingError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return AvailabilityOut(
        service_id=service.id,
        service_name=service.name or "",
        duration_minutes=int(service.duration_minutes or 60),
        sample=calendly.current(db).is_stub,
        slots=[SlotOut(starts_at=s.starts_at, ends_at=s.ends_at,
                       label=s.label, ref=s.ref) for s in slots],
    )


@router.post("/hold", response_model=AppointmentOut,
             summary="Reserve a time while the customer finishes")
def hold(payload: HoldIn, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == payload.job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="That job no longer exists.")

    service_id = None
    if job.items_json:
        first = (job.items_json or [{}])[0]
        service_id = first.get("item_id") or first.get("service_id")
    service = db.query(Service).filter(Service.id == service_id).first() if service_id else None
    duration = int(service.duration_minutes or 60) if service else 60

    from datetime import timedelta
    slot = calendly.Slot(
        starts_at=payload.starts_at,
        ends_at=payload.starts_at + timedelta(minutes=duration),
        ref=payload.ref,
    )
    try:
        return _out(booking_service.hold(db, job, slot))
    except booking_service.BookingError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/confirm", response_model=AppointmentOut,
             summary="Take the held time and book it")
def confirm(payload: ConfirmIn, db: Session = Depends(get_db)):
    appointment = (
        db.query(Appointment).filter(Appointment.id == payload.appointment_id).first()
    )
    if appointment is None:
        raise HTTPException(status_code=404, detail="That appointment no longer exists.")

    try:
        booked = booking_service.confirm(
            db, appointment,
            name=payload.name, email=payload.email, phone=payload.phone,
            address=payload.address, notes=payload.notes,
        )
    except booking_service.BookingError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    job = db.query(Job).filter(Job.id == booked.job_id).first()
    if job is not None:
        job.status = "scheduled"
        job.appointment_date = booked.starts_at.date()
        job.appointment_time = booked.starts_at.strftime("%-I:%M %p")
        job.access_notes = payload.notes or job.access_notes
        db.commit()

    return _out(booked)


def _signature_ok(raw: bytes, header: str) -> bool:
    """Calendly signs each delivery. Without this the endpoint would take a
    cancellation from anybody who found the address.

    Their header looks like "t=1234,v1=abc". The signed value is the timestamp
    and the body joined by a full stop.
    """
    secret = settings.CALENDLY_WEBHOOK_SECRET
    if not secret:
        return False
    parts = dict(
        piece.split("=", 1) for piece in header.split(",") if "=" in piece
    )
    timestamp, sent = parts.get("t"), parts.get("v1")
    if not timestamp or not sent:
        return False
    expected = hmac.new(secret.encode(),
                        f"{timestamp}.{raw.decode('utf-8', 'replace')}".encode(),
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sent)


@router.post("/webhooks/calendly", summary="Told when a booking moves or is cancelled")
async def calendly_webhook(
    request: Request,
    calendly_webhook_signature: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Without this the office works from a diary that quietly disagrees with
    the plumber's, and the first sign is a customer ringing about a visit that
    moved hours ago."""
    raw = await request.body()

    if settings.CALENDLY_WEBHOOK_SECRET:
        if not _signature_ok(raw, calendly_webhook_signature):
            logger.warning("[BOOKING] webhook rejected: bad signature")
            raise HTTPException(status_code=401, detail="Bad signature.")
    else:
        # Loud, because an unsigned webhook endpoint is an open door and the
        # only thing standing between it and the diary is that nobody has
        # guessed the address.
        logger.warning("[BOOKING] webhook accepted UNSIGNED; set CALENDLY_WEBHOOK_SECRET")

    body = await request.json()
    event = body.get("event", "")
    scheduled = (body.get("payload") or {}).get("scheduled_event") or {}
    uri = scheduled.get("uri") or (body.get("payload") or {}).get("uri") or ""
    if not uri:
        return {"status": "ignored", "why": "no event reference"}

    starts = scheduled.get("start_time")
    ends = scheduled.get("end_time")

    appointment = booking_service.apply_calendar_change(
        db,
        calendly_uri=uri,
        event=event,
        starts_at=datetime.fromisoformat(starts.replace("Z", "+00:00")).replace(tzinfo=None)
        if starts else None,
        ends_at=datetime.fromisoformat(ends.replace("Z", "+00:00")).replace(tzinfo=None)
        if ends else None,
        reason=((body.get("payload") or {}).get("cancellation") or {}).get("reason", ""),
    )
    return {"status": "applied" if appointment else "unknown appointment"}


# ── booking in one step ──────────────────────────────────────────────────────

class BookIn(BaseModel):
    """Everything a booking needs, in one request."""

    service_id: int
    starts_at: datetime
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=5, max_length=40)
    address: str = Field(min_length=3, max_length=400)
    notes: str = Field(default="", max_length=2000)
    session_id: str = Field(default="", max_length=64)


class BookedOut(BaseModel):
    job_id: int
    appointment_id: int
    service_name: str
    starts_at: datetime
    label: str
    price: float
    customer_id: int


@router.post("/book", response_model=BookedOut,
             summary="Take a time and create the job, in one step")
def book(payload: BookIn, db: Session = Depends(get_db)):
    """The whole booking, as one call.

    Deliberately not the shop's two step cart and checkout. A visit is one job
    at one time at one address, so there is nothing to accumulate and nothing to
    review: the moment the customer has chosen a time and given their details,
    the booking either exists or it does not.

    Doing it in one transaction is also what stops the half finished states the
    cart produced. The live system had forty three conversations, two abandoned
    cart rows, and zero jobs, zero appointments and zero customers.
    """
    service = db.query(Service).filter(Service.id == payload.service_id).first()
    if service is None:
        raise HTTPException(status_code=404, detail="We do not offer that service.")

    booking_service.release_expired(db)

    customer = job_service.upsert_customer(db, CustomerIn(
        name=payload.name, email=payload.email, phone=payload.phone,
        address=payload.address,
    ))

    job = Job(
        customer_id=customer.id,
        status="pending",
        total_amount=float(service.price or 0),
        items_json=[{
            "item_id": service.id,
            "name": service.name,
            "price": float(service.price or 0),
            "quantity": 1,
        }],
        notes=payload.notes or None,
        access_notes=payload.notes or None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    duration = int(service.duration_minutes or 60)
    slot = calendly.Slot(
        starts_at=payload.starts_at,
        ends_at=payload.starts_at + timedelta(minutes=duration),
    )

    try:
        appointment = booking_service.hold(db, job, slot)
        appointment = booking_service.confirm(
            db, appointment,
            name=payload.name, email=payload.email, phone=payload.phone,
            address=payload.address, notes=payload.notes,
        )
    except booking_service.BookingError as exc:
        # The job would otherwise sit there with no appointment attached, which
        # is exactly the half finished state this endpoint exists to avoid.
        db.delete(job)
        db.commit()
        raise HTTPException(status_code=409, detail=str(exc))

    job.status = "scheduled"
    job.appointment_date = appointment.starts_at.date()
    job.appointment_time = appointment.starts_at.strftime("%-I:%M %p")
    db.commit()

    logger.info(
        f"[BOOKING] job {job.id}: {service.name} for {customer.email} "
        f"at {appointment.starts_at:%Y-%m-%d %H:%M}"
    )
    return BookedOut(
        job_id=job.id,
        appointment_id=appointment.id,
        service_name=service.name or "",
        starts_at=appointment.starts_at,
        label=appointment.starts_at.strftime("%A %-d %B, %-I:%M %p"),
        price=float(service.price or 0),
        customer_id=customer.id,
    )
