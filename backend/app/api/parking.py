"""Parking passes: asking for one, showing it, checking it, ending it.

The shape the client asked for. A resident who wants to park has to be
registered and signed in, because a pass is personal and the office has to be
able to say whose vehicle is on the property. They get a QR code, on screen and
by email. The office can look any pass up and see who it belongs to. And the
pass expires when the vehicle leaves.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from app.api.deps import current_account, require_admin
from app.db.database import get_db
from app.models.parking import ParkingPass
from app.services import parking, parking_emails

logger = logging.getLogger("parking")

router = APIRouter(prefix="/parking", tags=["parking"])


class PassRequest(BaseModel):
    community: str
    vehicle_registration: str = Field(min_length=1, max_length=32)
    vehicle_description: str = ""
    visiting: str = ""
    days: int = parking.DEFAULT_DAYS


class PassOut(BaseModel):
    id: int
    community: str
    vehicle_registration: str
    vehicle_description: str | None = None
    #: "valid", "used", "expired" or "cancelled". Three ways a pass stops
    #: working, and somebody at a barrier needs to know which.
    state: str
    issued_at: datetime
    expires_at: datetime
    exited_at: datetime | None = None
    #: The image itself, inline, so the screen showing a pass needs no second
    #: request and works with the phone offline once it has been opened.
    qr_svg: str = ""
    check_url: str = ""


class PassHolder(PassOut):
    """What the office sees: the pass, and who is standing behind it."""
    holder_name: str | None = None
    holder_email: str | None = None
    visiting: str | None = None


def _out(pass_: ParkingPass, with_qr: bool = True) -> PassOut:
    return PassOut(
        id=pass_.id,
        community=pass_.community,
        vehicle_registration=pass_.vehicle_registration,
        vehicle_description=pass_.vehicle_description,
        state=pass_.state(),
        issued_at=pass_.issued_at,
        expires_at=pass_.expires_at,
        exited_at=pass_.exited_at,
        qr_svg=parking.qr_svg(pass_.token) if with_qr else "",
        check_url=parking.verify_url(pass_.token),
    )


def _with_holder(pass_: ParkingPass) -> PassHolder:
    """The pass plus who is behind it, for whoever is at the barrier.

    The name comes from the customer record rather than the login, because a
    login is an email address and a person at a gate needs a name to say.
    """
    account = getattr(pass_, "account", None)
    customer = getattr(pass_, "customer", None)
    return PassHolder(
        **_out(pass_, with_qr=False).model_dump(),
        holder_name=getattr(customer, "name", None) or getattr(account, "name", None),
        holder_email=getattr(account, "email", None) or getattr(customer, "email", None),
        visiting=pass_.visiting,
    )


COMMUNITIES_PATH = Path(__file__).resolve().parent.parent / "data" / "communities.json"


@router.get("/communities", summary="The communities a pass can be issued for")
def communities() -> dict:
    """The list the pass form offers.

    It used to come from the community documents index, which has moved to its
    own application. A parking pass still belongs to a community, so the small
    registry stayed behind with the product that needs it. Nothing here reads a
    document or an index: it is a list of names.
    """
    try:
        data = json.loads(COMMUNITIES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # A missing registry must not take the parking form down with it.
        logger.warning("[PARKING] the community registry could not be read")
        return {"communities": [], "home": ""}

    found = [{"key": c["key"], "label": c["label"]} for c in data.get("communities", [])]
    return {"communities": found, "home": found[0]["key"] if found else ""}


@router.post("", response_model=PassOut, status_code=status.HTTP_201_CREATED,
             summary="Ask for a parking pass")
def request_pass(payload: PassRequest,
                 account=Depends(current_account),
                 db: DbSession = Depends(get_db)) -> PassOut:
    """Signed in only, which is the point rather than a detail.

    `current_account` refuses anybody without a session, so a pass always has a
    person attached to it and the office can always answer "whose car is that".
    """
    try:
        pass_ = parking.issue(
            db, account=account,
            community=payload.community,
            vehicle_registration=payload.vehicle_registration,
            vehicle_description=payload.vehicle_description,
            visiting=payload.visiting,
            days=payload.days,
        )
    except parking.ParkingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(pass_)

    # Emailed as well as shown, because a resident who closes the tab on the way
    # out of the door still needs the code at the barrier.
    parking_emails.send_pass(pass_, to=account.email, name=getattr(account, "name", ""))
    return _out(pass_)


@router.get("", response_model=list[PassOut], summary="My passes, newest first")
def my_passes(account=Depends(current_account),
              db: DbSession = Depends(get_db)) -> list[PassOut]:
    rows = (db.query(ParkingPass)
            .filter(ParkingPass.account_id == account.id)
            .order_by(ParkingPass.issued_at.desc()).limit(20).all())
    return [_out(p) for p in rows]


@router.post("/{pass_id}/exit", response_model=PassOut,
             summary="The vehicle has left")
def leave(pass_id: int, account=Depends(current_account),
          db: DbSession = Depends(get_db)) -> PassOut:
    pass_ = db.query(ParkingPass).filter(ParkingPass.id == pass_id).first()
    if pass_ is None or pass_.account_id != account.id:
        raise HTTPException(status_code=404, detail="No such pass.")
    parking.mark_exit(db, pass_)
    db.commit()
    db.refresh(pass_)
    return _out(pass_, with_qr=False)


# ── the gate ────────────────────────────────────────────────────────────────

@router.get("/check/{token}", response_model=PassHolder,
            summary="What this code is, for whoever scanned it")
def check(token: str, db: DbSession = Depends(get_db),
          _: bool = Depends(require_admin)) -> PassHolder:
    """Behind the office token on purpose.

    Scanning a code must not tell a passer by whose car it is, where they live
    or when they are away. The QR is a pointer; reading what it points at is a
    privileged act.
    """
    pass_ = db.query(ParkingPass).filter(ParkingPass.token == token).first()
    if pass_ is None:
        raise HTTPException(status_code=404, detail="That code is not one of ours.")
    return _with_holder(pass_)


@router.post("/check/{token}/exit", response_model=PassHolder,
             summary="Let the vehicle out, and spend the pass")
def exit_at_gate(token: str, db: DbSession = Depends(get_db),
                 _: bool = Depends(require_admin)) -> PassHolder:
    pass_ = db.query(ParkingPass).filter(ParkingPass.token == token).first()
    if pass_ is None:
        raise HTTPException(status_code=404, detail="That code is not one of ours.")
    parking.mark_exit(db, pass_)
    db.commit()
    db.refresh(pass_)
    return check(token, db, True)


# ── the office ──────────────────────────────────────────────────────────────

@router.get("/all", response_model=list[PassHolder],
            summary="Every pass, for the office")
def all_passes(community: str = "", state: str = "",
               db: DbSession = Depends(get_db),
               _: bool = Depends(require_admin)) -> list[PassHolder]:
    query = db.query(ParkingPass).order_by(ParkingPass.issued_at.desc())
    if community:
        query = query.filter(ParkingPass.community == " ".join(community.lower().split()))
    rows = query.limit(200).all()
    out = []
    for pass_ in rows:
        if state and pass_.state() != state:
            continue
        out.append(_with_holder(pass_))
    return out


@router.get("/{pass_id}/qr.svg", summary="The code on its own")
def qr(pass_id: int, db: DbSession = Depends(get_db),
       _: bool = Depends(require_admin)) -> Response:
    pass_ = db.query(ParkingPass).filter(ParkingPass.id == pass_id).first()
    if pass_ is None:
        raise HTTPException(status_code=404, detail="No such pass.")
    return Response(content=parking.qr_svg(pass_.token), media_type="image/svg+xml")
