"""Adopting an external product into the catalog.

The id allocation is the part worth testing hardest. `items.id` has no
AUTO_INCREMENT on the client's schema and defaults to 0, and the ids in it are
assigned by his system, so getting this wrong either collides on the primary key
or lets a later import overwrite a real product with one of ours.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base
from app.models.external_item import ExternalItem
from app.models.product import Product
from app.services import adopt_service
from app.services.adopt_service import AdoptError
from app.services.shopping.base import ExternalProduct
from app.services.shopping.stub_provider import StubProvider


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()

    # Embedding loads a 90 MB transformer; the adoption logic is what is under
    # test, not the model. Stub it and record that it was called.
    calls: list[int] = []
    monkeypatch.setattr(
        "app.services.rag.reindex_product",
        lambda product, session_: calls.append(product.id),
    )
    # Rebuilding the index is deferred work with a timer; not wanted in tests.
    monkeypatch.setattr("app.services.reindex_queue.request", lambda: None)
    session.embed_calls = calls  # type: ignore[attr-defined]
    yield session
    session.close()


def sample(**kw) -> ExternalProduct:
    base = {
        "source_id": "ext-1", "name": "Saffron Threads 2g", "price": 18.5,
        "image_url": "https://cdn.example.com/saffron.jpg",
        "product_url": "https://example.com/p/1", "seller": "Spice House",
        "description": "Premium saffron.",
    }
    base.update(kw)
    return ExternalProduct(**base)


def add_client_product(db, pid: int):
    """A row like one imported from the client's own catalog."""
    db.execute(
        text("INSERT INTO items (id, name, price, tax, status, stock) "
             "VALUES (:id, 'Client product', 1.0, 0, 1, 10)"),
        {"id": pid},
    )
    db.flush()


# ── id allocation ────────────────────────────────────────────────────────────

def test_first_adopted_id_sits_above_the_clients_range(db):
    add_client_product(db, 228346)   # the top of the real catalog
    product, created = adopt_service.adopt(db, sample(), source="google_shopping")
    assert created is True
    assert product.id > settings.ADOPTED_ITEM_ID_BASE
    assert product.id > 228346


def test_ids_do_not_collide_with_each_other(db):
    """No AUTO_INCREMENT means a repeated id would violate the primary key."""
    a, _ = adopt_service.adopt(db, sample(source_id="a"), source="s")
    b, _ = adopt_service.adopt(db, sample(source_id="b"), source="s")
    c, _ = adopt_service.adopt(db, sample(source_id="c"), source="s")
    assert len({a.id, b.id, c.id}) == 3
    assert b.id == a.id + 1 and c.id == b.id + 1


def test_a_growing_client_catalog_does_not_push_our_ids(db):
    """Allocation looks only within our own band, so his ids never move ours."""
    first, _ = adopt_service.adopt(db, sample(source_id="a"), source="s")
    add_client_product(db, 500_000)     # his catalog grows
    second, _ = adopt_service.adopt(db, sample(source_id="b"), source="s")
    assert second.id == first.id + 1


# ── adopting ─────────────────────────────────────────────────────────────────

def test_adopting_creates_a_usable_catalog_row(db):
    product, _ = adopt_service.adopt(db, sample(), source="google_shopping", query="saffron")

    assert product.name == "Saffron Threads 2g"
    assert float(product.price) == 18.5
    # NOT NULL in the client's schema, and the ORM default does not reach the DB.
    assert product.tax is not None
    assert product.status is True
    assert product.stock and product.stock > 0
    # Not one of the client's groupings, so left unset.
    assert product.category_id is None
    # NOT NULL in the real schema with no default. SQLite lets these through as
    # NULL, so assert them here or the failure only shows up against MySQL.
    assert product.store_id is not None
    assert product.module_id is not None
    assert product.is_approved is True


def test_provenance_is_recorded(db):
    product, _ = adopt_service.adopt(
        db, sample(), source="google_shopping", query="saffron threads",
    )
    row = db.query(ExternalItem).filter(ExternalItem.item_id == product.id).one()
    assert row.source == "google_shopping"
    assert row.seller == "Spice House"
    assert row.query == "saffron threads"
    assert row.image_url == "https://cdn.example.com/saffron.jpg"


def test_the_same_external_product_is_adopted_once(db):
    first, created_first = adopt_service.adopt(db, sample(), source="s")
    second, created_second = adopt_service.adopt(db, sample(), source="s")
    assert created_first is True
    assert created_second is False
    assert first.id == second.id
    assert db.query(Product).count() == 1


def test_the_same_id_from_a_different_source_is_a_different_product(db):
    a, _ = adopt_service.adopt(db, sample(source_id="shared"), source="source-a")
    b, _ = adopt_service.adopt(db, sample(source_id="shared"), source="source-b")
    assert a.id != b.id


def test_new_product_is_embedded(db):
    product, _ = adopt_service.adopt(db, sample(), source="s")
    assert db.embed_calls == [product.id]  # type: ignore[attr-defined]


def test_an_already_adopted_product_is_not_re_embedded(db):
    adopt_service.adopt(db, sample(), source="s")
    adopt_service.adopt(db, sample(), source="s")
    assert len(db.embed_calls) == 1  # type: ignore[attr-defined]


# ── rejecting what cannot be sold ────────────────────────────────────────────

@pytest.mark.parametrize("price", [0, -5, None])
def test_a_product_without_a_price_is_rejected(db, price):
    with pytest.raises(AdoptError) as exc:
        adopt_service.adopt(db, sample(price=price), source="s")
    assert "price" in exc.value.message.lower()


def test_a_product_without_a_name_is_rejected(db):
    with pytest.raises(AdoptError):
        adopt_service.adopt(db, sample(name="   "), source="s")


def test_an_over_long_image_url_is_dropped_rather_than_truncated(db):
    """A truncated URL is a broken image; no image falls back to a category icon."""
    product, _ = adopt_service.adopt(
        db, sample(image_url="https://cdn.example.com/" + "x" * 600), source="s",
    )
    assert product.image is None
    # The full URL is still kept alongside, so nothing is actually lost.
    row = db.query(ExternalItem).filter(ExternalItem.item_id == product.id).one()
    assert len(row.image_url) > 512


def test_a_normal_image_url_is_stored_on_the_item(db):
    product, _ = adopt_service.adopt(db, sample(), source="s")
    assert product.image == "https://cdn.example.com/saffron.jpg"


# ── the stub provider ────────────────────────────────────────────────────────

def test_stub_returns_priced_results():
    results = StubProvider().search("saffron", limit=3)
    assert len(results) == 3
    assert all(r.price > 0 and r.name and r.source_id for r in results)


def test_stub_is_stable_for_the_same_query():
    """Adopting the same result twice must look like the same product."""
    assert [r.source_id for r in StubProvider().search("saffron")] == \
           [r.source_id for r in StubProvider().search("saffron")]


def test_stub_returns_nothing_for_an_empty_query():
    assert StubProvider().search("   ") == []


# ── refusing to source nonsense ──────────────────────────────────────────────
# A voice turn heard as "00:01" reached the search on the live server, the
# provider templated it, and two orderable products called "Organic 00:01, 100g"
# and "00:01 Premium Selection" were created in the catalog.

@pytest.mark.parametrize("query", ["00:01", "123", "...", "a1", "", "   ", "4:20", "!!"])
def test_a_query_with_no_words_is_not_worth_sourcing(query):
    from app.services.shopping.base import looks_like_a_product
    assert looks_like_a_product(query) is False


@pytest.mark.parametrize(
    "query", ["milk", "tea", "oat milk 1l", "saffron threads", "2kg rice", "Member's Mark"]
)
def test_a_real_query_is_accepted(query):
    from app.services.shopping.base import looks_like_a_product
    assert looks_like_a_product(query) is True


# ── not spending the search allowance on nothing ─────────────────────────────
# SerpApi bills per fresh search: 250 a month free, 1,000 for $25. Cached
# answers are free on their side too, so every avoidable call is money.

def test_near_identical_queries_share_one_cached_search(monkeypatch):
    """"Harissa Paste" and " harissa  paste " must not be two paid searches."""
    from app.services.shopping import serpapi_provider as sp

    calls: list[str] = []

    class FakeResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"shopping_results": [
                {"title": "Harissa", "extracted_price": 9.99, "product_id": "x"},
            ]}

    def fake_get(url, params=None, timeout=None):
        calls.append(params["q"])
        return FakeResponse()

    monkeypatch.setattr(sp.settings, "SERPAPI_KEY", "test-key")
    monkeypatch.setattr(sp.httpx, "get", fake_get)
    sp._CACHE.clear()

    provider = sp.SerpApiProvider()
    for phrasing in ("harissa paste", "Harissa Paste", "  harissa   paste  "):
        assert provider.search(phrasing), phrasing

    assert len(calls) == 1, f"one paid search, not {len(calls)}"


def test_the_cache_outlives_a_single_hour():
    """Grocery listings do not turn over hourly, and a longer cache is directly
    fewer paid searches."""
    from app.services.shopping import serpapi_provider as sp
    assert sp._CACHE_TTL_SECONDS >= 6 * 60 * 60


# ── sample data must never become orderable stock ────────────────────────────
# "Organic Banks, 100g" at $12.99 reached the live dev catalog through the adopt
# endpoint while the provider was the stub. It was fabricated by our own server:
# invented name, invented price, no real seller behind it. A shopper could have
# ordered it. This is the same fault as the "00:01" products, one layer up.

def test_the_stub_declares_itself_as_sample():
    from app.services.shopping.stub_provider import StubProvider
    from app.services.shopping.serpapi_provider import SerpApiProvider
    assert StubProvider.is_sample is True
    assert SerpApiProvider.is_sample is False


def test_a_sample_result_links_somewhere_real():
    """The link used to be https://example.com/product/..., which renders IANA's
    "Example Domain" placeholder and reads as a broken product page. Samples now
    point at a real retailer's search for whatever was typed, so the journey can
    be walked through without a paid provider account."""
    from app.services.shopping.stub_provider import StubProvider
    results = StubProvider().search("harissa paste")

    assert results, "the stub returns something"
    for r in results:
        assert r.product_url, r.name
        assert "example.com" not in r.product_url
        assert "harissa+paste" in r.product_url, "the shopper's own words"
    assert {r.seller for r in results} >= {"ALDI", "Costco"}


def test_adopting_is_refused_while_the_provider_is_sample(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services import shopping
    from app.services.shopping.stub_provider import StubProvider

    monkeypatch.setattr(shopping, "current", lambda: StubProvider())
    client = TestClient(app)

    res = client.post("/api/v1/shopping/adopt", json={
        "session_id": "s-1",
        "query": "banks",
        "product": {"source_id": "stub_x", "name": "Organic Banks, 100g", "price": 12.99},
    })

    assert res.status_code == 409
    assert "sample data" in res.json()["detail"].lower()


def test_the_status_endpoint_says_when_results_are_sample(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services import shopping
    from app.services.shopping.stub_provider import StubProvider

    monkeypatch.setattr(shopping, "current", lambda: StubProvider())
    body = TestClient(app).get("/api/v1/shopping/status").json()

    assert body["enabled"] is True
    assert body["sample"] is True, "the interface needs this to label the panel"


def test_a_stale_cached_url_cannot_reintroduce_a_dead_link(monkeypatch):
    """Offers stored before the stub stopped inventing URLs still hold
    "https://example.com/product/...". A "Show more" landing on IANA's Example
    Domain page is what the client actually saw, so the link is withheld at the
    boundary rather than trusting whatever was cached."""
    from app.api.shopping import _out
    from app.services.shopping.base import ExternalProduct

    cached = ExternalProduct(
        source_id="stub_x", name="Organic Harissa Paste, 100g", price=12.99,
        product_url="https://example.com/product/7e733aaaa6c3",
    )

    # Dead by destination, whether or not the row is flagged as sample.
    assert _out(cached, stored=True, sample=True).product_url is None
    assert _out(cached, stored=True, sample=False).product_url is None

    alive = ExternalProduct(
        source_id="s", name="Harissa", price=1.0,
        product_url="https://www.aldi.us/results?q=harissa",
    )
    assert _out(alive, stored=True, sample=True).product_url.startswith("https://www.aldi.us")


def test_every_sample_link_uses_a_pattern_that_actually_resolves():
    """The first attempt used https://www.aldi.us/results?q=..., which 404s.
    A link that does not work is the fault this replaced, so the shapes are
    pinned here rather than checked by eye once."""
    from app.services.shopping.stub_provider import StubProvider

    expected = {
        "ALDI":    "www.aldi.us/store/aldi/s?k=",
        "Costco":  "sameday.costco.com/store/costco/s?k=",
        "Walmart": "www.walmart.com/search?q=",
        "Target":  "www.target.com/s?searchTerm=",
        "Amazon":  "www.amazon.com/s?k=",
    }
    for r in StubProvider().search("harissa paste"):
        assert expected[r.seller] in r.product_url, r.seller


# ── the vendor's own product page ────────────────────────────────────────────
# The affiliate and drop-ship link: where the shopper goes to see the product,
# and where the order is fulfilled from.

def test_adopting_stores_the_vendor_product_page(db):
    product, _ = adopt_service.adopt(
        db,
        sample(product_url="https://www.walmart.com/ip/Mina-Mild-Harissa-Sauce/773599552"),
        source="google_shopping",
    )
    assert product.vendor_prod_prod_page_url == (
        "https://www.walmart.com/ip/Mina-Mild-Harissa-Sauce/773599552"
    )


def test_a_product_with_no_vendor_page_is_still_adoptable(db):
    """The client's own 25,631 products have nothing in this column until his
    import fills it, so an empty value has to be ordinary rather than an error."""
    product, _ = adopt_service.adopt(db, sample(product_url=None), source="s")
    assert product.vendor_prod_prod_page_url is None
