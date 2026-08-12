"""Coalesce index rebuilds into one, after things go quiet.

The catalog index is an immutable snapshot with no append: making a new product
searchable means rebuilding all 25,631 rows, which is a measured 15 to 26
seconds. Adopting five products one at a time would otherwise cost five full
rebuilds, most of them thrown away before they finished.

So a rebuild is *requested* rather than performed. A single timer waits for the
requests to stop arriving and then rebuilds once. Adding ten products in quick
succession costs one rebuild, not ten.

The delay is the tradeoff: an adopted product is in the cart and orderable
immediately, and only becomes *searchable* once the rebuild lands.
"""

import logging
import threading

from app.core.config import settings
from app.services import catalog_index

logger = logging.getLogger("shopping")

_lock = threading.Lock()
_timer: threading.Timer | None = None
_pending = 0


def _run() -> None:
    global _timer, _pending
    with _lock:
        count = _pending
        _pending = 0
        _timer = None
    logger.info(f"[INDEX] rebuilding after {count} change(s)")
    try:
        catalog_index.build()
    except Exception as exc:  # noqa: BLE001 - a failed rebuild leaves the old index serving
        logger.warning(f"[INDEX] deferred rebuild failed: {type(exc).__name__}: {exc}")


def request() -> None:
    """Ask for a rebuild soon. Repeated calls push the deadline out.

    Daemon timer: a rebuild is never worth holding shutdown open for, since the
    index is rebuilt from the database on the next boot anyway.
    """
    global _timer, _pending
    delay = settings.REINDEX_DEBOUNCE_SECONDS
    if delay <= 0:
        _run()
        return

    with _lock:
        _pending += 1
        if _timer is not None:
            _timer.cancel()
        _timer = threading.Timer(delay, _run)
        _timer.daemon = True
        _timer.start()
    logger.info(f"[INDEX] rebuild requested, waiting {delay}s for quiet")


def status() -> dict:
    with _lock:
        return {"pending_changes": _pending, "rebuild_scheduled": _timer is not None}
