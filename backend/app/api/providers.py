"""Finding a provider, and a provider managing themselves.

Two audiences in one file, separated by what they are allowed to touch.

Customers get discovery: who offers this service, what do they charge, how long
do they take, when could they come. Open without signing in, because somebody
should be able to see who can fix a leak before they make an account.

Providers get their own profile, services, hours and closures. Every one of
those endpoints reads the provider from the token rather than from the request,
so there is no id for a caller to change.
"""

import logging
from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_provider
from app.core.config import settings
from app.db.database import get_db
from app.models.provider import (
    Provider, ProviderAvailability, ProviderService, ProviderTimeOff,
)
from app.models.service import Service
from app.services import booking_service, discovery

logger = logging.getLogger("booking")

router = APIRouter(prefix="/providers", tags=["providers"])


# ── what a customer sees ─────────────────────────────────────────────────────

class OfferingOut(BaseModel):
    provider_id: int
    business_name: str
    description: str | None = None
    website: str | None = None
    phone: str | None = None
    city: str | None = None
    #: This provider's own price and duration, not the service's guide figures.
    price: float
    duration_minutes: int
    provider_service_id: int
    next_available: datetime | None = None
    next_available_label: str | None = None


class DiscoveryOut(BaseModel):
    service_id: int
    service_name: str
    ranked_by: str
    providers: list[OfferingOut]


@router.get("/for-service/{service_id}", response_model=DiscoveryOut,
            summary="Who can do this, soonest first")
def for_service(service_id: int, db: Session = Depends(get_db)):
    """Open deliberately: choosing who to call should not need an account."""
    service = db.query(Service).filter(Service.id == service_id).first()
    if service is None:
        raise HTTPException(status_code=404, detail="We do not know that service.")

    offerings = discovery.offerings_for_service(db, service)

    return DiscoveryOut(
        service_id=service.id,
        service_name=service.name or "",
        ranked_by=settings.PROVIDER_RANKING,
        providers=[
            OfferingOut(
                provider_id=o.provider.id,
                business_name=o.provider.business_name,
                description=o.provider.description,
                website=o.provider.website,
                phone=o.provider.phone,
                city=o.provider.city,
                price=o.price,
                duration_minutes=o.duration_minutes,
                provider_service_id=o.provider_service.id,
                next_available=o.next_available,
                next_available_label=(
                    o.next_available.strftime("%A %-d %B, %-I:%M %p")
                    if o.next_available else None
                ),
            )
            for o in offerings
        ],
    )


class ProviderDetailOut(BaseModel):
    id: int
    business_name: str
    contact_name: str | None = None
    description: str | None = None
    website: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    postcode: str | None = None
    status: str
    services: list[dict]


@router.get("/{provider_id}", response_model=ProviderDetailOut,
            summary="One provider, and what they offer")
def provider_detail(provider_id: int, db: Session = Depends(get_db)):
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if provider is None or provider.status != "active":
        # Same answer for missing and not-yet-approved, so the endpoint is not a
        # way to enumerate pending applications.
        raise HTTPException(status_code=404, detail="No such provider.")

    rows = (
        db.query(ProviderService, Service)
        .join(Service, Service.id == ProviderService.service_id)
        .filter(ProviderService.provider_id == provider.id,
                ProviderService.active.is_(True))
        .all()
    )
    return ProviderDetailOut(
        id=provider.id,
        business_name=provider.business_name,
        contact_name=provider.contact_name,
        description=provider.description,
        website=provider.website,
        phone=provider.phone,
        email=provider.email,
        city=provider.city,
        postcode=provider.postcode,
        status=provider.status,
        services=[{
            "provider_service_id": ps.id,
            "service_id": service.id,
            "name": service.name,
            "price": float(ps.price) if ps.price is not None else float(service.price or 0),
            "duration_minutes": ps.duration_minutes or service.duration_minutes or 60,
            "notes": ps.notes,
        } for ps, service in rows],
    )


class AvailabilityOut(BaseModel):
    provider_id: int
    service_id: int
    duration_minutes: int
    slots: list[dict]


@router.get("/{provider_id}/availability", response_model=AvailabilityOut,
            summary="When this provider could attend")
def provider_availability(
    provider_id: int,
    service_id: int = Query(..., ge=1),
    days_ahead: int = Query(0, ge=0, le=60),
    db: Session = Depends(get_db),
):
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if provider is None or provider.status != "active":
        raise HTTPException(status_code=404, detail="No such provider.")

    service = db.query(Service).filter(Service.id == service_id).first()
    if service is None:
        raise HTTPException(status_code=404, detail="We do not know that service.")

    offering = (
        db.query(ProviderService)
        .filter(ProviderService.provider_id == provider_id,
                ProviderService.service_id == service_id,
                ProviderService.active.is_(True))
        .first()
    )
    if offering is None:
        raise HTTPException(status_code=404,
                            detail="That provider does not offer that service.")

    booking_service.release_expired(db)
    duration = int(offering.duration_minutes or service.duration_minutes or 60)

    try:
        slots = booking_service.available_slots(
            db, service, provider_id, duration_minutes=duration,
            days_ahead=days_ahead or settings.BOOKING_DAYS_AHEAD,
        )
    except booking_service.BookingError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return AvailabilityOut(
        provider_id=provider_id,
        service_id=service_id,
        duration_minutes=duration,
        slots=[{
            "starts_at": s.starts_at,
            "ends_at": s.ends_at,
            "label": s.label,
        } for s in slots],
    )


# ── a provider managing themselves ───────────────────────────────────────────

class ProfileIn(BaseModel):
    business_name: str | None = Field(default=None, max_length=200)
    contact_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    website: str | None = Field(default=None, max_length=400)
    description: str | None = Field(default=None, max_length=4000)
    address: str | None = Field(default=None, max_length=400)
    city: str | None = Field(default=None, max_length=120)
    postcode: str | None = Field(default=None, max_length=20)
    travel_radius_miles: int | None = Field(default=None, ge=0, le=500)
    requires_approval: bool | None = None


@router.get("/me/profile", summary="My business")
def my_profile(provider: Provider = Depends(require_provider)):
    """A pending provider can read and edit this. What waiting gates is being
    offered to customers, not managing your own details."""
    return {
        "id": provider.id,
        "business_name": provider.business_name,
        "contact_name": provider.contact_name,
        "email": provider.email,
        "phone": provider.phone,
        "website": provider.website,
        "description": provider.description,
        "address": provider.address,
        "city": provider.city,
        "postcode": provider.postcode,
        "travel_radius_miles": provider.travel_radius_miles,
        "requires_approval": provider.requires_approval,
        "status": provider.status,
    }


@router.patch("/me/profile", summary="Change my business details")
def update_profile(payload: ProfileIn,
                   provider: Provider = Depends(require_provider),
                   db: Session = Depends(get_db)):
    # `status` is deliberately not in ProfileIn. A provider approving themselves
    # would make the approval step decorative.
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(provider, field, value)
    db.commit()
    db.refresh(provider)
    return {"status": "saved", "provider_status": provider.status}


class ServiceOfferIn(BaseModel):
    service_id: int
    price: float | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, ge=15, le=600)
    notes: str | None = Field(default=None, max_length=2000)
    active: bool = True


@router.get("/me/services", summary="What I offer")
def my_services(provider: Provider = Depends(require_provider),
                db: Session = Depends(get_db)):
    rows = (
        db.query(ProviderService, Service)
        .join(Service, Service.id == ProviderService.service_id)
        .filter(ProviderService.provider_id == provider.id)
        .all()
    )
    return [{
        "provider_service_id": ps.id,
        "service_id": service.id,
        "name": service.name,
        "price": float(ps.price) if ps.price is not None else None,
        "duration_minutes": ps.duration_minutes,
        "guide_price": float(service.price or 0),
        "guide_duration": service.duration_minutes,
        "notes": ps.notes,
        "active": bool(ps.active),
    } for ps, service in rows]


@router.put("/me/services", summary="Offer a service, or change my terms for it")
def set_service(payload: ServiceOfferIn,
                provider: Provider = Depends(require_provider),
                db: Session = Depends(get_db)):
    """One call for both adding and editing, because from the provider's point
    of view "I do this, for this much" is one statement either way."""
    service = db.query(Service).filter(Service.id == payload.service_id).first()
    if service is None:
        raise HTTPException(status_code=404, detail="We do not know that service.")

    row = (
        db.query(ProviderService)
        .filter(ProviderService.provider_id == provider.id,
                ProviderService.service_id == payload.service_id)
        .first()
    )
    if row is None:
        row = ProviderService(provider_id=provider.id, service_id=payload.service_id)
        db.add(row)

    row.price = payload.price
    row.duration_minutes = payload.duration_minutes
    row.notes = payload.notes
    row.active = payload.active
    db.commit()
    db.refresh(row)
    return {"provider_service_id": row.id, "status": "saved"}


@router.delete("/me/services/{provider_service_id}", summary="Stop offering a service")
def remove_service(provider_service_id: int,
                   provider: Provider = Depends(require_provider),
                   db: Session = Depends(get_db)):
    row = (
        db.query(ProviderService)
        .filter(ProviderService.id == provider_service_id,
                # Scoped to the caller: an id from somebody else's business
                # simply does not exist as far as this endpoint is concerned.
                ProviderService.provider_id == provider.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Not one of yours.")

    # Deactivated rather than deleted, so past bookings keep the terms they were
    # made under.
    row.active = False
    db.commit()
    return {"status": "withdrawn"}


class HoursIn(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 is Monday")
    opens_at: time
    closes_at: time


@router.get("/me/availability", summary="My working week")
def my_hours(provider: Provider = Depends(require_provider),
             db: Session = Depends(get_db)):
    rows = (
        db.query(ProviderAvailability)
        .filter(ProviderAvailability.provider_id == provider.id)
        .order_by(ProviderAvailability.weekday, ProviderAvailability.opens_at)
        .all()
    )
    return [{
        "id": r.id, "weekday": r.weekday,
        "opens_at": r.opens_at.isoformat(), "closes_at": r.closes_at.isoformat(),
    } for r in rows]


@router.put("/me/availability", summary="Set the hours for a day")
def set_hours(payload: HoursIn,
              provider: Provider = Depends(require_provider),
              db: Session = Depends(get_db)):
    if payload.closes_at <= payload.opens_at:
        raise HTTPException(status_code=400,
                            detail="Closing time has to be after opening time.")

    row = (
        db.query(ProviderAvailability)
        .filter(ProviderAvailability.provider_id == provider.id,
                ProviderAvailability.weekday == payload.weekday)
        .first()
    )
    if row is None:
        row = ProviderAvailability(provider_id=provider.id, weekday=payload.weekday)
        db.add(row)
    row.opens_at = payload.opens_at
    row.closes_at = payload.closes_at
    db.commit()
    return {"status": "saved"}


@router.delete("/me/availability/{weekday}", summary="Close on a day")
def clear_hours(weekday: int,
                provider: Provider = Depends(require_provider),
                db: Session = Depends(get_db)):
    """No row for a day means closed, which is why this deletes rather than
    setting a flag."""
    (db.query(ProviderAvailability)
       .filter(ProviderAvailability.provider_id == provider.id,
               ProviderAvailability.weekday == weekday)
       .delete())
    db.commit()
    return {"status": "closed"}


class TimeOffIn(BaseModel):
    starts_at: datetime
    ends_at: datetime
    reason: str | None = Field(default=None, max_length=200)


@router.post("/me/time-off", summary="Block out a holiday or a closure")
def add_time_off(payload: TimeOffIn,
                 provider: Provider = Depends(require_provider),
                 db: Session = Depends(get_db)):
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=400, detail="That period ends before it starts.")

    row = ProviderTimeOff(provider_id=provider.id, starts_at=payload.starts_at,
                          ends_at=payload.ends_at, reason=payload.reason)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "status": "blocked out"}


@router.get("/me/appointments", summary="My diary")
def my_appointments(upcoming_only: bool = Query(True),
                    provider: Provider = Depends(require_provider),
                    db: Session = Depends(get_db)):
    """Scoped to the caller's own business, so there is no id to tamper with."""
    from app.models.appointment import Appointment
    from app.models.customer import Customer
    from app.models.job import Job

    query = (
        db.query(Appointment, Job, Customer)
        .join(Job, Job.id == Appointment.job_id)
        .outerjoin(Customer, Customer.id == Job.customer_id)
        .filter(Appointment.provider_id == provider.id)
    )
    if upcoming_only:
        query = query.filter(Appointment.starts_at >= datetime.utcnow())

    rows = query.order_by(Appointment.starts_at).limit(200).all()
    return [{
        "appointment_id": a.id,
        "job_id": j.id,
        "status": a.status,
        "starts_at": a.starts_at,
        "ends_at": a.ends_at,
        "label": a.starts_at.strftime("%A %-d %B, %-I:%M %p"),
        "customer_name": c.name if c else None,
        "customer_phone": c.phone if c else None,
        "address": c.address if c else None,
        "notes": j.access_notes,
    } for a, j, c in rows]


# ── the office ───────────────────────────────────────────────────────────────

@router.post("/{provider_id}/approve", summary="Approve or suspend a provider")
def set_status(provider_id: int, new_status: str = Query(..., pattern="^(active|suspended|rejected|pending)$"),
               _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if provider is None:
        raise HTTPException(status_code=404, detail="No such provider.")
    provider.status = new_status
    db.commit()
    logger.info(f"[BOOKING] provider {provider_id} set to {new_status}")
    return {"provider_id": provider_id, "status": new_status}


@router.get("/", summary="Every provider, for the office")
def list_providers(status_filter: str | None = Query(default=None, alias="status"),
                   _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    query = db.query(Provider)
    if status_filter:
        query = query.filter(Provider.status == status_filter)
    return [{
        "id": p.id, "business_name": p.business_name, "email": p.email,
        "city": p.city, "status": p.status, "created_at": p.created_at,
    } for p in query.order_by(Provider.id.desc()).limit(200).all()]
