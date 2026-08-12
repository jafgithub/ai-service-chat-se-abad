"""A customer's problem, before it is anybody's job.

Separate from booking because most problems never become bookings, and those are
the ones worth keeping: they show where there is no cover and what people ask
for that nobody offers.

The conversation is not stored here. A transcript records how somebody was
helped, changes shape whenever the prompt does, and contains the assistant's
guesses alongside the customer's words. The request stores the problem and what
it was matched to, and keeps the session id so the two can be read together.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_customer
from app.db.database import get_db
from app.models.customer import Customer
from app.models.provider import Provider
from app.models.service import Service
from app.models.service_request import ServiceRequest

logger = logging.getLogger("booking")

router = APIRouter(prefix="/requests", tags=["service requests"])


class RequestIn(BaseModel):
    description: str = Field(min_length=3, max_length=4000)
    service_id: int | None = None
    address: str = Field(default="", max_length=400)
    postcode: str = Field(default="", max_length=20)
    urgency: str = Field(default="whenever", pattern="^(whenever|this_week|urgent)$")
    session_id: str = Field(default="", max_length=64)


class RequestOut(BaseModel):
    id: int
    description: str
    status: str
    urgency: str
    address: str | None = None
    postcode: str | None = None
    service_id: int | None = None
    service_name: str | None = None
    provider_id: int | None = None
    provider_name: str | None = None
    job_id: int | None = None
    created_at: str


def _out(request: ServiceRequest, service: Service | None = None,
         provider: Provider | None = None) -> RequestOut:
    return RequestOut(
        id=request.id,
        description=request.description,
        status=request.status,
        urgency=request.urgency,
        address=request.address,
        postcode=request.postcode,
        service_id=request.service_id,
        service_name=service.name if service else None,
        provider_id=request.provider_id,
        provider_name=provider.business_name if provider else None,
        job_id=request.job_id,
        created_at=request.created_at.isoformat() if request.created_at else "",
    )


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED,
             summary="Record what the customer needs")
def create_request(payload: RequestIn,
                   customer: Customer = Depends(require_customer),
                   db: Session = Depends(get_db)):
    """Belongs to whoever is signed in. The customer is never taken from the
    body, so a request cannot be filed in somebody else's name."""
    service = None
    if payload.service_id:
        service = db.query(Service).filter(Service.id == payload.service_id).first()
        if service is None:
            raise HTTPException(status_code=404, detail="We do not know that service.")

    request = ServiceRequest(
        customer_id=customer.id,
        description=payload.description,
        address=payload.address or customer.address,
        postcode=payload.postcode or None,
        urgency=payload.urgency,
        service_id=service.id if service else None,
        # "matched" only when we actually matched something. A request with no
        # service is the interesting kind and should not look resolved.
        status="matched" if service else "open",
        session_id=payload.session_id or None,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    logger.info(f"[BOOKING] request {request.id} from customer {customer.id}")
    return _out(request, service)


@router.get("", response_model=list[RequestOut], summary="My requests")
def my_requests(customer: Customer = Depends(require_customer),
                db: Session = Depends(get_db)):
    rows = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.customer_id == customer.id)
        .order_by(ServiceRequest.created_at.desc())
        .limit(100)
        .all()
    )
    services = {s.id: s for s in db.query(Service).filter(
        Service.id.in_([r.service_id for r in rows if r.service_id] or [0])).all()}
    providers = {p.id: p for p in db.query(Provider).filter(
        Provider.id.in_([r.provider_id for r in rows if r.provider_id] or [0])).all()}
    return [_out(r, services.get(r.service_id), providers.get(r.provider_id))
            for r in rows]


@router.get("/{request_id}", response_model=RequestOut, summary="One of my requests")
def one_request(request_id: int,
                customer: Customer = Depends(require_customer),
                db: Session = Depends(get_db)):
    request = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.id == request_id,
                # Scoped to the caller, so another customer's id simply does not
                # exist here rather than returning a forbidden that confirms it.
                ServiceRequest.customer_id == customer.id)
        .first()
    )
    if request is None:
        raise HTTPException(status_code=404, detail="Not one of your requests.")

    service = (db.query(Service).filter(Service.id == request.service_id).first()
               if request.service_id else None)
    provider = (db.query(Provider).filter(Provider.id == request.provider_id).first()
                if request.provider_id else None)
    return _out(request, service, provider)


class CloseIn(BaseModel):
    outcome_note: str = Field(default="", max_length=2000)


@router.post("/{request_id}/close", response_model=RequestOut,
             summary="Close a request that came to nothing")
def close_request(request_id: int, payload: CloseIn,
                  customer: Customer = Depends(require_customer),
                  db: Session = Depends(get_db)):
    request = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.id == request_id,
                ServiceRequest.customer_id == customer.id)
        .first()
    )
    if request is None:
        raise HTTPException(status_code=404, detail="Not one of your requests.")
    if request.status == "booked":
        raise HTTPException(status_code=409,
                            detail="That one became a booking. Cancel the booking instead.")

    request.status = "closed"
    request.outcome_note = payload.outcome_note or None
    db.commit()
    db.refresh(request)
    return _out(request)


@router.get("/admin/unserved", summary="What people asked for that nobody could do")
def unserved(limit: int = Query(100, ge=1, le=500),
             _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    """The reason requests are kept separately from bookings.

    Every row here is somebody who wanted something and did not get it: no
    provider offering it, nobody covering the area, or a description that matched
    nothing. It is the list that says what to recruit for next.
    """
    rows = (
        db.query(ServiceRequest)
        .filter(ServiceRequest.status.in_(("open", "unserved")))
        .order_by(ServiceRequest.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{
        "id": r.id,
        "description": r.description,
        "postcode": r.postcode,
        "urgency": r.urgency,
        "status": r.status,
        "matched_service_id": r.service_id,
        "created_at": r.created_at,
    } for r in rows]
