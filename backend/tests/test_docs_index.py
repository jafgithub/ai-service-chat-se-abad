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
    assert docs_index._vectors.shape[0] == len(docs_index._chunks)
    assert docs_index._vectors.shape[1] == 384


def test_every_document_the_client_sent_is_represented():
    docs = {c["document_short"] for c in docs_index._chunks}
    for expected in ("Rules and Regulations", "Application Package",
                     "ARB modification form", "Amenities fees",
                     "Temporary parking pass", "Lauderdale Lakes code handbook"):
        assert expected in docs, expected


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


# ── the things people say that are not questions about the documents ─────────

from app.api.docs import _small_talk  # noqa: E402


@pytest.mark.parametrize("message", [
    "hi", "Hello", "hey!", "Good morning", "Assalam Alaikum", "howdy",
])
def test_a_greeting_is_answered_warmly_and_says_what_it_can_do(message):
    reply = _small_talk(message)
    assert reply is not None, message
    assert "quiet hours" in reply, "a greeting should say what it can help with"


@pytest.mark.parametrize("message, needle", [
    ("how are you?", "thank you for asking"),
    ("thanks!", "very welcome"),
    ("bye", "Goodbye"),
    ("what can you do?", "Serenity community assistant"),
    ("are you a real person?", "not a person"),
])
def test_conversational_openers_get_a_conversational_reply(message, needle):
    reply = _small_talk(message)
    assert reply is not None and needle in reply, message


def test_a_greeting_carrying_a_real_question_is_not_swallowed():
    """The point of anchoring the greeting patterns.

    "hi, what are the quiet hours" must reach the documents. Answering it with
    a wave would be worse than not having small talk at all.
    """
    assert _small_talk("hi, what are the quiet hours?") is None
    assert _small_talk("hello - how much is the application fee?") is None


@pytest.mark.parametrize("question", [
    "What are the quiet hours for music and parties?",
    "How much is the application fee?",
    "Can I keep a dog?",
    "What is the minimum lease term?",
])
def test_real_questions_are_never_treated_as_small_talk(question):
    assert _small_talk(question) is None, question



# ── the documents added on 20 August ─────────────────────────────────────────

@pytest.mark.parametrize("question, needle", [
    ("How much for a copy of the condo docs?", "25.00"),
    ("How many days is a temporary parking pass?", "five (5) days"),
    ("When can vendors work on my property?", "6:30"),
    ("Do I need approval before I start building?", "ARB"),
])
def test_the_new_documents_are_reachable(question, needle):
    assert hits_mentioning(question, needle), question


def test_the_fee_line_survived_chunking():
    """It did not, the first time.

    "Condo Docs/Bylaws Fee $25.00" is six words, and the generic chunker
    dropped anything under twelve. On a form the short lines are the facts, so
    short blocks are now merged forward rather than discarded.
    """
    corpus = " ".join(c["text"] for c in docs_index._chunks)
    assert "Condo Docs/Bylaws" in corpus
    assert "25.00" in corpus


def test_letterhead_is_not_indexed_as_content():
    """Both management companies' addresses repeat on every page, which made
    the office address the most retrievable text in the amenities sheet."""
    for c in docs_index._chunks:
        assert "grsmanagement.com" not in c["text"].lower(), c["section"]
        assert "lcroyal@" not in c["text"].lower(), c["section"]


# ── one community must not be answered out of another's documents ────────────

def test_another_communitys_rules_are_indexed_but_not_searched_by_default():
    """The client sent a City of Lauderdale Lakes handbook with the Serenity
    documents. Serenity Point is in Miami Lakes. It is indexed because he asked
    for it, and excluded from ordinary answers because a resident asking about
    their own bins must not be told another city's ordinance."""
    assert any(c["community"] == "lauderdale lakes" for c in docs_index._chunks)
    for hit in docs_index.search("When is my rubbish collected?"):
        assert hit["community"] == "serenity", hit["section"]


def test_naming_the_other_community_scopes_the_search_to_it():
    """Naming a place now scopes to that place rather than adding it to home.

    Both together was the old behaviour and it cost the home answer: the
    Lauderdale handbook is ninety three chunks against Serenity's ninety six, so
    naming Lauderdale was enough for its ordinances to fill the top four.
    """
    hits = docs_index.search("What does the Lauderdale Lakes code say about grass?")
    assert hits
    assert {h["community"] for h in hits} == {"lauderdale lakes"}


# ── routing between the booking chat and the documents ───────────────────────

from app.services.conversation import _wants_documents  # noqa: E402


@pytest.mark.parametrize("message", [
    "What are the quiet hours?", "How much is the application fee?",
    "When are trash days?", "Can I park a boat in my driveway?",
    "Do I need ARB approval to paint my door?", "How many days is a parking pass?",
])
def test_a_rules_question_routes_to_the_documents(message):
    assert _wants_documents(message), message


@pytest.mark.parametrize("message", [
    "my boiler is leaking", "I need a plumber", "book a dog walker",
    "someone to cut my grass", "can I book someone to cut the grass",
    "can you send a plumber", "window cleaning please",
])
def test_a_booking_request_never_routes_to_the_documents(message):
    """The overlap this exists for. "Someone to cut my grass" reaches the lawn
    rule at 0.470, higher than several genuine policy questions score, so the
    score cannot make this call on its own."""
    assert not _wants_documents(message), message
