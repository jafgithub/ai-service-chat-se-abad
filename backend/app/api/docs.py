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
- Plain text only. No markdown, no asterisks, no bold or italics, no headings.
- Do not cite rule numbers or passage numbers in your answer; the interface shows the source beside it.
  The one exception is a disagreement, where naming the document is the point.
- Never write the word "Passage", or "the passages", or "the text provided". The resident cannot see
  them and does not know what they are. State the rule as a fact about the community."""


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class SourceOut(BaseModel):
    section: str
    document: str
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


def _credits(hits: list[dict]) -> list["SourceOut"]:
    """Which passages to name under the answer.

    Retrieval passes four to the model on purpose, because a neighbouring
    passage often supplies a qualifier. Naming all four is a different job:
    these are shown to a person as "where this came from", so a weak fourth
    place is noise rather than evidence.
    """
    best = hits[0]["score"]
    keep = [h for h in hits if best - h["score"] <= CREDIT_MARGIN][:2]
    return [
        SourceOut(section=h["section"], document=h["document_short"], score=h["score"])
        for h in keep
    ]


def _context(hits: list[dict]) -> str:
    return "\n\n".join(
        f"[Passage {i}] From \"{h['document']}\", {h['section']}:\n{h['text']}"
        for i, h in enumerate(hits, 1)
    )


def answer_from_documents(question: str) -> "str | None":
    """A grounded answer, or None. The shared core, used by two callers.

    The floating panel calls it through `/docs/ask` below. The main chat calls
    it directly when the service catalogue has nothing, so a resident who types
    "what are the quiet hours" into the booking chat gets the same answer they
    would get from the panel, out of the same index, with the same grounding.

    None means "the documents do not answer this", including small talk and
    model failures, so a caller with its own wording for that case can use it.
    """
    question = (question or "").strip()
    if _small_talk(question) is not None:
        return None

    hits = docs_index.search(question, k=4)
    if not hits:
        return None

    reply = gemini_service.generate(
        SYSTEM,
        f"{_context(hits)}\n\nResident's question: {question}",
        max_tokens=320,
        temperature=0.0,
    )
    if not reply:
        return None
    reply = _tidy(reply.strip())
    if "NO_ANSWER" in reply.upper() or len(reply) < 2:
        return None
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
    reply = re.sub(r"(?im)^\s*(?:and\s+)?passage\s*\d+\s*(?:also\s*)?"
                   r"(?:states|says|notes|adds|indicates)\s*(?:that\s*)?", "", reply)
    reply = re.sub(r"(?m)^([a-z])", lambda m: m.group(1).upper(), reply)
    return re.sub(r"[ \t]{2,}", " ", reply).strip()


@router.post("/ask", response_model=AskOut)
def ask(payload: AskIn) -> AskOut:
    question = payload.question.strip()

    chat = _small_talk(question)
    if chat is not None:
        return AskOut(answer=chat, grounded=False, kind="chat")

    hits = docs_index.search(question, k=4)
    if not hits:
        # No model call at all. Fastest possible path, and the one case where
        # inventing an answer would matter most.
        return AskOut(answer=NO_ANSWER, grounded=False, kind="no_answer")

    reply = gemini_service.generate(
        SYSTEM,
        f"{_context(hits)}\n\nResident's question: {question}",
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
        return AskOut(answer=NO_ANSWER, grounded=False, kind="no_answer")

    return AskOut(answer=reply, grounded=True, kind="answer", sources=_credits(hits))


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
