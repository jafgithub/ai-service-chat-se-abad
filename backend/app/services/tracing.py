"""The journey a single request took, measured rather than guessed.

Every number here comes from `time.perf_counter` around real work. Nothing is
estimated, because the whole point is to show a client what actually happened
inside a request, and a plausible-looking invented figure is worse than no
figure at all.

Two consumers, one shape:

  * the reply to the person who asked carries their own trace, so the interface
    can show the journey while they wait;
  * `recent()` backs a public feed for the live view, and holds the last 50 in
    memory. No database and no disk: this is a window on what is happening now,
    not a record, and a request should never pay for a write it does not need.

Nothing in a trace is private, and that is by construction rather than by
filtering afterwards. Stage details carry counts and model names, never the
question, the reply, a document, or anything a person typed. That is why the
same object can be handed to the asker and to the public feed without a second
redacted version to keep in step.

The context variable rather than a parameter threaded through twenty function
signatures: retrieval and the engine call sit four and five frames deep in
pipelines shared with the voice endpoint, and passing a recorder through all of
them would have touched far more code than the feature is worth. Context
variables are the right tool for exactly this, and they follow a sync endpoint
into Starlette's worker thread as well as an async one.

Every function here swallows its own errors. Telemetry that can break a reply
is not worth having.
"""

import contextvars
import logging
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager

logger = logging.getLogger("trace")

#: Which of the three agents this is. It travels with every trace so one live
#: view can show all three side by side.
AGENT = "service"

#: How many journeys the live feed can look back over.
MAX_KEPT = 50

_current: contextvars.ContextVar = contextvars.ContextVar("current_trace", default=None)
_recent: deque = deque(maxlen=MAX_KEPT)
_lock = threading.Lock()


class _Stage:
    """Handed out by `stage()` so the caller can fill in the detail it only
    knows once the work has been done, such as how many things it found."""

    __slots__ = ("detail",)

    def __init__(self) -> None:
        self.detail = ""


def start() -> None:
    """Begin a trace for this request. Safe to call twice; the second wins."""
    try:
        _current.set({
            "id": uuid.uuid4().hex[:12],
            "agent": AGENT,
            "at": time.time(),
            "total_ms": 0,
            # "none" until something actually calls a model. A request that was
            # answered from the catalogue without a model is a real and common
            # outcome, and the view is meant to show it rather than imply an
            # engine ran.
            "engine": {"chosen": "", "used": "none", "fell_back": False,
                       "reason": "", "model": ""},
            "stages": [],
            "_started": time.perf_counter(),
        })
    except Exception:  # noqa: BLE001 - a reply must never fail over telemetry
        logger.debug("[TRACE] could not start", exc_info=True)


@contextmanager
def stage(name: str, label: str):
    """Time one leg of the journey.

        with tracing.stage("retrieve", "Searching the documents") as s:
            hits = search(...)
            s.detail = f"{len(hits)} of {total} above the floor"
    """
    marker = _Stage()
    started = time.perf_counter()
    try:
        yield marker
    finally:
        try:
            trace = _current.get()
            if trace is not None:
                trace["stages"].append({
                    "name": name,
                    "label": label,
                    "ms": int(round((time.perf_counter() - started) * 1000)),
                    "detail": marker.detail,
                })
        except Exception:  # noqa: BLE001
            logger.debug("[TRACE] could not record stage %s", name, exc_info=True)


def record(name: str, label: str, ms: int, detail: str = "") -> None:
    """Record a leg that already measured itself.

    Retrieval times its own work and logs the figure; asking it to also sit
    inside a context manager would measure the same thing twice and disagree
    with its own log line by a millisecond or two. This takes the number it
    already has.
    """
    try:
        trace = _current.get()
        if trace is None:
            return
        trace["stages"].append({"name": name, "label": label,
                                "ms": int(ms), "detail": detail})
    except Exception:  # noqa: BLE001
        logger.debug("[TRACE] could not record leg %s", name, exc_info=True)


def engine(chosen: str | None = None, used: str | None = None,
           fell_back: bool | None = None, reason: str | None = None,
           model: str | None = None) -> None:
    """Record which engine was asked for and which one answered."""
    try:
        trace = _current.get()
        if trace is None:
            return
        facts = trace["engine"]
        if chosen is not None:
            facts["chosen"] = chosen
        if used is not None:
            facts["used"] = used
        if fell_back is not None:
            facts["fell_back"] = fell_back
        if reason is not None:
            facts["reason"] = reason
        if model is not None:
            facts["model"] = model
    except Exception:  # noqa: BLE001
        logger.debug("[TRACE] could not record the engine", exc_info=True)


def finish(chosen_when_no_engine_ran: str = "gemini") -> dict | None:
    """Close the trace, keep it for the feed, and hand it back for the reply.

    `chosen_when_no_engine_ran` fills in the switch position for a request that
    never called a model, where nothing else would have recorded it. The caller
    passes a value it can read without blocking: a local file on this machine,
    or a cached answer. Never a network call, which would put a timeout on the
    end of every reply.
    """
    try:
        trace = _current.get()
        if trace is None:
            return None
        started = trace.pop("_started", None)
        if started is not None:
            trace["total_ms"] = int(round((time.perf_counter() - started) * 1000))
        if not trace["engine"]["chosen"]:
            trace["engine"]["chosen"] = chosen_when_no_engine_ran
        _current.set(None)
        with _lock:
            _recent.append(trace)
        return trace
    except Exception:  # noqa: BLE001
        logger.debug("[TRACE] could not finish", exc_info=True)
        return None


def recent(limit: int = 20) -> list[dict]:
    """The most recent journeys, newest first."""
    try:
        with _lock:
            kept = list(_recent)
        kept.reverse()
        return kept[:max(1, min(int(limit), MAX_KEPT))]
    except Exception:  # noqa: BLE001
        logger.debug("[TRACE] could not read the feed", exc_info=True)
        return []
