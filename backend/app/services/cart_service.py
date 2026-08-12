"""
Server-side cart operations.

The cart lives in the ``cart_items`` table keyed by session, and is the single
source of truth shared by chat, voice, the UI buttons and checkout. Every
mutation validates the product against the live ``services`` list and snapshots
its price at add-time.
"""

import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chat_session import ChatSession
from app.models.cart_item import CartItem
from app.models.service import Service
from app.services.media import serialized_image

logger = logging.getLogger("cart")


class CartError(Exception):
    """Raised for user-facing cart problems (unknown product, out of stock)."""


def get_or_create_session(
    db: Session,
    session_id: Optional[str],
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> ChatSession:
    """Fetch the session by id, creating it if missing. Refreshes location if given."""
    sid = (session_id or "").strip() or uuid.uuid4().hex
    session = db.get(ChatSession, sid)
    if session is None:
        session = ChatSession(id=sid)
        db.add(session)
        db.flush()
        logger.info(f"[CART] Created session {sid}")

    if latitude is not None:
        session.latitude = latitude
    if longitude is not None:
        session.longitude = longitude

    return session


def _get_active_product(db: Session, item_id: int) -> Service:
    product = db.query(Service).filter(
        Service.id == item_id,
        Service.status == True,
    ).first()
    if product is None:
        raise CartError("That product isn't available.")
    return product


def add_item(db: Session, session: ChatSession, item_id: int, quantity: int = 1) -> Service:
    """Add ``quantity`` of a product, merging with an existing line. Returns the product."""
    quantity = max(1, int(quantity))
    product = _get_active_product(db, item_id)

    line = db.query(CartItem).filter(
        CartItem.session_id == session.id,
        CartItem.item_id == item_id,
    ).first()

    existing_qty = line.quantity if line else 0
    if (product.stock or 0) < existing_qty + quantity:
        raise CartError(f"Sorry, there isn't enough stock for '{product.name}'.")

    if line:
        line.quantity += quantity
        line.unit_price = product.price
    else:
        line = CartItem(
            session_id=session.id,
            item_id=item_id,
            quantity=quantity,
            unit_price=product.price,
        )
        db.add(line)

    db.flush()
    logger.info(f"[CART] {session.id}: +{quantity} item {item_id} ('{product.name}')")
    return product


def set_quantity(db: Session, session: ChatSession, item_id: int, quantity: int) -> Optional[Service]:
    """Set an exact quantity. Quantity <= 0 removes the line. Returns product (or None if removed)."""
    quantity = int(quantity)
    line = db.query(CartItem).filter(
        CartItem.session_id == session.id,
        CartItem.item_id == item_id,
    ).first()

    if quantity <= 0:
        if line:
            db.delete(line)
            db.flush()
        return None

    product = _get_active_product(db, item_id)
    if (product.stock or 0) < quantity:
        raise CartError(f"Sorry, there isn't enough stock for '{product.name}'.")

    if line:
        line.quantity = quantity
        line.unit_price = product.price
    else:
        line = CartItem(session_id=session.id, item_id=item_id, quantity=quantity, unit_price=product.price)
        db.add(line)
    db.flush()
    return product


def remove_item(db: Session, session: ChatSession, item_id: int) -> Optional[Service]:
    """Remove a product entirely. Returns the product (for a friendly reply) or None."""
    line = db.query(CartItem).filter(
        CartItem.session_id == session.id,
        CartItem.item_id == item_id,
    ).first()
    product = db.query(Service).filter(Service.id == item_id).first()
    if line:
        db.delete(line)
        db.flush()
        logger.info(f"[CART] {session.id}: removed item {item_id}")
    return product


def clear(db: Session, session: ChatSession) -> None:
    db.query(CartItem).filter(CartItem.session_id == session.id).delete()
    db.flush()


def serialize_cart(db: Session, session: ChatSession) -> dict:
    """Build the cart payload the frontend renders: lines, totals and item count.

    ``total`` is the grand total the customer pays — subtotal plus tax — so every
    existing caller keeps showing the right number; ``subtotal`` and ``tax`` are
    the breakdown.
    """
    lines = db.query(CartItem).filter(CartItem.session_id == session.id).all()
    if not lines:
        return {
            "session_id": session.id, "items": [],
            "subtotal": 0.0, "tax": 0.0, "total": 0.0, "count": 0,
        }

    item_ids = [l.item_id for l in lines]
    products = {
        p.id: p
        for p in db.query(Service).filter(Service.id.in_(item_ids)).all()
    }

    # Where a sourced product came from, for the "Show More" link out. Only
    # products we adopted have a row here, so an ordinary catalog line simply
    # gets None and the link does not appear.
    sourced: dict[int, dict] = {}
    try:
        from app.models.external_item import ExternalItem
        for row in db.query(ExternalItem).filter(ExternalItem.item_id.in_(item_ids)):
            sourced[row.item_id] = {"seller": row.seller, "product_url": row.product_url}
    except Exception:  # noqa: BLE001 - provenance is a nicety, the cart is not
        sourced = {}

    items = []
    goods_total = 0.0
    for line in lines:
        product = products.get(line.item_id)
        unit_price = float(line.unit_price)
        subtotal = round(unit_price * line.quantity, 2)
        goods_total += subtotal
        items.append({
            "item_id": line.item_id,
            "name": product.name if product else f"Item {line.item_id}",
            "unit": "unit",
            "unit_price": unit_price,
            "quantity": line.quantity,
            "subtotal": subtotal,
            "image_url": serialized_image(product) if product else None,
            # From our own `services` table. The client asked for the cart to show
            # a description, and explicitly not to spend a provider search on
            # something we already hold.
            "description": (product.description or None) if product else None,
            # `Service.category` is a string property, not a relationship: it
            # falls back to str(category_id) when no name has been joined on.
            "category": (product.category or None) if product else None,
            # Present only for products sourced from outside our catalog: the
            # retailer and their page, so "Show More" has somewhere to go.
            "seller": sourced.get(line.item_id, {}).get("seller"),
            "product_url": sourced.get(line.item_id, {}).get("product_url"),
        })

    subtotal = round(goods_total, 2)
    tax = round(subtotal * settings.TAX_RATE, 2)
    return {
        "session_id": session.id,
        "items": items,
        "subtotal": subtotal,
        "tax": tax,
        "total": round(subtotal + tax, 2),
        "count": sum(l.quantity for l in lines),
    }
