"""Reading an order back after paying for it.

This endpoint exists because the return trip from Stripe or PayPal lands on
`/chat?paid={order_id}` with no other state, and the page has to be able to show
the shopper what they just bought.

The interesting property is what it *refuses*. Keying the lookup on the order id
would have been the obvious design and would have let anyone read every order in
the system by counting upwards, so these tests pin the choice of key.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.services import job_service


class CustomerIn:
    def __init__(self, **kw):
        self._d = {"name": "A", "email": "a@example.com", "phone": None,
                   "latitude": None, "longitude": None, "address": None}
        self._d.update(kw)
        for k, v in self._d.items():
            setattr(self, k, v)

    def model_dump(self):
        return dict(self._d)


@pytest.fixture
def db():
    # StaticPool keeps one in-memory database across the connections the
    # TestClient and the fixture both open; without it they see separate ones.
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


def make_order(db, key: str | None, total: float = 21.60):
    db.execute(
        text("INSERT INTO items (id, name, price, tax, status, stock, category_id, store_id) "
             "VALUES (1, 'Whole Milk', 10.0, 0, 1, 50, 1, 1)")
    )
    db.flush()
    customer = job_service.upsert_customer(db, CustomerIn(name="Buyer"))
    details, subtotal = job_service.build_line_items(
        db, [type("I", (), {"product_id": 1, "quantity": 2})()]
    )
    order = job_service.create_order(
        db, customer, details, total, status="pending", idempotency_key=key,
    )
    db.commit()
    return order


def test_the_key_returns_the_order(client, db):
    order = make_order(db, "3f8c1c2e-0f4d-4a5b-9c7e-1d2a3b4c5d6e")

    res = client.get("/api/v1/orders/by-key/3f8c1c2e-0f4d-4a5b-9c7e-1d2a3b4c5d6e")

    assert res.status_code == 200
    body = res.json()
    assert body["order_id"] == order.id
    assert body["status"] == "pending"
    assert body["items"][0]["product_name"] == "Whole Milk"
    assert body["items"][0]["quantity"] == 2


def test_the_order_id_is_not_a_key(client, db):
    """The whole point: knowing the order number must not be enough."""
    order = make_order(db, "3f8c1c2e-0f4d-4a5b-9c7e-1d2a3b4c5d6e")

    assert client.get(f"/api/v1/orders/by-key/{order.id}").status_code == 404


@pytest.mark.parametrize("guess", ["1", "42", "abc", "", "   ", "0" * 15])
def test_short_or_guessable_values_are_refused(client, db, guess):
    make_order(db, "3f8c1c2e-0f4d-4a5b-9c7e-1d2a3b4c5d6e")

    res = client.get(f"/api/v1/orders/by-key/{guess}")
    assert res.status_code in (404, 405, 307), guess


def test_a_wrong_key_of_the_right_shape_is_refused(client, db):
    make_order(db, "3f8c1c2e-0f4d-4a5b-9c7e-1d2a3b4c5d6e")

    res = client.get("/api/v1/orders/by-key/00000000-0000-4000-8000-000000000000")
    assert res.status_code == 404


def test_an_order_placed_without_a_key_cannot_be_fetched(client, db):
    """A null key must not match a null lookup and hand back someone's order."""
    make_order(db, None)

    assert client.get("/api/v1/orders/by-key/null").status_code == 404
    assert client.get("/api/v1/orders/by-key/undefined").status_code == 404
    assert client.get("/api/v1/orders/by-key/None").status_code == 404
