"""
Server-side voice: speech-to-text and text-to-speech, from whichever provider
SPEECH_PROVIDER names ("gemini" or "openai").

Keeping this on the server means the API key never ships to the browser (the old
frontend called ElevenLabs directly with an exposed key). Whisper accepts the
browser's WebM/Opus recording directly; Gemini needs WAV, so that path transcodes
with ffmpeg first.

Both directions degrade rather than fail: an unavailable STT raises VoiceError and
the caller asks the shopper to repeat themselves, and an unavailable TTS returns ''
so the browser speaks the reply in its own voice.
"""

import base64
import logging
import subprocess
import tempfile
import os

from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger("voice")

client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None


class VoiceError(Exception):
    """Raised when STT/TTS can't be performed (not configured / provider error)."""


def _to_wav(audio_bytes: bytes) -> bytes | None:
    """Transcode a browser WebM/Opus clip to mono 16 kHz WAV via ffmpeg (Gemini needs WAV)."""
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as src:
        src.write(audio_bytes)
        src_path = src.name
    dst_path = src_path.replace(".webm", ".wav")
    try:
        subprocess.run(
            [settings.FFMPEG_PATH, "-y", "-i", src_path, "-ac", "1", "-ar", "16000", dst_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
        )
        with open(dst_path, "rb") as f:
            return f.read()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.warning(f"[VOICE] ffmpeg transcode failed: {type(exc).__name__}")
        return None
    finally:
        for p in (src_path, dst_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def transcribe(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe a recorded clip to text. Returns '' when no speech is detected."""
    # Gemini path (local demo): transcode to WAV, then Gemini speech-to-text.
    if settings.SPEECH_PROVIDER == "gemini":
        from app.services import gemini_service
        if not gemini_service.is_configured():
            raise VoiceError("Voice is not configured on the server.")
        wav = _to_wav(audio_bytes)
        if wav is None:
            raise VoiceError("Could not process the audio (ffmpeg unavailable).")
        return gemini_service.transcribe(wav)

    if client is None:
        raise VoiceError("Voice is not configured on the server.")
    try:
        result = client.audio.transcriptions.create(
            model=settings.OPENAI_TRANSCRIPTION_MODEL,
            file=(filename, audio_bytes),
            language="en",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[VOICE] STT failed: {type(exc).__name__}")
        raise VoiceError("Could not transcribe the audio.") from exc

    text = (getattr(result, "text", "") or "").strip()
    logger.info(f"[VOICE] transcript ({len(text)} chars)")
    return text


def synthesize(text: str) -> str:
    """Speak `text`; returns a base64 audio data URL. '' means the browser should
    fall back to its own SpeechSynthesis voice."""
    # Gemini path: the reply is spoken by the same provider that understood it,
    # so the assistant has one consistent voice instead of whatever voice the
    # visitor's browser and operating system happen to ship.
    if settings.SPEECH_PROVIDER == "gemini":
        from app.services import gemini_service
        if not gemini_service.is_configured() or not settings.GEMINI_TTS_MODEL:
            return ""
        return gemini_service.speak(text)

    if settings.SPEECH_PROVIDER != "openai":
        return ""
    if client is None or not text.strip():
        return ""
    try:
        speech = client.audio.speech.create(
            model=settings.OPENAI_TTS_MODEL,
            voice=settings.OPENAI_TTS_VOICE,
            input=text,
            response_format="mp3",
        )
        audio_bytes = speech.read() if hasattr(speech, "read") else speech.content
    except Exception as exc:  # noqa: BLE001 - TTS is best-effort; the text reply still works
        logger.warning(f"[VOICE] TTS failed: {type(exc).__name__}")
        return ""

    b64 = base64.b64encode(audio_bytes).decode("ascii")
    return f"data:audio/mpeg;base64,{b64}"
