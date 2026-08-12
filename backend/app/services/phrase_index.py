"""Match against each phrase a customer might say, not an average of all of them.

The problem this solves, measured rather than assumed. Each service holds one
line of the phrases customers use, and that whole line is embedded as a single
vector. Averaging twenty words dilutes any one of them, so:

    "mobile mechanic"     Mobile mechanic call out    0.601   found
    "flat tyre"           Tyres fitted                0.560   found
    "my car broke down"   Locksmith call out          0.295   wrong trade
    "car will not start"  Electrician call out        0.263   wrong trade

"Car will not start" is written verbatim in the mechanic's description and still
lost to a locksmith, because it is one phrase among many in a single vector.

So each phrase gets its own vector, and a service scores as well as its best
phrase does. Lowering the similarity threshold instead would have surfaced the
locksmith rather than the mechanic, which is worse than answering nothing.

Small enough to hold in memory and rebuild in a moment: 32 services come to a
few hundred phrases.
"""

import logging
import threading
from typing import Optional

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("rag")

# Phrases are comma separated in the description, which is how they are written
# and how a person would list them.
_SEPARATORS = (",", ";", "\n")
# Anything shorter is a fragment rather than a phrase, and matches everything.
_MIN_PHRASE_CHARS = 4

_matrix: Optional[np.ndarray] = None
_service_ids: Optional[np.ndarray] = None
_lock = threading.Lock()


def split_phrases(name: str, description: str) -> list[str]:
    """The things a customer might say for one service.

    The name is included because it is what somebody who knows the trade term
    will type, and the phrases are what everybody else types.
    """
    parts: list[str] = [name.strip()] if name else []
    text_in = description or ""
    for sep in _SEPARATORS[1:]:
        text_in = text_in.replace(sep, _SEPARATORS[0])
    for piece in text_in.split(_SEPARATORS[0]):
        piece = piece.strip()
        if len(piece) >= _MIN_PHRASE_CHARS:
            parts.append(piece)
    # Order preserved, duplicates dropped.
    return list(dict.fromkeys(p for p in parts if p))


def build(db: Session) -> int:
    """Load every phrase vector into memory. Safe to call again."""
    global _matrix, _service_ids

    rows = db.execute(text(
        "SELECT service_id, vector FROM service_phrases ORDER BY id"
    )).fetchall()

    if not rows:
        with _lock:
            _matrix, _service_ids = None, None
        logger.info("[PHRASE] no phrase vectors; falling back to whole descriptions")
        return 0

    import json
    vectors, ids = [], []
    for service_id, blob in rows:
        try:
            vectors.append(np.asarray(json.loads(blob), dtype=np.float32))
            ids.append(int(service_id))
        except (ValueError, TypeError):
            continue

    matrix = np.vstack(vectors) if vectors else None
    with _lock:
        _matrix = matrix
        _service_ids = np.asarray(ids, dtype=np.int64) if ids else None

    logger.info(f"[PHRASE] {len(ids)} phrases across {len(set(ids))} services")
    return len(ids)


def best_scores(query_vector: list[float]) -> dict[int, float]:
    """For each service, how well its best phrase matches. Empty when unbuilt."""
    matrix, ids = _matrix, _service_ids
    if matrix is None or ids is None:
        return {}

    query = np.asarray(query_vector, dtype=np.float32)
    # Both sides are normalised, so a dot product is the cosine.
    sims = matrix @ query

    out: dict[int, float] = {}
    for service_id, score in zip(ids.tolist(), sims.tolist()):
        if score > out.get(service_id, -1.0):
            out[service_id] = float(score)
    return out


def is_ready() -> bool:
    return _matrix is not None
