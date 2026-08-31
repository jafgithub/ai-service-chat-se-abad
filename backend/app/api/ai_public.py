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

from app.services import ai_runtime

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/provider", summary="Which engine is switched on, platform wide")
def provider() -> dict:
    return {"provider": ai_runtime.current()}
