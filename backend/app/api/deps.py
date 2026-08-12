"""Who is calling, and what they are allowed to touch.

One place, so that an endpoint cannot quietly invent its own rule. The guards
are deliberately small and boring: the interesting decisions are which one an
endpoint asks for, and that is visible in its signature.

The admin role is unchanged. It has always been a shared token in an
`X-Admin-Token` header, it works, and moving it would break the existing admin
screens for no gain. `require_admin` accepts either that header or an account
with the admin role, so both routes in are supported and nothing that worked
stops working.
"""

import logging
import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.account import Account
from app.models.customer import Customer
from app.models.provider import Provider
from app.services import auth

logger = logging.getLogger("auth")

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Please sign in.",
    headers={"WWW-Authenticate": "Bearer"},
)
_FORBIDDEN = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="That is not yours to look at.",
)


def _bearer(authorization: str | None) -> str:
    if not authorization:
        return ""
    scheme, _, token = authorization.partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def optional_account(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Account | None:
    """Whoever is calling, or nobody.

    For endpoints that work signed out but do more when signed in: booking is
    the obvious one, since a customer should not be forced to make an account
    before they can get a leak fixed.
    """
    return auth.account_for_token(db, _bearer(authorization))


def current_account(
    account: Account | None = Depends(optional_account),
) -> Account:
    if account is None:
        raise _UNAUTHENTICATED
    return account


def require_customer(
    account: Account = Depends(current_account),
    db: Session = Depends(get_db),
) -> Customer:
    """The signed-in customer's own record.

    Returns the customer rather than the account on purpose: an endpoint that
    holds the customer cannot accidentally read somebody else's id from the
    request body, because it never needs to look one up.
    """
    if account.role not in ("customer", "admin"):
        raise _FORBIDDEN
    if account.customer_id is None:
        raise _FORBIDDEN
    customer = db.query(Customer).filter(Customer.id == account.customer_id).first()
    if customer is None:
        raise _FORBIDDEN
    return customer


def require_provider(
    account: Account = Depends(current_account),
    db: Session = Depends(get_db),
) -> Provider:
    """The signed-in provider's own business.

    Same reasoning as `require_customer`: an endpoint given the provider cannot
    be tricked into managing a different one, because the id never comes from
    the caller.
    """
    if account.role not in ("provider", "admin"):
        raise _FORBIDDEN
    if account.provider_id is None:
        raise _FORBIDDEN
    provider = db.query(Provider).filter(Provider.id == account.provider_id).first()
    if provider is None:
        raise _FORBIDDEN
    return provider


def require_active_provider(
    provider: Provider = Depends(require_provider),
) -> Provider:
    """A provider the office has approved.

    Managing your own profile while pending is fine; being bookable is not, and
    that difference is what the approval step is for.
    """
    if provider.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This account is {provider.status}. The office has to approve it first.",
        )
    return provider


def require_admin(
    x_admin_token: str | None = Header(default=None),
    account: Account | None = Depends(optional_account),
) -> bool:
    """Either the existing shared token, or an admin account.

    The header is how the admin screens have always authenticated and it keeps
    working untouched. The account route exists so admin does not have to stay a
    password taped to the wall forever.
    """
    if account is not None and account.role == "admin":
        return True

    if not settings.ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoints are disabled: set ADMIN_TOKEN in .env to enable them.",
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.ADMIN_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bad admin token.",
        )
    return True


def owns_customer(customer: Customer, customer_id: int) -> None:
    """Refuse a customer reaching for somebody else's record.

    Called where an id still has to travel in a path, so the check sits next to
    the thing it protects rather than being remembered at each call site.
    """
    if customer.id != customer_id:
        logger.warning(
            f"[AUTH] customer {customer.id} tried to reach customer {customer_id}"
        )
        raise _FORBIDDEN
