from pydantic import BaseModel
from typing import Optional, Any

from app.schemas.chat import ServiceResult
from app.schemas.cart import CartOut


class VoiceResponse(BaseModel):
    session_id: str
    transcript: str
    reply: str
    speech: str = ""                 # short text for voice (long lists aren't read aloud)
    audio: str                       # base64 mp3 data URL for the spoken reply ('' if TTS unavailable)
    products: list[ServiceResult]
    total_services: int = 0
    cart: CartOut
    action: Optional[dict[str, Any]] = None
    # Same purpose as on the chat response: only a genuine product search should
    # ever reach out to a paid third-party search.
    intent: Optional[str] = None
