"""
The conversation pipeline shared by the text (`/chat`) and voice (`/voice`)
endpoints. One message in → intent parse → RAG / cart mutation → phrased reply,
plus the updated cart and a structured `action` the frontend can react to.
"""

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import rag, ai, intent as intent_svc, cart_service, response

logger = logging.getLogger("chat")


def process(message: str, session, db: Session, category_filter: str | None = None) -> dict:
    intent = intent_svc.parse(message, session, db)
    logger.info(f"[CHAT] intent={intent.type} refs={[(r.item_id, r.quantity) for r in intent.refs]}")

    services: list[dict] = []
    action: dict | None = None
    speech: str | None = None   # short version spoken aloud (long lists aren't read out)

    # ── search ───────────────────────────────────────────────────────────────
    if intent.type == "search":
        services = rag.search_products(query=intent.query, db=db, top_k=None, category_filter=category_filter)
        session.last_shown_json = response.build_shown(services)
        if services:
            session.last_referenced_item_id = int(services[0]["id"])
        # The list is already composed, numbered and priced by response.py, and
        # those numbers are what "add item 2" resolves against. Asking a model to
        # restate it cost a measured 4.1 s per search and risked the wording
        # drifting from the numbering. SMART_REPLIES=false restores the old path.
        if settings.SMART_REPLIES:
            reply = response.search_reply(services)
        else:
            reply = ai.search_intro(message, services) or response.search_reply(services)
        if services:
            speech = "Here is the list."

    # ── add to cart ──────────────────────────────────────────────────────────
    elif intent.type == "add_to_cart":
        added: list[tuple[str, int]] = []
        for ref in intent.refs:
            try:
                service = cart_service.add_item(db, session, ref.item_id, ref.quantity)
                added.append((service.name, ref.quantity))
                session.last_referenced_item_id = ref.item_id
            except cart_service.CartError as exc:
                reply = str(exc)
                return _finish(db, session, reply, services, action, intent_type=intent.type)
        reply = response.added_reply(added)
        if added:
            action = {"type": "added", "items": [{"item_id": r.item_id, "name": n, "quantity": q}
                                                  for r, (n, q) in zip(intent.refs, added)]}

    # ── remove from cart ─────────────────────────────────────────────────────
    elif intent.type == "remove_from_cart":
        removed_name = None
        for ref in intent.refs:
            service = cart_service.remove_item(db, session, ref.item_id)
            removed_name = service.name if service else ref.name
        reply = response.removed_reply(removed_name)
        if removed_name and intent.refs:
            action = {"type": "removed", "items": [{"item_id": intent.refs[0].item_id, "name": removed_name}]}

    # ── set quantity ─────────────────────────────────────────────────────────
    elif intent.type == "set_quantity":
        name = None
        if intent.refs:
            ref = intent.refs[0]
            try:
                service = cart_service.set_quantity(db, session, ref.item_id, intent.quantity)
                name = service.name if service else ref.name
                action = {"type": "quantity", "items": [{"item_id": ref.item_id, "name": name, "quantity": intent.quantity}]}
            except cart_service.CartError as exc:
                reply = str(exc)
                return _finish(db, session, reply, services, action, intent_type=intent.type)
        reply = response.quantity_reply(name, intent.quantity)

    # ── view cart ────────────────────────────────────────────────────────────
    elif intent.type == "view_cart":
        cart = cart_service.serialize_cart(db, session)
        reply = response.cart_reply(cart)
        if cart["items"]:
            speech = "Here's your cart."

    # ── checkout ─────────────────────────────────────────────────────────────
    elif intent.type == "checkout":
        cart = cart_service.serialize_cart(db, session)
        reply = response.checkout_reply(cart)
        if cart["items"]:
            action = {"type": "checkout"}

    # ── small talk ───────────────────────────────────────────────────────────
    else:  # conversational
        reply = ai.small_talk(message) or "Thanks! Is there anything else I can help you with?"

    return _finish(db, session, reply, services, action, speech, intent_type=intent.type)


# How many services travel to the browser. The search itself still scores the
# whole catalog and the true count is reported, but sending every match was
# costing 310 KB and about a second on "cheese" (1,118 matches) to draw 24
# cards. Nobody scrolls past a hundred results, and the ones beyond that scored
# too low to be worth the wait.
MAX_SERVICES_RETURNED = 100


def _finish(db: Session, session, reply: str, services: list[dict], action: dict | None,
            speech: str | None = None, intent_type: str | None = None) -> dict:
    return {
        "reply": reply,
        "speech": speech or reply,   # spoken text falls back to the full reply
        "services": services[:MAX_SERVICES_RETURNED],
        "total_services": len(services),
        "cart": cart_service.serialize_cart(db, session),
        "action": action,
        "intent": intent_type,
    }
