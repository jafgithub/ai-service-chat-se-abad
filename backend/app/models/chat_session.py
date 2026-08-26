from sqlalchemy import Column, String, Numeric, JSON, BigInteger, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class ChatSession(Base):
    """
    One conversational session (text or voice). Holds the short-term memory the
    assistant needs between turns — most importantly ``last_shown_json``, the
    numbered product list from the most recent search, which lets the user say
    "add item 2 to cart" and have the backend resolve it deterministically.
    """
    __tablename__ = "chat_sessions"

    id                       = Column(String(64), primary_key=True)   # uuid4 hex, minted by the client
    latitude                 = Column(Numeric(10, 7))
    longitude                = Column(Numeric(10, 7))
    last_shown_json          = Column(JSON)                           # [{position, id, name, price, ...}]
    last_referenced_item_id  = Column(BigInteger)

    # ── what this conversation is about ──────────────────────────────────────
    #
    # The three below are the documents' equivalent of `last_shown_json`, and
    # they exist for the same reason: a resident says "download that" and the
    # only way to know what "that" is, is to have kept it.
    #
    # Held here rather than in the browser even though the interface already
    # sends the community, because `/voice` cannot send it: that endpoint takes
    # a session id and an audio file and nothing else, so a spoken question was
    # being answered from the home community whatever the resident had picked.
    community                = Column(String(64))                     # the association being asked about
    last_documents_json      = Column(JSON)                           # [{id, title, community}]
    conversation_mode        = Column(String(16))                     # "documents" | "services" | None

    created_at               = Column(DateTime, server_default=func.now())
    updated_at               = Column(DateTime, server_default=func.now(), onupdate=func.now())

    cart_items = relationship(
        "CartItem",
        back_populates="session",
        cascade="all, delete-orphan",
    )
