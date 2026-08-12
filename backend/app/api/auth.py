"""Registering, signing in, and signing out.

One authentication system for both sides of the platform. A customer and a
provider differ in which domain record their account points at, not in how they
prove who they are, so there is one login endpoint and one token format.

The part worth reading is `_customer_for`: this database already holds customers
created by booking, with no login attached. Somebody registering with an email
we have already seen is that person, and gets their existing record and their
existing bookings rather than a second row that quietly splits their history.
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import current_account, optional_account
from app.db.database import get_db
from app.models.account import Account
from app.models.customer import Customer
from app.models.provider import Provider, ProviderService
from app.models.service import Service
from app.services import auth, rate_limit

logger = logging.getLogger("auth")

router = APIRouter(prefix="/auth", tags=["auth"])


# ── what goes in and out ─────────────────────────────────────────────────────

class CustomerRegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    phone: str = Field(default="", max_length=40)
    address: str = Field(default="", max_length=400)


class ProviderRegisterIn(BaseModel):
    business_name: str = Field(min_length=2, max_length=200)
    contact_name: str = Field(default="", max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    phone: str = Field(default="", max_length=40)
    website: str = Field(default="", max_length=400)
    description: str = Field(default="", max_length=4000)
    address: str = Field(default="", max_length=400)
    city: str = Field(default="", max_length=120)
    postcode: str = Field(default="", max_length=20)
    #: What they do, with their own price and duration. Optional at sign up,
    #: because a business filling in a form should not be blocked by not having
    #: decided its prices yet; they can add them from the profile afterwards.
    services: list["ProviderServiceIn"] = Field(default_factory=list)


class ProviderServiceIn(BaseModel):
    service_id: int
    price: float | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, ge=15, le=600)
    notes: str | None = Field(default=None, max_length=2000)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    token: str
    role: str
    #: What the interface needs to know without a second call.
    name: str
    customer_id: int | None = None
    provider_id: int | None = None
    #: For a provider, whether the office has approved them yet.
    provider_status: str | None = None


class MeOut(BaseModel):
    account_id: int
    email: str
    role: str
    name: str
    customer_id: int | None = None
    provider_id: int | None = None
    provider_status: str | None = None


# ── helpers ──────────────────────────────────────────────────────────────────

def _existing_account(db: Session, email: str) -> Account | None:
    return db.query(Account).filter(Account.email == email.lower()).first()


def _customer_for(db: Session, payload: CustomerRegisterIn) -> Customer:
    """The customer this registration belongs to.

    Bookings can be taken without an account, so a customer row may already
    exist for this email. Reusing it is the whole point: otherwise somebody who
    booked a leak repair last week registers today and finds no history, and the
    office sees two people with one email.
    """
    customer = (
        db.query(Customer)
        .filter(Customer.email == payload.email.lower())
        .order_by(Customer.id.asc())
        .first()
    )
    if customer is not None:
        # Fill gaps from the registration without overwriting what they gave at
        # booking time, which is likelier to be the address work happened at.
        customer.name = customer.name or payload.name
        customer.phone = customer.phone or (payload.phone or None)
        customer.address = customer.address or (payload.address or None)
        logger.info(f"[AUTH] registration linked to existing customer {customer.id}")
        return customer

    customer = Customer(
        name=payload.name,
        email=payload.email.lower(),
        phone=payload.phone or None,
        address=payload.address or None,
        type="customer",
    )
    db.add(customer)
    db.flush()
    return customer


def _token_out(account: Account, token: str, name: str,
               provider: Provider | None = None) -> TokenOut:
    return TokenOut(
        token=token,
        role=account.role,
        name=name,
        customer_id=account.customer_id,
        provider_id=account.provider_id,
        provider_status=provider.status if provider else None,
    )


# ── registration ─────────────────────────────────────────────────────────────

@router.post("/register/customer", response_model=TokenOut,
             status_code=status.HTTP_201_CREATED,
             summary="Create a customer account")
def register_customer(payload: CustomerRegisterIn, db: Session = Depends(get_db)):
    if _existing_account(db, payload.email):
        # Says an account exists, which is unavoidable on registration: the
        # alternative is silently doing nothing and leaving somebody stuck.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="There is already an account with that email.")

    customer = _customer_for(db, payload)
    account = Account(
        email=payload.email.lower(),
        password_hash=auth.hash_password(payload.password),
        role="customer",
        customer_id=customer.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    token, _ = auth.start_session(db, account)
    logger.info(f"[AUTH] customer account {account.id} registered")
    return _token_out(account, token, customer.name or payload.name)


@router.post("/register/provider", response_model=TokenOut,
             status_code=status.HTTP_201_CREATED,
             summary="Apply as a service provider")
def register_provider(payload: ProviderRegisterIn, db: Session = Depends(get_db)):
    """Anybody may apply. The office decides who becomes bookable.

    The account is created and usable straight away, so an applicant can sign in
    and fill in their services and hours while they wait. What waiting gates is
    being offered to customers, which is `require_active_provider`.
    """
    if _existing_account(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="There is already an account with that email.")
    if db.query(Provider).filter(Provider.email == payload.email.lower()).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="A provider is already registered with that email.")

    provider = Provider(
        business_name=payload.business_name,
        contact_name=payload.contact_name or None,
        email=payload.email.lower(),
        phone=payload.phone or None,
        website=payload.website or None,
        description=payload.description or None,
        address=payload.address or None,
        city=payload.city or None,
        postcode=payload.postcode or None,
        status="pending",
    )
    db.add(provider)
    db.flush()

    # Only services we actually know. A made up id is skipped rather than
    # refusing the whole application, because losing a registration over one bad
    # row is worse than a business having to add that service afterwards.
    known = {
        row[0] for row in db.query(Service.id).filter(
            Service.id.in_([s.service_id for s in payload.services] or [0])
        ).all()
    }
    skipped = []
    for offering in payload.services:
        if offering.service_id not in known:
            skipped.append(offering.service_id)
            continue
        db.add(ProviderService(
            provider_id=provider.id,
            service_id=offering.service_id,
            price=offering.price,
            duration_minutes=offering.duration_minutes,
            notes=offering.notes,
            active=True,
        ))
    if skipped:
        logger.warning(f"[AUTH] provider {provider.id} listed unknown services: {skipped}")

    account = Account(
        email=payload.email.lower(),
        password_hash=auth.hash_password(payload.password),
        role="provider",
        provider_id=provider.id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    db.refresh(provider)

    token, _ = auth.start_session(db, account)
    logger.info(f"[AUTH] provider {provider.id} applied: {provider.business_name}")
    return _token_out(account, token, provider.business_name, provider)


# ── signing in and out ───────────────────────────────────────────────────────

@router.post("/login", response_model=TokenOut, summary="Sign in")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    """One endpoint for both roles. The account knows which side it is."""
    caller = request.client.host if request.client else "unknown"

    wait = rate_limit.check(payload.email, caller)
    if wait is not None:
        # 429 with Retry-After, so a browser or a client library knows what to
        # do rather than treating it as a wrong password.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait and try again.",
            headers={"Retry-After": str(wait)},
        )

    account = _existing_account(db, payload.email)

    # Deliberately identical for a missing account and a wrong password, and the
    # hash is still computed when the account is missing so the two take about
    # the same time. Otherwise the response time says which emails exist.
    if account is None:
        auth.hash_password(payload.password)
        rate_limit.record_failure(payload.email, caller)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Those details do not match an account.")
    if not auth.verify_password(payload.password, account.password_hash):
        rate_limit.record_failure(payload.email, caller)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Those details do not match an account.")

    # A wrong guess before the right password should not count towards a later
    # lockout.
    rate_limit.clear(payload.email, caller)

    # Quietly upgrade a hash written when the cost was lower.
    if auth.needs_rehash(account.password_hash):
        account.password_hash = auth.hash_password(payload.password)
        db.commit()

    name, provider = "", None
    if account.provider_id:
        provider = db.query(Provider).filter(Provider.id == account.provider_id).first()
        name = provider.business_name if provider else ""
    elif account.customer_id:
        customer = db.query(Customer).filter(Customer.id == account.customer_id).first()
        name = customer.name if customer else ""

    token, _ = auth.start_session(db, account)
    return _token_out(account, token, name, provider)


@router.post("/logout", summary="Revoke the current session")
def logout(authorization: str | None = Header(default=None),
           db: Session = Depends(get_db)):
    """Idempotent. Signing out twice is not an error, and saying so would tell
    a caller whether a token was live."""
    token = ""
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = value.strip()
    auth.revoke(db, token)
    return {"status": "signed out"}


@router.get("/me", response_model=MeOut, summary="Who is signed in")
def me(account: Account = Depends(current_account), db: Session = Depends(get_db)):
    name, provider_status = "", None
    if account.provider_id:
        provider = db.query(Provider).filter(Provider.id == account.provider_id).first()
        if provider:
            name, provider_status = provider.business_name, provider.status
    elif account.customer_id:
        customer = db.query(Customer).filter(Customer.id == account.customer_id).first()
        if customer:
            name = customer.name

    return MeOut(
        account_id=account.id,
        email=account.email,
        role=account.role,
        name=name,
        customer_id=account.customer_id,
        provider_id=account.provider_id,
        provider_status=provider_status,
    )


@router.get("/session", summary="Whether the current token is still good")
def session_state(account: Account | None = Depends(optional_account)):
    """For the interface to decide what to show without a 401 in the console."""
    return {"signed_in": account is not None,
            "role": account.role if account else None}
