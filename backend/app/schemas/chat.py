from pydantic import BaseModel
from typing import Optional, Any

from app.schemas.cart import CartOut


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    category_filter: Optional[str] = None
    #: Which association the resident belongs to, so a rules answer is scoped to
    #: their own documents rather than the home community's.
    community: Optional[str] = None
    #: Set only when they answered "community or a service?" by tapping one of
    #: the two buttons: "documents" or "services". Skips the guess for that one
    #: message rather than making them rephrase.
    route: Optional[str] = None
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


class DocumentResult(BaseModel):
    """A document the assistant found by name, ready to download.

    Separate from `services` because it is not one: nothing here is bookable,
    priced, or scored against the catalogue. The frontend draws it as a link.
    """
    id: str
    title: str
    community: str
    #: False for a scan. Said on the card, because a resident who downloads a
    #: site map and then asks a question about it should not be surprised.
    answerable: bool = True
    #: The section the answer leant on, when this document was cited rather than
    #: asked for by name. Shown under the title so a reader knows where to look
    #: once the PDF is open.
    section: str = ""
    download_url: str
    #: The same file served inline, so the title can open it in a tab instead of
    #: putting a 900KB PDF in somebody's downloads to check one line.
    view_url: str = ""


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
    #: Documents matched by name, or cited under an answer.
    documents: list[DocumentResult] = []
    #: Everything the resident's association holds, while the conversation is
    #: about that association. Sent with the reply rather than fetched
    #: separately so the panel is a pure function of the last answer, and so
    #: the voice path gets it without a second round trip it cannot make.
    shelf: list[DocumentResult] = []
    action: Optional[dict[str, Any]] = None
    # What the shopper's message was understood as: "search", "add_to_cart",
    # "view_cart", "checkout" and so on. The frontend uses it to decide whether
    # looking outside our catalog is even appropriate, which matters because
    # that costs a paid third-party search.
    intent: Optional[str] = None
