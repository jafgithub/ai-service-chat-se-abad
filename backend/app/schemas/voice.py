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
    # `services`, not `products`. This field was renamed everywhere else when
    # the shop became a booking system and was missed here, so the endpoint was
    # passing `services=` to a model that required `products`: every voice turn
    # failed validation and returned a 500. The interface has always read
    # `services`, which is why the fix is the rename rather than the reverse.
    services: list[ServiceResult]
    total_services: int = 0
    cart: CartOut
    action: Optional[dict[str, Any]] = None
    # Same purpose as on the chat response: only a genuine product search should
    # ever reach out to a paid third-party search.
    intent: Optional[str] = None
