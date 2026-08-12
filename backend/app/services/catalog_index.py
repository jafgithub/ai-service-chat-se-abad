"""
In-memory catalog index
───────────────────────
The catalog barely changes, but until now every single search re-read all of it:
~25,600 rows and ~206 MB of embedding text pulled out of MySQL, re-parsed, and
stacked into a fresh 25,631 x 384 matrix — just to run one dot service that takes
microseconds. The load *was* the response time.

This module does that work once, at startup, and keeps the result in memory:

    matrix   (N, 384) float32   the embeddings, exactly as stored in the database
    meta     N tuples           the fields a search result needs, so ranking a
                                query never touches the database at all

A search is then `matrix @ query_vector`, a threshold, and a sort.

Two rules govern everything here, because this is a *speed* change and the client
must not see his results move:

1. **Identical output.** The scoring, the 0.35 threshold, the stable ordering and
   the deal-intent price blend are reproduced step for step from the original
   `rag._search_products_db`. Every stored vector was verified to be unit-length
   already, so the same dot service remains true cosine similarity. See
   `benchmark_search.py --parity`, which asserts this against the live database.
2. **Never worse.** If the index is missing, still building, or disabled, callers
   silently fall back to the original database path.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine
from app.services.media import serialized_image_for

logger = logging.getLogger("rag")

# One statement replaces the per-request trio of queries the old path ran (the
# catalog scan plus the two `IN (...)` lookups in rag._enrich_products).
_BUILD_SQL = """
    SELECT i.id, i.name, i.description, i.price, i.stock, i.image,
           i.store_id, i.category_id,
           i.duration_minutes, i.emergency,
           c.name  AS category_name,
           s.email AS owner_email,
           i.item_vector
    FROM services i
    LEFT JOIN categories c ON c.id = i.category_id
    LEFT JOIN stores     s ON s.id = i.store_id
    WHERE i.status = 1 AND i.item_vector IS NOT NULL
    ORDER BY i.id
"""

_COUNT_SQL = "SELECT COUNT(*) FROM services WHERE status = 1 AND item_vector IS NOT NULL"

_CHUNK = 2000

# Meta tuple layout. Indexing a tuple by constant is far cheaper in both memory
# and time than 25k dicts, and results are only ever materialised for the handful
# of rows a query actually returns.
#
# `duration` and `emergency` are carried here rather than fetched per result:
# the service card shows how long a visit takes and whether it is attended out
# of hours, and going back to the database for two columns on every card would
# undo the point of the index.
(_ID, _NAME, _DESC, _PRICE, _STOCK, _IMAGE, _STORE, _CATID, _CAT, _EMAIL,
 _DURATION, _EMERGENCY) = range(12)

# Set by build(); read by search. Assignment is atomic under the GIL, so a
# rebuild swaps the whole index in one statement and readers never see it torn.
_index: Optional["CatalogIndex"] = None
_build_lock = threading.Lock()
_state = "cold"          # cold | building | ready | error | disabled
_last_error: str | None = None


class CatalogIndex:
    """An immutable snapshot of the searchable catalog."""

    __slots__ = ("matrix", "meta", "cat_codes", "cat_names_lower",
                 "dims", "rows", "built_at", "build_seconds", "bytes")

    def __init__(self, matrix, meta, cat_codes, cat_names_lower, build_seconds):
        self.matrix = matrix
        self.meta = meta
        self.cat_codes = cat_codes
        self.cat_names_lower = cat_names_lower
        self.dims = int(matrix.shape[1]) if matrix.size else 0
        self.rows = int(matrix.shape[0])
        self.built_at = datetime.now(timezone.utc)
        self.build_seconds = build_seconds
        self.bytes = int(matrix.nbytes + cat_codes.nbytes)

    # ── search ────────────────────────────────────────────────────────────────

    def _category_mask(self, category_filter: str) -> Optional[np.ndarray]:
        """Rows whose category name contains the filter, matching the old
        substring test `filter.lower() in category_name.lower()`."""
        needle = category_filter.lower()
        codes = [i for i, name in enumerate(self.cat_names_lower) if needle in name]
        if not codes:
            return None
        return np.isin(self.cat_codes, np.asarray(codes, dtype=np.int32))

    def _result(self, row: int, similarity: float) -> dict:
        m = self.meta[row]
        return {
            "id":             m[_ID],
            "name":           m[_NAME],
            "category":       m[_CAT],
            "description":    m[_DESC] or "",
            "unit":           "unit",
            "price_per_unit": m[_PRICE],
            "stock":          m[_STOCK],
            "image_url":      serialized_image_for(m[_ID], m[_IMAGE], m[_STORE]),
            "owner_email":    m[_EMAIL],
            "duration_minutes": m[_DURATION],
            "emergency":      m[_EMERGENCY],
            "similarity":     round(similarity, 4),
        }

    def search(
        self,
        query_vector: list[float],
        top_k: Optional[int] = None,
        category_filter: Optional[str] = None,
        min_similarity: float = 0.35,
        is_deal_query: bool = False,
    ) -> list[dict]:
        if not self.rows:
            return []

        # Re-normalise exactly as the original path did, so a query embedded
        # here scores identically to one embedded there.
        q = np.asarray(query_vector, dtype=np.float32)
        q = q / (np.linalg.norm(q) + 1e-10)

        sims = self.matrix @ q
        keep = sims >= min_similarity

        if category_filter:
            mask = self._category_mask(category_filter)
            if mask is None:
                return []
            keep &= mask

        hits = np.flatnonzero(keep)
        if hits.size == 0:
            return []

        if is_deal_query:
            return self._rank_by_deal(hits, sims, top_k)

        # Stable descending sort: ties keep catalog (id) order, which is what
        # Python's stable list.sort did on the database path.
        order = hits[np.argsort(-sims[hits], kind="stable")]
        if top_k is not None:
            order = order[:top_k]
        return [self._result(int(i), float(sims[i])) for i in order]

    def _rank_by_deal(self, hits, sims, top_k) -> list[dict]:
        """Blend similarity with cheapness — the original 0.6/0.4 weighting,
        min-max normalised across the surviving matches."""
        prices = [self.meta[int(i)][_PRICE] for i in hits]
        min_price = min(prices)
        max_price = max(prices)
        price_range = (max_price - min_price) or 1.0

        blended = []
        for pos, row in enumerate(hits):
            sim = float(sims[row])
            price_score = 1.0 - (prices[pos] - min_price) / price_range
            blended.append(((sim * 0.6) + (price_score * 0.4), int(row)))

        blended.sort(key=lambda x: x[0], reverse=True)
        if top_k is not None:
            blended = blended[:top_k]
        return [self._result(row, final) for final, row in blended]


# ── build ─────────────────────────────────────────────────────────────────────

def build() -> Optional[CatalogIndex]:
    """Load the whole catalog into a fresh index and publish it.

    Safe to call at any time: it builds into a local variable and only swaps the
    global once complete, so searches keep serving the previous index (or the
    database path) throughout.
    """
    global _index, _state, _last_error

    if not settings.RAG_USE_INDEX:
        _state = "disabled"
        logger.info("[INDEX] disabled (RAG_USE_INDEX=false)")
        return None

    if not _build_lock.acquire(blocking=False):
        logger.info("[INDEX] build already in progress — skipping duplicate request")
        return _index

    try:
        _state = "building"
        _last_error = None
        t0 = time.perf_counter()

        with engine.connect() as conn:
            expected = int(conn.execute(text(_COUNT_SQL)).scalar() or 0)
            if expected == 0:
                logger.warning("[INDEX] no indexable rows — leaving the database path in place")
                _state = "error"
                _last_error = "catalog has no rows with embeddings"
                return None
            if expected > settings.INDEX_MAX_ROWS:
                msg = (f"catalog has {expected:,} rows, above INDEX_MAX_ROWS "
                       f"({settings.INDEX_MAX_ROWS:,}) — refusing to build")
                logger.error(f"[INDEX] {msg}")
                _state = "error"
                _last_error = msg
                return None

            logger.info(f"[INDEX] building from {expected:,} catalog rows...")
            idx = _load(conn, expected, t0)

        _index = idx
        _state = "ready"
        logger.info(
            f"[INDEX] ready — {idx.rows:,} rows x {idx.dims} dims, "
            f"{idx.bytes / 1048576:.1f} MB, built in {idx.build_seconds:.1f}s"
        )
        return idx

    except Exception as exc:
        # A failed build must never take the API down: the database path is
        # still there and still correct, just slow.
        _state = "error"
        _last_error = f"{type(exc).__name__}: {exc}"
        logger.exception("[INDEX] build failed — falling back to the database path")
        return None
    finally:
        _build_lock.release()


def _load(conn, expected: int, t0: float) -> CatalogIndex:
    """Stream the catalog into a pre-allocated matrix.

    Streaming plus pre-allocation is what keeps peak memory near the 38 MB the
    matrix actually needs, instead of briefly holding the whole 206 MB of vector
    text as Python lists.
    """
    result = conn.execution_options(stream_results=True).execute(text(_BUILD_SQL))

    matrix: np.ndarray | None = None
    meta: list[tuple] = []
    cat_codes: list[int] = []
    cat_names_lower: list[str] = []
    cat_code_of: dict[str, int] = {}
    # The same handful of category names and store emails repeat across tens of
    # thousands of rows; sharing one string object each saves real memory.
    interned: dict[str, str] = {}
    dims = 0
    n = 0
    skipped = 0

    def intern(value):
        if value is None:
            return None
        got = interned.get(value)
        if got is None:
            interned[value] = value
            got = value
        return got

    for partition in result.partitions(_CHUNK):
        for row in partition:
            raw = row.item_vector
            if raw is None:
                skipped += 1
                continue
            try:
                vec = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw
            except (ValueError, TypeError):
                skipped += 1
                continue
            if not vec:
                skipped += 1
                continue

            if matrix is None:
                dims = len(vec)
                matrix = np.empty((expected, dims), dtype=np.float32)
            elif len(vec) != dims:
                # A wrong-width vector would have crashed the old path outright.
                skipped += 1
                continue

            if n == matrix.shape[0]:      # catalog grew mid-build; extend
                matrix = np.concatenate(
                    [matrix, np.empty((max(1024, n // 10), dims), dtype=np.float32)]
                )

            matrix[n] = vec

            # "General" reproduces the old cat_map.get(category_id, "General").
            cat_name = intern(row.category_name or "General")
            code = cat_code_of.get(cat_name)
            if code is None:
                code = len(cat_names_lower)
                cat_code_of[cat_name] = code
                cat_names_lower.append(cat_name.lower())
            cat_codes.append(code)

            meta.append((
                int(row.id),
                row.name,
                row.description,
                float(row.price or 0),
                float(row.stock or 0),
                row.image,
                int(row.store_id) if row.store_id is not None else None,
                int(row.category_id) if row.category_id is not None else None,
                cat_name,
                intern(row.owner_email),
                int(row.duration_minutes) if row.duration_minutes is not None else None,
                bool(row.emergency),
            ))
            n += 1

    if matrix is None:
        matrix = np.empty((0, 0), dtype=np.float32)
    else:
        matrix = matrix[:n]            # trim the tail of the pre-allocation

    if skipped:
        logger.warning(f"[INDEX] skipped {skipped} rows with missing or malformed vectors")

    return CatalogIndex(
        matrix=np.ascontiguousarray(matrix),
        meta=meta,
        cat_codes=np.asarray(cat_codes, dtype=np.int32),
        cat_names_lower=cat_names_lower,
        build_seconds=round(time.perf_counter() - t0, 2),
    )


# ── accessors ─────────────────────────────────────────────────────────────────

def get() -> Optional[CatalogIndex]:
    """The current index, or None if it isn't usable yet."""
    if not settings.RAG_USE_INDEX:
        return None
    return _index


def status() -> dict:
    """Index health, surfaced on /health so the state is observable in production."""
    if not settings.RAG_USE_INDEX:
        return {"state": "disabled"}
    idx = _index
    info: dict = {"state": _state}
    if _last_error:
        info["error"] = _last_error
    if idx is not None:
        info.update({
            "rows": idx.rows,
            "dims": idx.dims,
            "bytes_mb": round(idx.bytes / 1048576, 1),
            "build_seconds": idx.build_seconds,
            "built_at": idx.built_at.isoformat(timespec="seconds"),
        })
    return info


def clear() -> None:
    """Drop the index (tests, and the disabled path)."""
    global _index, _state
    _index = None
    _state = "cold"
