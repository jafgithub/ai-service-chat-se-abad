"""Which engine is switched on, readable without a token.

The Service Assistant owns the switch for the whole platform: one admin page
decides which engine answers, and the other two agents follow it. For that to
work they have to be able to read it, and they hold no admin token for this
machine and should not.

What this exposes is one word, "gemini" or "gpu". It names no address, no key
and no instance, and knowing it lets nobody do anything. Writing still needs
the admin token, on the authenticated route next to it.
"""

from fastapi import APIRouter

from app.services import ai_runtime, tracing

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/provider", summary="Which engine is switched on, platform wide")
def provider() -> dict:
    return {"provider": ai_runtime.current()}


@router.get("/trace", summary="The last requests, and the journey each one took")
def trace(limit: int = 20) -> dict:
    """A window on what is happening now, for the live view.

    Unauthenticated for the same reason as `/provider` above: what it returns is
    stage names, timings, counts and which engine answered. There is no question
    text, no reply text and no document in it, by construction rather than by
    filtering, so there is nothing here to protect.
    """
    return {"agent": tracing.AGENT, "traces": tracing.recent(limit)}
