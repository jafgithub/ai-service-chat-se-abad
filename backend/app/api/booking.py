"""Free times, taking one, and hearing when the calendar changes.

This is the step that replaces the shopping basket. Everything either side of
it, understanding what was asked for and confirming what was agreed, is the
machinery the grocery system already uses.
"""

import hashlib
import hmac
import logging
from datetime import datetime, timedelta

from fastapi import (APIRouter, BackgroundTasks, Depends, Header, HTTPException,
                     Query, Request)
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.appointment import Appointment
from app.models.job import Job
from app.models.customer import Customer
from app.models.provider import Provider, ProviderService
from app.models.service import Service
from app.models.service_request import ServiceRequest
from app.api.deps import require_customer
from app.services import booking_service, calendly
from app.services.booking_notify import (send_booking_emails,
                                         send_cancellation_email)

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
    """Everything a booking needs, in one request.

    No customer fields: the customer is whoever is signed in. Taking a name and
    an email from the body would let anybody book in somebody else's name, and
    would quietly create a second customer record for a person we already have.
    """

    provider_id: int
    service_id: int
    starts_at: datetime
    #: Where the work is, if different from the address on the account.
    address: str = Field(default="", max_length=400)
    notes: str = Field(default="", max_length=2000)
    #: The problem this booking answers, when the customer recorded one first.
    service_request_id: int | None = None
    #: How they intend to pay. Cash is settled with the provider on the day and
    #: needs nothing further; the other two send the customer to that provider's
    #: own page, and the booking is held meanwhile.
    payment_method: str = Field(default="cod", pattern="^(cod|stripe|paypal)$")


class BookedOut(BaseModel):
    """Everything a confirmation screen needs, so it needs no follow up call.

    The payment fields are carried now and unused until payments move into this
    flow: amount, currency, the job they belong to and who is owed. Adding them
    here rather than later means the frontend written against this response does
    not change shape when payment is switched on.
    """

    job_id: int
    appointment_id: int
    reference: str

    provider_id: int
    provider_name: str
    provider_phone: str | None = None
    provider_website: str | None = None

    service_id: int
    service_name: str

    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    label: str

    price: float
    currency: str
    #: What was chosen: cod, stripe or paypal.
    payment_method: str = "cod"
    #: "cod", "unpaid" or "paid". Never invented: only the payment provider's
    #: own webhook may set this to paid, because a browser arriving back on a
    #: success page proves nothing.
    payment_status: str = "unpaid"
    #: True when the customer still has to be sent to a payment page.
    payment_due: bool = False

    customer_id: int
    customer_name: str
    customer_email: str | None = None
    address: str | None = None
    notes: str | None = None

    status: str
    service_request_id: int | None = None


@router.post("/book", response_model=BookedOut,
             summary="Take a time with a provider, in one step")
def book(payload: BookIn,
         background: BackgroundTasks,
         customer: Customer = Depends(require_customer),
         db: Session = Depends(get_db)):
    """The whole booking, as one call, against one provider.

    Deliberately not a cart and a checkout. A visit is one job at one time at one
    address, so there is nothing to accumulate and nothing to review.

    The price and the duration come from `provider_services`, not from the
    service row. The service carries a guide figure for matching and for showing
    a range before anybody is chosen; what a business charges and how long it
    takes are the business's to say, and are what a booking is made against.
    """
    provider = db.query(Provider).filter(Provider.id == payload.provider_id).first()
    if provider is None:
        raise HTTPException(status_code=404, detail="No such provider.")
    if provider.status != "active":
        # A pending application can fill in its profile; it cannot receive work.
        raise HTTPException(
            status_code=409,
            detail="That provider is not taking bookings yet.",
        )

    service = db.query(Service).filter(Service.id == payload.service_id).first()
    if service is None:
        raise HTTPException(status_code=404, detail="We do not offer that service.")

    offering = (
        db.query(ProviderService)
        .filter(ProviderService.provider_id == provider.id,
                ProviderService.service_id == service.id,
                ProviderService.active.is_(True))
        .first()
    )
    if offering is None:
        raise HTTPException(status_code=409,
                            detail="That provider does not offer that service.")

    price = float(offering.price if offering.price is not None else (service.price or 0))
    duration = int(offering.duration_minutes or service.duration_minutes or 60)

    booking_service.release_expired(db)

    if payload.address and not customer.address:
        customer.address = payload.address

    request = None
    if payload.service_request_id:
        request = (
            db.query(ServiceRequest)
            .filter(ServiceRequest.id == payload.service_request_id,
                    # Scoped to the caller: a request id from somebody else is
                    # not a way to attach their problem to your booking.
                    ServiceRequest.customer_id == customer.id)
            .first()
        )
        if request is None:
            raise HTTPException(status_code=404, detail="Not one of your requests.")

    job = Job(
        customer_id=customer.id,
        provider_id=provider.id,
        provider_service_id=offering.id,
        service_request_id=request.id if request else None,
        currency=settings.PAYMENT_CURRENCY,
        status="pending",
        total_amount=price,
        items_json=[{
            "item_id": service.id,
            "name": service.name,
            "price": price,
            "quantity": 1,
        }],
        notes=payload.notes or None,
        access_notes=payload.notes or None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    slot = calendly.Slot(
        starts_at=payload.starts_at,
        ends_at=payload.starts_at + timedelta(minutes=duration),
    )

    try:
        appointment = booking_service.hold(db, job, slot, provider.id)
        appointment = booking_service.confirm(
            db, appointment,
            name=customer.name, email=customer.email,
            phone=customer.phone or "", address=payload.address or customer.address or "",
            notes=payload.notes,
        )
    except booking_service.BookingError as exc:
        # Otherwise the job sits there with no appointment, which is exactly the
        # half finished state this endpoint exists to avoid.
        db.delete(job)
        db.commit()
        raise HTTPException(status_code=409, detail=str(exc))

    job.status = "scheduled"
    job.payment_method = payload.payment_method
    # Cash is settled with the provider, so there is nothing outstanding here.
    # Anything else is unpaid until that provider's webhook says otherwise.
    job.payment_status = "cod" if payload.payment_method == "cod" else "unpaid"
    job.appointment_date = appointment.starts_at.date()
    job.appointment_time = appointment.starts_at.strftime("%-I:%M %p")
    if request is not None:
        request.status = "booked"
        request.provider_id = provider.id
        request.job_id = job.id
    db.commit()

    logger.info(
        f"[BOOKING] job {job.id}: {service.name} with {provider.business_name} "
        f"for customer {customer.id} at {appointment.starts_at:%Y-%m-%d %H:%M}"
    )

    # After the commit and outside the request. The booking exists either way:
    # a relay that is slow or refusing must not hold this response open, and
    # must not turn a booking that worked into an error on screen.
    background.add_task(send_booking_emails, appointment.id)

    return BookedOut(
        job_id=job.id,
        appointment_id=appointment.id,
        reference=f"BK-{job.id:05d}",
        provider_id=provider.id,
        provider_name=provider.business_name,
        provider_phone=provider.phone,
        provider_website=provider.website,
        service_id=service.id,
        service_name=service.name or "",
        starts_at=appointment.starts_at,
        ends_at=appointment.ends_at,
        duration_minutes=duration,
        label=appointment.starts_at.strftime("%A %-d %B, %-I:%M %p"),
        price=price,
        currency=job.currency or settings.PAYMENT_CURRENCY,
        payment_method=job.payment_method,
        payment_status=job.payment_status,
        payment_due=job.payment_status == "unpaid",
        customer_id=customer.id,
        customer_name=customer.name or "",
        customer_email=customer.email,
        address=payload.address or customer.address,
        notes=payload.notes or None,
        status=appointment.status,
        service_request_id=request.id if request else None,
    )


@router.get("/mine", summary="My bookings")
def my_bookings(when: str = Query("all", pattern="^(all|upcoming|past|cancelled)$"),
                customer: Customer = Depends(require_customer),
                db: Session = Depends(get_db)):
    """Scoped to the signed-in customer. There is no id to tamper with, because
    the endpoint never takes one."""
    rows = (
        db.query(Appointment, Job, Provider)
        .join(Job, Job.id == Appointment.job_id)
        .outerjoin(Provider, Provider.id == Appointment.provider_id)
        .filter(Job.customer_id == customer.id)
        .order_by(Appointment.starts_at.desc())
        .limit(200)
        .all()
    )

    now = datetime.utcnow()
    if when == "upcoming":
        rows = [r for r in rows
                if r[0].starts_at >= now and r[0].status not in ("cancelled",)]
    elif when == "past":
        rows = [r for r in rows
                if r[0].starts_at < now or r[0].status == "completed"]
    elif when == "cancelled":
        rows = [r for r in rows if r[0].status == "cancelled"]
    return [{
        "reference": f"BK-{j.id:05d}",
        "appointment_id": a.id,
        "job_id": j.id,
        "status": a.status,
        "starts_at": a.starts_at,
        "label": a.starts_at.strftime("%A %-d %B, %-I:%M %p"),
        "provider_name": p.business_name if p else None,
        "provider_phone": p.phone if p else None,
        "service": (j.items_json or [{}])[0].get("name"),
        "price": float(j.total_amount or 0),
        "currency": j.currency or settings.PAYMENT_CURRENCY,
        "starts_at": a.starts_at,
        "ends_at": a.ends_at,
        "provider_website": p.website if p else None,
        "address": None,
        "notes": j.access_notes,
        "payment_method": j.payment_method or "cod",
        "payment_status": j.payment_status or "unpaid",
    } for a, j, p in rows]


@router.post("/{appointment_id}/cancel", summary="Cancel one of my bookings")
def cancel_booking(appointment_id: int,
                   background: BackgroundTasks,
                   customer: Customer = Depends(require_customer),
                   db: Session = Depends(get_db)):
    """Only the customer whose booking it is. The join to `jobs` is what
    enforces that: somebody else's appointment id finds nothing."""
    row = (
        db.query(Appointment, Job)
        .join(Job, Job.id == Appointment.job_id)
        .filter(Appointment.id == appointment_id, Job.customer_id == customer.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Not one of your bookings.")

    appointment, job = row
    if appointment.status in ("cancelled", "completed"):
        return {"status": appointment.status, "reference": f"BK-{job.id:05d}"}

    appointment.status = "cancelled"
    appointment.cancel_reason = "Cancelled by the customer."
    job.status = "cancelled"
    db.commit()
    logger.info(f"[BOOKING] appointment {appointment.id} cancelled by customer {customer.id}")

    # The provider is told, because a freed slot is only useful to somebody who
    # knows it is free.
    background.add_task(send_cancellation_email, appointment.id)

    return {"status": "cancelled", "reference": f"BK-{job.id:05d}"}
