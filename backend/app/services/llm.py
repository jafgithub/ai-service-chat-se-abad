"""
Whichever engine is switched on, with Gemini underneath it.

Everything in the application that wants a sentence written asks this module,
and this module decides where the work goes:

    switch says gemini                     -> Gemini
    switch says gpu, and the GPU is ready  -> Ollama, on our own hardware
    switch says gpu, and it is not         -> Gemini, and the panel says so

That last line is the whole design. A resident asking about their quiet hours
does not care whose hardware answers, and must never see a broken assistant
because a machine was still booting. What matters is that the admin page tells
the truth about it, so nobody demonstrates "our own GPU" to a room while Gemini
is quietly doing the work.

The readiness check never blocks. It reads a cached value that the admin panel's
own polling keeps fresh, which is running at exactly the moment somebody is
watching the GPU start up. A cold cache reads as not ready, so the very first
question after a restart goes to Gemini, which is the right way round.
"""

import logging
import time
from typing import Optional

from app.services import ai_runtime, gemini_service, ollama_service

logger = logging.getLogger("ai")

#: What actually answered last, and why, for the admin panel. This is a
#: statement about the past, not a prediction: it says what happened, which is
#: the only thing worth showing next to a switch that claims what should happen.
_last: dict = {"served_by": "", "at": 0.0, "fell_back": False, "reason": ""}


def generate(system: str, user: str, max_tokens: int = 300,
             temperature: float = 0.4) -> Optional[str]:
    """Phrase a reply. None on failure, exactly as both providers promise."""
    if ai_runtime.current() == ai_runtime.GPU:
        # Imported here rather than at module scope: gpu_instance imports boto3,
        # and a deployment that has never set up a GPU should not need it.
        from app.services import gpu_instance

        ready = gpu_instance.health()
        if ready["ready"]:
            reply = ollama_service.generate(system, user, max_tokens=max_tokens,
                                            temperature=temperature)
            if reply is not None:
                _record("gpu", False, "")
                return reply
            # It was ready a moment ago and has just failed. Rather than hand
            # the resident nothing, ask Gemini and say plainly that we did.
            reason = "The GPU stopped answering mid-question."
        else:
            reason = ready["reason"]

        logger.info("[AI] switch says GPU but serving from Gemini: %s", reason)
        reply = gemini_service.generate(system, user, max_tokens=max_tokens,
                                        temperature=temperature)
        _record("gemini", True, reason)
        return reply

    reply = gemini_service.generate(system, user, max_tokens=max_tokens,
                                    temperature=temperature)
    _record("gemini", False, "")
    return reply


def _record(served_by: str, fell_back: bool, reason: str) -> None:
    _last.update({"served_by": served_by, "at": time.time(),
                  "fell_back": fell_back, "reason": reason})


def serving() -> dict:
    """What answered the last question, for the admin page."""
    return dict(_last)
