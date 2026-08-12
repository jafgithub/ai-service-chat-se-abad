"""Storing provider results so the same search is never paid for twice.

SerpApi bills per fresh search: 250 a month free, 1,000 for $25. The client
asked for responses to be stored and reused rather than re-fetched, so the tests
that matter here are the ones about not spending a search.
"""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models.external_offer import ExternalOffer
from app.services import offer_store
from app.services.shopping.base import ExternalProduct

SOURCE = "google_shopping"


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    yield session
    session.close()


def offers(n=3):
    return [
        ExternalProduct(
            source_id=f"id-{i}",
            name=f"Harissa Paste {i}",
            price=10.0 + i,
            image_url=f"https://cdn.example.com/{i}.jpg",
            product_url=f"https://store.example.com/p/{i}",
            seller="Wholefoods Direct",
            description="A hot chilli paste.",
            extra={"rating": 4.5, "reviews": 120, "source_url": f"https://google.com/{i}"},
        )
        for i in range(n)
    ]


# ── the point of the whole table ─────────────────────────────────────────────

def test_a_stored_search_is_served_without_paying_again(db):
    offer_store.save(db, "harissa paste", SOURCE, offers())

    again = offer_store.get_fresh(db, "harissa paste", SOURCE)

    assert len(again) == 3
    assert again[0].name == "Harissa Paste 0"
    assert again[0].extra["stored"] is True


@pytest.mark.parametrize("phrasing", ["Harissa Paste", "  harissa   paste ", "HARISSA PASTE"])
def test_near_identical_phrasings_hit_the_same_stored_search(db, phrasing):
    offer_store.save(db, "harissa paste", SOURCE, offers())
    assert len(offer_store.get_fresh(db, phrasing, SOURCE)) == 3


def test_an_unrelated_search_is_not_served_from_it(db):
    offer_store.save(db, "harissa paste", SOURCE, offers())
    assert offer_store.get_fresh(db, "olive oil", SOURCE) == []


def test_stale_results_are_not_served(db):
    """Past the window we would rather spend a search than quote an old price."""
    offer_store.save(db, "harissa paste", SOURCE, offers())
    for row in db.query(ExternalOffer):
        row.fetched_at = offer_store._utcnow() - timedelta(days=offer_store.OFFER_TTL_DAYS + 1)
    db.commit()

    assert offer_store.get_fresh(db, "harissa paste", SOURCE) == []


# ── writing ──────────────────────────────────────────────────────────────────

def test_running_the_same_search_again_updates_rather_than_duplicates(db):
    offer_store.save(db, "harissa paste", SOURCE, offers())

    cheaper = offers()
    cheaper[0].price = 3.50
    offer_store.save(db, "harissa paste", SOURCE, cheaper)

    assert db.query(ExternalOffer).count() == 3, "refreshed in place, not duplicated"
    first = db.query(ExternalOffer).filter(ExternalOffer.source_id == "id-0").one()
    assert float(first.price) == 3.50


def test_everything_the_client_asked_to_keep_is_kept(db):
    offer_store.save(db, "harissa paste", SOURCE, offers(1))
    row = db.query(ExternalOffer).one()

    assert row.name and row.price is not None
    assert row.seller == "Wholefoods Direct"
    assert row.product_url.startswith("https://store.example.com")   # the store page
    assert row.source_url.startswith("https://google.com")           # the listing
    assert row.image_url and row.description
    assert row.rating is not None and row.reviews == 120
    assert row.source_id == "id-0"                                   # the identifier
    assert row.raw, "the untouched response, so a later field needs no re-fetch"


def test_the_provider_order_is_preserved(db):
    """So "relevance" can be reproduced from storage without asking again."""
    offer_store.save(db, "harissa paste", SOURCE, offers())
    assert [o.name for o in offer_store.get_fresh(db, "harissa paste", SOURCE)] == [
        "Harissa Paste 0", "Harissa Paste 1", "Harissa Paste 2",
    ]


def test_saving_nothing_is_harmless(db):
    assert offer_store.save(db, "harissa paste", SOURCE, []) == 0
    assert offer_store.save(db, "", SOURCE, offers()) == 0


def test_a_storage_failure_does_not_break_the_search(db, monkeypatch):
    """A cache is a convenience; the shopper is waiting on the search itself."""
    monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    assert offer_store.save(db, "harissa paste", SOURCE, offers()) == 0


def test_stale_rows_are_deleted_not_merely_ignored(db):
    """Otherwise the table grows forever: every distinct search anyone runs
    leaves rows behind, and stale ones are never served anyway."""
    offer_store.save(db, "old search", SOURCE, offers())
    for row in db.query(ExternalOffer):
        row.fetched_at = offer_store._utcnow() - timedelta(days=offer_store.OFFER_TTL_DAYS + 1)
    db.commit()

    # Any later save triggers the sweep.
    offer_store.save(db, "new search", SOURCE, offers(1))

    remaining = {r.query for r in db.query(ExternalOffer)}
    assert remaining == {"new search"}, "the stale search was cleared out"


def test_the_immersive_token_is_kept_for_later(db):
    """Resolving the retailer's own page costs a billed search. Keeping the
    token means that can be done later, on demand, without re-running the
    search that produced the row."""
    products = offers(1)
    products[0].extra["immersive_token"] = "tok-abc"
    offer_store.save(db, "harissa paste", SOURCE, products)

    row = db.query(ExternalOffer).one()
    assert row.immersive_token == "tok-abc"
    assert row.detail_json is None, "not resolved until somebody opens it"
