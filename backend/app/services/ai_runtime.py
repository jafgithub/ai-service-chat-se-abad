"""
Which engine answers: Gemini, or our own GPU.

`settings` is a pydantic BaseSettings built once at import (core/config.py), so
`.env` cannot be the switch: changing it would need a restart, and the whole
point is that somebody can flip this from the admin panel a minute before a
meeting starts.

So the switch is a small JSON file, the same way `docs_index` holds the
community registry:

    app/data/ai_runtime.json   {"provider": "gemini", "updated_at": "..."}

One deliberate difference from that registry. It gets away with an explicit
`reload_registry()` because the refresher re-reads it every ten minutes and
nothing breaks if a change is seen late. This has to take effect on the very
next message, and under more than one worker process an in-memory global would
go stale in whichever worker did not serve the POST that changed it. So the
cache is keyed on the file's modification time and a `stat()` happens per read,
which costs nothing and cannot be wrong.

A corrupt or missing file reads as Gemini. That is the safe floor: Gemini is
configured, always up, and costs a fraction of a cent. Falling back to the GPU
by accident would mean answering from a machine that is probably switched off.
"""

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("ai")

#: Beside the community registry and the document index, for the same reason:
#: it is state the application owns and rewrites, not configuration.
RUNTIME_PATH = Path(__file__).resolve().parent.parent / "data" / "ai_runtime.json"

GEMINI = "gemini"
GPU = "gpu"
PROVIDERS = (GEMINI, GPU)

#: (mtime, provider). `None` means nothing has been read yet.
_cache: tuple[float, str] | None = None


def _read() -> str:
    try:
        data = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
        provider = (data.get("provider") or "").strip().lower()
        if provider in PROVIDERS:
            return provider
        logger.warning("[AI] %s names an unknown provider %r", RUNTIME_PATH, provider)
    except FileNotFoundError:
        # Normal on a fresh deployment: nobody has touched the switch yet.
        pass
    except Exception:  # noqa: BLE001 - a broken file must not take the app down
        logger.exception("[AI] runtime switch unreadable")
    return GEMINI


def current() -> str:
    """Which engine is switched on. Cheap enough to call per request."""
    global _cache
    try:
        stamp = RUNTIME_PATH.stat().st_mtime
    except OSError:
        return GEMINI

    if _cache is not None and _cache[0] == stamp:
        return _cache[1]

    provider = _read()
    _cache = (stamp, provider)
    return provider


def set_provider(provider: str) -> str:
    """Switch engines. Raises ValueError for anything we do not offer.

    Written the way docs_index writes the index: to a temporary file, then
    renamed over the real one. A rename is atomic, so a reader can never catch
    a half written file, which is exactly what would happen on the one request
    that arrives while the admin is pressing the button.
    """
    global _cache

    provider = (provider or "").strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Choose one of {', '.join(PROVIDERS)}.")

    payload = {
        "provider": provider,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = RUNTIME_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(RUNTIME_PATH)

    _cache = None  # the next read picks up the new mtime
    logger.info("[AI] engine switched to %s", provider)
    return provider
