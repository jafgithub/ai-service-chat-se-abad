"""Does retrieval actually find the passage that holds the answer?

Every expectation below was read off the PDFs by hand first. The point is not
that the retriever returns something, it is that it returns the right thing, and
that it returns nothing at all for questions the documents do not cover.
"""

import pytest

from app.services import docs_index


def top_sections(question: str, k: int = 4) -> list[str]:
    return [h["section"] for h in docs_index.search(question, k=k)]


def hits_mentioning(question: str, needle: str) -> bool:
    return any(needle.lower() in h["text"].lower() for h in docs_index.search(question))


# ── the index loads at all ───────────────────────────────────────────────────

def test_the_index_is_present_and_the_right_shape():
    assert docs_index.ready(), "no index file: run scripts/build_doc_index.py"
    assert docs_index._vectors.shape[0] == 81
    assert docs_index._vectors.shape[1] == 384


# ── the four questions the panel offers first ────────────────────────────────

def test_quiet_hours_finds_the_noise_rule():
    assert hits_mentioning("What are the quiet hours for music and parties?", "10pm")


def test_application_fee_finds_the_fee():
    assert hits_mentioning("How much is the application fee?", "$125.00")


def test_trash_days_finds_tuesdays_and_fridays():
    assert hits_mentioning("When are trash and recycling days?", "Tuesdays")


def test_boat_parking_finds_the_vehicle_rule():
    assert hits_mentioning("Can I park a boat or commercial vehicle in my driveway?", "boat")


# ── things a resident would really ask ───────────────────────────────────────

@pytest.mark.parametrize("question, needle", [
    ("How long does the application take?", "15 business days"),
    ("What is the fine for breaking the rules?", "$100.00"),
    ("Do I need approval to paint my house?", "approval of the ACC"),
    ("What colour can I paint my house?", "pastel"),
    ("Can I run a business from my home?", "commercial"),
    ("What happens if my grass gets too long?", "grass"),
    ("How long can I rent my home for?", "lease"),
    ("Who decides on a complaint?", "Board of Directors"),
    ("When can construction work happen?", "Monday-Friday"),
])
def test_real_questions_reach_the_right_passage(question, needle):
    assert hits_mentioning(question, needle), question


# ── the refusal path: this is the part that must not drift ───────────────────

@pytest.mark.parametrize("question", [
    "Do you offer free wifi in the clubhouse?",
    "What is the capital of France?",
    "How do I reset my email password?",
    "Who won the World Cup?",
])
def test_questions_far_from_the_documents_retrieve_nothing(question):
    """Nothing clears the floor, so the route answers without a model at all.

    Note what is *not* in this list. "Which bank does the association use?"
    reaches Leases at 0.38, because that section really does discuss accounts
    the Association maintains, and "How do I file my tax return?" reaches the
    application requirements at 0.32. Both are refused by the model rather than
    by the floor, which is the correct division of labour: retrieval decides
    what is nearby, the model decides whether nearby is an answer.
    """
    assert docs_index.search(question) == [], question


def test_a_question_adjacent_to_the_documents_still_retrieves():
    """The floor is not the only guard, and should not be.

    "What are your opening hours on Christmas Day?" pulls Rule 2 at about 0.40,
    because Rule 2 really does talk about holidays and curfews. It is the
    nearest thing in the corpus and retrieval is right to return it. The
    documents still do not state opening hours, so the refusal for this class of
    question is the model's job, and `test_docs_route.py` is where that is
    checked. Raising the floor to swallow this case would cost real answers:
    "What colour can I paint my house?" scores 0.478.
    """
    hits = docs_index.search("What are your opening hours on Christmas Day?")
    assert hits, "expected the nuisance rule as the nearest neighbour"
    assert all(h["score"] < 0.45 for h in hits), "adjacent, not a real match"


def test_a_blank_question_is_not_searched():
    assert docs_index.search("") == []
    assert docs_index.search("  ") == []


# ── the two known contradictions must both be reachable ──────────────────────

def test_both_sides_of_the_lease_contradiction_are_indexed():
    """One year in the application requirements, six months in the use
    restrictions. The assistant can only tell a resident about both if
    retrieval can see both."""
    corpus = " ".join(c["text"] for c in docs_index._chunks)
    assert "Lease minimum is 1 year" in corpus
    assert "less than six (6) months" in corpus
