"""Keep what is held in memory in step with what is in the database.

The service catalog is read out of MySQL at start up and kept in memory. It is
correct the moment it is built and slowly stops being correct afterwards: a
service added to the catalog is invisible until the next restart.

So this checks, on a timer, whether it has moved, and rebuilds only if it has.
The check itself is deliberately cheap, one COUNT and one MAX over an indexed
column, because rebuilding costs real time and memory and nothing should be
rebuilt on a hunch.

It used to watch the community document index as well. That moved to its own
application on its own machine, so there is one index here now.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine
from app.services import catalog_index

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
    global _catalog_seen, _last_run

    did = {"catalog": False}
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
