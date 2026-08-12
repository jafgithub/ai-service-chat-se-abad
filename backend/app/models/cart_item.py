from sqlalchemy import Column, BigInteger, Integer, String, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class CartItem(Base):
    """
    A line in a session's server-side cart. The cart is the single source of
    truth shared by chat, voice, the "+ Add to Cart" buttons and checkout.

    ``unit_price`` is snapshotted at add-time from ``items.price`` so the cart
    total is stable even if the catalog price changes mid-session.
    """
    __tablename__ = "cart_items"

    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(64), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id    = Column(BigInteger, nullable=False)          # → items.id (jjaitraindb catalog)
    quantity   = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(24, 2), nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    session = relationship("ChatSession", back_populates="cart_items")
