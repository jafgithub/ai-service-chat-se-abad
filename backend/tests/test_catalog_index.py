"""
Tests for the in-memory catalog index.

The point of these is not that the index finds sensible products — that's the
embedding model's job — but that it ranks *identically to the database path it
replaces*. So the core test scores a random catalog with a plain-Python copy of
the old algorithm and demands the same answer, ordering and all.

    cd backend && .venv/bin/python -m pytest tests/ -q
"""

import json

import numpy as np
import pytest
from sqlalchemy import create_engine, text

from app.services import catalog_index
from app.services.catalog_index import CatalogIndex

DIMS = 8


def unit(rng, n=DIMS):
    v = rng.standard_normal(n).astype(np.float32)
    return v / np.linalg.norm(v)


def make_index(vectors, prices=None, categories=None):
    """Build a CatalogIndex directly, bypassing the database."""
    matrix = np.ascontiguousarray(np.asarray(vectors, dtype=np.float32))
    n = len(matrix)
    prices = prices or [1.0] * n
    categories = categories or ["General"] * n

    names, codes = [], []
    lookup = {}
    for c in categories:
        if c not in lookup:
            lookup[c] = len(names)
            names.append(c.lower())
        codes.append(lookup[c])

    meta = [
        (i + 1, f"Product {i + 1}", f"desc {i + 1}", float(prices[i]), 10.0,
         None, None, None, categories[i], None)
        for i in range(n)
    ]
    return CatalogIndex(matrix, meta, np.asarray(codes, dtype=np.int32), names, 0.0)


def reference_search(vectors, query, prices, categories, top_k=None,
                     category_filter=None, min_similarity=0.35, deal=False):
    """The original rag._search_products_db algorithm, transcribed.

    Kept deliberately naive and Python-loopy — it is the thing the fast path has
    to agree with, so it must be obviously a copy of the old code rather than a
    clever reimplementation.
    """
    rows = list(range(len(vectors)))
    if category_filter:
        rows = [i for i in rows if category_filter.lower() in categories[i].lower()]

    matrix = np.array([vectors[i] for i in rows], dtype=np.float32)
    q = np.array(query, dtype=np.float32)
    q = q / (np.linalg.norm(q) + 1e-10)
    if matrix.size == 0:
        return []
    sims = matrix @ q

    scored = [(float(sims[k]), rows[k]) for k in range(len(rows))
              if sims[k] >= min_similarity]

    if deal and scored:
        p = [float(prices[i]) for _, i in scored]
        lo, hi = min(p), max(p)
        span = (hi - lo) or 1.0
        blended = [((sim * 0.6) + ((1.0 - (float(prices[i]) - lo) / span) * 0.4), i)
                   for sim, i in scored]
        blended.sort(key=lambda x: x[0], reverse=True)
        out = blended if top_k is None else blended[:top_k]
    else:
        scored.sort(key=lambda x: x[0], reverse=True)
        out = scored if top_k is None else scored[:top_k]

    return [(i + 1, round(score, 4)) for score, i in out]


# ── the parity test that matters ──────────────────────────────────────────────

@pytest.mark.parametrize("seed", range(8))
def test_matches_the_database_algorithm_exactly(seed):
    rng = np.random.default_rng(seed)
    n = 300
    vectors = [unit(rng) for _ in range(n)]
    prices = [round(float(rng.uniform(1, 60)), 2) for _ in range(n)]
    cats = [["Dairy", "Bakery", "Meat", "General"][int(rng.integers(0, 4))] for _ in range(n)]
    index = make_index(vectors, prices, cats)

    for _ in range(5):
        query = unit(rng).tolist()
        for deal in (False, True):
            for top_k in (None, 1, 5, 20):
                for cat in (None, "dairy", "Mea"):
                    got = [(r["id"], r["similarity"])
                           for r in index.search(query, top_k, cat, 0.35, deal)]
                    want = reference_search(vectors, query, prices, cats,
                                            top_k, cat, 0.35, deal)
                    assert got == want, f"seed={seed} deal={deal} top_k={top_k} cat={cat}"


def test_ties_keep_catalog_order():
    """Identical scores must fall back to id order, as the old stable sort did."""
    v = unit(np.random.default_rng(0))
    index = make_index([v, v, v])
    ids = [r["id"] for r in index.search(v.tolist(), None, None, 0.0)]
    assert ids == [1, 2, 3]


# ── behaviour around the edges ────────────────────────────────────────────────

def test_threshold_excludes_weak_matches():
    rng = np.random.default_rng(1)
    target = unit(rng)
    opposite = -target
    index = make_index([target, opposite])
    results = index.search(target.tolist(), None, None, 0.35)
    assert [r["id"] for r in results] == [1]


def test_top_k_limits_results():
    rng = np.random.default_rng(2)
    v = unit(rng)
    index = make_index([v] * 10)
    assert len(index.search(v.tolist(), 3, None, 0.0)) == 3
    assert len(index.search(v.tolist(), None, None, 0.0)) == 10


def test_unknown_category_returns_nothing():
    rng = np.random.default_rng(3)
    v = unit(rng)
    index = make_index([v], categories=["Dairy"])
    assert index.search(v.tolist(), None, "frozen pizza", 0.0) == []


def test_deal_intent_prefers_cheaper_of_two_equal_matches():
    rng = np.random.default_rng(4)
    v = unit(rng)
    index = make_index([v, v], prices=[50.0, 2.0])
    plain = [r["id"] for r in index.search(v.tolist(), None, None, 0.0, False)]
    deal = [r["id"] for r in index.search(v.tolist(), None, None, 0.0, True)]
    assert plain == [1, 2]      # equal scores, catalog order
    assert deal == [2, 1]       # cheaper one wins


def test_empty_index_is_safe():
    empty = CatalogIndex(np.empty((0, 0), dtype=np.float32), [],
                         np.asarray([], dtype=np.int32), [], 0.0)
    assert empty.search([0.0] * DIMS, None, None, 0.35) == []


def test_result_shape_matches_the_api_contract():
    rng = np.random.default_rng(5)
    v = unit(rng)
    index = make_index([v], prices=[4.25], categories=["Dairy"])
    r = index.search(v.tolist(), None, None, 0.0)[0]
    assert set(r) == {"id", "name", "category", "description", "unit",
                      "price_per_unit", "stock", "image_url", "owner_email",
                      "similarity"}
    assert r["category"] == "Dairy"
    assert r["price_per_unit"] == 4.25
    assert r["unit"] == "unit"


# ── the build path ────────────────────────────────────────────────────────────

@pytest.fixture
def sqlite_catalog(monkeypatch):
    """A miniature catalog in SQLite so build() can be exercised without MySQL."""
    engine = create_engine("sqlite://")
    rng = np.random.default_rng(7)
    with engine.begin() as c:
        c.execute(text("CREATE TABLE categories (id INT, name TEXT)"))
        c.execute(text("CREATE TABLE stores (id INT, email TEXT)"))
        c.execute(text("""CREATE TABLE items (
            id INT, name TEXT, description TEXT, price REAL, stock INT, image TEXT,
            store_id INT, category_id INT, status INT, item_vector TEXT)"""))
        c.execute(text("INSERT INTO categories VALUES (1,'Dairy'),(2,'Bakery')"))
        c.execute(text("INSERT INTO stores VALUES (9,'shop@example.com')"))
        for i in range(1, 21):
            c.execute(
                text("INSERT INTO items VALUES (:id,:n,:d,:p,5,NULL,9,:c,:s,:v)"),
                {"id": i, "n": f"Item {i}", "d": "d", "p": float(i),
                 "c": 1 if i % 2 else 2,
                 "s": 0 if i == 20 else 1,          # one inactive row
                 "v": json.dumps(unit(rng).tolist())},
            )
        # A row with no vector: it must be excluded, not crash the build.
        c.execute(text("INSERT INTO items VALUES (21,'No vector','d',1.0,5,NULL,9,1,1,NULL)"))

    monkeypatch.setattr(catalog_index, "engine", engine)
    catalog_index.clear()
    yield engine
    catalog_index.clear()


def test_build_loads_only_active_rows_with_vectors(sqlite_catalog):
    index = catalog_index.build()
    assert index is not None
    assert index.rows == 19        # 20 items, minus the inactive one; no-vector excluded
    assert index.dims == DIMS
    assert catalog_index.status()["state"] == "ready"
    assert catalog_index.get() is index


def test_build_resolves_joined_category_and_store(sqlite_catalog):
    index = catalog_index.build()
    r = index.search(index.matrix[0].tolist(), 1, None, 0.0)[0]
    assert r["id"] == 1
    assert r["category"] == "Dairy"
    assert r["owner_email"] == "shop@example.com"


def test_rebuild_swaps_the_index(sqlite_catalog):
    first = catalog_index.build()
    with sqlite_catalog.begin() as c:
        c.execute(text("UPDATE items SET status = 0 WHERE id <= 5"))
    second = catalog_index.build()
    assert second is not first
    assert second.rows == first.rows - 5
    assert catalog_index.get() is second


def test_row_cap_refuses_to_build(sqlite_catalog, monkeypatch):
    monkeypatch.setattr(catalog_index.settings, "INDEX_MAX_ROWS", 5)
    assert catalog_index.build() is None
    assert catalog_index.status()["state"] == "error"
    assert catalog_index.get() is None      # callers fall back to the database


def test_disabled_flag_keeps_the_index_out_of_the_way(sqlite_catalog, monkeypatch):
    catalog_index.build()
    monkeypatch.setattr(catalog_index.settings, "RAG_USE_INDEX", False)
    assert catalog_index.get() is None
    assert catalog_index.status() == {"state": "disabled"}
