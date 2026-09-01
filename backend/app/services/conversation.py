"""
The conversation pipeline shared by the text (`/chat`) and voice (`/voice`)
endpoints. One message in → intent parse → RAG / cart mutation → phrased reply,
plus the updated cart and a structured `action` the frontend can react to.
"""

import re
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import rag, ai, intent as intent_svc, cart_service, response, tracing

logger = logging.getLogger("chat")


# A greeting, and nothing else. Anchored to the whole message so that
# "hi, my sink is blocked" is treated as the plumbing problem it is.
_GREETING = re.compile(
    r"^\s*(hi|hey|hello|yo|hiya|howdy|good\s*(morning|afternoon|evening)|"
    r"salaam|assalam[ou]?\s*alaikum)\b[\s!.,]*$",
    re.IGNORECASE,
)

UNSURE_REPLY = (
    "I could not find that. Tell me what has gone wrong in your own words and "
    "I will look again."
)


# One box, two jobs, said in the order people ask for them.
GREETING_REPLY = (
    "Hello. Tell me what needs doing and I will find someone who does it. "
    "I can also get you a parking pass for a visitor."
)


def process(message: str, session, db: Session, category_filter: str | None = None) -> dict:
    """One message in, one screen out.

    It used to take a `community` and a `route` as well, and decide between the
    association's documents and the service catalogue. Community moved to its
    own application, so there is one job here and nothing to route between.
    """
    with tracing.stage("understand", "Working out what was asked") as leg:
        intent = intent_svc.parse(message, session, db)
        leg.detail = f"read as {intent.type}"

    logger.info("[CHAT] intent=%s refs=%s", intent.type,
                [(r.item_id, r.quantity) for r in intent.refs])

    services: list[dict] = []
    action: dict | None = None
    speech: str | None = None   # short version spoken aloud (long lists aren't read out)

    # ── a greeting ───────────────────────────────────────────────────────────
    # Before anything else, because "hi" is not a search. It was reaching the
    # catalogue, finding nothing, and being answered with "try a different
    # keyword, leaks and blocked drains are the usual ones", which is a cold
    # thing to say to somebody who has just said hello.
    if _GREETING.match(message or ""):
        return _finish(db, session, GREETING_REPLY, [], None,
                       speech=GREETING_REPLY, intent_type="greeting")

    # ── a parking pass ───────────────────────────────────────────────────────
    #
    # The chat recognises the request and the frontend opens the form, the same
    # way asking to check out opens the checkout. Eleven details asked one at a
    # time is a worse way to fill in a form than a form, so the conversation
    # stops here and hands over.
    if intent.type == "parking":
        reply = ("Let's get you a parking pass. Fill this in and I will issue "
                 "it and email you the code.")
        return _finish(db, session, reply, [], {"type": "parking"},
                       speech="Let's get you a parking pass.", intent_type=intent.type)

    # ── search ───────────────────────────────────────────────────────────────
    if intent.type == "search" or intent.type == "document":
        services = rag.search_products(query=intent.query, db=db, top_k=None, category_filter=category_filter)
        session.last_shown_json = response.build_shown(services)
        if services:
            session.last_referenced_item_id = int(services[0]["id"])
        # The list is already composed, numbered and priced by response.py, and
        # those numbers are what "add item 2" resolves against. Asking a model to
        # restate it cost a measured 4.1 s per search and risked the wording
        # drifting from the numbering. SMART_REPLIES=false restores the old path.
        if not services:
            return _finish(db, session, UNSURE_REPLY, [], {"type": "clarify", "question": message},
                           speech=UNSURE_REPLY, intent_type="unsure")

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

    return _finish(db, session, reply, services, action, speech,
                   intent_type=intent.type)


# A message that carries the thread on rather than starting something new.
# "and the pet rules?", "what about weekends", "ok what about that one".
MAX_SERVICES_RETURNED = 100


def _finish(db: Session, session, reply: str, services: list[dict], action: dict | None,
            speech: str | None = None, intent_type: str | None = None) -> dict:
    """One shape for every branch, so none of them can forget a field."""
    return {
        "reply": reply,
        "speech": speech or reply,   # spoken text falls back to the full reply
        "services": services[:MAX_SERVICES_RETURNED],
        "total_services": len(services),
        "cart": cart_service.serialize_cart(db, session),
        "action": action,
        "intent": intent_type,
    }
