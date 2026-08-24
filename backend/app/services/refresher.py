"""Keep what is held in memory in step with what is on disk and in the database.

Two indexes are built once and then kept in memory: the service catalog, read
out of MySQL at start up, and the document index behind the community
assistant. Both are correct the moment they are built and slowly stop being
correct afterwards. A service added to the catalog, or a document index rebuilt
from the source files, is invisible until the next restart.

So this checks, on a timer, whether either has moved, and rebuilds only the one
that did. The check itself is deliberately cheap: one COUNT and one MAX over an
indexed column, and two file timestamps. Rebuilding costs real time and memory,
which is why nothing is rebuilt on a hunch.

Documents uploaded through the admin screen do not need this. They go into the
live index as part of the upload, and a resident can ask about them a second
later. This is for every other way the data changes.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine
from app.services import catalog_index, docs_index

logger = logging.getLogger("rag")

# The population the catalog index is built from, plus the rows that are waiting
# for an embedding. A service saved in the admin screen has no `item_vector`
# until it is vectorised, so counting those separately is what turns "the
# assistant cannot find the new service" into a line in the log.
_PROBE_SQL = """
    SELECT COUNT(*),
           MAX(updated_at),
           SUM(CASE WHEN item_vector IS NULL THEN 1 ELSE 0 END)
    FROM services
    WHERE status = 1
"""

_thread: Optional[threading.Thread] = None
_catalog_seen: tuple | None = None
_docs_seen: tuple | None = None
_last_run: float = 0.0


def _catalog_stamp() -> tuple | None:
    """How many active services there are and when one last changed.

    None means the question could not be asked, which is not the same as
    nothing having changed: a database that is briefly unreachable must not
    look like a catalog that is up to date.
    """
    try:
        with engine.connect() as conn:
            count, changed, pending = conn.execute(text(_PROBE_SQL)).one()
        return int(count or 0), str(changed or ""), int(pending or 0)
    except Exception as exc:  # noqa: BLE001 - a probe never takes the API down
        logger.warning("[REFRESH] could not read the catalog: %s", type(exc).__name__)
        return None


def refresh_once() -> dict:
    """One pass. Returns what was rebuilt, which is usually nothing."""
    global _catalog_seen, _docs_seen, _last_run

    did = {"catalog": False, "documents": False}
    _last_run = time.time()

    stamp = _catalog_stamp()
    if stamp is not None:
        if _catalog_seen is None:
            # First pass after start up. The index was built moments ago from
            # exactly this data, so record it and rebuild nothing.
            _catalog_seen = stamp
        elif stamp != _catalog_seen:
            count, _, pending = stamp
            logger.info("[REFRESH] catalog moved: %d active services, %d waiting for an embedding",
                        count, pending)
            catalog_index.build()
            _catalog_seen = stamp
            did["catalog"] = True

    stamp = docs_index.stamps()
    if _docs_seen is None:
        _docs_seen = stamp
    elif stamp != _docs_seen:
        logger.info("[REFRESH] the document index changed on disk, reading it again")
        docs_index.reload_index()
        docs_index.reload_registry()
        _docs_seen = stamp
        did["documents"] = True

    return did


def status() -> dict:
    return {
        "every_minutes": settings.REFRESH_MINUTES,
        "running": bool(_thread and _thread.is_alive()),
        "last_run": _last_run or None,
    }


def _loop(seconds: int) -> None:
    while True:
        time.sleep(seconds)
        try:
            refresh_once()
        except Exception:  # noqa: BLE001 - one bad pass must not end the timer
            logger.exception("[REFRESH] pass failed, will try again")


def start() -> None:
    """Start the timer. Safe to call twice; the second call does nothing."""
    global _thread

    if settings.REFRESH_MINUTES <= 0:
        logger.info("[REFRESH] switched off (REFRESH_MINUTES=0)")
        return
    if _thread and _thread.is_alive():
        return

    # Take the first reading now, so the first pass compares against the state
    # the indexes were actually built from rather than against nothing.
    refresh_once()

    seconds = settings.REFRESH_MINUTES * 60
    _thread = threading.Thread(target=_loop, args=(seconds,), name="refresher", daemon=True)
    _thread.start()
    logger.info("[REFRESH] checking every %d minutes", settings.REFRESH_MINUTES)
