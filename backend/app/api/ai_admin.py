"""
The engine switch, and the button that starts the GPU.

Four endpoints, all admin only. `Depends(require_admin)` rather than admin.py's
own local `_require_token`, because require_admin accepts either the shared
header or a signed in admin account, and there is no reason for a new surface to
inherit the older of the two.

Everything is POST rather than PUT or PATCH. Not taste: `apiClient.put` and
`.patch` in the frontend take no headers argument, so they cannot carry
X-Admin-Token at all. get, post, del and postForm can.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import require_admin
from app.core.config import settings
from app.services import ai_runtime, llm

logger = logging.getLogger("ai")

router = APIRouter(prefix="/admin/ai", tags=["admin"])


class ProviderIn(BaseModel):
    provider: str


def _status() -> dict:
    """Everything the panel draws, in one call.

    The health reading is forced fresh here (max_age=0) on purpose. This is the
    one place where somebody is definitely watching, and the value it writes is
    the same cache that llm.generate reads without blocking, so the panel's
    polling is what keeps the request path fast.
    """
    from app.services import gpu_instance

    gpu = gpu_instance.state()
    ready = gpu_instance.health(max_age=0)

    return {
        # What is switched on, versus what actually answered the last question.
        # Two different facts, and showing only the first is how a demo ends up
        # claiming credit for Gemini's work.
        "provider": ai_runtime.current(),
        "serving": llm.serving(),
        "gpu": {
            "configured": gpu_instance.is_configured(),
            "state": gpu["state"],
            "ip": gpu["ip"],
            "since": gpu["since"],
            "ready": ready["ready"],
            "reason": ready["reason"],
            "error": gpu["error"],
            "endpoint": gpu_instance.endpoint(),
        },
        "model": settings.OLLAMA_MODEL,
        "idle_minutes": settings.GPU_IDLE_MINUTES,
        "region": settings.AWS_REGION,
    }


@router.get("/status", summary="Which engine is on, and what the GPU is doing")
def status(_: bool = Depends(require_admin)):
    return _status()


@router.post("/provider", summary="Switch between Gemini and our own GPU")
def set_provider(payload: ProviderIn, _: bool = Depends(require_admin)):
    try:
        ai_runtime.set_provider(payload.provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _status()


@router.post("/gpu/start", summary="Start the GPU")
def start(_: bool = Depends(require_admin)):
    from app.services import gpu_instance

    result = gpu_instance.start()
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result["error"])
    return _status()


@router.post("/gpu/stop", summary="Stop the GPU")
def stop(_: bool = Depends(require_admin)):
    from app.services import gpu_instance

    result = gpu_instance.stop()
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result["error"])
    return _status()
