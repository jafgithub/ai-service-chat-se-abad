import logging
import sys
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.services import phrase_index
from app.db.database import engine, Base
from app.models import (  # noqa: F401 - imported so create_all registers every table
    Service, Customer, Job, JobLine, Payment, ChatSession, CartItem, Appointment,
)
from app.api import admin, chat, jobs, payments, services, cart, voice, media, booking


def setup_logging():
    fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)

    # Explicit allowlist: a logger missing from it has its output silently
    # discarded, so anything new that logs has to be added here too.
    for name in ("rag", "ai", "chat", "jobs", "payments", "booking", "voice",
                 "uvicorn.access"):
        log = logging.getLogger(name)
        log.setLevel(logging.DEBUG)
        log.addHandler(handler)
        log.propagate = False

setup_logging()


_model_state: dict = {"loaded": False}


def _warmup() -> None:
    """Pay the two one-off start-up costs here instead of on a shopper's first search.

    1. The sentence-transformer takes 15-100s to load, and used to load lazily —
       so whoever searched first after a restart absorbed all of it.
    2. The catalog index reads every embedding once; after this, searches never
       touch the database.

    Runs on a background thread so the API serves traffic while it works. Until
    it finishes, searches use the original database path — slower, but correct.
    """
    log = logging.getLogger("rag")
    try:
        from app.services import catalog_index, rag

        t0 = time.perf_counter()
        rag.embed_text("warm up")
        _model_state.update(loaded=True, load_seconds=round(time.perf_counter() - t0, 2))
        log.info(f"[WARMUP] embedding model ready in {_model_state['load_seconds']:.1f}s")

        catalog_index.build()
        # Phrases live in their own small index; without this a restart falls
        # back to whole-description matching and the symptom phrases stop
        # working again.
        from app.db.database import SessionLocal
        _db = SessionLocal()
        try:
            phrase_index.build(_db)
        except Exception as exc:  # noqa: BLE001 - never block start up on this
            log.warning(f"[PHRASE] not loaded: {type(exc).__name__}")
        finally:
            _db.close()
        log.info("[WARMUP] complete")
    except Exception:
        # Warm-up is an optimisation, never a startup requirement.
        log.exception("[WARMUP] failed — the API keeps serving via the database path")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    if settings.WARMUP_ON_STARTUP:
        threading.Thread(target=_warmup, name="warmup", daemon=True).start()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "https://d3furrbwf3rlfc.cloudfront.net", "https://d2cvowfviwj76s.cloudfront.net"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router,    prefix="/api/v1")
app.include_router(chat.router,     prefix="/api/v1")
app.include_router(jobs.router,     prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(services.router, prefix="/api/v1")
app.include_router(cart.router,     prefix="/api/v1")
app.include_router(voice.router,    prefix="/api/v1")
app.include_router(media.router,    prefix="/api/v1")
app.include_router(booking.router,  prefix="/api/v1")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Last-resort safety net: log the full traceback, return a friendly message
    instead of a raw 'Internal Server Error' to the user."""
    logging.getLogger("chat").exception(
        "Unhandled error on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end. Please try again."},
    )


@app.get("/health")
def health():
    """Liveness plus search-readiness.

    `index.state` tells you which path searches are currently taking:
    `ready` means they're served from memory, anything else means they're
    falling back to the (correct but slow) database scan.
    """
    from app.services import catalog_index

    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "index": catalog_index.status(),
        "model": _model_state,
    }