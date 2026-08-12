"""Service requests, rate limiting, and the shapes the frontend will rely on.

The response-shape tests look fussy and are not. Phase E is written against
these fields; a rename here that nobody notices becomes a blank confirmation
screen there, and the frontend has no way to tell a missing field from a null
one.
"""

from datetime import datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.models.appointment import Appointment
from app.models.provider import Provider, ProviderAvailability, ProviderService
from app.models.service import Service
from app.models.service_request import ServiceRequest
from app.services import rate_limit


@pytest.fixture(autouse=True)
def _clean_limits():
    """The limiter is process wide, so one test's failures would otherwise lock
    out the next one."""
    rate_limit.reset()
    yield
    rate_limit.reset()


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _add_functions(conn, _record):
        conn.create_function("UTC_TIMESTAMP", 0,
                             lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    yield session
    session.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


_ids = iter(range(2000, 9999))


def a_service(db, name="Leak found and fixed", price=95, minutes=90):
    service = Service(id=next(_ids), name=name, description=f"{name}, leak, drip",
                      price=price, duration_minutes=minutes, status=True,
                      store_id=0, stock=999999)
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def a_provider(db, name="Riverside", status="active", opens=8, closes=17):
    provider = Provider(business_name=name,
                        email=f"{name.lower().replace(' ', '')}@example.test",
                        phone="01234 567890", website="https://example.test",
                        status=status)
    db.add(provider)
    db.commit()
    db.refresh(provider)
    for weekday in range(5):
        db.add(ProviderAvailability(provider_id=provider.id, weekday=weekday,
                                    opens_at=time(opens, 0), closes_at=time(closes, 0)))
    db.commit()
    return provider


def offers(db, provider, service, price=None, minutes=None):
    row = ProviderService(provider_id=provider.id, service_id=service.id,
                          price=price, duration_minutes=minutes, active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def customer(client, email="req@example.com"):
    res = client.post("/api/v1/auth/register/customer", json={
        "name": "Requester", "email": email, "password": "a-long-enough-password",
        "phone": "07700900000", "address": "1 Test Street"})
    return {"Authorization": f"Bearer {res.json()['token']}"}


def first_slot(db, provider, service, minutes=90):
    from app.services.calendly.local_provider import LocalCalendar
    return LocalCalendar(db, provider.id).free_slots(service.id, minutes, days_ahead=7)[0]


# ── the customer's problem, as its own record ────────────────────────────────

def test_a_request_keeps_the_customer_s_own_words(client, db):
    a_service(db)
    headers = customer(client)

    res = client.post("/api/v1/requests", headers=headers, json={
        "description": "There is a water leak underneath my kitchen sink.",
        "urgency": "urgent"})

    assert res.status_code == 201
    stored = db.query(ServiceRequest).one()
    assert stored.description == "There is a water leak underneath my kitchen sink."
    assert stored.urgency == "urgent"


def test_a_request_that_matched_nothing_stays_open(client, db):
    """These are the ones worth keeping: they show what nobody offers."""
    headers = customer(client)

    res = client.post("/api/v1/requests", headers=headers, json={
        "description": "I need somebody to move a piano"})

    assert res.json()["status"] == "open"
    assert res.json()["service_id"] is None


def test_a_matched_request_says_so(client, db):
    service = a_service(db)
    headers = customer(client)

    res = client.post("/api/v1/requests", headers=headers, json={
        "description": "Leak under the sink", "service_id": service.id})

    assert res.json()["status"] == "matched"
    assert res.json()["service_name"] == service.name


def test_a_request_needs_an_account(client, db):
    res = client.post("/api/v1/requests", json={"description": "Anything"})

    assert res.status_code == 401


def test_a_customer_sees_only_their_own_requests(client, db):
    mine = customer(client, "mine@example.com")
    client.post("/api/v1/requests", headers=mine, json={"description": "Mine"})
    theirs = customer(client, "theirs@example.com")

    assert len(client.get("/api/v1/requests", headers=mine).json()) == 1
    assert client.get("/api/v1/requests", headers=theirs).json() == []


def test_another_customer_s_request_is_not_reachable_by_id(client, db):
    mine = customer(client, "mine@example.com")
    made = client.post("/api/v1/requests", headers=mine,
                       json={"description": "Mine"}).json()
    theirs = customer(client, "theirs@example.com")

    res = client.get(f"/api/v1/requests/{made['id']}", headers=theirs)

    assert res.status_code == 404


def test_booking_marks_the_request_booked_and_links_the_job(client, db):
    service = a_service(db)
    provider = a_provider(db)
    offers(db, provider, service, price=95, minutes=90)
    headers = customer(client)
    made = client.post("/api/v1/requests", headers=headers, json={
        "description": "Leak under the sink", "service_id": service.id}).json()
    slot = first_slot(db, provider, service)

    booked = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat(),
        "service_request_id": made["id"]}).json()

    stored = db.query(ServiceRequest).one()
    assert stored.status == "booked"
    assert stored.job_id == booked["job_id"]
    assert stored.provider_id == provider.id


def test_another_customer_s_request_cannot_be_attached_to_my_booking(client, db):
    service = a_service(db)
    provider = a_provider(db)
    offers(db, provider, service)
    theirs = customer(client, "theirs@example.com")
    not_mine = client.post("/api/v1/requests", headers=theirs,
                           json={"description": "Theirs"}).json()

    mine = customer(client, "mine@example.com")
    slot = first_slot(db, provider, service)
    res = client.post("/api/v1/booking/book", headers=mine, json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat(),
        "service_request_id": not_mine["id"]})

    assert res.status_code == 404


# ── what the confirmation screen will read ───────────────────────────────────

def test_the_booking_response_carries_everything_a_confirmation_needs(client, db):
    service = a_service(db)
    provider = a_provider(db)
    offers(db, provider, service, price=95, minutes=90)
    headers = customer(client)
    slot = first_slot(db, provider, service)

    body = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat(), "notes": "Back door"}).json()

    for field in ("job_id", "appointment_id", "reference", "provider_id",
                  "provider_name", "provider_phone", "service_id", "service_name",
                  "starts_at", "ends_at", "duration_minutes", "label", "price",
                  "currency", "payment_status", "customer_id", "customer_name",
                  "customer_email", "status"):
        assert field in body, f"the confirmation screen needs {field}"
    assert body["reference"].startswith("BK-")
    # "cod" for a booking settled on the day, "unpaid" for one on its way to a
    # payment page. Never "paid": only a provider's webhook may say that, and no
    # money has moved at this point either way.
    assert body["payment_status"] in ("cod", "unpaid"), "never claim money has been taken"
    assert body["payment_method"] in ("cod", "stripe", "paypal")


def test_the_response_reports_the_provider_s_terms_not_the_service_s(client, db):
    service = a_service(db, price=95, minutes=90)
    provider = a_provider(db)
    offers(db, provider, service, price=150, minutes=45)
    headers = customer(client)
    slot = first_slot(db, provider, service, minutes=45)

    body = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat()}).json()

    assert body["price"] == 150
    assert body["duration_minutes"] == 45
    minutes = (datetime.fromisoformat(body["ends_at"])
               - datetime.fromisoformat(body["starts_at"])).total_seconds() / 60
    assert minutes == 45, "the appointment has to be as long as it says it is"


def test_my_bookings_can_be_filtered(client, db):
    service = a_service(db)
    provider = a_provider(db)
    offers(db, provider, service)
    headers = customer(client)
    slot = first_slot(db, provider, service)
    booked = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat()}).json()

    upcoming = client.get("/api/v1/booking/mine?when=upcoming", headers=headers).json()
    assert len(upcoming) == 1

    client.post(f"/api/v1/booking/{booked['appointment_id']}/cancel", headers=headers)
    assert client.get("/api/v1/booking/mine?when=cancelled",
                      headers=headers).json()[0]["status"] == "cancelled"
    assert client.get("/api/v1/booking/mine?when=upcoming", headers=headers).json() == []


def test_a_legacy_appointment_with_no_provider_still_appears(client, db):
    """The one taken before providers existed. It must not disappear or crash a
    list because its provider is null."""
    from app.models.job import Job

    headers = customer(client)
    account_customer = db.query(ServiceRequest).first()  # noqa: F841
    from app.models.customer import Customer
    me = db.query(Customer).one()

    job = Job(customer_id=me.id, status="scheduled", total_amount=95,
              items_json=[{"item_id": 1, "name": "Old booking"}])
    db.add(job)
    db.commit()
    db.add(Appointment(job_id=job.id, provider_id=None,
                       starts_at=datetime.utcnow() + timedelta(days=2),
                       ends_at=datetime.utcnow() + timedelta(days=2, hours=1),
                       status="booked"))
    db.commit()

    listed = client.get("/api/v1/booking/mine", headers=headers).json()

    assert len(listed) == 1
    assert listed[0]["provider_name"] is None


# ── cancellation ─────────────────────────────────────────────────────────────

def test_cancelling_twice_is_safe(client, db):
    service = a_service(db)
    provider = a_provider(db)
    offers(db, provider, service)
    headers = customer(client)
    slot = first_slot(db, provider, service)
    booked = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat()}).json()

    first = client.post(f"/api/v1/booking/{booked['appointment_id']}/cancel",
                        headers=headers)
    second = client.post(f"/api/v1/booking/{booked['appointment_id']}/cancel",
                         headers=headers)

    assert first.status_code == second.status_code == 200
    assert second.json()["status"] == "cancelled"


def test_cancelling_keeps_the_history(client, db):
    """A cancelled visit still happened as a decision. Deleting the row would
    lose the fact that somebody booked and changed their mind."""
    from app.models.job import Job

    service = a_service(db)
    provider = a_provider(db)
    offers(db, provider, service)
    headers = customer(client)
    slot = first_slot(db, provider, service)
    booked = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat()}).json()

    client.post(f"/api/v1/booking/{booked['appointment_id']}/cancel", headers=headers)

    assert db.query(Appointment).filter(
        Appointment.id == booked["appointment_id"]).one().status == "cancelled"
    assert db.query(Job).filter(Job.id == booked["job_id"]).one().status == "cancelled"


# ── clear errors on impossible combinations ──────────────────────────────────

def test_an_unknown_provider_or_service_says_which(client, db):
    service = a_service(db)
    provider = a_provider(db)
    offers(db, provider, service)
    headers = customer(client)
    when = (datetime.utcnow() + timedelta(days=1, hours=9)).isoformat()

    no_provider = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": 9999, "service_id": service.id, "starts_at": when})
    no_service = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": provider.id, "service_id": 9999, "starts_at": when})

    assert no_provider.status_code == 404
    assert "provider" in no_provider.json()["detail"].lower()
    assert no_service.status_code == 404
    assert "service" in no_service.json()["detail"].lower()


def test_availability_for_a_service_a_provider_does_not_offer_is_a_clear_404(client, db):
    service = a_service(db)
    other = a_service(db, name="Something else")
    provider = a_provider(db)
    offers(db, provider, other)

    res = client.get(f"/api/v1/providers/{provider.id}/availability?service_id={service.id}")

    assert res.status_code == 404
    assert "does not offer" in res.json()["detail"]


def test_a_pending_provider_is_not_visible_publicly(client, db):
    """Same answer as missing, so the endpoint cannot be used to enumerate
    applications."""
    waiting = a_provider(db, "Waiting", status="pending")

    assert client.get(f"/api/v1/providers/{waiting.id}").status_code == 404


# ── rate limiting ────────────────────────────────────────────────────────────

def test_repeated_wrong_passwords_are_eventually_refused(client, db):
    customer(client, "target@example.com")

    codes = [client.post("/api/v1/auth/login", json={
        "email": "target@example.com", "password": "wrong"}).status_code
        for _ in range(rate_limit.MAX_PER_EMAIL + 2)]

    assert 401 in codes
    assert codes[-1] == 429, "guessing has to stop being free at some point"


def test_the_lockout_says_how_long_to_wait(client, db):
    customer(client, "target@example.com")
    for _ in range(rate_limit.MAX_PER_EMAIL + 1):
        res = client.post("/api/v1/auth/login", json={
            "email": "target@example.com", "password": "wrong"})

    assert res.status_code == 429
    assert int(res.headers["Retry-After"]) > 0


def test_a_success_forgets_earlier_failures(client, db):
    """One mistyped password before the right one should not count towards a
    lockout an hour later."""
    customer(client, "target@example.com")
    for _ in range(rate_limit.MAX_PER_EMAIL - 1):
        client.post("/api/v1/auth/login", json={
            "email": "target@example.com", "password": "wrong"})

    good = client.post("/api/v1/auth/login", json={
        "email": "target@example.com", "password": "a-long-enough-password"})
    after = client.post("/api/v1/auth/login", json={
        "email": "target@example.com", "password": "wrong"})

    assert good.status_code == 200
    assert after.status_code == 401, "the counter should have been cleared"


def test_one_account_being_attacked_does_not_lock_out_another(client, db):
    customer(client, "victim@example.com")
    customer(client, "bystander@example.com")
    for _ in range(rate_limit.MAX_PER_EMAIL + 1):
        client.post("/api/v1/auth/login", json={
            "email": "victim@example.com", "password": "wrong"})

    other = client.post("/api/v1/auth/login", json={
        "email": "bystander@example.com", "password": "a-long-enough-password"})

    assert other.status_code == 200


def test_an_unknown_email_is_rate_limited_too(client, db):
    """Otherwise the limiter itself tells an attacker which emails exist."""
    codes = [client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com", "password": "wrong"}).status_code
        for _ in range(rate_limit.MAX_PER_EMAIL + 2)]

    assert codes[-1] == 429


# ── provider registration with services ──────────────────────────────────────

def test_registering_a_provider_can_list_what_they_offer(client, db):
    service = a_service(db)

    res = client.post("/api/v1/auth/register/provider", json={
        "business_name": "New Firm", "email": "new@firm.example",
        "password": "a-long-enough-password",
        "services": [{"service_id": service.id, "price": 110, "duration_minutes": 60}],
    })

    assert res.status_code == 201
    provider_id = res.json()["provider_id"]
    offering = db.query(ProviderService).filter(
        ProviderService.provider_id == provider_id).one()
    assert float(offering.price) == 110
    assert offering.duration_minutes == 60


def test_an_unknown_service_at_registration_is_skipped_not_fatal(client, db):
    """Losing a whole application over one bad row would be worse than the
    business adding that service afterwards."""
    service = a_service(db)

    res = client.post("/api/v1/auth/register/provider", json={
        "business_name": "New Firm", "email": "new@firm.example",
        "password": "a-long-enough-password",
        "services": [{"service_id": service.id}, {"service_id": 999999}],
    })

    assert res.status_code == 201
    assert db.query(ProviderService).count() == 1


def test_a_new_provider_starts_pending_and_is_not_discoverable(client, db):
    from app.services import discovery

    service = a_service(db)
    res = client.post("/api/v1/auth/register/provider", json={
        "business_name": "New Firm", "email": "new@firm.example",
        "password": "a-long-enough-password",
        "services": [{"service_id": service.id, "price": 50}]})

    assert res.json()["provider_status"] == "pending"
    assert discovery.offerings_for_service(db, service) == []
