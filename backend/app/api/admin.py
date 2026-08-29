"""
Operational and reporting endpoints for staff.

Two jobs. Rebuilding the in-memory catalog index, which goes stale the moment
the catalog changes (after `import_items_from_remote.py` runs, or after prices
are edited directly). And read-only reporting for the admin page: orders,
payments and takings.

Guarded by ADMIN_TOKEN (sent as `X-Admin-Token`). With no token set the routes
refuse to run at all, so a box that never configures one is never exposed.
Everything here is read-only apart from the reindex, which touches no data.
"""

import logging
import threading
from datetime import datetime, timedelta

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.config import settings
from app.db.database import get_db
from app.models.customer import Customer
from app.models.job import Job
from app.models.appointment import Appointment
from app.models.payment import Payment
from app.services import catalog_index

logger = logging.getLogger("rag")

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_token(supplied: str | None) -> None:
    if not settings.ADMIN_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Admin endpoints are disabled — set ADMIN_TOKEN in .env to enable them.",
        )
    # compare_digest keeps the check constant-time so the token can't be guessed
    # a character at a time by timing the responses.
    import secrets
    if not supplied or not secrets.compare_digest(supplied, settings.ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid admin token.")


@router.get("/index-status", summary="Current state of the in-memory catalog index")
def index_status(x_admin_token: str | None = Header(default=None)):
    _require_token(x_admin_token)
    return catalog_index.status()


@router.post("/reindex", summary="Rebuild the in-memory catalog index")
def reindex(x_admin_token: str | None = Header(default=None)):
    """Kick off a rebuild and return immediately.

    The rebuild runs on a background thread and only replaces the live index once
    it has finished, so searches keep being served from the current snapshot the
    whole time — there is no window where the catalog is unsearchable.
    """
    _require_token(x_admin_token)

    before = catalog_index.status()
    if before.get("state") == "building":
        return {"started": False, "reason": "a rebuild is already in progress", "index": before}

    logger.info("[INDEX] rebuild requested via /admin/reindex")
    threading.Thread(target=catalog_index.build, name="reindex", daemon=True).start()

    return {
        "started": True,
        "message": "Rebuild started. Poll /health (or /admin/index-status) until "
                   "state is 'ready' and built_at has moved.",
        "index_before": before,
    }


# ── reporting ────────────────────────────────────────────────────────────────
# Read-only. The admin page is a static export, so it holds the token in the
# browser and sends it with each request; there is no server to keep a session on.

@router.get("/summary", summary="Headline numbers for the admin dashboard")
def summary(
    days: int = Query(30, ge=1, le=365),
    x_admin_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)
    _require_token(x_admin_token)

    def money(value) -> float:
        return round(float(value or 0), 2)

    # Only confirmed orders count as takings. Pending ones have not been paid
    # for, and counting them would overstate revenue.
    paid_q = db.query(Job).filter(Job.status.in_(("confirmed", "dispatched", "delivered")))

    by_status = dict(
        db.query(Job.status, func.count(Job.id))
        .filter(Job.created_at >= since)
        .group_by(Job.status).all()
    )
    by_provider = [
        {"provider": p, "status": s, "count": c, "amount": money(a)}
        for p, s, c, a in db.query(
            Payment.provider, Payment.status, func.count(Payment.id), func.sum(Payment.amount)
        ).filter(Payment.created_at >= since)
         .group_by(Payment.provider, Payment.status).all()
    ]

    return {
        "window_days": days,
        "orders": {
            "total":      db.query(func.count(Job.id)).scalar() or 0,
            "in_window":  db.query(func.count(Job.id)).filter(Job.created_at >= since).scalar() or 0,
            "by_status":  by_status,
        },
        "revenue": {
            "all_time":  money(paid_q.with_entities(func.sum(Job.total_amount)).scalar()),
            "in_window": money(
                paid_q.filter(Job.created_at >= since)
                      .with_entities(func.sum(Job.total_amount)).scalar()
            ),
        },
        "payments": by_provider,
        # Partner enquiries are written into `customers` with type="partner" by
        # api/partners.py, so they must be excluded from a shopper count.
        "customers": db.query(func.count(Customer.id)).filter(
            (Customer.type == "customer") | (Customer.type.is_(None))
        ).scalar() or 0,
        "index": catalog_index.status(),
    }


@router.get("/orders", summary="Recent orders, newest first")
def list_orders(
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    x_admin_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_token(x_admin_token)

    q = db.query(Job, Customer).outerjoin(Customer, Customer.id == Job.customer_id)
    if status:
        q = q.filter(Job.status == status)
    rows = q.order_by(Job.id.desc()).limit(limit).all()

    # One query for every payment involved, rather than one per order.
    order_ids = [o.id for o, _ in rows]

    # When each booking is, which in this application lives on the appointment
    # rather than on the job. The shop's version of this endpoint read
    # `delivery_date` straight off the order, and that attribute does not exist
    # here, so the staff list has been a 500 since the day it was forked. One
    # query, not one per row.
    appointments: dict[int, Appointment] = {}
    if order_ids:
        for appt in db.query(Appointment).filter(Appointment.job_id.in_(order_ids)).all():
            appointments.setdefault(appt.job_id, appt)
    payments: dict[int, list] = {}
    if order_ids:
        for p in db.query(Payment).filter(Payment.order_id.in_(order_ids)).all():
            payments.setdefault(p.order_id, []).append(
                {"provider": p.provider, "status": p.status, "amount": float(p.amount or 0)}
            )

    return [
        {
            "id": o.id,
            "status": o.status,
            # Cash orders look identical to paid ones by status alone, so the
            # staff list has to say which is which: a "confirmed" cash order
            # still has money outstanding.
            "payment_method": o.payment_method,
            "total": float(o.total_amount or 0),
            # Part of the total above, and owed to the provider rather than
            # earned on the job. Worth its own field so the two can be reported
            # apart.
            "tip": float(o.tip_amount or 0),
            "items": len(o.items_json or []),
            "customer_name": c.name if c else None,
            "customer_email": c.email if c else None,
            "delivery_date": (appointments[o.id].starts_at.date().isoformat()
                              if o.id in appointments and appointments[o.id].starts_at else None),
            "delivery_time": (appointments[o.id].starts_at.strftime("%H:%M")
                              if o.id in appointments and appointments[o.id].starts_at else None),
            "created_at": o.created_at,
            "payments": payments.get(o.id, []),
        }
        for o, c in rows
    ]


@router.get("/payments", summary="Recent payment attempts, newest first")
def list_payments(
    limit: int = Query(50, ge=1, le=200),
    x_admin_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _require_token(x_admin_token)
    return [
        {
            "id": p.id,
            "order_id": p.order_id,
            "provider": p.provider,
            "status": p.status,
            "amount": float(p.amount or 0),
            "currency": p.currency,
            # Truncated: the full provider reference is long and only useful for
            # looking the payment up in the provider's own dashboard.
            "provider_ref": (p.provider_ref or "")[:32],
            "created_at": p.created_at,
        }
        for p in db.query(Payment).order_by(Payment.id.desc()).limit(limit).all()
    ]
