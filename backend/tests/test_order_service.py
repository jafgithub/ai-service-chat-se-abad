"""The money-safety rules in order_service.

Each of these covers a hazard that was real in the code before payments went in,
so they are regression tests, not hypotheticals:

  * two shoppers could buy the same last unit (read-modify-write on stock)
  * a double-clicked checkout placed two orders
  * a failed payment kept the stock reserved forever
  * a replayed webhook confirmed an order, and emailed the shopper, twice
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.customer import Customer
from app.models.order import Order
from app.services import order_service
from app.services.order_service import OrderError


@pytest.fixture
def db():
    """SQLite stands in for MySQL. The statements under test are plain SQL that
    behaves the same on both, which is the point of pushing the decrement down
    into the database instead of doing it in Python."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    yield session
    session.close()


def add_product(db, pid: int, stock: float, price: float = 10.0, name: str = "Milk"):
    db.execute(
        text("INSERT INTO items (id, name, price, tax, status, stock, category_id, store_id) "
             "VALUES (:id, :n, :p, 0, 1, :s, 1, 1)"),
        {"id": pid, "n": name, "p": price, "s": stock},
    )
    db.flush()


def stock_of(db, pid: int) -> float:
    return db.execute(text("SELECT stock FROM items WHERE id = :id"), {"id": pid}).scalar()


class Item:
    """Stands in for OrderItemIn without pulling in pydantic validation."""

    def __init__(self, product_id, quantity):
        self.product_id = product_id
        self.quantity = quantity


# ── reserving stock ──────────────────────────────────────────────────────────

def test_reserving_stock_decrements_once(db):
    add_product(db, 1, stock=5)
    assert order_service._reserve_stock(db, 1, 2) is True
    assert stock_of(db, 1) == 3


def test_cannot_reserve_more_than_exists(db):
    add_product(db, 1, stock=2)
    assert order_service._reserve_stock(db, 1, 3) is False
    assert stock_of(db, 1) == 2, "a failed reservation must not touch stock"


def test_last_unit_cannot_be_sold_twice(db):
    """The oversell that the old read-modify-write allowed."""
    add_product(db, 1, stock=1)
    assert order_service._reserve_stock(db, 1, 1) is True
    assert order_service._reserve_stock(db, 1, 1) is False
    assert stock_of(db, 1) == 0, "stock must never go negative"


def test_build_line_items_reserves_and_prices(db):
    add_product(db, 1, stock=10, price=2.50)
    details, subtotal = order_service.build_line_items(db, [Item(1, 4)])
    assert subtotal == 10.0
    assert details[0]["unit_price"] == 2.50
    assert stock_of(db, 1) == 6


def test_build_line_items_rejects_insufficient_stock(db):
    add_product(db, 1, stock=1)
    with pytest.raises(OrderError) as exc:
        order_service.build_line_items(db, [Item(1, 5)])
    assert "Not enough stock" in exc.value.message
    assert stock_of(db, 1) == 1


def test_build_line_items_rejects_unknown_product(db):
    with pytest.raises(OrderError) as exc:
        order_service.build_line_items(db, [Item(999, 1)])
    assert exc.value.status_code == 404


# ── confirming and cancelling ────────────────────────────────────────────────

def _pending_order(db, pid=1, qty=2):
    add_product(db, pid, stock=10)
    customer = Customer(name="A", email="a@example.com")
    db.add(customer)
    db.flush()
    details, subtotal = order_service.build_line_items(db, [Item(pid, qty)])
    _, total = order_service.totals_for(subtotal)
    return order_service.create_order(db, customer, details, total, status="pending")


def test_confirm_moves_pending_to_confirmed(db):
    order = _pending_order(db)
    assert order_service.confirm_order(db, order) is True
    assert order.status == "confirmed"


def test_confirming_twice_is_a_no_op(db):
    """A replayed webhook must not re-confirm, because the caller emails the
    shopper on a True return."""
    order = _pending_order(db)
    assert order_service.confirm_order(db, order) is True
    assert order_service.confirm_order(db, order) is False
    assert order.status == "confirmed"


def test_cancelling_releases_the_reserved_stock(db):
    order = _pending_order(db, qty=3)
    assert stock_of(db, 1) == 7
    assert order_service.cancel_order(db, order, "card declined") is True
    assert order.status == "cancelled"
    assert stock_of(db, 1) == 10, "a failed payment must put the stock back"


def test_cancelling_a_confirmed_order_does_nothing(db):
    order = _pending_order(db, qty=3)
    order_service.confirm_order(db, order)
    assert order_service.cancel_order(db, order) is False
    assert order.status == "confirmed"
    assert stock_of(db, 1) == 7, "stock must not be handed back for a paid order"


# ── idempotency ──────────────────────────────────────────────────────────────

def test_idempotency_key_finds_the_original_order(db):
    add_product(db, 1, stock=10)
    customer = Customer(name="A", email="a@example.com")
    db.add(customer)
    db.flush()
    details, subtotal = order_service.build_line_items(db, [Item(1, 1)])
    _, total = order_service.totals_for(subtotal)
    first = order_service.create_order(
        db, customer, details, total, status="pending", idempotency_key="abc-123",
    )
    db.flush()
    assert order_service.find_by_idempotency_key(db, "abc-123").id == first.id


def test_no_key_never_matches_an_existing_order(db):
    """Orders placed without a key must not collide with each other."""
    assert order_service.find_by_idempotency_key(db, None) is None
    assert order_service.find_by_idempotency_key(db, "") is None


def test_duplicate_idempotency_key_is_rejected_by_the_database(db):
    """The unique index is the real guard; the lookup is only the fast path."""
    from sqlalchemy.exc import IntegrityError

    add_product(db, 1, stock=10)
    customer = Customer(name="A", email="a@example.com")
    db.add(customer)
    db.flush()
    details, subtotal = order_service.build_line_items(db, [Item(1, 1)])
    _, total = order_service.totals_for(subtotal)

    order_service.create_order(db, customer, details, total, status="pending",
                               idempotency_key="same-key")
    db.flush()
    # create_order flushes internally to get the order id, so the constraint
    # fires inside the call rather than at a later flush.
    with pytest.raises(IntegrityError):
        order_service.create_order(db, customer, details, total, status="pending",
                                   idempotency_key="same-key")


# ── customers ────────────────────────────────────────────────────────────────

class CustomerIn:
    def __init__(self, **kw):
        self._d = {"name": "A", "email": "a@example.com", "phone": None,
                   "latitude": None, "longitude": None, "address": None}
        self._d.update(kw)
        for k, v in self._d.items():
            setattr(self, k, v)

    def model_dump(self):
        return dict(self._d)


def test_upsert_customer_reuses_the_same_email(db):
    first  = order_service.upsert_customer(db, CustomerIn(name="First"))
    second = order_service.upsert_customer(db, CustomerIn(name="Second"))
    assert first.id == second.id, "one customer per email, not one per order"
    assert second.name == "Second", "details from the latest order win"
    assert db.query(Customer).count() == 1
