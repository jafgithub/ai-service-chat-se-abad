"""The community documents, held in memory and searched by meaning.

Eighty one chunks and 384 dimensions is 124 KB of floats. Holding it in RAM and
doing the whole search with one matrix multiply is both simpler and faster than
any store we could add, and it follows what `catalog_index` already does for
the service catalogue, so there is one pattern here rather than two.

The index is built offline by `scripts/build_doc_index.py` and shipped as JSON.
Nothing is embedded at startup except the query, and the model is the same
`all-MiniLM-L6-v2` that `rag.py` already loads, so this costs no new dependency,
no API call and no extra memory for weights.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("docs")

INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "serenity_docs.json"

# Below this, the best chunk is not really about the question. Chosen by running
# the real questions in tests/test_docs_index.py: genuine questions score 0.35
# to 0.75, and things the documents say nothing about ("do you offer wifi",
# "what time does the pool close" where no closing time is stated) sit under
# 0.30. The gap is comfortable, and the cost of being wrong is asymmetric: a
# refusal is a small annoyance, an invented rule about someone's home is not.
MIN_SCORE = 0.30

# The community the assistant speaks for. Chunks from anywhere else are indexed
# but not searched unless the question names that place, because the client sent
# a City of Lauderdale Lakes code handbook along with the Serenity documents and
# Serenity Point is in Miami Lakes. A resident asking about their own bin day
# must not be answered out of another city's ordinances.
HOME_COMMUNITY = "serenity"

_lock = threading.Lock()
_vectors: Optional[np.ndarray] = None
_chunks: list[dict] = []


def _load() -> bool:
    global _vectors, _chunks
    if _vectors is not None:
        return True
    with _lock:
        if _vectors is not None:
            return True
        if not INDEX_PATH.exists():
            logger.warning("[DOCS] no index at %s; the assistant will refuse everything", INDEX_PATH)
            return False
        data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        chunks = data.get("chunks") or []
        if not chunks:
            return False
        _vectors = np.asarray([c.pop("vector") for c in chunks], dtype=np.float32)
        _chunks = chunks
        logger.info("[DOCS] %d chunks loaded, %d dimensions", len(_chunks), _vectors.shape[1])
        return True


def _embed(query: str) -> Optional[np.ndarray]:
    """The query as a vector, from the model `rag` already holds open.

    Through `rag.embed_text` rather than a SentenceTransformer of our own, and
    that is not a stylistic preference. The first version loaded its own copy,
    which is roughly 90 MB of weights plus torch's allocator on top, and the
    `plumber` service runs under `MemoryMax=700M` and already sits at about
    500 MB. Every question failed with "embedding model unavailable" on the live
    box while passing in the test suite, because pytest runs outside the cgroup
    and without the rest of the app loaded.

    The index was built with the same model and `normalize_embeddings=True`, so
    the vectors are directly comparable and a dot product is the cosine.
    """
    from app.services import rag

    try:
        return np.asarray(rag.embed_text(query), dtype=np.float32)
    except Exception:  # noqa: BLE001 - a missing model must not 500 the route
        logger.exception("[DOCS] embedding model unavailable")
        return None


def ready() -> bool:
    return _load()


def _allowed(query: str) -> set:
    """Which communities this question may be answered from.

    Home only, unless the question names somewhere else, in which case that
    place is added rather than substituted: "how does Lauderdale Lakes handle
    bins" is a fair question and so is comparing the two.
    """
    lowered = query.lower()
    allowed = {HOME_COMMUNITY}
    for chunk in _chunks:
        community = chunk.get("community", HOME_COMMUNITY)
        if community != HOME_COMMUNITY and community in lowered:
            allowed.add(community)
    return allowed


def search(query: str, k: int = 4) -> list[dict]:
    """The k passages closest to the question, best first, above MIN_SCORE.

    Returns an empty list when nothing clears the floor, and the caller treats
    that as "the documents do not answer this" without asking a model anything.
    That is the whole grounding guarantee: no passages, no answer, no chance to
    invent one.
    """
    query = (query or "").strip()
    if len(query) < 3 or not _load():
        return []
    vec = _embed(query)
    if vec is None:
        return []

    scores = _vectors @ vec
    allowed = _allowed(query)
    # Ranked over everything, then filtered, so a strong match in another
    # community cannot push a weaker home match out of the top k.
    order = np.argsort(-scores)
    top = [i for i in order
           if _chunks[i].get("community", HOME_COMMUNITY) in allowed][: max(k, 1)]
    hits = [
        {**_chunks[i], "score": round(float(scores[i]), 4)}
        for i in top
        if scores[i] >= MIN_SCORE
    ]
    logger.info(
        "[DOCS] %r -> %d hit(s), best %.3f, scope=%s",
        query[:60], len(hits), float(scores[top[0]]) if top else 0.0,
        ",".join(sorted(allowed)),
    )
    return hits
