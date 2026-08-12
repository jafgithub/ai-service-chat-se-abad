"""How somebody proves who they are.

There was no authentication at all: a customer was a session id, and admin was a
shared token in a header. That is fine for a demonstration and impossible for a
platform where a provider manages their own diary and a customer sees their own
bookings and nobody else's.

Kept as a separate table rather than columns on `customers`, for two reasons.
The same person can be both a customer and a provider, and a password has a
different lifetime from a customer record: an old booking's customer row must
survive somebody deleting their login.

The admin role stays where it is, guarded by ADMIN_TOKEN in a header, because it
already works and nothing is gained by moving it.
"""

from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey, Index, Integer, String,
)
from sqlalchemy.sql import func

from app.db.database import Base


class Account(Base):
    """A login, and which side of the platform it belongs to."""

    __tablename__ = "accounts"

    id    = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, unique=True)

    # Never the password. PBKDF2 with a per-account salt, both stored here; see
    # services/auth.py for why that rather than something faster.
    password_hash = Column(String(255), nullable=False)

    role = Column(Enum("customer", "provider", "admin"), nullable=False,
                  default="customer")

    # Whichever side this login is. Exactly one is set for customer and provider
    # roles, which is checked on creation rather than by the database, because
    # MySQL will not enforce a conditional foreign key.
    customer_id = Column(Integer, ForeignKey("customers.id"))
    provider_id = Column(Integer, ForeignKey("providers.id"))

    last_login_at = Column(DateTime)
    created_at    = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_account_role", "role"),
    )


class Session(Base):
    """A bearer token, and when it stops working.

    Tokens rather than cookies because the frontend is a static export served
    from a different path than the API, and because the existing admin
    convention is already a header. One mechanism, not two.

    Rows rather than signed tokens so a session can actually be revoked. A
    signed token that cannot be withdrawn is not a session, it is a password
    with an expiry.
    """

    __tablename__ = "sessions"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"),
                        nullable=False)

    # The token itself is never stored, only its hash, so a leaked database
    # does not hand over live sessions.
    token_hash = Column(String(64), nullable=False, unique=True)

    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    revoked_at = Column(DateTime)

    __table_args__ = (
        Index("ix_session_account", "account_id"),
        Index("ix_session_expiry", "expires_at"),
    )
