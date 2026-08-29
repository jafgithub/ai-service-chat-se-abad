"""
Thin Ollama client, used when the AI engine is switched to our own GPU.

One job, deliberately. `gemini_service` does three: phrasing, speech-to-text and
text-to-speech. This does only the first, because Ollama does only the first.
Voice stays on Gemini, and `voice_service` is untouched by any of this.

The contract is copied from `gemini_service.generate` on purpose, so the two are
interchangeable behind `llm.py`:

    generate(system, user, max_tokens=300, temperature=0.4) -> str | None

None means "no answer", never an exception. Every caller in this codebase
already treats that as "fall back to the deterministic text", which is the whole
reason a second provider can be dropped in at all.

No client object is held at module level. The address of the GPU changes every
time it is stopped and started, so it is resolved per call.
"""

import logging
import time
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("ai")


def is_configured() -> bool:
    """Whether there is a GPU to talk to at all.

    An instance id is enough: the address is read from the AWS API rather than
    configured, because a stopped instance comes back with a different one.
    OLLAMA_URL is the manual override, for testing against a box by hand.
    """
    return bool(settings.OLLAMA_URL or settings.GPU_INSTANCE_ID)


def _base_url() -> str:
    """Where Ollama is, this minute.

    The override wins so a developer can point at localhost without touching
    AWS. Otherwise ask the instance itself; see gpu_instance.endpoint.
    """
    if settings.OLLAMA_URL:
        return settings.OLLAMA_URL.rstrip("/")

    from app.services import gpu_instance
    return (gpu_instance.endpoint() or "").rstrip("/")


def generate(system: str, user: str, max_tokens: int = 300,
             temperature: float = 0.4) -> Optional[str]:
    """Phrase a reply on our own hardware. None on any failure.

    `num_predict` is Ollama's name for max_tokens. Unlike Gemini there is no
    thinking budget to leave headroom for, so it is passed straight through.
    """
    base = _base_url()
    if not base:
        logger.warning("[OLLAMA] no address for the GPU; nothing to call")
        return None

    payload = {
        "model": settings.OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }

    t0 = time.perf_counter()
    try:
        resp = httpx.post(f"{base}/api/chat", json=payload,
                          timeout=settings.OLLAMA_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        # The instance is stopping, or the security group is wrong, or the model
        # is still loading. All of them are "ask Gemini instead".
        logger.warning(f"[OLLAMA] request failed: {type(exc).__name__}")
        return None

    if resp.status_code != 200:
        logger.warning(f"[OLLAMA] HTTP {resp.status_code}: {resp.text[:180]}")
        return None

    try:
        data = resp.json()
    except ValueError:
        # Not theoretical. A stopped instance whose address has been reassigned
        # answers with somebody else's HTML, with a perfectly good 200 on it.
        logger.warning("[OLLAMA] 200 response was not valid JSON; falling back")
        return None

    text = ((data.get("message") or {}).get("content") or "").strip()
    logger.info(
        f"[OLLAMA] reply in {(time.perf_counter() - t0) * 1000:.0f}ms "
        f"({len(text)} chars, {settings.OLLAMA_MODEL})"
    )
    return text or None


def is_up(base: str, timeout: float = 2.0) -> bool:
    """Is Ollama answering at this address? Used by the health probe.

    Deliberately cheap and deliberately short: this is the question "can we send
    a resident's question here", and a slow answer to it is the same as no.
    """
    if not base:
        return False
    try:
        resp = httpx.get(f"{base.rstrip('/')}/api/tags", timeout=timeout)
    except httpx.HTTPError:
        return False
    return resp.status_code == 200
