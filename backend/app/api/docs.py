"""Answering resident questions from the community documents, and nothing else.

The rule this route exists to keep: an answer is either supported by a passage
we retrieved, or it is a refusal. There is no third path. Two mechanics enforce
that rather than trusting a prompt to hold.

  * Retrieval decides first. If no chunk clears `docs_index.MIN_SCORE` the route
    returns the refusal itself and never calls a model, so the usual failure
    mode of a document assistant, answering plausibly from the model's own
    training, has nowhere to happen.
  * When passages do clear it, they are the only context the model sees, and it
    is told to refuse if they do not cover the question.

The passages are returned to the caller as `sources`, so the panel can show
which rule an answer came from and a resident can check it.
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import docs_index, gemini_service

logger = logging.getLogger("docs")

router = APIRouter(prefix="/docs", tags=["docs"])

# What the assistant can actually help with, in the resident's words. Used both
# when someone says hello and when the documents do not cover what they asked,
# because "I cannot answer that" on its own leaves them with nowhere to go.
CAN_HELP_WITH = (
    "I can help with quiet hours, parking and boats, pets, trash days, "
    "approvals for exterior changes, leasing, and the application process."
)

# Said whenever the documents do not cover the question. Deliberately names what
# it does hold and what to do next, so the resident knows where the edge is
# instead of guessing.
NO_ANSWER = (
    "I could not find that in the community documents, so I would rather say "
    f"so than guess. {CAN_HELP_WITH}\n\n"
    "For anything else, L&C Royal Management can help on (305) 228-7326."
)


def _no_documents(missing: list) -> str:
    """We know the place, we do not have its paperwork.

    Said instead of an answer, never alongside one. A resident asking about
    Three Lakes used to be handed the Serenity rules, because "Lake" sits close
    to "lakes" in the embedding space and nothing downstream knew the difference
    mattered. It matters more than a refusal does: rules about somebody's home,
    delivered confidently, out of a document that does not govern them.
    """
    names = " and ".join(c.label for c in missing)
    return (
        f"I do not have the {names} documents, so I cannot answer from them, "
        "and I will not answer from another community's rules instead. "
        "I hold the Serenity Point documents: the Rules and Regulations, the "
        "application package, amenities fees, the ARB form and the temporary "
        f"parking pass.\n\nFor {names} you would need that association directly."
    )


def not_in_documents(question: str, chosen: str = "") -> str:
    """The ordinary refusal, naming whichever documents were actually searched.

    "I could not find that in the community documents" is misleading when the
    question named Lauderdale Lakes and the Lauderdale handbook is what got
    searched, because the resident cannot tell whether we looked in the right
    book. Naming it tells them where the edge is.
    """
    scoped = [c for c in docs_index.named_communities(question)
              if c.key != docs_index.HOME_COMMUNITY]
    # Nothing named in the question, but the resident has told us which
    # community they are in. Answering them with Serenity's list of topics
    # would be the same mistake in a smaller key: it is not their association.
    if not scoped and chosen and chosen != docs_index.HOME_COMMUNITY:
        scoped = [c for c in docs_index.COMMUNITIES if c.key == chosen]
    if not scoped:
        return NO_ANSWER

    names = " and ".join(c.label for c in scoped)
    titles = [t for c in scoped for t in docs_index.documents_for(c.key)]
    held = f" What I hold for {names} is the {_join(titles)}." if titles else ""
    # No list of topics here. It used to offer "parking, bins, grass, animals or
    # fines", which came from the Lauderdale handbook and is nonsense to a
    # resident of an association whose only document is a paint colour sheet.
    # Naming what we hold says the same thing and is true of every community.
    return (
        f"I could not find that in the {names} documents, so I would rather say "
        f"so than guess.{held} Ask me about something in there and I will look it up."
    )


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


# ── the things people say that are not questions about the documents ─────────
#
# Handled here rather than by the model, and before retrieval. A greeting is not
# a search: sending "hi" through the retriever gets whichever rule happens to be
# nearest and then a refusal, which is a cold answer to a friendly opening and
# costs a model call to produce. These are instant and predictable.
SMALL_TALK: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\s*(hi|hey|hello|yo|hiya|good\s*(morning|afternoon|evening)|"
                r"salaam|assalam[ou]?\s*alaikum|howdy)\b[\s!.,]*$", re.I),
     "Hello. " + CAN_HELP_WITH + " What would you like to know?"),

    (re.compile(r"\b(how are you|how'?s it going|how do you do|are you (ok|well))\b", re.I),
     "Doing well, thank you for asking. " + CAN_HELP_WITH),

    (re.compile(r"^\s*(thanks|thank you|thankyou|ty|cheers|appreciate it|nice one)\b[\s!.,]*$", re.I),
     "You are very welcome. Ask me anything else about the community rules or "
     "the application process."),

    (re.compile(r"^\s*(bye|goodbye|see ya|see you|good\s*night|later)\b[\s!.,]*$", re.I),
     "Goodbye. I am here whenever you need the community rules."),

    (re.compile(r"\b(who are you|what are you|what can you do|what do you do|"
                r"how (can|do) you help|help me|what can i ask)\b", re.I),
     "I am the Serenity community assistant. I answer from the association's "
     f"own documents, the Rules and Regulations and the application package. "
     f"{CAN_HELP_WITH}"),

    (re.compile(r"\b(are you (a )?(human|real|person|bot|robot|ai))\b", re.I),
     "I am an assistant, not a person. I only repeat what the community "
     "documents say, and I will tell you when they do not cover something. "
     "For anything that needs a human, L&C Royal Management are on "
     "(305) 228-7326."),

    (re.compile(r"\b(sorry|my bad|oops)\b", re.I),
     "No need to apologise. What would you like to know about the community?"),
]


def _small_talk(question: str) -> "str | None":
    """A friendly reply to something that is not a question about the rules.

    Deliberately narrow. The greeting patterns are anchored to the whole
    message so that "hi, what are the quiet hours" goes to the documents rather
    than being answered with a wave, and only the unanchored ones, which are
    unmistakable phrases like "how are you", may appear mid-sentence.
    """
    for pattern, reply in SMALL_TALK:
        if pattern.search(question):
            return reply
    return None

SYSTEM = """You answer questions for residents and applicants of the Serenity community association.

Answer ONLY from the numbered passages given to you. They are the association's own documents.

Rules you must follow:
- If the passages do not contain the answer, reply with exactly: NO_ANSWER
- Never use knowledge from outside the passages. Never guess a number, a time, a fee or a date.
- Quote the document's own figures exactly as written.
- If two passages disagree, say so plainly and give both, naming the document each came from.
- Be brief. Aim for under 45 words. Two sentences is usually plenty.
- When the answer really has several parts, use a short dash list, one line each, rather than
  one long paragraph. A wall of text in a small chat panel does not get read.
- Write for a resident, warm and plain. No legal preamble, no "according to the provided context".
- Answer directly. No greeting, no "Hi there", no restating the question back.
- A resident may type a topic, or a heading copied straight out of a document, or just a few
  words, rather than a full question: "quiet hours", "DUTIES AND POWERS", "pets". That is still
  a request. Tell them what the passages say about it. Do not reply NO_ANSWER merely because
  the message was not phrased as a question.
- Plain text only. No markdown, no asterisks, no bold or italics, no headings.
- Do not cite rule numbers or passage numbers in your answer; the interface shows the source beside it.
  The one exception is a disagreement, where naming the document is the point.
- Never write the word "Passage", or "the passages", or "the text provided". The resident cannot see
  them and does not know what they are. State the rule as a fact about the community."""


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    #: The community the resident is asking as, chosen once and remembered by
    #: the interface. Empty means we have not asked them yet.
    community: str = ""


class SourceOut(BaseModel):
    section: str
    document: str
    #: The community whose document this is, named as a resident would say it.
    #: Shown because an answer can draw on more than one document, and with
    #: several associations loaded, "which rules are these" is the first thing
    #: a reader needs to know.
    community: str = ""
    score: float


class AskOut(BaseModel):
    answer: str
    #: True only when the answer came out of the documents.
    grounded: bool
    #: What sort of reply this is, because "not grounded" covers three very
    #: different things and the panel has to look different for each. Styling a
    #: cheerful "Hello" as a warning, which is what a single boolean forced,
    #: reads as though something had gone wrong.
    #:
    #:   answer     from the documents, with sources
    #:   chat       a greeting or a question about the assistant itself
    #:   no_answer  the documents do not cover it
    #:   error      the assistant could not be reached
    kind: str = "answer"
    sources: list[SourceOut] = []


# How far behind the best match a passage may be and still be worth naming.
# The fee question retrieves requirement 2 at 0.62 and requirements 5 and 7 in
# the 0.4s, and only the first is about fees. Printing all three under a
# one-line answer invites the resident to go and read two irrelevant sections.
CREDIT_MARGIN = 0.12

# How many to name. Three rather than two, because a question can genuinely
# straddle three documents now that several associations are loaded, and the
# client asked for all of them to be named rather than the best two.
MAX_CREDITS = 3


def _credits(hits: list[dict]) -> list["SourceOut"]:
    """Which passages to name under the answer.

    Retrieval passes four to the model on purpose, because a neighbouring
    passage often supplies a qualifier. Naming all four is a different job:
    these are shown to a person as "where this came from", so a weak fourth
    place is noise rather than evidence.
    """
    best = hits[0]["score"]
    close = [h for h in hits if best - h["score"] <= CREDIT_MARGIN]

    # One credit per document first, then fill up with the next best. An answer
    # that draws on two documents has to name both, and naming the same document
    # twice while the second one goes unmentioned is the failure that matters:
    # the two Serenity rulebooks disagree with each other.
    seen: set[str] = set()
    keep: list[dict] = []
    for hit in close:
        if hit["document_short"] not in seen:
            seen.add(hit["document_short"])
            keep.append(hit)
    shown = {(h["document_short"], h["section"]) for h in keep}
    for hit in close:
        if len(keep) >= MAX_CREDITS:
            break
        # A long section split into parts retrieves as several chunks with the
        # same label. Three identical chips under one answer is not evidence,
        # it is a stutter.
        key = (hit["document_short"], hit["section"])
        if key in shown:
            continue
        shown.add(key)
        keep.append(hit)
    keep = sorted(keep[:MAX_CREDITS], key=lambda h: -h["score"])

    return [
        SourceOut(
            section=h["section"],
            document=h["document_short"],
            community=docs_index.label_for(h.get("community", docs_index.HOME_COMMUNITY)),
            score=h["score"],
        )
        for h in keep
    ]


_QUESTION_SHAPE = re.compile(
    r"\?|^\s*(what|when|where|which|who|how|why|can|may|do|does|did|is|are|"
    r"was|were|should|could|would|will|am|has|have|tell me|explain)\b",
    re.IGNORECASE,
)


def _asked(message: str) -> str:
    """How the resident's message is put to the model.

    A question is passed through as one. Anything else is named as a topic,
    because the client typed "DUTIES AND POWERS of lauderdale lake", copied from
    a heading in the handbook, and got a refusal: retrieval had found the right
    passage at 0.626, and the model then judged it against a question nobody had
    asked. The passages are unchanged and so is the licence to refuse; only the
    framing of the request differs.
    """
    if _QUESTION_SHAPE.search(message):
        return f"Resident's question: {message}"
    return (f"Resident asked about: {message}\n\n"
            "Tell them what the community documents say about that.")


def _context(hits: list[dict]) -> str:
    return "\n\n".join(
        f"[Passage {i}] From \"{h['document']}\", {h['section']}:\n{h['text']}"
        for i, h in enumerate(hits, 1)
    )


def answer_from_documents(question: str,
                          sources: "list[SourceOut] | None" = None,
                          chosen: str = "") -> "str | None":
    """A grounded answer, or None. The shared core, used by two callers.

    The floating panel calls it through `/docs/ask` below. The booking chat used
    to call it as well; it does not any more, because one box answering both
    "what are the quiet hours" and "my sink is blocked" had to guess which of
    them was being asked, and guessing wrong is what the client kept seeing.

    None means "the documents do not answer this", including small talk and
    model failures, so a caller with its own wording for that case can use it.
    """
    question = (question or "").strip()
    if _small_talk(question) is not None:
        return None

    # A community we have no documents for is answered, not passed over. The
    # caller's fallback is a catalogue search, and letting "what are the rules
    # in Three Lakes" fall through to that would show somebody a plumber and
    # leave the question hanging. Say plainly that we do not hold them.
    missing = docs_index.unavailable(question)
    if missing:
        return _no_documents(missing)

    hits = docs_index.search(question, k=4, chosen=chosen or None)
    if not hits:
        return None

    reply = gemini_service.generate(
        SYSTEM,
        f"{_context(hits)}\n\n{_asked(question)}",
        max_tokens=320,
        temperature=0.0,
    )
    if not reply:
        return None
    reply = _tidy(reply.strip())
    if "NO_ANSWER" in reply.upper() or len(reply) < 2:
        return None
    if sources is not None:
        sources.extend(_credits(hits))
    return reply


def _tidy(reply: str) -> str:
    """Strip what the model adds despite being asked not to.

    The prompt forbids markdown and passage numbers and mostly holds, but
    *Serenity Point Rules and Regulations* and "Passage 2 states" both reached
    live answers. The panel renders text rather than markdown, and the resident
    has never seen a passage, so both are removed here as well as forbidden
    there.
    """
    reply = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", reply)
    reply = re.sub(r"\s*\((?:see |per |from )?[^)]*(?:Rule|Passage)\s*\d+[^)]*\)", "", reply)
    # The bullet in front defeated the old anchor: "- Passage 1 states ..." kept
    # the words the resident must never see, because the line no longer began
    # with "Passage". Allow the list marker before it.
    reply = re.sub(r"(?im)^(\s*[-*\u2022]?\s*)(?:and\s+)?passage\s*\d+\s*(?:also\s*)?"
                   r"(?:states|says|notes|adds|indicates)\s*(?:that\s*)?", r"\1", reply)
    # And the same words mid sentence, which is where they land when the model
    # is contrasting two of them.
    reply = re.sub(r"(?i)\b(?:and\s+)?passage\s*\d+\s*(?:also\s*)?"
                   r"(?:states|says|notes|adds|indicates)\s*(?:that\s*)?", "", reply)
    reply = re.sub(r"(?m)^([a-z])", lambda m: m.group(1).upper(), reply)
    return re.sub(r"[ \t]{2,}", " ", reply).strip()


@router.post("/ask", response_model=AskOut)
def ask(payload: AskIn) -> AskOut:
    question = payload.question.strip()

    chat = _small_talk(question)
    if chat is not None:
        return AskOut(answer=chat, grounded=False, kind="chat")

    missing = docs_index.unavailable(question)
    if missing:
        logger.info("[DOCS] %r names %s, which we hold nothing for",
                    question[:60], ", ".join(c.label for c in missing))
        return AskOut(answer=_no_documents(missing), grounded=False, kind="no_answer")

    hits = docs_index.search(question, k=4, chosen=payload.community or None)
    if not hits:
        # No model call at all. Fastest possible path, and the one case where
        # inventing an answer would matter most.
        return AskOut(answer=not_in_documents(question, payload.community),
                      grounded=False, kind="no_answer")

    reply = gemini_service.generate(
        SYSTEM,
        f"{_context(hits)}\n\n{_asked(question)}",
        max_tokens=320,
        temperature=0.0,
    )

    if not reply:
        # The model is down or the key is missing. Say so rather than dressing a
        # failure up as "not in the documents", which would be a lie the
        # resident cannot tell apart from a real answer.
        logger.warning("[DOCS] no reply from the model for %r", question[:60])
        return AskOut(
            answer="I could not reach the assistant just now. Please try again in a moment.",
            grounded=False, kind="error",
        )

    reply = _tidy(reply.strip())
    if "NO_ANSWER" in reply.upper() or len(reply) < 2:
        return AskOut(answer=not_in_documents(question, payload.community),
                      grounded=False, kind="no_answer")

    return AskOut(answer=reply, grounded=True, kind="answer", sources=_credits(hits))


@router.get("/communities", summary="The communities a resident can be answered from")
def communities() -> dict:
    """For the interface to offer, so nobody has to type their own address.

    Only the ones we hold documents for. Three Lakes is recognised by name and
    refused politely, which is right for a typed question and wrong for a menu:
    a choice that cannot be answered should not be offered.
    """
    return {
        "communities": [
            {
                "key": c.key,
                "label": c.label,
                "documents": len(docs_index.documents_for(c.key)),
            }
            for c in docs_index.answerable()
        ],
        "home": docs_index.HOME_COMMUNITY,
    }


@router.get("/suggestions")
def suggestions() -> dict:
    """What to offer before the resident has typed anything.

    Hard-coded rather than generated: every one of these was checked against the
    documents and has an exact answer, which is the point of a suggestion. A
    generated question that the documents cannot answer would open the
    conversation with a refusal.
    """
    return {
        "greeting": "Hi. Ask me anything about the Serenity community rules, "
                    "or the application process.",
        "questions": [
            "What are the quiet hours for music and parties?",
            "How much is the application fee?",
            "When are trash and recycling days?",
            "Can I park a boat or commercial vehicle in my driveway?",
        ],
    }
