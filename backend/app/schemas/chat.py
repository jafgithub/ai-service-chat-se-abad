from pydantic import BaseModel
from typing import Optional, Any

from app.schemas.cart import CartOut


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    category_filter: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ServiceResult(BaseModel):
    id: int
    name: str
    category: str
    description: Optional[str]
    unit: str
    price_per_unit: float
    stock: float
    image_url: Optional[str]
    #: How long a visit for this usually takes, and whether it is attended out
    #: of hours. Both belong to the service rather than to any one provider, so
    #: the card describes them as a guide; the provider's own figures replace
    #: them once one is chosen.
    duration_minutes: Optional[int] = None
    emergency: bool = False
    similarity: float


class DocumentSource(BaseModel):
    """Where a community documents answer came from, for the interface to show.

    Both halves are needed. The section on its own does not say which document
    it is in, and with two Serenity rulebooks that disagree with each other,
    that is exactly the thing a resident needs to see.
    """
    section: str
    document: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    speech: str = ""          # short text for voice (long lists aren't read aloud)
    services: list[ServiceResult]
    # How many matched in total. `services` carries only the best of them, so
    # the interface needs this to say "1,118 matches, showing the best 100"
    # rather than claiming the catalog holds 100 cheeses.
    total_services: int = 0
    cart: CartOut
    action: Optional[dict[str, Any]] = None
    #: Filled only when the reply came out of the community documents.
    sources: list[DocumentSource] = []
    # What the shopper's message was understood as: "search", "add_to_cart",
    # "view_cart", "checkout" and so on. The frontend uses it to decide whether
    # looking outside our catalog is even appropriate, which matters because
    # that costs a paid third-party search.
    intent: Optional[str] = None
