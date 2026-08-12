"""Registering, signing in, and who is allowed to see what.

The tests that matter most are the last two groups. A booking platform holds
somebody's home address and when they will be out, so a customer reaching
another customer's record is not a bug to be tidied up later.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import require_customer, require_provider
from app.core.config import settings
from app.db.database import Base, get_db
from app.main import app
from app.models.account import Account, Session as AuthSession
from app.models.customer import Customer
from app.models.provider import Provider
from app.services import auth


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    yield session
    session.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def register(client, email="someone@example.com", password="a-long-enough-password"):
    return client.post("/api/v1/auth/register/customer", json={
        "name": "Someone", "email": email, "password": password,
        "phone": "07700900000", "address": "1 Test Street",
    })


def register_provider(client, email="firm@example.com", password="a-long-enough-password"):
    return client.post("/api/v1/auth/register/provider", json={
        "business_name": "Test Services", "email": email, "password": password,
    })


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── passwords ────────────────────────────────────────────────────────────────

def test_a_password_is_never_stored_as_written():
    stored = auth.hash_password("hunter2-and-then-some")

    assert "hunter2" not in stored
    assert stored.startswith("pbkdf2_sha256$")
    assert auth.verify_password("hunter2-and-then-some", stored)
    assert not auth.verify_password("something else", stored)


def test_the_same_password_hashes_differently_each_time():
    """A shared salt would let one cracked hash reveal every account using that
    password."""
    a = auth.hash_password("the same password")
    b = auth.hash_password("the same password")

    assert a != b
    assert auth.verify_password("the same password", a)
    assert auth.verify_password("the same password", b)


def test_a_cheaper_old_hash_still_verifies_and_is_flagged():
    """The cost is recorded with the hash so it can be raised later without
    locking everybody out."""
    import hashlib
    import secrets

    salt = secrets.token_hex(16)
    weak = hashlib.pbkdf2_hmac("sha256", b"old password", salt.encode(), 1000).hex()
    stored = f"pbkdf2_sha256$1000${salt}${weak}"

    assert auth.verify_password("old password", stored)
    assert auth.needs_rehash(stored)
    assert not auth.needs_rehash(auth.hash_password("new password"))


def test_a_malformed_hash_is_refused_rather_than_crashing(db):
    for rubbish in ("", "not-a-hash", "pbkdf2_sha256$abc$x$y", "md5$1$a$b"):
        assert not auth.verify_password("anything", rubbish)


# ── registration ─────────────────────────────────────────────────────────────

def test_registering_creates_an_account_and_a_customer(client, db):
    res = register(client)

    assert res.status_code == 201
    body = res.json()
    assert body["role"] == "customer"
    assert body["token"]
    assert db.query(Customer).count() == 1
    assert db.query(Account).count() == 1


def test_registering_reuses_a_customer_who_already_booked(client, db):
    """Bookings can be taken without an account. Somebody who booked last week
    and registers today is the same person, and must keep their history rather
    than becoming a second row with the same email."""
    existing = Customer(name="Booked Already", email="repeat@example.com",
                        phone="07700900111", address="9 Old Road", type="customer")
    db.add(existing)
    db.commit()
    existing_id = existing.id

    res = register(client, email="repeat@example.com")

    assert res.status_code == 201
    assert res.json()["customer_id"] == existing_id
    assert db.query(Customer).count() == 1, "a duplicate customer would split their history"


def test_registering_does_not_overwrite_details_given_at_booking(client, db):
    """The address given when booking is likelier to be where work happened."""
    db.add(Customer(name="Booked Already", email="repeat@example.com",
                    phone="07700900111", address="9 Old Road", type="customer"))
    db.commit()

    register(client, email="repeat@example.com")

    customer = db.query(Customer).filter(Customer.email == "repeat@example.com").one()
    assert customer.address == "9 Old Road"
    assert customer.phone == "07700900111"


def test_the_same_email_cannot_register_twice(client):
    register(client)
    again = register(client)

    assert again.status_code == 409


def test_a_short_password_is_refused(client):
    res = client.post("/api/v1/auth/register/customer", json={
        "name": "Someone", "email": "short@example.com", "password": "abc",
    })

    assert res.status_code == 422


def test_a_provider_applies_and_starts_pending(client, db):
    """Anybody may apply; the office decides who customers can book."""
    res = register_provider(client)

    assert res.status_code == 201
    body = res.json()
    assert body["role"] == "provider"
    assert body["provider_status"] == "pending"
    assert db.query(Provider).one().status == "pending"


# ── signing in ───────────────────────────────────────────────────────────────

def test_signing_in_returns_a_working_token(client):
    register(client)

    res = client.post("/api/v1/auth/login", json={
        "email": "someone@example.com", "password": "a-long-enough-password",
    })

    assert res.status_code == 200
    token = res.json()["token"]
    me = client.get("/api/v1/auth/me", headers=bearer(token))
    assert me.status_code == 200
    assert me.json()["email"] == "someone@example.com"


def test_a_wrong_password_and_an_unknown_email_look_the_same(client):
    """Different wording would tell somebody which emails have accounts."""
    register(client)

    wrong = client.post("/api/v1/auth/login", json={
        "email": "someone@example.com", "password": "not the password"})
    unknown = client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com", "password": "not the password"})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_a_login_upgrades_a_hash_written_when_the_cost_was_lower(client, db):
    import hashlib
    import secrets

    register(client)
    account = db.query(Account).one()
    salt = secrets.token_hex(16)
    weak = hashlib.pbkdf2_hmac("sha256", b"a-long-enough-password", salt.encode(), 1000).hex()
    account.password_hash = f"pbkdf2_sha256$1000${salt}${weak}"
    db.commit()

    res = client.post("/api/v1/auth/login", json={
        "email": "someone@example.com", "password": "a-long-enough-password"})

    assert res.status_code == 200
    db.refresh(account)
    assert not auth.needs_rehash(account.password_hash)


# ── sessions ─────────────────────────────────────────────────────────────────

def test_the_token_is_never_stored(client, db):
    """A leaked database must not hand over live logins."""
    token = register(client).json()["token"]

    stored = [s.token_hash for s in db.query(AuthSession).all()]
    assert token not in stored
    assert all(len(h) == 64 for h in stored)


def test_signing_out_stops_the_token_working(client):
    token = register(client).json()["token"]
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 200

    client.post("/api/v1/auth/logout", headers=bearer(token))

    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401


def test_signing_out_twice_is_not_an_error(client):
    """Saying so would tell a caller whether a token was live."""
    token = register(client).json()["token"]

    first = client.post("/api/v1/auth/logout", headers=bearer(token))
    second = client.post("/api/v1/auth/logout", headers=bearer(token))

    assert first.status_code == second.status_code == 200


def test_an_expired_session_is_refused(client, db):
    token = register(client).json()["token"]
    row = db.query(AuthSession).one()
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401


def test_revoking_everything_signs_out_every_device(client, db):
    register(client)
    a = client.post("/api/v1/auth/login", json={
        "email": "someone@example.com", "password": "a-long-enough-password"}).json()["token"]
    b = client.post("/api/v1/auth/login", json={
        "email": "someone@example.com", "password": "a-long-enough-password"}).json()["token"]

    auth.revoke_all(db, db.query(Account).one())

    assert client.get("/api/v1/auth/me", headers=bearer(a)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=bearer(b)).status_code == 401


def test_no_token_and_a_made_up_token_are_both_refused(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me",
                      headers=bearer("not-a-real-token")).status_code == 401
    assert client.get("/api/v1/auth/me",
                      headers={"Authorization": "Basic abc"}).status_code == 401


# ── who may touch what ───────────────────────────────────────────────────────

def test_a_customer_cannot_use_a_provider_guard(client, db):
    """The guard, directly. A customer reaching provider tools is the failure
    this exists to prevent."""
    from fastapi import HTTPException

    register(client)
    account = db.query(Account).one()

    with pytest.raises(HTTPException) as raised:
        require_provider(account=account, db=db)
    assert raised.value.status_code == 403


def test_a_provider_cannot_use_a_customer_guard(client, db):
    from fastapi import HTTPException

    register_provider(client)
    account = db.query(Account).one()

    with pytest.raises(HTTPException) as raised:
        require_customer(account=account, db=db)
    assert raised.value.status_code == 403


def test_a_guard_returns_the_signed_in_record_not_a_requested_one(client, db):
    """`require_customer` hands back the caller's own customer, so an endpoint
    holding it cannot be talked into reading somebody else's by id."""
    register(client)
    account = db.query(Account).one()

    customer = require_customer(account=account, db=db)

    assert customer.id == account.customer_id


def test_one_customer_cannot_reach_another(client, db):
    from fastapi import HTTPException

    from app.api.deps import owns_customer

    register(client)
    mine = db.query(Customer).one()

    owns_customer(mine, mine.id)                       # my own is fine
    with pytest.raises(HTTPException) as raised:
        owns_customer(mine, mine.id + 999)
    assert raised.value.status_code == 403


def test_a_pending_provider_cannot_be_treated_as_active(client, db):
    """Filling in your profile while you wait is fine. Being bookable is not."""
    from fastapi import HTTPException

    from app.api.deps import require_active_provider

    register_provider(client)
    provider = db.query(Provider).one()

    with pytest.raises(HTTPException) as raised:
        require_active_provider(provider=provider)
    assert raised.value.status_code == 403

    provider.status = "active"
    assert require_active_provider(provider=provider) is provider


def test_admin_still_works_by_header_and_refuses_a_customer_token(client, db, monkeypatch):
    """The admin screens have always used a shared header. That must keep
    working, and a signed-in customer must not inherit admin."""
    monkeypatch.setattr(settings, "ADMIN_TOKEN", "the-admin-token")
    token = register(client).json()["token"]

    ok = client.get("/api/v1/admin/summary", headers={"X-Admin-Token": "the-admin-token"})
    assert ok.status_code == 200

    as_customer = client.get("/api/v1/admin/summary", headers=bearer(token))
    assert as_customer.status_code == 401
