"""
The conversation pipeline shared by the text (`/chat`) and voice (`/voice`)
endpoints. One message in → intent parse → RAG / cart mutation → phrased reply,
plus the updated cart and a structured `action` the frontend can react to.
"""

import re
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import rag, ai, intent as intent_svc, cart_service, response, docs_index

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

# The vocabulary of the documents, for questions that are not questions.
#
# "Lauderdale Lake community rules" is how people actually search: a noun
# phrase, no verb, no question mark. It opens with none of the words above, so
# the shape test called it a service search, the catalogue found "Community hall
# booking" at a weak score, and a resident asking about the rules was shown a
# hall to hire. One loose catalogue match was enough to hide the documents
# entirely, because the fallback below only runs when the catalogue finds
# nothing at all.
_DOC_SHAPE = re.compile(
    r"\b(rules?|regulations?|by-?laws?|covenants?|guidelines?|restrictions?|"
    r"policy|policies|hoa|association|ordinances?|handbook|"
    r"quiet hours?|curfew|noise|"
    r"architectural|arb|approval|violation|fine[sd]?|"
    r"lease|leasing|tenant|pets?|trash|recycling|amenit(y|ies))\b",
    re.IGNORECASE,
)


def _wants_documents(message: str) -> bool:
    """Ask the community documents before the service catalogue?

    Booking still wins outright, whatever else the message contains, because a
    resident who says "I need someone to cut my grass" wants a gardener and not
    the lawn rule, and both score about the same. Past that, either shape is
    enough: a question ("what are the quiet hours") or the documents' own
    vocabulary ("Serenity parking rules").

    Cheap to be wrong in this direction. When the documents do not cover it the
    lookup returns None and the catalogue search runs exactly as before, so the
    worst case is one extra retrieval against 189 chunks in memory.
    """
    if _BOOKING_SHAPE.search(message):
        return False
    return bool(_POLICY_SHAPE.search(message) or _DOC_SHAPE.search(message))


# A greeting, and nothing else. Anchored to the whole message so that
# "hi, what are the quiet hours" goes to the documents rather than being waved
# at, which is the same rule the floating panel uses.
_GREETING = re.compile(
    r"^\s*(hi|hey|hello|yo|hiya|howdy|good\s*(morning|afternoon|evening)|"
    r"salaam|assalam[ou]?\s*alaikum)\b[\s!.,]*$",
    re.IGNORECASE,
)

GREETING_REPLY = (
    "Hello. Tell me what needs doing and I will find someone who does it. "
    "I can also answer questions about the community rules: quiet hours, "
    "parking, pets, trash days and the application process."
)


def _document_answer(message: str, sources: list | None = None,
                     chosen: str = "") -> "str | None":
    """The community documents' answer to a question the catalogue could not meet.

    Shares one index and one endpoint with the floating help panel, so a resident
    gets the same answer whichever way they ask, and there is one place to fix a
    wrong one. Grounding is unchanged: retrieval has to clear its floor before a
    model is asked anything, and "the documents do not cover this" returns None
    so the caller falls back to its own "nothing found" wording rather than
    printing two.

    One case does return text rather than None: a question naming a community we
    hold no documents for. That is not a miss to fall through, it is the answer,
    and the resident has to hear it rather than be shown a tradesperson.
    """
    try:
        from app.api.docs import answer_from_documents
        return answer_from_documents(message, sources, chosen)
    except Exception:  # noqa: BLE001 - the chat must survive a documents outage
        logger.exception("[CHAT] document lookup failed")
        return None


def _document_miss(message: str, chosen: str = "") -> str:
    """What to say when the documents were the right place and had nothing."""
    try:
        from app.api.docs import not_in_documents
        return not_in_documents(message, chosen)
    except Exception:  # noqa: BLE001 - the chat must survive a documents outage
        logger.exception("[CHAT] document lookup failed")
        return "I could not find that in the community documents."


def process(message: str, session, db: Session, category_filter: str | None = None,
            community: str | None = None) -> dict:
    intent = intent_svc.parse(message, session, db)
    logger.info(f"[CHAT] intent={intent.type} refs={[(r.item_id, r.quantity) for r in intent.refs]}")

    services: list[dict] = []
    action: dict | None = None
    speech: str | None = None   # short version spoken aloud (long lists aren't read out)
    #: Set when the reply did not come from the catalogue after all, so the
    #: results pane can label itself honestly.
    intent_override: str | None = None
    #: The passages behind a documents answer, when there was one.
    cited: list = []

    # ── a greeting ───────────────────────────────────────────────────────────
    # Before anything else, because "hi" is not a search. It was reaching the
    # catalogue, finding nothing, and being answered with "try a different
    # keyword, leaks and blocked drains are the usual ones", which is a cold
    # thing to say to somebody who has just said hello.
    if _GREETING.match(message or ""):
        return _finish(db, session, GREETING_REPLY, [], None,
                       speech=GREETING_REPLY, intent_type="greeting")

    # ── search ───────────────────────────────────────────────────────────────
    if intent.type == "search":
        # A question about the community rules, asked in the booking chat. The
        # catalogue will always return something loosely related (asking about
        # quiet hours returned pet sitting and a community hall), so an empty
        # result is not the signal. Shape decides, and retrieval's own floor
        # decides whether the documents really cover it.
        # Naming a community is a signal in its own right, separate from the
        # vocabulary test. The client typed "DUTIES AND POWERS of lauderdale
        # lake", a heading copied out of the handbook: no question word, none of
        # the words in _DOC_SHAPE, but unmistakably about a document we hold.
        names_community = (bool(docs_index.named_communities(message))
                           and not _BOOKING_SHAPE.search(message))
        asked_the_documents = _wants_documents(message) or names_community
        if asked_the_documents:
            # No extra score gate here on purpose. Shape has already ruled out
            # booking requests, so the index's own floor is the right test of
            # coverage, and the model refusing is the second one: both return
            # None and the catalogue search below runs as normal. An earlier
            # 0.45 gate was rejecting "how much for a copy of the condo docs",
            # which the amenities sheet answers outright at $25.00, because it
            # only scored 0.382.
            grounded = _document_answer(message, found := [], community or "")
            if grounded:
                logger.info("[CHAT] answered from the community documents")
                return _finish(db, session, grounded, [], None,
                               speech="Here is what the community documents say.",
                               intent_type="documents", sources=found)

            # Named a place and asked about its rules, and the documents came
            # back empty. Say so. Falling through to the catalogue is what the
            # client photographed: "Lauderdale Lake community rules" answered
            # with "Community hall booking, from $35.00", because one weak
            # catalogue match is still a match. A tradesperson is not a worse
            # answer to this question, it is not an answer to it.
            # Owned outright only when the message is also about the rules.
            # A community name on its own is not enough: "plumber in Serenity
            # Point" is a request for a tradesperson that happens to say where,
            # and it must still reach the catalogue.
            if names_community and _wants_documents(message):
                logger.info("[CHAT] %r names a community; the documents own it",
                            message[:60])
                # A miss, not an answer. The two must not arrive under the same
                # label: the results pane reads it, and it was announcing
                # "Answered from the community documents" beside "I could not
                # find that in the Lauderdale Lakes documents".
                return _finish(db, session, _document_miss(message, community or ""), [], None,
                               intent_type="documents_miss")

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
            #
            # And only if the gate above did not already ask, or a question the
            # documents cannot answer would pay for two retrievals and two model
            # calls to arrive at the same refusal twice.
            grounded = (None if asked_the_documents
                        else _document_answer(message, found := [], community or ""))
            if grounded:
                reply, speech = grounded, "Here is what the community documents say."
                cited, intent_override = found, "documents"
            elif names_community:
                intent_override = "documents_miss"
                # Named a place, and neither the documents nor the catalogue had
                # anything. "Try a different keyword, leaks and blocked drains
                # are the usual ones" is a poor answer to a question about a
                # community's rules, so say which documents were searched.
                reply, speech = _document_miss(message, community or ""), None

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
                   intent_type=intent_override or intent.type, sources=cited)


# How many services travel to the browser. The search itself still scores the
# whole catalog and the true count is reported, but sending every match was
# costing 310 KB and about a second on "cheese" (1,118 matches) to draw 24
# cards. Nobody scrolls past a hundred results, and the ones beyond that scored
# too low to be worth the wait.
MAX_SERVICES_RETURNED = 100


def _finish(db: Session, session, reply: str, services: list[dict], action: dict | None,
            speech: str | None = None, intent_type: str | None = None,
            sources: list | None = None) -> dict:
    return {
        "sources": [{"section": s.section, "document": s.document,
                     "community": s.community} for s in (sources or [])],
        "reply": reply,
        "speech": speech or reply,   # spoken text falls back to the full reply
        "services": services[:MAX_SERVICES_RETURNED],
        "total_services": len(services),
        "cart": cart_service.serialize_cart(db, session),
        "action": action,
        "intent": intent_type,
    }
