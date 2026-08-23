"""Issuing a parking pass, drawing its QR code, and expiring it on the way out.

The QR is generated here rather than by a third party, which the client asked
for and which is right anyway: a pass that depends on somebody else's uptime is
a barrier that will not open one morning.

**What the code contains.** A token and nothing else. A QR on a windscreen can
be photographed by anyone walking past, so it must not carry the resident's
name, their unit, or their registration. Those are looked up from the token, by
somebody authorised to look.
"""

import io
import logging
import secrets
from datetime import datetime, timedelta

import segno

from app.core.config import settings
from app.models.parking import EXPIRED, ISSUED, ParkingPass

logger = logging.getLogger("parking")

#: Serenity's own temporary parking pass form allows five days. It is the only
#: written rule any of these associations has given us, so it is the default
#: everywhere until somebody says otherwise, and it is one number to change.
DEFAULT_DAYS = 5
MAX_DAYS = 30

#: How many live passes one resident may hold. Serenity's form says one per
#: adult; without a per-community rule this stops a single account quietly
#: issuing passes for a street full of cars.
MAX_LIVE_PER_ACCOUNT = 3


def new_token() -> str:
    """32 hex characters from `secrets`.

    Not a sequence and not derived from anything: knowing one pass's token must
    tell you nothing about any other, because a token is the whole credential.
    """
    return secrets.token_hex(16)


def qr_svg(token: str, scale: int = 8) -> str:
    """The pass as an SVG, for a screen or an email.

    SVG rather than PNG because it stays sharp on a phone held up to a scanner
    at any size, and because it needs no image library.
    """
    code = segno.make(verify_url(token), error="m")
    # Bytes, not text: segno writes SVG as encoded bytes even though it is a
    # text format, and handing it a StringIO fails with "string argument
    # expected, got bytes".
    buffer = io.BytesIO()
    code.save(buffer, kind="svg", scale=scale, border=2, dark="#14130F")
    return buffer.getvalue().decode("utf-8")


def qr_png(token: str, scale: int = 8) -> bytes:
    """The pass as a PNG, for email clients that will not render SVG.

    Most will not. Outlook has never rendered inline SVG, so the emailed copy
    has to be a raster or the resident opens a message with a hole in it.
    """
    code = segno.make(verify_url(token), error="m")
    buffer = io.BytesIO()
    code.save(buffer, kind="png", scale=scale, border=2, dark="#14130F")
    return buffer.getvalue()


def verify_url(token: str) -> str:
    """What the QR points at: the page a guard lands on when they scan it.

    A URL rather than a bare token, so scanning with any phone camera does
    something useful instead of showing 32 characters of hex to somebody
    standing at a barrier in the rain.
    """
    base = (settings.SITE_BASE_URL or "").rstrip("/")
    # A query string rather than a path segment, because the site is a static
    # export: a page at /parking/check exists as a file, while
    # /parking/check/<token> would need a file per pass.
    return f"{base}/parking/check?t={token}"


def live_passes(db, account_id: int) -> list[ParkingPass]:
    now = datetime.utcnow()
    return [p for p in db.query(ParkingPass)
            .filter(ParkingPass.account_id == account_id,
                    ParkingPass.status == ISSUED,
                    ParkingPass.exited_at.is_(None))
            .order_by(ParkingPass.issued_at.desc()).all()
            if p.expires_at > now]


class ParkingError(Exception):
    """Something the resident can fix, said in words they can act on."""


def issue(db, *, account, community: str, vehicle_registration: str,
          vehicle_description: str = "", visiting: str = "",
          days: int = DEFAULT_DAYS) -> ParkingPass:
    registration = " ".join((vehicle_registration or "").upper().split())
    if not registration:
        raise ParkingError("Which vehicle is this for? Enter its registration.")
    if not community.strip():
        raise ParkingError("Which community are you parking in?")

    days = max(1, min(int(days or DEFAULT_DAYS), MAX_DAYS))

    live = live_passes(db, account.id)
    if len(live) >= MAX_LIVE_PER_ACCOUNT:
        raise ParkingError(
            f"You already have {len(live)} passes in use. End one before "
            f"asking for another, or ask the office.")

    # The same car twice is a mistake, not a request. Hand back the pass they
    # already have rather than a second one that lets two people in.
    for existing in live:
        if existing.vehicle_registration == registration:
            logger.info("[PARKING] %s already has a live pass for %s",
                        account.email, registration)
            return existing

    now = datetime.utcnow()
    pass_ = ParkingPass(
        account_id=account.id,
        customer_id=getattr(account, "customer_id", None),
        community=" ".join(community.lower().split()),
        vehicle_registration=registration,
        vehicle_description=(vehicle_description or "").strip() or None,
        visiting=(visiting or "").strip() or None,
        token=new_token(),
        status=ISSUED,
        issued_at=now,
        expires_at=now + timedelta(days=days),
    )
    db.add(pass_)
    db.flush()
    logger.info("[PARKING] pass %s issued to %s for %s until %s",
                pass_.id, account.email, registration, pass_.expires_at)
    return pass_


def mark_exit(db, pass_: ParkingPass) -> ParkingPass:
    """The vehicle has left, so the pass is spent.

    This is the expiry the client asked for. Time is the backstop; leaving is
    the real end, because a pass that still opens the barrier after the car has
    gone is a pass that can be handed to somebody else.
    """
    if pass_.exited_at is None:
        pass_.exited_at = datetime.utcnow()
        logger.info("[PARKING] pass %s used on exit", pass_.id)
    return pass_


def cancel(db, pass_: ParkingPass) -> ParkingPass:
    pass_.status = EXPIRED
    logger.info("[PARKING] pass %s cancelled by the office", pass_.id)
    return pass_
