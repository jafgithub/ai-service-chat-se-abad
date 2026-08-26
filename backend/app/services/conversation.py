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

# Said when a community conversation gives way to a tradesperson, so the change
# of subject is never silent. No dash: these go straight to residents.
SWITCHING_TO_SERVICES = "Switching to services for this one."

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


# ── remembering what the conversation is about ───────────────────────────────
#
# Read through helpers, never as bare attributes. The tests fake the session as
# a plain object carrying `last_shown_json` and `last_referenced_item_id` and
# nothing else, and a bare `session.mode` would raise there rather than in
# anything a resident touches.

DOCUMENTS = "documents"
SERVICES = "services"


def _remembered_community(session, sent: str) -> str:
    """Which association this conversation is about.

    What the interface sent wins, because a resident who has just changed it in
    the picker means it. The session is the fallback, and it is what makes
    `/voice` work at all: that endpoint cannot send a community.
    """
    return sent or getattr(session, "community", "") or ""


def _remembered_documents(session) -> list[dict]:
    return getattr(session, "last_documents_json", None) or []


def _mode(session) -> str:
    return getattr(session, "conversation_mode", "") or ""


def _remember(session, *, community: str = "", documents: list[dict] | None = None,
              mode: str = "") -> None:
    """Keep what the next message will need. Assigned wholesale, never mutated
    in place: the column is a plain JSON type with no change tracking, so an
    in-place append would never reach the database."""
    if community:
        session.community = community
    if documents is not None:
        session.last_documents_json = [
            {"id": d["id"], "title": d["title"], "community": d.get("community", "")}
            for d in documents
        ]
    if mode:
        session.conversation_mode = mode


def process(message: str, session, db: Session, category_filter: str | None = None,
            community: str = "", route: str = "") -> dict:
    """One message in, one screen out.

    `community` is which association the resident belongs to, so a rules answer
    is scoped to their own documents. `route` is set only when they answered the
    "community or a service?" question by tapping one of the two buttons, and it
    skips the guess entirely for that one message.
    """
    intent = intent_svc.parse(message, session, db)

    # What this conversation is already about, before this message is judged.
    # The community the interface sent wins over the remembered one, because a
    # resident who has just changed it in the picker means it.
    community = _remembered_community(session, community)
    sticky = _mode(session) == DOCUMENTS
    remembered = _remembered_documents(session)

    # Naming a community is a signal in its own right, and it is needed twice,
    # so it is settled before anything decides anything.
    names_community = (bool(docs_index.named_communities(message))
                       and not _BOOKING_SHAPE.search(message))

    # Leaving the documents for a tradesperson.
    #
    # Staying used to be the default and "plumber" could not get out. A bare
    # trade name matches no booking verb, so after one rules question it was
    # answered with "I could not find that in the community documents". Sticky
    # has to mean "keep the thread", not "keep everything".
    leaving = sticky and (
        route == "services"
        or bool(_BOOKING_SHAPE.search(message))
        or not _still_about_documents(message, remembered, names_community)
    )
    if leaving:
        sticky = False
        _remember(session, mode=SERVICES)
    # Announced, but not when they tapped the button: telling somebody what
    # they just chose reads as the assistant not having listened.
    announce = SWITCHING_TO_SERVICES if (leaving and route != "services") else ""

    logger.info("[CHAT] intent=%s mode=%s community=%r refs=%s", intent.type,
                _mode(session) or "-", community,
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

    # ── a document by name ───────────────────────────────────────────────────
    #
    # Matched on the *title*, which is the only thing that can work: the client's
    # own example, "get me the application for occupancy", names a scan with no
    # readable text in it. Nothing inside that document can ever match a query,
    # so searching what is inside it finds nothing and always did.
    if intent.type == "document":
        # What was just on screen comes first. The client asked "can you
        # download the color archive for me" one message after being told
        # "what I hold for Kendall Square is the Approved colour archive", and
        # the archive was the obvious answer only because it had just been
        # said. Nothing was keeping it, so he got a question back.
        found = doc_library.resolve_remembered(message, remembered)
        # Re-read the library record. What is remembered is a name and an id,
        # deliberately, so a document withdrawn mid conversation cannot be
        # served from memory; everything else about it, `kind` above all, has
        # to come from the library or a perfectly readable document gets
        # described to the resident as a scan.
        found = [doc for doc in (doc_library.get(d["id"]) for d in found) if doc]
        # Then by name, inside their own association. Scoped and left scoped:
        # falling back to every community would hand a Kendall Square resident
        # Three Lakes' paperwork, which is the same failure as answering them
        # from it.
        if not found:
            found = doc_library.search_titles(intent.query, community=community)
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
            _enter_documents(session, community or _key_for(documents[0]["community"]),
                             documents)
            return _finish(db, session, reply, [], {"type": "documents"},
                           speech=reply, intent_type=intent.type, documents=documents)

        # Nothing by that name. Falling through to the catalogue is what told a
        # resident asking for a PDF to "book item 2", so it now happens only
        # when the message was never really about a document: "send me a
        # plumber" reads as one to the matcher and is not one.
        if sticky or community:
            return _finish(db, session, _document_miss(message, community), [],
                           {"type": "documents_miss", "community": community,
                            "question": message},
                           intent_type="documents_miss", announce=announce)

    # ── a question about the community ───────────────────────────────────────
    #
    # Before the catalogue, because the catalogue always returns something
    # loosely related: asking about quiet hours used to return pet sitting and a
    # community hall. An empty result is therefore not the signal. Shape decides
    # what kind of message this is, and retrieval's own floor decides whether
    # the documents really cover it.
    if intent.type in ("search", "document") and route != "services":
        # `names_community` is computed at the top of `process`. It is a signal
        # of its own, separate from the vocabulary test: the client once typed
        # "DUTIES AND POWERS of lauderdale lake", a heading copied out of the
        # handbook, with no question word and none of the words in _DOC_SHAPE.
        # `sticky` is what keeps "what about weekends" and "and the pet rules?"
        # with the documents. `_wants_documents` stays a pure function of the
        # message: fifteen parametrised tests assert it directly, and threading
        # a session into it would break every one.
        asked = (route == "documents" or _wants_documents(message)
                 or names_community or sticky)

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
                        speech=PICK_COMMUNITY_REPLY, intent_type="pick_community",
                        announce=announce)

            sources: list = []
            grounded = _document_answer(message, sources, community or "")
            if grounded:
                found = _documents_behind(sources)
                logger.info("[CHAT] answered from the community documents, %d source(s)",
                            len(found))
                _enter_documents(session, community, found)
                return _finish(db, session, grounded, [], None,
                               speech="Here is what the community documents say.",
                               intent_type="documents", documents=found,
                               announce=announce)

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
                or sticky
                or bool(_DOC_SHAPE.search(message))
                or (names_community and _wants_documents(message))
            )
            if owns_the_question:
                # The reply names what the community does hold. The action gives
                # the resident somewhere to go with that, because being told
                # "not here" and nothing else is what turned one question into
                # five identical retries in the logs on 26 August.
                where = community or (named_communities_key(message) or "")
                # Remember the shelf, not just the community. The reply names
                # what the association does hold, so those titles are now on
                # screen and "download the colour archive" has to resolve
                # against them. This is the exact turn the client got stuck on.
                _enter_documents(session, where, doc_library.for_community(where))
                return _finish(db, session, _document_miss(message, community or ""),
                               [], {"type": "documents_miss", "community": where,
                                    "question": message},
                               intent_type="documents_miss", announce=announce)

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
            # A genuine catalogue answer ends the community conversation, so
            # "the first one" means a service again.
            _remember(session, mode=SERVICES)

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
                   intent_type=intent.type, announce=announce)


# A message that carries the thread on rather than starting something new.
# "and the pet rules?", "what about weekends", "ok what about that one".
_FOLLOW_UP = re.compile(
    r"^\s*(and|also|plus|ok(ay)?|then|so)\b|"
    r"\b(what|how)\s+about\b|"
    r"\b(that|those|this|these|it|the\s+same|the\s+other)\b",
    re.IGNORECASE,
)


def _still_about_documents(message: str, remembered: list[dict],
                           names_community: bool) -> bool:
    """Is this message carrying the community conversation on, or starting
    something else?

    Sticky mode used to answer "yes" to everything, which is how "plumber"
    came to be answered with "I could not find that in the community
    documents". A bare trade name matches no booking verb, so nothing let it
    out. Staying now has to be earned by the message looking like it belongs:
    the rules' own vocabulary or a question, a word that points back at what
    was just said, a community by name, or the name of a document already on
    screen.

    Anything else is a new subject, and the catalogue is a better guess at it
    than the documents are.
    """
    if _wants_documents(message) or names_community:
        return True
    if _FOLLOW_UP.search(message or ""):
        return True
    # "the colour one" after the colour archive was named. Reuses the resolver
    # rather than a second list of ways to refer to a document.
    return bool(doc_library.resolve_remembered(message, remembered))


def _enter_documents(session, community: str, documents: list[dict] | None = None) -> None:
    """This conversation is about the community now.

    `last_shown_json` is cleared deliberately. It is the numbered *service*
    list, and `intent.parse` resolves a bare "the first one" against it before
    anything else gets a look. Left in place, a resident who asked for a
    plumber, switched to the rules, and then said "download the first one"
    would have been sold a boiler service.
    """
    _remember(session, community=community, documents=documents, mode=DOCUMENTS)
    session.last_shown_json = []
    session.last_referenced_item_id = None


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


def _shelf_for(session) -> list[dict]:
    """Everything the association holds, while the conversation is about it.

    Composed here rather than fetched by the interface, so the panel cannot
    disagree with the answer beside it, and so `/voice` gets it too: that
    endpoint has no way to ask a second question.
    """
    if _mode(session) != DOCUMENTS:
        return []
    key = getattr(session, "community", "") or ""
    if not key:
        return []
    return [{
        "id": d["id"],
        "title": d["title"],
        "community": docs_index.label_for(d["community"]),
        "answerable": d.get("kind") == doc_library.ANSWERABLE,
        "section": "",
        "download_url": f"/api/v1/documents/{d['id']}/file",
        "view_url": f"/api/v1/documents/{d['id']}/file?view=1",
    } for d in doc_library.for_community(key)]


def _finish(db: Session, session, reply: str, services: list[dict], action: dict | None,
            speech: str | None = None, intent_type: str | None = None,
            documents: list[dict] | None = None, announce: str = "") -> dict:
    """`announce` is prefixed here rather than at each call site, so every
    branch says the change of subject the same way and none of them forget."""
    if announce:
        reply = f"{announce}\n\n{reply}"
        speech = f"{announce} {speech}" if speech else reply
    return {
        "reply": reply,
        "speech": speech or reply,   # spoken text falls back to the full reply
        "services": services[:MAX_SERVICES_RETURNED],
        "total_services": len(services),
        "cart": cart_service.serialize_cart(db, session),
        "documents": documents or [],
        "shelf": _shelf_for(session),
        "action": action,
        "intent": intent_type,
    }
