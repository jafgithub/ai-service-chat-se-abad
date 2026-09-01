"""
RAG Pipeline
────────────
1. Embed each service's text using sentence-transformers (local, free).
2. Store/update the vector in items.item_vector.
3. At query time: embed the user query → cosine-similarity against all service vectors.
4. Return top-K most relevant services.

Step 3 runs against the in-memory catalog index (app/services/catalog_index.py),
which holds the embeddings in RAM so a search never re-reads the catalog. The
original database-scanning implementation is kept below as `_search_products_db`
and is used automatically whenever the index is unavailable, still building, or
switched off with RAG_USE_INDEX — so search always works, it just gets slow.
"""

import json
import logging
import re
import time
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import numpy as np

# How many result lines a single search may log. With top_k=None a search can
# match thousands of services, and one log line each buries the journal.
_LOG_RESULT_LIMIT = 10

_DEAL_INTENT = re.compile(
    r"\b(best deal|cheapest|cheap|lowest price|affordable|budget|best price|"
    r"best value|most affordable|inexpensive|on sale|discount|bargain)\b",
    re.IGNORECASE,
)

from app.core.config import settings
from app.models.service import Service
from app.services import phrase_index, tracing
from app.services import catalog_index
from app.services.media import serialized_image

logger = logging.getLogger("rag")

_model = None


def _get_model():
    global _model
    if _model is None:
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info("[RAG] Loading sentence-transformer model: all-MiniLM-L6-v2")
        t0 = time.perf_counter()
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        elapsed = time.perf_counter() - t0
        logger.info(f"[RAG] Model loaded in {elapsed:.2f}s")
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return _model


def _enrich_products(services: list[Service], db: Session) -> None:
    """Attach _category_name, _unit_name, _owner_email to each service via JOIN."""
    if not services:
        return

    cat_ids = list({p.category_id for p in services if p.category_id})
    store_ids = list({p.store_id for p in services if p.store_id})

    cat_map: dict[int, str] = {}
    store_email_map: dict[int, str] = {}

    if cat_ids:
        rows = db.execute(
            text("SELECT id, name FROM categories WHERE id IN :ids"),
            {"ids": tuple(cat_ids) if len(cat_ids) > 1 else (cat_ids[0], cat_ids[0])},
        ).fetchall()
        cat_map = {r[0]: r[1] for r in rows}

    if store_ids:
        rows = db.execute(
            text("SELECT id, email FROM stores WHERE id IN :ids"),
            {"ids": tuple(store_ids) if len(store_ids) > 1 else (store_ids[0], store_ids[0])},
        ).fetchall()
        store_email_map = {r[0]: r[1] for r in rows}

    for p in services:
        p._category_name = cat_map.get(p.category_id, "General")
        p._unit_name = "unit"
        p._owner_email = store_email_map.get(p.store_id)


def _product_text(service: Service) -> str:
    category = getattr(service, "_category_name", None) or str(service.category_id or "")
    parts = [service.name or ""]
    if category:
        parts.append(category)
    if service.description:
        parts.append(service.description)
    parts.append(f"Price: {service.price}")
    return " | ".join(filter(None, parts))


def _bulk_cosine_similarity(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query_vec and every row in matrix using numpy."""
    # query_vec is already normalized (normalize_embeddings=True in embed_text)
    # so dot service == cosine similarity
    return matrix @ query_vec


def embed_text(text_input: str) -> list[float]:
    model = _get_model()
    t0 = time.perf_counter()
    vector = model.encode(text_input, normalize_embeddings=True)
    elapsed = time.perf_counter() - t0
    result = vector.tolist()
    logger.info(f"[VECTOR] Embedded in {elapsed*1000:.1f}ms | dims={len(result)}")
    return result


def index_all_products(db: Session) -> int:
    """Embed every active service that has no vector yet."""
    services = db.query(Service).filter(
        Service.status == True,
        Service.item_vector == None,
    ).all()

    _enrich_products(services, db)
    logger.info(f"[RAG] Indexing {len(services)} unembedded services...")
    count = 0
    for service in services:
        service.item_vector = embed_text(_product_text(service))
        count += 1

    db.commit()
    logger.info(f"[RAG] Indexing complete — {count} services embedded")
    return count


def reindex_product(service: Service, db: Session) -> None:
    """Re-embed a single service."""
    _enrich_products([service], db)
    service.item_vector = embed_text(_product_text(service))
    db.commit()


def search_products(
    query: str,
    db: Session,
    top_k: Optional[int] = None,
    category_filter: Optional[str] = None,
    # 0.30, not the 0.35 the shop uses. That number was tuned against 25,631
    # products, where a loose match buries the right one. Here there are 32
    # services, and the failure that matters is the opposite: a customer saying
    # "my car broke down" and being told we do nothing of the sort. A service
    # description is also one long line of phrases embedded as a single vector,
    # which dilutes any one of them, so symptom phrases score lower than they
    # read as though they should.
    min_similarity: float = 0.30,
) -> list[dict]:
    """Find the services most relevant to `query`.

    Served from the in-memory index when it's ready, otherwise from the database.
    Both paths score and order results identically; only the speed differs.
    """
    t0 = time.perf_counter()
    logger.info(f"[RAG] SEARCH: \"{query}\" | category={category_filter} | top_k={top_k}")

    query_vector = embed_text(query)
    is_deal_query = bool(_DEAL_INTENT.search(query))

    # A service scores as well as its best phrase does, not as its average.
    # See phrase_index for the measurements that made this necessary; without
    # it, "car will not start" lost to a locksmith.
    phrase_best = phrase_index.best_scores(query_vector)
    # Ask for more than needed, then re-rank, because a service the whole
    # description scored below the threshold can still have one phrase that
    # matches squarely and belongs at the top.
    floor = min(min_similarity, 0.18) if phrase_best else min_similarity
    # The caller may ask for everything by passing no limit, which is what the
    # chat pipeline does. Widening a limit that is not there is what broke this
    # the first time.
    widened = None if top_k is None else max(top_k * 4, 20)

    index = catalog_index.get()
    if index is not None:
        results = index.search(
            query_vector, widened, category_filter, floor, is_deal_query
        )
        via, scanned = "index", index.rows
    else:
        results = _search_products_db(
            query, db, widened, category_filter, floor,
            query_vector=query_vector, is_deal_query=is_deal_query,
        )
        via, scanned = "db", None

    if phrase_best:
        for r in results:
            best = phrase_best.get(int(r["id"]))
            if best is not None and best > r["similarity"]:
                r["similarity"] = best
        results = [r for r in results if r["similarity"] >= min_similarity]
        results.sort(key=lambda r: r["similarity"], reverse=True)
        if top_k is not None:
            results = results[:top_k]

    # A service with no name cannot be offered to anyone. At least one exists
    # (id 194438), and a search for "titanium bicycle frame" surfaced it: the
    # assistant said "1. : $14.29" and the card showed a price with no title.
    #
    # Dropped here, after both search paths have joined, so the numbered list in
    # the reply and the cards on screen are built from the same rows. Filtering
    # in the browser instead would renumber the cards and "add item 2" would
    # then add something other than the item labelled 2.
    named = [r for r in results if (r.get("name") or "").strip()]
    if len(named) != len(results):
        logger.info(f"[RAG] dropped {len(results) - len(named)} unnamed service(s)")
        results = named

    for r in results[:_LOG_RESULT_LIMIT]:
        logger.info(f"[RAG]   #{r['id']} \"{r['name']}\" score={r['similarity']:.4f} "
                    f"price=${r['price_per_unit']}")
    if len(results) > _LOG_RESULT_LIMIT:
        logger.info(f"[RAG]   ... and {len(results) - _LOG_RESULT_LIMIT} more")

    took_ms = (time.perf_counter() - t0) * 1000
    scanned_txt = f"scanned={scanned:,} " if scanned is not None else ""
    logger.info(
        f"[RAG] SEARCH \"{query}\" via={via} {scanned_txt}hits={len(results)} "
        f"deal={is_deal_query} took={took_ms:.0f}ms"
    )
    # Counts and the score floor, never the query. See services/tracing.py on
    # why a trace carries nothing anybody typed.
    # Naming the path matters as much as the count. The in-memory index answers
    # in single digit milliseconds and the database path takes over a second,
    # so a slow leg here is explained by which one served it rather than
    # looking like an unexplained stall.
    scope = (f"{scanned:,} services in memory" if scanned is not None
             else "scored in the database")
    tracing.record("retrieve", "Searching the catalogue", round(took_ms),
                   f"{scope}, {len(results)} above {min_similarity}")
    return results


def _search_products_db(
    query: str,
    db: Session,
    top_k: Optional[int] = None,
    category_filter: Optional[str] = None,
    # 0.30, not the 0.35 the shop uses. That number was tuned against 25,631
    # products, where a loose match buries the right one. Here there are 32
    # services, and the failure that matters is the opposite: a customer saying
    # "my car broke down" and being told we do nothing of the sort. A service
    # description is also one long line of phrases embedded as a single vector,
    # which dilutes any one of them, so symptom phrases score lower than they
    # read as though they should.
    min_similarity: float = 0.30,
    query_vector: Optional[list[float]] = None,
    is_deal_query: Optional[bool] = None,
) -> list[dict]:
    """The original catalog-scanning search.

    Kept as the fallback for when the index isn't available, and as the reference
    implementation the parity check in benchmark_search.py measures against.
    """
    if query_vector is None:
        query_vector = embed_text(query)
    if is_deal_query is None:
        is_deal_query = bool(_DEAL_INTENT.search(query))

    q = db.query(Service).filter(
        Service.status == True,
        Service.item_vector != None,
    )
    services = q.all()
    logger.info(f"[RAG] {len(services)} services with embeddings")

    _enrich_products(services, db)

    # apply category filter first
    if category_filter:
        services = [
            p for p in services
            if category_filter.lower() in (getattr(p, "_category_name", "") or "").lower()
        ]

    # parse vectors and build matrix for bulk numpy scoring
    vecs = []
    valid_products = []
    for p in services:
        vec = p.item_vector
        if isinstance(vec, str):
            vec = json.loads(vec)
        if vec:
            vecs.append(vec)
            valid_products.append(p)

    if not vecs:
        return []

    matrix = np.array(vecs, dtype=np.float32)
    query_arr = np.array(query_vector, dtype=np.float32)
    # normalize query (services are already normalized from embed_text)
    query_arr = query_arr / (np.linalg.norm(query_arr) + 1e-10)

    sim_scores = _bulk_cosine_similarity(query_arr, matrix)

    # filter by min similarity
    scored = [
        (float(sim_scores[i]), valid_products[i])
        for i in range(len(valid_products))
        if sim_scores[i] >= min_similarity
    ]

    # blend a price score in when the customer asked for a deal
    if is_deal_query and scored:
        logger.info("[RAG] Deal intent detected — applying price scoring")
        prices = [float(p.price) for _, p in scored]
        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price or 1.0

        blended = []
        for sim, p in scored:
            price_score = 1.0 - (float(p.price) - min_price) / price_range
            final = (sim * 0.6) + (price_score * 0.4)
            blended.append((final, sim, p))
        blended.sort(key=lambda x: x[0], reverse=True)
        top = blended if top_k is None else blended[:top_k]

        results = []
        for final, sim, p in top:
            category = getattr(p, "_category_name", None) or str(p.category_id or "")
            results.append({
                "id":             p.id,
                "name":           p.name,
                "category":       category,
                "description":    p.description or "",
                "unit":           "unit",
                "price_per_unit": float(p.price),
                "stock":          float(p.stock or 0),
                "image_url":      serialized_image(p),
                "owner_email":    getattr(p, "_owner_email", None),
                "duration_minutes": p.duration_minutes,
                "emergency":      bool(p.emergency),
                "similarity":     round(final, 4),
            })
    else:
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored if top_k is None else scored[:top_k]

        results = []
        for score, p in top:
            category = getattr(p, "_category_name", None) or str(p.category_id or "")
            results.append({
                "id":             p.id,
                "name":           p.name,
                "category":       category,
                "description":    p.description or "",
                "unit":           "unit",
                "price_per_unit": float(p.price),
                "stock":          float(p.stock or 0),
                "image_url":      serialized_image(p),
                "owner_email":    getattr(p, "_owner_email", None),
                "duration_minutes": p.duration_minutes,
                "emergency":      bool(p.emergency),
                "similarity":     round(score, 4),
            })

    return results
