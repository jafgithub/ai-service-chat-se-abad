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

# Said whenever the documents do not cover the question. Deliberately names what
# it does hold, so the resident knows where the edge is instead of guessing.
NO_ANSWER = (
    "I could not find that in the Serenity community documents. I can only "
    "answer from the Rules and Regulations and the application package, so it "
    "may be worth contacting L&C Royal Management on (305) 228-7326."
)

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
  The one exception is a disagreement, where naming the document is the point."""


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class SourceOut(BaseModel):
    section: str
    document: str
    score: float


class AskOut(BaseModel):
    answer: str
    #: False when the documents did not cover it. The panel styles these
    #: differently so a refusal never reads like an answer.
    grounded: bool
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


@router.post("/ask", response_model=AskOut)
def ask(payload: AskIn) -> AskOut:
    question = payload.question.strip()

    hits = docs_index.search(question, k=4)
    if not hits:
        # No model call at all. Fastest possible path, and the one case where
        # inventing an answer would matter most.
        return AskOut(answer=NO_ANSWER, grounded=False)

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
            grounded=False,
        )

    reply = reply.strip()
    if "NO_ANSWER" in reply.upper() or len(reply) < 2:
        return AskOut(answer=NO_ANSWER, grounded=False)

    # Belt and braces on top of the prompt. The model mostly obeys "plain text",
    # but it slipped *Serenity Point Rules and Regulations* into a live answer,
    # and the panel renders text rather than markdown, so the reader would have
    # seen the asterisks. Stripping is safer than teaching the panel markdown.
    reply = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", reply)
    reply = re.sub(r"\s*\((?:see |per |from )?[^)]*(?:Rule|Passage)\s*\d+[^)]*\)", "", reply)
    reply = re.sub(r"[ \t]{2,}", " ", reply).strip()

    return AskOut(answer=reply, grounded=True, sources=_credits(hits))


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
