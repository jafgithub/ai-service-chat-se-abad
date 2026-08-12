"""Passwords, tokens and sessions.

Two choices worth explaining, because both look like shortcuts and are not.

**PBKDF2 rather than bcrypt or argon2.** Neither is installed, and this runs on
a 1.9 GB box that also holds an embedding model; adding a native dependency
there is a real cost. PBKDF2-HMAC-SHA256 at 480,000 iterations is in the
standard library, is what Django ships as its default, and is a sound choice.
The format below records the algorithm and the iteration count, so raising the
cost later, or moving to argon2, is a migration rather than a rewrite: an old
hash still verifies while new ones are written the new way.

**Sessions as rows holding a hash of the token.** The token is shown once and
never stored, so a leaked database does not hand over live logins. Rows rather
than signed strings because a session has to be revocable, and a signed token
that cannot be withdrawn is a password with an expiry.
"""

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.models.account import Account, Session as AuthSession

logger = logging.getLogger("auth")

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 480_000
_SALT_BYTES = 16
_TOKEN_BYTES = 32


class AuthError(Exception):
    """Something the caller is allowed to be told. Never says which half of a
    login was wrong, because that tells an attacker which emails exist."""


# ── passwords ────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """"pbkdf2_sha256$480000$<salt>$<hash>", so the cost is recorded with it."""
    salt = secrets.token_hex(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _ITERATIONS
    ).hex()
    return f"{_ALGORITHM}${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """Check a password against a stored hash, in constant time.

    Reads the iteration count out of the stored value rather than assuming the
    current one, so hashes written before the cost was raised keep working.
    """
    try:
        algorithm, iterations, salt, expected = stored.split("$", 3)
    except ValueError:
        return False
    if algorithm != _ALGORITHM:
        return False
    try:
        rounds = int(iterations)
    except ValueError:
        return False

    computed = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), rounds
    ).hex()
    return hmac.compare_digest(computed, expected)


def needs_rehash(stored: str) -> bool:
    """True when a password was hashed more cheaply than we now require."""
    try:
        _, iterations, _, _ = stored.split("$", 3)
        return int(iterations) < _ITERATIONS
    except (ValueError, TypeError):
        return True


# ── sessions ─────────────────────────────────────────────────────────────────

def _fingerprint(token: str) -> str:
    """What goes in the database. A plain SHA-256 rather than PBKDF2: the token
    is 256 bits of randomness, so there is nothing to brute force, and this is
    read on every request."""
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(db: DbSession, account: Account) -> tuple[str, AuthSession]:
    """Issue a token. It is returned once and never recoverable afterwards."""
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    row = AuthSession(
        account_id=account.id,
        token_hash=_fingerprint(token),
        expires_at=datetime.utcnow() + timedelta(days=settings.SESSION_DAYS),
    )
    db.add(row)
    account.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    logger.info(f"[AUTH] session for account {account.id} ({account.role})")
    return token, row


def account_for_token(db: DbSession, token: str) -> Account | None:
    """The account behind a bearer token, or None.

    Expiry and revocation are checked here rather than by a background sweep, so
    a revoked session stops working on the next request rather than eventually.
    """
    if not token:
        return None

    row = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == _fingerprint(token))
        .first()
    )
    if row is None or row.revoked_at is not None:
        return None
    if row.expires_at <= datetime.utcnow():
        return None

    return db.query(Account).filter(Account.id == row.account_id).first()


def revoke(db: DbSession, token: str) -> bool:
    """Log out. Idempotent: revoking twice is not an error."""
    row = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == _fingerprint(token))
        .first()
    )
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.utcnow()
    db.commit()
    logger.info(f"[AUTH] session revoked for account {row.account_id}")
    return True


def revoke_all(db: DbSession, account: Account) -> int:
    """Every session for an account. What a password change should do."""
    rows = (
        db.query(AuthSession)
        .filter(AuthSession.account_id == account.id,
                AuthSession.revoked_at.is_(None))
        .all()
    )
    now = datetime.utcnow()
    for row in rows:
        row.revoked_at = now
    if rows:
        db.commit()
    return len(rows)


def purge_expired(db: DbSession) -> int:
    """Housekeeping. Expired rows are already refused; this stops the table
    growing without bound."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    removed = (
        db.query(AuthSession)
        .filter(AuthSession.expires_at < cutoff)
        .delete(synchronize_session=False)
    )
    if removed:
        db.commit()
    return int(removed or 0)
