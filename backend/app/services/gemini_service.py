"""
Thin Gemini REST client (generativelanguage API) used when the LLM/speech
provider is set to "gemini" — e.g. the local demo with the Gemini key.

Three jobs:
  • generate()   — phrase a reply (plain text), mirroring the OpenAI phrasing role.
  • transcribe() — speech-to-text from WAV audio (inline base64).
  • speak()      — text-to-speech, returned as WAV the browser can play directly.

The API key is read from settings (which loads it from .env) and is never logged.
`thinkingBudget: 512` is the POC-proven floor that keeps gemini-flash-latest from
spending many seconds "thinking" (a budget of 0 is rejected by the model).
"""

import base64
import io
import logging
import re
import time
import wave
from collections import OrderedDict
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("ai")

_TRANSCRIBE_PROMPT = (
    "Transcribe only the spoken words in this audio. Return plain text only. "
    "If there is no intelligible speech, return an empty string."
)


def is_configured() -> bool:
    return bool(settings.GEMINI_API_KEY)


def _endpoint(model: str | None = None) -> str:
    name = model or settings.GEMINI_MODEL
    return f"{settings.GEMINI_BASE_URL.rstrip('/')}/models/{name}:generateContent"


def _post(payload: dict, timeout: int, model: str | None = None) -> Optional[dict]:
    if not is_configured():
        return None
    try:
        resp = httpx.post(
            _endpoint(model),
            headers={"x-goog-api-key": settings.GEMINI_API_KEY},
            json=payload,
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        logger.warning(f"[GEMINI] request failed: {type(exc).__name__}")
        return None
    if resp.status_code != 200:
        # Never include the key; error bodies from Google don't contain it.
        logger.warning(f"[GEMINI] HTTP {resp.status_code}: {resp.text[:180]}")
        return None
    try:
        return resp.json()
    except ValueError:  # a 200 with a non-JSON body (proxy/HTML error page)
        logger.warning("[GEMINI] 200 response was not valid JSON; falling back")
        return None


def _extract_text(data: dict) -> str:
    parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", []) or []
    return " ".join(p.get("text", "") for p in parts).strip()


def generate(system: str, user: str, max_tokens: int = 300,
             temperature: float = 0.4) -> Optional[str]:
    """Phrase a reply. Returns text, or None on any failure (caller falls back).

    Uses GEMINI_TEXT_MODEL rather than GEMINI_MODEL: wording a sentence is a far
    smaller job than understanding speech, and the lighter model does it in about
    a third of the time. Transcription stays on GEMINI_MODEL.

    `temperature` defaults to the conversational 0.4 every existing caller
    expects. Answering from a document passes 0: there the job is to repeat what
    the passage says, and variety is not a feature.
    """
    model = settings.GEMINI_TEXT_MODEL or settings.GEMINI_MODEL
    t0 = time.perf_counter()
    data = _post(
        {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                # gemini-flash-latest counts "thinking" tokens against
                # maxOutputTokens, so leave headroom above the 512 thinking budget
                # or the visible reply gets cut off (finishReason MAX_TOKENS).
                "maxOutputTokens": max_tokens + 768,
                "thinkingConfig": {"thinkingBudget": 512},
            },
        },
        timeout=20,
        model=model,
    )
    if data is None:
        return None
    text = _extract_text(data)
    logger.info(
        f"[GEMINI] reply in {(time.perf_counter() - t0) * 1000:.0f}ms "
        f"({len(text)} chars, {model})"
    )
    return text or None


def transcribe(wav_bytes: bytes, mime: str = "audio/wav") -> str:
    """Speech-to-text. Returns transcript ('' if none / on failure)."""
    t0 = time.perf_counter()
    audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
    data = _post(
        {
            "contents": [{
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": mime, "data": audio_b64}},
                    {"text": _TRANSCRIBE_PROMPT},
                ],
            }],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 1280, "thinkingConfig": {"thinkingBudget": 512}},
        },
        timeout=settings.TRANSCRIBE_TIMEOUT_SECONDS,
    )
    if data is None:
        return ""
    text = _extract_text(data)
    # Seconds, not kilobytes. The server transcodes to 16 kHz mono 16 bit, a
    # fixed 32 KB per second, so a clip arriving at the frontend's 15 second cap
    # looks like 480 KB and nothing in the log said so.
    seconds = len(wav_bytes) / 32_768
    logger.info(
        f"[GEMINI] transcript in {(time.perf_counter() - t0) * 1000:.0f}ms "
        f"({seconds:.1f}s of audio, {len(text)} chars)"
    )
    return text


def _pcm_to_wav(pcm: bytes, mime: str) -> bytes:
    """Wrap raw PCM in a RIFF/WAV container.

    The TTS models return headerless signed 16-bit little-endian PCM, which no
    browser will play from an <audio> element. The sample rate is only stated in
    the mime type, and its spelling varies by model ("audio/L16;codec=pcm;rate=24000"
    and "audio/l16; rate=24000; channels=1" both occur), so read it out rather than
    hardcoding it.
    """
    rate = int(m.group(1)) if (m := re.search(r"rate=(\d+)", mime)) else 24000
    channels = int(m.group(1)) if (m := re.search(r"channels=(\d+)", mime)) else 1
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)          # L16 => 16-bit samples
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


# The assistant says a handful of phrases constantly: "Here is the list." after
# every search, "Here's your cart." after every cart view. Each one costs a 2 to
# 7 second round trip to produce audio that is byte for byte what it was last
# time, so keep the recent ones. Bounded by count and by length, which together
# cap this at a few MB: replies naming a product are long and varied, so they
# would only churn the cache without ever being reused.
_SPEECH_CACHE: "OrderedDict[tuple[str, str, str], str]" = OrderedDict()
_SPEECH_CACHE_MAX = 32
_SPEECH_CACHE_MAX_CHARS = 120


def speak(text: str) -> str:
    """Text-to-speech. Returns a base64 WAV data URL, or '' on any failure.

    '' is not an error the caller has to handle: the browser falls back to its
    own speech synthesis, so a TTS outage costs voice quality, never the reply.
    """
    if not text.strip():
        return ""

    key = (text, settings.GEMINI_TTS_MODEL, settings.GEMINI_TTS_VOICE)
    cacheable = len(text) <= _SPEECH_CACHE_MAX_CHARS
    if cacheable and key in _SPEECH_CACHE:
        _SPEECH_CACHE.move_to_end(key)
        logger.info(f"[GEMINI] speech served from cache ({len(text)} chars)")
        return _SPEECH_CACHE[key]

    t0 = time.perf_counter()
    data = _post(
        {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": settings.GEMINI_TTS_VOICE}
                    }
                },
            },
        },
        timeout=30,
        model=settings.GEMINI_TTS_MODEL,
    )
    if data is None:
        return ""
    try:
        blob = data["candidates"][0]["content"]["parts"][0]["inlineData"]
        pcm = base64.b64decode(blob["data"])
        wav = _pcm_to_wav(pcm, blob.get("mimeType", ""))
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning(f"[GEMINI] TTS response had no usable audio ({type(exc).__name__})")
        return ""
    logger.info(
        f"[GEMINI] speech in {(time.perf_counter() - t0) * 1000:.0f}ms "
        f"({len(text)} chars, {len(wav) // 1024} KB wav)"
    )
    url = f"data:audio/wav;base64,{base64.b64encode(wav).decode('ascii')}"
    if cacheable:
        _SPEECH_CACHE[key] = url
        while len(_SPEECH_CACHE) > _SPEECH_CACHE_MAX:
            _SPEECH_CACHE.popitem(last=False)     # drop the least recently spoken
    return url
