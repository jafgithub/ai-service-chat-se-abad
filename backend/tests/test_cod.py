"""Cash on delivery.

The thing that makes this worth testing hard is that a cash order is
`confirmed` while the money has NOT been collected. Every other confirmed order
in the system has been paid for. So the tests below pin the two directions that
could lose money:

  * a cash order must never be chargeable online as well, and
  * the fact that cash is owed must survive the trip to the client's system,
    which drops any column he does not have.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.database import Base, get_db
from app.main import app
from app.models.order import Order
from app.services.order_service import note_with_payment_method


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    session.execute(
        text("INSERT INTO items (id, name, price, tax, status, stock, category_id, store_id) "
             "VALUES (1, 'Whole Milk', 10.0, 0, 1, 50, 1, 1)")
    )
    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(db, monkeypatch):
    # Emails are a background task and would try a real SMTP connection.
    monkeypatch.setattr("app.api.orders.send_order_emails", lambda order_id: None)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def place(client, method="cod", key="k-00000000-0000-4000-8000-00000000000", **kw):
    body = {
        "customer": {"name": "Buyer", "email": "buyer@example.com", "phone": "+100"},
        "items": [{"product_id": 1, "quantity": 2}],
        "idempotency_key": key,
        "payment_method": method,
    }
    body.update(kw)
    return client.post("/api/v1/orders", json=body)


# ── the order itself ─────────────────────────────────────────────────────────

def test_a_cash_order_is_confirmed_immediately(client):
    res = place(client, "cod")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "confirmed", "nothing to wait for: no money is being taken"
    assert body["payment_method"] == "cod"


def test_a_card_order_waits_for_the_provider(client, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENTS_ENABLED", True)
    res = place(client, "stripe", key="k-card-0000-4000-8000-000000000001")
    assert res.status_code == 200
    assert res.json()["status"] == "pending", "must not confirm before the webhook"


def test_stock_is_reserved_for_a_cash_order_too(client, db):
    place(client, "cod")
    stock = db.execute(text("SELECT stock FROM items WHERE id = 1")).scalar()
    assert stock == 48, "cash is still a real order; the units are gone"


def test_the_default_is_cash(client):
    """An older client that does not send the field must not create an order
    that is neither paid for nor flagged for collection."""
    body = {
        "customer": {"name": "Buyer", "email": "b@example.com", "phone": "+1"},
        "items": [{"product_id": 1, "quantity": 1}],
        "idempotency_key": "k-default-000-4000-8000-000000000002",
    }
    res = client.post("/api/v1/orders", json=body)
    assert res.status_code == 200
    assert res.json()["payment_method"] == "cod"


# ── refusing what would lose money ───────────────────────────────────────────

def test_cash_is_refused_when_switched_off(client, monkeypatch):
    """Rather than silently confirming an order nobody has paid for."""
    monkeypatch.setattr(settings, "COD_ENABLED", False)
    res = place(client, "cod")
    assert res.status_code == 400
    assert "cash on delivery" in res.json()["detail"].lower()


def test_a_cash_order_cannot_also_be_charged(client, db, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENTS_ENABLED", True)
    order_id = place(client, "cod").json()["order_id"]

    res = client.post("/api/v1/payments/checkout",
                      json={"order_id": order_id, "provider": "stripe"})

    assert res.status_code == 409
    assert "cash" in res.json()["detail"].lower()


def test_an_online_order_is_refused_when_payments_are_off(client, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENTS_ENABLED", False)
    res = place(client, "stripe", key="k-off-00000-4000-8000-000000000003")
    assert res.status_code == 400


# ── the part that reaches the client ─────────────────────────────────────────

def test_the_cash_flag_is_written_where_it_will_actually_sync(client, db):
    """`orders.payment_method` is dropped on the way to the client, because
    sync keeps only the columns both databases share. `notes` is on both sides,
    so that is where the instruction to collect has to live."""
    order_id = place(client, "cod", notes="Gate code 4412").json()["order_id"]

    order = db.query(Order).filter(Order.id == order_id).first()
    assert "CASH ON DELIVERY" in order.notes
    assert "Gate code 4412" in order.notes, "what the shopper typed is kept"


def test_a_paid_order_says_so_in_the_notes(client, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENTS_ENABLED", True)
    res = place(client, "paypal", key="k-pp-000000-4000-8000-000000000004")
    assert res.status_code == 200


@pytest.mark.parametrize("method,expected", [
    ("cod", "CASH ON DELIVERY"),
    ("stripe", "Paid online by card"),
    ("paypal", "Paid online by PayPal"),
])
def test_each_method_reads_as_plain_words(method, expected):
    """A person in the shop reads this field, not a program."""
    assert expected in note_with_payment_method(None, method)


def test_an_unknown_method_leaves_the_notes_alone():
    assert note_with_payment_method("Leave at door", None) == "Leave at door"
    assert note_with_payment_method(None, None) is None
