"""Provider diaries, provider terms, and who is allowed to book what.

The rule underneath most of these: availability is a question about a
particular business. Two firms in the same trade keep different hours, take
different lengths of time over the same job, and are busy at different moments,
so anything scoped globally is wrong even when it happens to look right.
"""

from datetime import datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.database import Base, get_db
from app.main import app
from app.models.appointment import Appointment
from app.models.provider import (Provider, ProviderAvailability, ProviderService,
                                 ProviderTimeOff)
from app.models.service import Service
from app.services import booking_service, discovery
from app.services.calendly.local_provider import LocalCalendar


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )

    # The diary uses UTC_TIMESTAMP(), which MySQL has and SQLite does not.
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


# ── building a small marketplace ─────────────────────────────────────────────

#: `services.id` is a BigInteger primary key with no autoincrement, because in
#: production the ids come from the client's own catalogue rather than from us.
#: MySQL fills it from AUTO_INCREMENT on the real table; SQLite will not, so the
#: tests supply their own.
_next_service_id = iter(range(1000, 9999))


def a_service(db, name="Blocked drain cleared", price=89, minutes=60):
    service = Service(id=next(_next_service_id),
                      name=name, description=f"{name}, blockage, slow drain",
                      price=price, duration_minutes=minutes, status=True,
                      store_id=0, stock=999999)
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def a_provider(db, name="Riverside Plumbing", email=None, status="active",
               opens=8, closes=17, days=(0, 1, 2, 3, 4)):
    provider = Provider(business_name=name,
                        email=email or f"{name.lower().replace(' ', '')}@example.test",
                        status=status)
    db.add(provider)
    db.commit()
    db.refresh(provider)
    for weekday in days:
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


def sign_in_customer(client, email="booker@example.com"):
    res = client.post("/api/v1/auth/register/customer", json={
        "name": "Booker", "email": email, "password": "a-long-enough-password",
        "phone": "07700900000", "address": "1 Test Street",
    })
    return {"Authorization": f"Bearer {res.json()['token']}"}


def sign_in_provider(client, email="firm@example.com"):
    res = client.post("/api/v1/auth/register/provider", json={
        "business_name": "Signed In Firm", "email": email,
        "password": "a-long-enough-password",
    })
    return {"Authorization": f"Bearer {res.json()['token']}"}, res.json()["provider_id"]


# ── a provider's own diary ───────────────────────────────────────────────────

def test_availability_comes_from_that_provider_s_hours(db):
    service = a_service(db)
    early = a_provider(db, "Early Start", opens=7, closes=18)
    short = a_provider(db, "Short Day", opens=10, closes=13)
    offers(db, early, service)
    offers(db, short, service)

    early_slots = LocalCalendar(db, early.id).free_slots(service.id, 60, days_ahead=7)
    short_slots = LocalCalendar(db, short.id).free_slots(service.id, 60, days_ahead=7)

    assert len(early_slots) > len(short_slots), "a longer working day means more slots"
    assert all(7 <= s.starts_at.hour < 18 for s in early_slots)
    assert all(10 <= s.starts_at.hour < 13 for s in short_slots)


def test_a_day_with_no_hours_is_closed(db):
    """Absence of a row means closed, which is why weekends usually have none."""
    service = a_service(db)
    weekdays_only = a_provider(db, "Weekdays Only", days=(0, 1, 2, 3, 4))
    offers(db, weekdays_only, service)

    slots = LocalCalendar(db, weekdays_only.id).free_slots(service.id, 60, days_ahead=14)

    assert slots
    assert not any(s.starts_at.weekday() >= 5 for s in slots)


def test_a_longer_job_gets_fewer_starts_and_finishes_before_closing(db):
    """A two hour visit cannot start at half past four in a day ending at five."""
    service = a_service(db)
    provider = a_provider(db, "Fixed Hours", opens=9, closes=17)
    offers(db, provider, service)

    hour = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)
    two_hours = LocalCalendar(db, provider.id).free_slots(service.id, 120, days_ahead=7)

    assert len(two_hours) < len(hour)
    assert all(s.ends_at.hour <= 17 for s in two_hours)


def test_an_existing_appointment_blocks_that_time_for_that_provider_only(db):
    """The bug this guards against: one firm's busy Tuesday hiding another
    firm's free one."""
    service = a_service(db)
    busy = a_provider(db, "Busy Firm")
    free = a_provider(db, "Free Firm")
    offers(db, busy, service)
    offers(db, free, service)

    taken = LocalCalendar(db, busy.id).free_slots(service.id, 60, days_ahead=7)[0]
    db.add(Appointment(job_id=1, provider_id=busy.id, starts_at=taken.starts_at,
                       ends_at=taken.ends_at, status="booked"))
    db.commit()

    busy_now = LocalCalendar(db, busy.id).free_slots(service.id, 60, days_ahead=7)
    free_now = LocalCalendar(db, free.id).free_slots(service.id, 60, days_ahead=7)

    assert taken.starts_at not in [s.starts_at for s in busy_now]
    assert taken.starts_at in [s.starts_at for s in free_now], \
        "another provider's diary must be untouched"


def test_time_off_is_subtracted_like_an_appointment(db):
    from app.models.provider import ProviderTimeOff

    service = a_service(db)
    provider = a_provider(db, "Away Next Week")
    offers(db, provider, service)

    first = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)[0]
    db.add(ProviderTimeOff(provider_id=provider.id,
                           starts_at=first.starts_at - timedelta(hours=1),
                           ends_at=first.starts_at + timedelta(hours=4),
                           reason="Training"))
    db.commit()

    after = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)

    assert first.starts_at not in [s.starts_at for s in after]


def test_a_live_hold_blocks_a_slot_and_an_expired_one_does_not(db):
    service = a_service(db)
    provider = a_provider(db, "Holding Firm")
    offers(db, provider, service)
    slot = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)[0]

    held = Appointment(job_id=1, provider_id=provider.id, starts_at=slot.starts_at,
                       ends_at=slot.ends_at, status="held",
                       hold_expires_at=datetime.utcnow() + timedelta(minutes=10))
    db.add(held)
    db.commit()
    during = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)

    held.hold_expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    after = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)

    assert slot.starts_at not in [s.starts_at for s in during]
    assert slot.starts_at in [s.starts_at for s in after], \
        "an abandoned conversation has to give its hour back"


def test_an_expired_hold_is_released(db):
    service = a_service(db)
    provider = a_provider(db, "Sweeping Firm")
    offers(db, provider, service)
    db.add(Appointment(job_id=1, provider_id=provider.id,
                       starts_at=datetime.utcnow() + timedelta(days=1),
                       ends_at=datetime.utcnow() + timedelta(days=1, hours=1),
                       status="held",
                       hold_expires_at=datetime.utcnow() - timedelta(minutes=1)))
    db.commit()

    released = booking_service.release_expired(db)

    assert released == 1
    assert db.query(Appointment).one().status == "cancelled"


# ── the provider's terms, not the service's ──────────────────────────────────

def test_two_providers_offer_the_same_service_on_their_own_terms(db):
    service = a_service(db, price=89, minutes=60)
    cheap = a_provider(db, "Cheap And Quick")
    dear = a_provider(db, "Dear And Thorough")
    offers(db, cheap, service, price=89, minutes=60)
    offers(db, dear, service, price=120, minutes=90)

    found = discovery.offerings_for_service(db, service)

    by_name = {o.provider.business_name: o for o in found}
    assert by_name["Cheap And Quick"].price == 89
    assert by_name["Cheap And Quick"].duration_minutes == 60
    assert by_name["Dear And Thorough"].price == 120
    assert by_name["Dear And Thorough"].duration_minutes == 90


def test_the_service_price_is_only_a_fallback(db):
    """The service row carries a guide figure for matching. It must never
    override what a business actually charges."""
    service = a_service(db, price=89, minutes=60)
    provider = a_provider(db, "Sets Own Terms")
    offers(db, provider, service, price=150, minutes=45)

    offering = discovery.offerings_for_service(db, service)[0]

    assert offering.price == 150
    assert offering.duration_minutes == 45


def test_a_provider_with_no_price_falls_back_to_the_guide(db):
    service = a_service(db, price=89, minutes=60)
    provider = a_provider(db, "Uses Defaults")
    offers(db, provider, service, price=None, minutes=None)

    offering = discovery.offerings_for_service(db, service)[0]

    assert offering.price == 89
    assert offering.duration_minutes == 60


# ── ranking ──────────────────────────────────────────────────────────────────

def test_ranking_puts_the_soonest_first_then_the_cheapest(db, monkeypatch):
    monkeypatch.setattr(settings, "PROVIDER_RANKING", "soonest")
    service = a_service(db)
    later = a_provider(db, "Opens Later", opens=8, closes=17)
    sooner_dear = a_provider(db, "Sooner Dear", opens=8, closes=17)
    sooner_cheap = a_provider(db, "Sooner Cheap", opens=8, closes=17)

    # "Later" used to mean opening at 14:00 against the others' 8:00, and that
    # made the test depend on the hour it was run at: after two in the afternoon
    # all three have the same next free slot, the tie falls to price, and this
    # provider is the cheapest, so it came first and the assertion failed. It
    # passed every morning. Two days blocked out makes "later" true at any hour.
    db.add(ProviderTimeOff(
        provider_id=later.id,
        starts_at=datetime.utcnow() - timedelta(hours=1),
        ends_at=datetime.utcnow() + timedelta(days=2),
        reason="Away, so genuinely cannot come sooner",
    ))
    db.commit()

    offers(db, later, service, price=10)
    offers(db, sooner_dear, service, price=200)
    offers(db, sooner_cheap, service, price=50)

    order = [o.provider.business_name
             for o in discovery.offerings_for_service(db, service)]

    assert order.index("Sooner Cheap") < order.index("Sooner Dear"), \
        "same time, so the cheaper one comes first"
    assert order[-1] == "Opens Later", "cheapest, but cannot come until later"


def test_ranking_by_price_can_be_selected(db, monkeypatch):
    monkeypatch.setattr(settings, "PROVIDER_RANKING", "price")
    service = a_service(db)
    dear = a_provider(db, "Dear", opens=8, closes=17)
    cheap = a_provider(db, "Cheap", opens=14, closes=17)
    offers(db, dear, service, price=200)
    offers(db, cheap, service, price=50)

    order = [o.provider.business_name
             for o in discovery.offerings_for_service(db, service)]

    assert order[0] == "Cheap"


def test_an_unimplemented_ranking_falls_back_rather_than_ordering_by_nothing(db, monkeypatch):
    monkeypatch.setattr(settings, "PROVIDER_RANKING", "distance")
    service = a_service(db)
    provider = a_provider(db, "Only One")
    offers(db, provider, service)

    found = discovery.offerings_for_service(db, service)

    assert [o.provider.business_name for o in found] == ["Only One"]


def test_a_pending_provider_is_not_offered_to_customers(db):
    service = a_service(db)
    approved = a_provider(db, "Approved", status="active")
    waiting = a_provider(db, "Waiting", status="pending")
    offers(db, approved, service)
    offers(db, waiting, service)

    names = [o.provider.business_name
             for o in discovery.offerings_for_service(db, service)]

    assert names == ["Approved"]


# ── booking ──────────────────────────────────────────────────────────────────

def test_booking_requires_signing_in(client, db):
    service = a_service(db)
    provider = a_provider(db)
    offers(db, provider, service)

    res = client.post("/api/v1/booking/book", json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
    })

    assert res.status_code == 401


def test_a_booking_records_customer_provider_service_and_appointment(client, db):
    service = a_service(db)
    provider = a_provider(db)
    offering = offers(db, provider, service, price=99, minutes=60)
    headers = sign_in_customer(client)
    slot = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)[0]

    res = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat(), "notes": "Back door",
    })

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["provider_id"] == provider.id
    assert body["price"] == 99, "the provider's price, not the service's"
    from app.models.job import Job
    job = db.query(Job).order_by(Job.id.desc()).first()
    assert job.provider_id == provider.id
    assert job.provider_service_id == offering.id
    appointment = db.query(Appointment).order_by(Appointment.id.desc()).first()
    assert appointment.provider_id == provider.id
    assert appointment.status == "booked"


def test_the_same_provider_cannot_be_booked_twice_for_one_slot(client, db):
    service = a_service(db)
    provider = a_provider(db)
    offers(db, provider, service)
    headers = sign_in_customer(client)
    slot = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)[0]
    payload = {"provider_id": provider.id, "service_id": service.id,
               "starts_at": slot.starts_at.isoformat()}

    first = client.post("/api/v1/booking/book", headers=headers, json=payload)
    second = client.post("/api/v1/booking/book", headers=headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 409


def test_two_providers_can_be_booked_for_the_same_hour(client, db):
    """Not a clash. It is a marketplace working."""
    service = a_service(db)
    one = a_provider(db, "Firm One")
    two = a_provider(db, "Firm Two")
    offers(db, one, service)
    offers(db, two, service)
    headers = sign_in_customer(client)
    slot = LocalCalendar(db, one.id).free_slots(service.id, 60, days_ahead=7)[0]

    a = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": one.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat()})
    b = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": two.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat()})

    assert a.status_code == 200
    assert b.status_code == 200


def test_a_pending_provider_cannot_receive_a_booking(client, db):
    service = a_service(db)
    waiting = a_provider(db, "Waiting", status="pending")
    offers(db, waiting, service)
    headers = sign_in_customer(client)

    res = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": waiting.id, "service_id": service.id,
        "starts_at": (datetime.utcnow() + timedelta(days=1, hours=9)).isoformat(),
    })

    assert res.status_code == 409
    assert "not taking bookings" in res.json()["detail"]


def test_a_provider_who_does_not_offer_the_service_is_refused(client, db):
    service = a_service(db)
    other = a_service(db, name="Something Else")
    provider = a_provider(db)
    offers(db, provider, other)
    headers = sign_in_customer(client)

    res = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": (datetime.utcnow() + timedelta(days=1, hours=9)).isoformat(),
    })

    assert res.status_code == 409


def test_a_failed_booking_leaves_no_job_behind(client, db):
    """The half finished state the cart used to produce."""
    from app.models.job import Job

    service = a_service(db)
    waiting = a_provider(db, "Waiting", status="pending")
    offers(db, waiting, service)
    headers = sign_in_customer(client)
    before = db.query(Job).count()

    client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": waiting.id, "service_id": service.id,
        "starts_at": (datetime.utcnow() + timedelta(days=1, hours=9)).isoformat()})

    assert db.query(Job).count() == before


# ── who may see and change what ──────────────────────────────────────────────

def test_a_customer_sees_only_their_own_bookings(client, db):
    service = a_service(db)
    provider = a_provider(db)
    offers(db, provider, service)
    mine = sign_in_customer(client, "mine@example.com")
    slot = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)[0]
    client.post("/api/v1/booking/book", headers=mine, json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat()})

    theirs = sign_in_customer(client, "theirs@example.com")

    assert len(client.get("/api/v1/booking/mine", headers=mine).json()) == 1
    assert client.get("/api/v1/booking/mine", headers=theirs).json() == []


def test_a_customer_cannot_cancel_somebody_else_s_booking(client, db):
    service = a_service(db)
    provider = a_provider(db)
    offers(db, provider, service)
    mine = sign_in_customer(client, "mine@example.com")
    slot = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)[0]
    booked = client.post("/api/v1/booking/book", headers=mine, json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat()}).json()

    theirs = sign_in_customer(client, "theirs@example.com")
    res = client.post(f"/api/v1/booking/{booked['appointment_id']}/cancel",
                      headers=theirs)

    assert res.status_code == 404, "somebody else's booking should not even exist"


def test_cancelling_frees_the_slot_again(client, db):
    service = a_service(db)
    provider = a_provider(db)
    offers(db, provider, service)
    headers = sign_in_customer(client)
    slot = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)[0]
    booked = client.post("/api/v1/booking/book", headers=headers, json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat()}).json()

    client.post(f"/api/v1/booking/{booked['appointment_id']}/cancel", headers=headers)

    free_again = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)
    assert slot.starts_at in [s.starts_at for s in free_again]


def test_a_provider_manages_only_their_own_services(client, db):
    service = a_service(db)
    headers, provider_id = sign_in_provider(client, "mine@firm.example")
    somebody_else = a_provider(db, "Somebody Else")
    theirs = offers(db, somebody_else, service, price=10)

    res = client.delete(f"/api/v1/providers/me/services/{theirs.id}", headers=headers)

    assert res.status_code == 404, "another firm's row should not be reachable"
    db.refresh(theirs)
    assert theirs.active is True


def test_a_customer_cannot_use_the_provider_endpoints(client, db):
    headers = sign_in_customer(client)

    assert client.get("/api/v1/providers/me/profile", headers=headers).status_code == 403
    assert client.get("/api/v1/providers/me/appointments", headers=headers).status_code == 403


def test_a_provider_sees_only_their_own_appointments(client, db):
    service = a_service(db)
    headers, provider_id = sign_in_provider(client, "diary@firm.example")
    provider = db.query(Provider).filter(Provider.id == provider_id).one()
    provider.status = "active"
    db.add(ProviderAvailability(provider_id=provider.id, weekday=0,
                                opens_at=time(8, 0), closes_at=time(17, 0)))
    db.commit()

    other = a_provider(db, "Other Firm")
    db.add(Appointment(job_id=1, provider_id=other.id,
                       starts_at=datetime.utcnow() + timedelta(days=1),
                       ends_at=datetime.utcnow() + timedelta(days=1, hours=1),
                       status="booked"))
    db.commit()

    mine = client.get("/api/v1/providers/me/appointments", headers=headers)

    assert mine.status_code == 200
    assert mine.json() == [], "another firm's diary must not appear"


def test_a_provider_cannot_approve_themselves(client, db):
    """Otherwise the approval step is decorative."""
    headers, provider_id = sign_in_provider(client, "eager@firm.example")

    client.patch("/api/v1/providers/me/profile", headers=headers,
                 json={"business_name": "Renamed", "status": "active"})

    provider = db.query(Provider).filter(Provider.id == provider_id).one()
    assert provider.business_name == "Renamed"
    assert provider.status == "pending", "status is not a field they can set"


# ── route ordering ───────────────────────────────────────────────────────────

def test_a_provider_can_read_their_own_week(db, client):
    """`/me/availability` must not be swallowed by `/{provider_id}/availability`.

    FastAPI matches routes in declaration order, and for a while the
    parameterised one came first: it took "me" as the id, failed to parse it as
    an integer, and answered 422. Nothing crashed and no test noticed, because
    saving hours used a different verb and worked fine. The only symptom was a
    provider whose own hours page would not load.
    """
    headers, provider_id = sign_in_provider(client, "week@example.com")

    saved = client.put("/api/v1/providers/me/availability",
                       json={"weekday": 0, "opens_at": "09:00:00", "closes_at": "17:00:00"},
                       headers=headers)
    assert saved.status_code == 200

    mine = client.get("/api/v1/providers/me/availability", headers=headers)
    assert mine.status_code == 200, mine.json()
    assert isinstance(mine.json(), list), "a 422 body is a dict, and that was the bug"
    assert [row["weekday"] for row in mine.json()] == [0]


def test_the_by_id_availability_route_still_works(db, client):
    """The move must not have broken the customer-facing one."""
    service = a_service(db)
    provider = a_provider(db, "Still Reachable")
    offers(db, provider, service)

    res = client.get(f"/api/v1/providers/{provider.id}/availability?service_id={service.id}")
    assert res.status_code == 200
    assert res.json()["slots"]


# ── the emails a booking produces ────────────────────────────────────────────
#
# Nothing here talks to a relay. What is worth testing is that the booking asks
# for the emails at all (it did not, for the whole of Phase E), that a refusing
# relay cannot break a booking, and that the wording is right, because these go
# straight to customers.

def test_booking_schedules_both_emails(db, client, monkeypatch):
    """The fault this guards against: no email was ever attempted for a booking.

    The endpoint existed, the sender existed, and nothing joined them, so the
    confirmation screen said "we have emailed you the details" and nothing had.
    """
    from app.services import booking_notify

    sent = []
    monkeypatch.setattr(booking_notify, "send_booking_emails", lambda a: sent.append(a))
    # The endpoint imported it by name, so that is the reference to replace.
    import app.api.booking as booking_api
    monkeypatch.setattr(booking_api, "send_booking_emails", lambda a: sent.append(a))

    service = a_service(db)
    provider = a_provider(db, "Emails Firm")
    offers(db, provider, service, price=95)
    headers = sign_in_customer(client, "emails@example.com")

    slot = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)[0]
    res = client.post("/api/v1/booking/book", json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat(),
    }, headers=headers)

    assert res.status_code == 200, res.json()
    assert sent == [res.json()["appointment_id"]], "the booking did not ask for its emails"


def test_a_refusing_relay_cannot_break_a_booking(db, client, monkeypatch):
    """The booking is committed first, so a send that fails is a logged warning
    and nothing more. Anything else turns a booking that worked into an error."""
    from app.services import booking_emails, booking_notify

    def refuse(**kwargs):
        raise OSError("relay refused the connection")

    monkeypatch.setattr(booking_emails, "send_customer_confirmation", refuse)
    monkeypatch.setattr(booking_emails, "send_provider_notification", refuse)

    service = a_service(db)
    provider = a_provider(db, "Unreachable Relay")
    offers(db, provider, service, price=95)
    headers = sign_in_customer(client, "relay@example.com")

    slot = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)[0]
    res = client.post("/api/v1/booking/book", json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat(),
    }, headers=headers)
    assert res.status_code == 200

    # Called directly, exactly as the background task would.
    booking_notify.send_booking_emails(res.json()["appointment_id"])


def test_cancelling_tells_the_provider(db, client, monkeypatch):
    import app.api.booking as booking_api

    told = []
    monkeypatch.setattr(booking_api, "send_cancellation_email", lambda a: told.append(a))

    service = a_service(db)
    provider = a_provider(db, "Told On Cancel")
    offers(db, provider, service, price=95)
    headers = sign_in_customer(client, "cancels@example.com")

    slot = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)[0]
    booked = client.post("/api/v1/booking/book", json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat(),
    }, headers=headers).json()

    client.post(f"/api/v1/booking/{booked['appointment_id']}/cancel", headers=headers)
    assert told == [booked["appointment_id"]]


def test_the_customer_email_says_what_it_should(monkeypatch):
    from app.services import booking_emails

    captured = {}
    monkeypatch.setattr(booking_emails, "_send",
                        lambda to, subject, html: captured.update(
                            to=to, subject=subject, html=html))

    booking_emails.send_customer_confirmation(
        to="someone@example.com", customer_name="Alex Morgan", reference="BK-00042",
        service_name="Leak found and fixed", provider_name="Quickfix Drains",
        provider_phone="01234 111222",
        starts_at=datetime(2026, 8, 12, 17, 0), duration_minutes=90,
        price=110.0, currency="USD", address="14 Mill Lane", notes="Dog is friendly",
    )

    html = captured["html"]
    for expected in ["BK-00042", "Leak found and fixed", "Quickfix Drains",
                     "01234 111222", "5:00 PM", "1 hr 30 min", "$110.00",
                     "14 Mill Lane", "Dog is friendly"]:
        assert expected in html, f"the customer email does not mention {expected!r}"

    assert "BK-00042" in captured["subject"]
    # It must not claim money has changed hands.
    assert "paid" not in html.lower() or "Nothing has been charged" in html
    # And it must not have picked up the shop's vocabulary.
    for shop_word in ["cart", "delivery", "SmartMarket"]:
        assert shop_word.lower() not in html.lower(), f"{shop_word!r} leaked into a booking email"


def test_the_provider_email_leads_with_the_address(monkeypatch):
    from app.services import booking_emails

    captured = {}
    monkeypatch.setattr(booking_emails, "_send",
                        lambda to, subject, html: captured.update(html=html))

    booking_emails.send_provider_notification(
        to="firm@example.com", provider_name="Quickfix Drains", reference="BK-00042",
        service_name="Leak found and fixed", customer_name="Alex Morgan",
        customer_email="alex@example.com", customer_phone="07700 900000",
        starts_at=datetime(2026, 8, 12, 17, 0), duration_minutes=90,
        price=110.0, currency="USD", address="14 Mill Lane", notes="Park on the drive",
    )

    html = captured["html"]
    assert "14 Mill Lane" in html
    assert "07700 900000" in html, "the provider cannot ring somebody without a number"
    assert "Park on the drive" in html


def test_a_missing_address_is_called_out_rather_than_left_blank(monkeypatch):
    """A provider setting off to an unknown address is the worst outcome here."""
    from app.services import booking_emails

    captured = {}
    monkeypatch.setattr(booking_emails, "_send",
                        lambda to, subject, html: captured.update(html=html))

    booking_emails.send_provider_notification(
        to="firm@example.com", provider_name="Quickfix Drains", reference="BK-00043",
        service_name="Leak found and fixed", customer_name="Alex Morgan",
        customer_email=None, customer_phone=None,
        starts_at=datetime(2026, 8, 12, 17, 0), duration_minutes=60,
        price=95.0, currency="USD", address=None, notes=None,
    )

    assert "Ring the customer before you set off" in captured["html"]


def test_no_booking_email_uses_a_banned_dash():
    """The client reads them as machine written, and these are customer facing."""
    from app.services import booking_emails

    captured = []
    original = booking_emails._send
    booking_emails._send = lambda to, subject, html: captured.append(subject + html)
    try:
        when = datetime(2026, 8, 12, 17, 0)
        booking_emails.send_customer_confirmation(
            to="a@example.com", customer_name="A", reference="BK-1", service_name="S",
            provider_name="P", provider_phone="1", starts_at=when, duration_minutes=90,
            price=1.0, currency="USD", address="X", notes="Y")
        booking_emails.send_provider_notification(
            to="a@example.com", provider_name="P", reference="BK-1", service_name="S",
            customer_name="C", customer_email="c@example.com", customer_phone="1",
            starts_at=when, duration_minutes=90, price=1.0, currency="USD",
            address="X", notes="Y")
        booking_emails.send_cancellation(
            to="a@example.com", provider_name="P", reference="BK-1", service_name="S",
            customer_name="C", starts_at=when)
    finally:
        booking_emails._send = original

    for text in captured:
        assert "—" not in text, "em dash in a booking email"
        assert "–" not in text, "en dash in a booking email"


# ── paying for a booking ─────────────────────────────────────────────────────

def _book(client, db, headers, method="cod", price=95):
    service = a_service(db, name=f"Paid job {method}")
    provider = a_provider(db, f"Firm {method}", email=f"{method}@example.test")
    offers(db, provider, service, price=price)
    slot = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)[0]
    return client.post("/api/v1/booking/book", json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat(), "payment_method": method,
    }, headers=headers)


def test_cash_owes_nothing_online(db, client):
    res = _book(client, db, sign_in_customer(client, "cash@example.com"), "cod")
    assert res.status_code == 200
    body = res.json()
    assert body["payment_method"] == "cod"
    assert body["payment_status"] == "cod"
    assert body["payment_due"] is False, "cash must not send anybody to a payment page"


def test_choosing_a_card_leaves_the_booking_unpaid_and_due(db, client):
    """The slot is taken before the money, deliberately. Somebody who abandons a
    card page still has a provider coming rather than nothing."""
    res = _book(client, db, sign_in_customer(client, "card@example.com"), "stripe")
    assert res.status_code == 200
    body = res.json()
    assert body["payment_method"] == "stripe"
    assert body["payment_status"] == "unpaid"
    assert body["payment_due"] is True
    assert body["status"] == "booked", "the appointment stands whatever the payment does"


def test_a_made_up_payment_method_is_refused(db, client):
    service = a_service(db)
    provider = a_provider(db, "Whatever")
    offers(db, provider, service)
    headers = sign_in_customer(client, "madeup@example.com")
    slot = LocalCalendar(db, provider.id).free_slots(service.id, 60, days_ahead=7)[0]

    res = client.post("/api/v1/booking/book", json={
        "provider_id": provider.id, "service_id": service.id,
        "starts_at": slot.starts_at.isoformat(), "payment_method": "bank transfer",
    }, headers=headers)
    assert res.status_code == 422


def test_a_cash_booking_cannot_start_a_checkout(db, client):
    """It is settled with the provider, so there is nothing here to pay."""
    booked = _book(client, db, sign_in_customer(client, "nocheckout@example.com"), "cod").json()

    res = client.post("/api/v1/payments/checkout",
                      json={"order_id": booked["job_id"], "provider": "stripe"})
    assert res.status_code == 409
    assert "cash" in res.json()["detail"].lower()


def test_an_already_paid_booking_cannot_be_paid_again(db, client):
    from app.models.job import Job

    booked = _book(client, db, sign_in_customer(client, "twice@example.com"), "stripe").json()
    job = db.query(Job).filter(Job.id == booked["job_id"]).first()
    job.payment_status = "paid"
    db.commit()

    res = client.post("/api/v1/payments/checkout",
                      json={"order_id": job.id, "provider": "stripe"})
    assert res.status_code == 409, "paying twice would take the money twice"


def test_a_scheduled_booking_may_still_start_a_checkout(db, client, monkeypatch):
    """The guard that nearly blocked this: the shop refuses checkout unless the
    job is "pending", and a booking is "scheduled" from the moment it is made,
    because the slot is genuinely taken whether or not the money has arrived."""
    from app.services import payments as payments_module

    class FakeSession:
        url = "https://example.test/pay/abc"
        provider_ref = "sess_abc"

    class FakeProvider:
        name = "stripe"
        def is_configured(self):
            return True
        def create_checkout(self, **kwargs):
            return FakeSession()

    monkeypatch.setattr(payments_module, "get", lambda name: FakeProvider())

    booked = _book(client, db, sign_in_customer(client, "scheduled@example.com"), "stripe").json()
    res = client.post("/api/v1/payments/checkout",
                      json={"order_id": booked["job_id"], "provider": "stripe"})

    assert res.status_code == 200, res.json()
    assert res.json()["url"] == FakeSession.url


def test_the_confirmation_email_says_how_it_will_be_paid(monkeypatch):
    """Three different truths, and one line for all of them would be wrong twice.
    Somebody paying by card who reads "you settle up with the provider" turns up
    expecting to pay again."""
    from app.services import booking_emails

    seen = {}
    monkeypatch.setattr(booking_emails, "_send",
                        lambda to, subject, html: seen.update(html=html))

    common = dict(
        to="a@example.com", customer_name="Alex", reference="BK-1",
        service_name="Leak found and fixed", provider_name="Quickfix Drains",
        provider_phone="1", starts_at=datetime(2026, 8, 12, 17, 0),
        duration_minutes=60, price=110.0, currency="USD", address="X", notes=None,
    )

    booking_emails.send_customer_confirmation(**common, payment_method="cod")
    assert "settle up with Quickfix Drains" in seen["html"]

    booking_emails.send_customer_confirmation(**common, payment_method="stripe")
    assert "has not completed yet" in seen["html"]

    booking_emails.send_customer_confirmation(**common, payment_method="stripe", paid=True)
    assert "Paid in full" in seen["html"]
    assert "settle up" not in seen["html"], "a paid booking must not ask for money again"


def test_the_provider_is_told_whether_to_collect(monkeypatch):
    from app.services import booking_emails

    seen = {}
    monkeypatch.setattr(booking_emails, "_send",
                        lambda to, subject, html: seen.update(html=html))

    common = dict(
        to="firm@example.com", provider_name="Quickfix Drains", reference="BK-1",
        service_name="Leak", customer_name="Alex", customer_email="a@example.com",
        customer_phone="1", starts_at=datetime(2026, 8, 12, 17, 0),
        duration_minutes=60, price=110.0, currency="USD", address="X", notes=None,
    )

    booking_emails.send_provider_notification(**common, payment_method="cod")
    assert "Collect $110.00 on the day" in seen["html"]

    booking_emails.send_provider_notification(**common, payment_method="stripe", paid=True)
    assert "Do not collect anything" in seen["html"]
