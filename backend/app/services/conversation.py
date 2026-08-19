"""
The conversation pipeline shared by the text (`/chat`) and voice (`/voice`)
endpoints. One message in → intent parse → RAG / cart mutation → phrased reply,
plus the updated cart and a structured `action` the frontend can react to.
"""

import re
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import rag, ai, intent as intent_svc, cart_service, response

logger = logging.getLogger("chat")


# A question about the rules, rather than a request for somebody to come out.
#
# Score alone cannot make this call: measured over twenty real phrasings the two
# overlap, because "someone to cut my grass" is both a service we book and a
# thing the rules have an opinion about (0.470 against the lawn rule), while
# "how much for a copy of the condo docs" is a pure policy question that only
# reaches 0.382. So shape decides what kind of message it is and the score
# decides whether the documents actually cover it.
_POLICY_SHAPE = re.compile(
    r"^\s*(what|when|where|which|who|how much|how many|how long|how do i|"
    r"can i|may i|am i allowed|do i need|is there|are there|are we|is it ok)\b",
    re.IGNORECASE,
)
# Books a job whatever else it looks like. "I need a plumber" opens with none of
# the above, but "can I book someone to cut the grass" opens with "can I" and
# would otherwise be read as a policy question.
_BOOKING_SHAPE = re.compile(
    r"\b(book|order|arrange|send|hire|come out|call out|quote|appointment|"
    r"i need (a|an|someone)|my \w+ (is|has) (broken|leaking|blocked|stopped))\b",
    re.IGNORECASE,
)

def _is_policy_question(message: str) -> bool:
    return bool(_POLICY_SHAPE.search(message)) and not _BOOKING_SHAPE.search(message)


def _document_answer(message: str) -> "str | None":
    """The community documents' answer to a question the catalogue could not meet.

    Shares one index and one endpoint with the floating help panel, so a resident
    gets the same answer whichever way they ask, and there is one place to fix a
    wrong one. Grounding is unchanged: retrieval has to clear its floor before a
    model is asked anything, and a refusal here returns None so the caller falls
    back to its own "nothing found" wording rather than printing two.
    """
    try:
        from app.api.docs import answer_from_documents
        return answer_from_documents(message)
    except Exception:  # noqa: BLE001 - the chat must survive a documents outage
        logger.exception("[CHAT] document lookup failed")
        return None


def process(message: str, session, db: Session, category_filter: str | None = None) -> dict:
    intent = intent_svc.parse(message, session, db)
    logger.info(f"[CHAT] intent={intent.type} refs={[(r.item_id, r.quantity) for r in intent.refs]}")

    services: list[dict] = []
    action: dict | None = None
    speech: str | None = None   # short version spoken aloud (long lists aren't read out)

    # ── search ───────────────────────────────────────────────────────────────
    if intent.type == "search":
        # A question about the community rules, asked in the booking chat. The
        # catalogue will always return something loosely related (asking about
        # quiet hours returned pet sitting and a community hall), so an empty
        # result is not the signal. Shape and confidence together are.
        if _is_policy_question(message):
            # No extra score gate here on purpose. Shape has already ruled out
            # booking requests, so the index's own floor is the right test of
            # coverage, and the model refusing is the second one: both return
            # None and the catalogue search below runs as normal. An earlier
            # 0.45 gate was rejecting "how much for a copy of the condo docs",
            # which the amenities sheet answers outright at $25.00, because it
            # only scored 0.382.
            grounded = _document_answer(message)
            if grounded:
                logger.info("[CHAT] answered from the community documents")
                return _finish(db, session, grounded, [], None,
                               speech="Here is what the community documents say.",
                               intent_type="documents")

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
        else:
            # Nothing in the catalogue matched, which is exactly when a question
            # about the community documents lands here: "what are the quiet
            # hours" is not a service anybody books. Before telling the resident
            # we found nothing, ask the documents.
            #
            # Only on the empty branch, deliberately. A message that did match
            # real services is a request for a tradesperson and hijacking it
            # with a policy answer would be worse than not trying.
            grounded = _document_answer(message)
            if grounded:
                reply, speech = grounded, "Here is what the community documents say."

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
