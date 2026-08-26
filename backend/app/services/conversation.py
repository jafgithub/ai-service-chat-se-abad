"""
The conversation pipeline shared by the text (`/chat`) and voice (`/voice`)
endpoints. One message in → intent parse → RAG / cart mutation → phrased reply,
plus the updated cart and a structured `action` the frontend can react to.
"""

import re
import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services import rag, ai, doc_library, docs_index, intent as intent_svc, cart_service, response

logger = logging.getLogger("chat")


# ── which of the two jobs is this message? ───────────────────────────────────
#
# This machinery was here, was taken out on 22 August when the documents moved
# behind the floating button, and is back because the client asked for the main
# chat to answer community questions itself. The reasoning it encodes is worth
# keeping intact rather than rediscovering.
#
# Score alone cannot make the call. Measured over twenty real phrasings the two
# overlap: "someone to cut my grass" is both a service we book and a thing the
# rules have an opinion about (0.470 against the lawn rule), while "how much for
# a copy of the condo docs" is a pure policy question that only reaches 0.382.
# So shape decides what kind of message it is, and the retrieval score decides
# whether the documents actually cover it.
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
# entirely.
_DOC_SHAPE = re.compile(
    r"\b(rules?|regulations?|by-?laws?|covenants?|guidelines?|restrictions?|"
    r"policy|policies|hoa|association|ordinances?|handbook|"
    r"quiet hours?|curfew|noise|"
    r"architectural|arb|approval|approved|violation|fine[sd]?|"
    r"lease|leasing|tenant|pets?|trash|recycling|amenit(y|ies))\b",
    re.IGNORECASE,
)


def _wants_documents(message: str) -> bool:
    """Ask the community documents before the service catalogue?

    Booking wins outright whatever else the message contains, because somebody
    who says "I need someone to cut my grass" wants a gardener and not the lawn
    rule, and both score about the same. Past that, either shape is enough: a
    question ("what are the quiet hours") or the documents' own vocabulary
    ("Serenity parking rules").

    Cheap to be wrong in this direction. When the documents do not cover it the
    lookup returns None and the catalogue search runs exactly as before.
    """
    if _BOOKING_SHAPE.search(message):
        return False
    return bool(_POLICY_SHAPE.search(message) or _DOC_SHAPE.search(message))


# Asked, found nothing, and the two possible readings are far enough apart that
# guessing is worse than asking. The frontend puts a button under each reading,
# so answering costs one tap rather than a retyped question.
# Asked once, the first time somebody asks about the rules without us knowing
# where they live. Never asked again: the answer is remembered in the browser
# and shared with the floating assistant.
PICK_COMMUNITY_REPLY = "Which community are you asking about?"

UNSURE_REPLY = (
    "I could not find that. Are you asking about your community's rules, "
    "or do you need someone to come out?"
)


# A greeting, and nothing else. Anchored to the whole message so that
# "hi, my sink is blocked" is treated as the plumbing problem it is.
_GREETING = re.compile(
    r"^\s*(hi|hey|hello|yo|hiya|howdy|good\s*(morning|afternoon|evening)|"
    r"salaam|assalam[ou]?\s*alaikum)\b[\s!.,]*$",
    re.IGNORECASE,
)

# One box, three jobs, said in the order people ask for them. The rules used to
# live only behind the floating button and the greeting sent people there; the
# client asked for everything to be reachable from the conversation, so it is
# named here instead of pointed at.
GREETING_REPLY = (
    "Hello. Tell me what needs doing and I will find someone who does it. "
    "I can also get you a parking pass, or find a document from your "
    "community's rules."
)


def process(message: str, session, db: Session, category_filter: str | None = None,
            community: str = "", route: str = "") -> dict:
    """One message in, one screen out.

    `community` is which association the resident belongs to, so a rules answer
    is scoped to their own documents. `route` is set only when they answered the
    "community or a service?" question by tapping one of the two buttons, and it
    skips the guess entirely for that one message.
    """
    intent = intent_svc.parse(message, session, db)
    logger.info(f"[CHAT] intent={intent.type} refs={[(r.item_id, r.quantity) for r in intent.refs]}")

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

    # ── a document by name ───────────────────────────────────────────────────
    #
    # Matched on the *title*, which is the only thing that can work: the client's
    # own example, "get me the application for occupancy", names a scan with no
    # readable text in it. Nothing inside that document can ever match a query,
    # so searching what is inside it finds nothing and always did.
    if intent.type == "document":
        found = doc_library.search_titles(intent.query)
        whole_shelf = ""
        if not found:
            # "show me the Kendall Square documents" names a community and no
            # document, and it means all of them. Matching on title cannot work
            # here: no title contains the community's name, so the ask that
            # sounds most natural was the one that found nothing.
            whole_shelf = named_communities_key(message)
            if whole_shelf:
                found = doc_library.for_community(whole_shelf)
        if found:
            documents = [{
                "id": d["id"],
                "title": d["title"],
                # The label, not the key: a resident reads "Serenity Point",
                # and "serenity" on a card is the database showing through.
                "community": docs_index.label_for(d["community"]),
                "answerable": d.get("kind") == doc_library.ANSWERABLE,
                "download_url": f"/api/v1/documents/{d['id']}/file",
            } for d in (found if whole_shelf else found[:4])]
            reply = (response.shelf_reply(docs_index.label_for(whole_shelf), documents)
                     if whole_shelf else response.documents_reply(documents))
            return _finish(db, session, reply, [], {"type": "documents"},
                           speech=reply, intent_type=intent.type, documents=documents)
        # Nothing by that name. Fall through to the catalogue rather than
        # refusing: "send me a plumber" reads as a document request to the
        # matcher and is not one.

    # ── a question about the community ───────────────────────────────────────
    #
    # Before the catalogue, because the catalogue always returns something
    # loosely related: asking about quiet hours used to return pet sitting and a
    # community hall. An empty result is therefore not the signal. Shape decides
    # what kind of message this is, and retrieval's own floor decides whether
    # the documents really cover it.
    if intent.type in ("search", "document") and route != "services":
        # Naming a community is a signal of its own, separate from the
        # vocabulary test. The client once typed "DUTIES AND POWERS of
        # lauderdale lake", a heading copied out of the handbook: no question
        # word, none of the words in _DOC_SHAPE, and unmistakably about a
        # document we hold.
        names_community = (bool(docs_index.named_communities(message))
                           and not _BOOKING_SHAPE.search(message))
        asked = route == "documents" or _wants_documents(message) or names_community

        if asked:
            # Which association? Asked here rather than on the way in, because
            # most people who open this want a plumber and being asked which
            # HOA they belong to first is a toll on the common case. By this
            # line the question is known to be about the rules, so the answer
            # genuinely cannot be given without knowing.
            if not community and not names_community:
                choices = docs_index.answerable()
                if len(choices) > 1:
                    return _finish(
                        db, session, PICK_COMMUNITY_REPLY, [],
                        {"type": "pick_community", "question": message,
                         "options": [{"key": c.key, "label": c.label} for c in choices]},
                        speech=PICK_COMMUNITY_REPLY, intent_type="pick_community")

            sources: list = []
            grounded = _document_answer(message, sources, community or "")
            if grounded:
                found = _documents_behind(sources)
                logger.info("[CHAT] answered from the community documents, %d source(s)",
                            len(found))
                return _finish(db, session, grounded, [], None,
                               speech="Here is what the community documents say.",
                               intent_type="documents", documents=found)

            # The documents came back empty. Whether that is the answer or
            # merely a miss depends on how certain we are the question was
            # theirs, and the two shapes are not equally certain.
            #
            # `_DOC_SHAPE` is the documents' own vocabulary: quiet hours, pets,
            # leasing, the ARB. A message using it is about the rules whatever
            # the catalogue thinks, so the documents own the answer including
            # the answer "we do not hold that". `_POLICY_SHAPE` is only the
            # shape of a question, and "what does a boiler service cost" is one
            # of those without being about the rules at all, so it still falls
            # through to the catalogue.
            #
            # Getting this wrong is what the client photographed twice. On 20
            # August "Lauderdale Lake community rules" was answered with
            # "Community hall booking, from $35.00". On 26 August a Kendall
            # Square resident asked five times for the quiet hours and was
            # offered a mobile mechanic at $70, because their association holds
            # one colour archive and nothing else, and nothing on screen said
            # so. A tradesperson is not a worse answer to those questions, it
            # is not an answer to them.
            owns_the_question = (
                route == "documents"
                or bool(_DOC_SHAPE.search(message))
                or (names_community and _wants_documents(message))
            )
            if owns_the_question:
                # The reply names what the community does hold. The action gives
                # the resident somewhere to go with that, because being told
                # "not here" and nothing else is what turned one question into
                # five identical retries in the logs on 26 August.
                where = community or (named_communities_key(message) or "")
                return _finish(db, session, _document_miss(message, community or ""),
                               [], {"type": "documents_miss", "community": where,
                                    "question": message},
                               intent_type="documents_miss")

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
        if not services and route != "services":
            # Nothing in the documents and nothing in the catalogue. The two
            # readings are far enough apart that guessing is worse than asking,
            # and the buttons make answering one tap rather than a retyped
            # question.
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

    return _finish(db, session, reply, services, action, speech, intent_type=intent.type)


def named_communities_key(message: str) -> str:
    """The community a message names, when it names exactly one."""
    named = docs_index.named_communities(message)
    return named[0].key if len(named) == 1 else ""


def _document_answer(message: str, sources: list, chosen: str = "") -> "str | None":
    """The documents' answer, or None when they do not cover it.

    Imported here rather than at the top because the chat must survive the
    documents being unavailable: a failure in that box returns None and the
    catalogue search runs exactly as it did before any of this existed.
    """
    try:
        from app.api.docs import answer_from_documents
        return answer_from_documents(message, sources, chosen)
    except Exception:  # noqa: BLE001 - a documents outage is not a chat outage
        logger.exception("[CHAT] document lookup failed")
        return None


def _document_miss(message: str, chosen: str = "") -> str:
    """What to say when the documents were the right place and had nothing."""
    try:
        from app.api.docs import not_in_documents
        return not_in_documents(message, chosen)
    except Exception:  # noqa: BLE001
        logger.exception("[CHAT] document miss wording failed")
        return UNSURE_REPLY


def _documents_behind(sources: list) -> list[dict]:
    """The documents an answer came out of, once each, in the order cited.

    Deduplicated by document rather than by section: three rules quoted from one
    handbook is one thing to download, and listing it three times reads as three
    documents. The first section is kept as the line under the title, because it
    is what the answer actually leant on and it tells a reader where to look
    once the PDF is open.
    """
    rows: list[dict] = []
    seen: set[str] = set()
    for source in sources:
        title = getattr(source, "document", "") or ""
        if not title or title in seen:
            continue
        seen.add(title)

        doc = doc_library.find(_key_for(getattr(source, "community", "")), title)
        if doc is None:
            # Cited but not in the library, so there is no file to offer. Left
            # out rather than shown as a row that cannot be opened.
            logger.warning("[CHAT] %r was cited with no file behind it", title)
            continue

        rows.append({
            "id": doc["id"],
            "title": doc["title"],
            "community": docs_index.label_for(doc["community"]),
            "answerable": doc.get("kind") == doc_library.ANSWERABLE,
            "section": getattr(source, "section", "") or "",
            "download_url": f"/api/v1/documents/{doc['id']}/file",
            "view_url": f"/api/v1/documents/{doc['id']}/file?view=1",
        })
    return rows


def _key_for(label: str) -> str:
    """The registry key behind a label, since a source carries the label."""
    for community in docs_index.COMMUNITIES:
        if community.label == label or community.key == label:
            return community.key
    return label.lower()


# How many services travel to the browser. The search itself still scores the
# whole catalog and the true count is reported, but sending every match was
# costing 310 KB and about a second on "cheese" (1,118 matches) to draw 24
# cards. Nobody scrolls past a hundred results, and the ones beyond that scored
# too low to be worth the wait.
MAX_SERVICES_RETURNED = 100


def _finish(db: Session, session, reply: str, services: list[dict], action: dict | None,
            speech: str | None = None, intent_type: str | None = None,
            documents: list[dict] | None = None) -> dict:
    return {
        "reply": reply,
        "speech": speech or reply,   # spoken text falls back to the full reply
        "services": services[:MAX_SERVICES_RETURNED],
        "total_services": len(services),
        "cart": cart_service.serialize_cart(db, session),
        "documents": documents or [],
        "action": action,
        "intent": intent_type,
    }
