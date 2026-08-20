"""Which community a question is answered from, and how it reaches the documents.

Both halves of what the client saw in his screenshots. "Lauderdale Lake
community rules" never reached the documents at all, and "Three Lake community
rules" reached them and came back with Serenity's rules about the lakes. The
first is a routing bug, the second is worse: rules about somebody's home, from a
document that does not govern it.

Retrieval here is real, so these need the index and the embedding model. Nothing
in this file calls a language model.
"""

import pytest

from app.api.docs import _no_documents, answer_from_documents, not_in_documents
from app.services import docs_index
from app.services.conversation import _wants_documents


# ── naming a community ───────────────────────────────────────────────────────

@pytest.mark.parametrize("question, expected", [
    ("Lauderdale Lake community rules", "lauderdale lakes"),
    ("Lauderdale Lakes quiet hours", "lauderdale lakes"),
    ("what does the City of Lauderdale Lakes say about bins", "lauderdale lakes"),
    ("Serenity parking rules", "serenity"),
    ("rules at Serenity Point", "serenity"),
    ("What are the rules in Three Lakes?", "three lakes"),
    ("Three Lake community rules", "three lakes"),
    ("three lakes community quiet hours", "three lakes"),
])
def test_a_named_community_is_recognised(question, expected):
    """Singular or plural, with or without "community" and "point".

    The client typed "Lauderdale Lake". The tag says "lauderdale lakes". The
    substring test this replaced missed by one letter and answered the question
    out of the Serenity documents.
    """
    keys = [c.key for c in docs_index.named_communities(question)]
    assert expected in keys, question


@pytest.mark.parametrize("question", [
    "What are the quiet hours?",
    "How much is the application fee?",
    "Can I keep a dog?",
    "I need someone to cut my grass",
])
def test_a_question_naming_nobody_names_nobody(question):
    assert docs_index.named_communities(question) == [], question


def test_a_lake_on_its_own_is_not_a_community():
    """"lake" alone must not resolve to anything, or every Serenity rule about
    the lakes would look like a question about Lauderdale Lakes."""
    assert docs_index.named_communities("can I fish in the lake") == []
    assert docs_index.named_communities("swimming in lakes") == []


def test_two_communities_in_one_question_are_both_found():
    keys = [c.key for c in docs_index.named_communities(
        "how do Serenity and Lauderdale Lakes differ on parking")]
    assert keys == ["serenity", "lauderdale lakes"]


# ── a community we hold nothing for ──────────────────────────────────────────

def test_three_lakes_is_known_but_unavailable():
    """Known by name so it can be refused by name. The PDF the client sent is a
    scan with no text layer, so there is nothing to index."""
    missing = docs_index.unavailable("What are the rules in Three Lakes?")
    assert [c.label for c in missing] == ["Three Lakes"]


@pytest.mark.parametrize("question", [
    "Serenity parking rules",
    "Lauderdale Lakes quiet hours",
    "What are the quiet hours?",
])
def test_a_community_we_hold_is_never_reported_missing(question):
    assert docs_index.unavailable(question) == [], question


@pytest.mark.parametrize("question", [
    "What are the rules in Three Lakes?",
    "Three Lake community rules",
    "quiet hours in Three Lake Community",
])
def test_an_unavailable_community_is_never_searched(question):
    """The heart of it. No passages means no model call and no answer, so there
    is no path by which Serenity's rules can be offered to somebody asking about
    Three Lakes."""
    assert docs_index.search(question) == [], question


@pytest.mark.parametrize("question", [
    "What are the rules in Three Lakes?",
    "Three Lake community rules",
])
def test_the_shared_core_says_so_rather_than_falling_through(question):
    """This is what the booking chat prints. It has to be the refusal itself,
    not None: None would send the resident on to a catalogue search and their
    question would go unanswered."""
    reply = answer_from_documents(question)
    assert reply is not None and "Three Lakes" in reply, question
    assert "do not have" in reply
    # The exact sentence he was shown instead, from Serenity's use restrictions.
    assert "fishing" not in reply.lower()
    assert "prohibited" not in reply.lower()


def test_the_refusal_names_the_community_and_offers_what_we_do_hold():
    reply = _no_documents(docs_index.named_communities("rules in Three Lakes"))
    assert "Three Lakes" in reply
    assert "Serenity Point documents" in reply


def test_a_miss_inside_a_community_we_hold_names_that_community():
    """"I could not find that in the community documents" is misleading when the
    question named Lauderdale Lakes: the resident cannot tell whether we looked
    in the right book."""
    reply = not_in_documents("Lauderdale Lakes wifi password")
    assert "Lauderdale Lakes" in reply
    assert "Lauderdale Lakes code handbook" in reply, "say what is in scope"
    assert "community documents" in not_in_documents("Do you offer free wifi?")


def test_the_documents_named_on_a_miss_are_the_ones_actually_indexed():
    """Only ever the truth about what the index holds, never a promise."""
    assert docs_index.documents_for("lauderdale lakes") == ["Lauderdale Lakes code handbook"]
    assert "Rules and Regulations" in docs_index.documents_for("serenity")
    assert docs_index.documents_for("three lakes") == []


# ── scope is applied before ranking ──────────────────────────────────────────

def communities_of(question: str) -> set:
    return {h["community"] for h in docs_index.search(question)}


def test_naming_lauderdale_returns_only_lauderdale():
    """It used to return both. Ninety three Lauderdale chunks against ninety six
    Serenity ones meant naming Lauderdale was enough for its ordinances to fill
    the top four and push the Serenity answer out."""
    hits = docs_index.search("Lauderdale Lakes quiet hours")
    assert hits, "the handbook should retrieve something"
    assert {h["community"] for h in hits} == {"lauderdale lakes"}


def test_naming_serenity_returns_only_serenity():
    hits = docs_index.search("Serenity parking rules")
    assert hits
    assert {h["community"] for h in hits} == {"serenity"}
    assert any("boat" in h["text"].lower() or "parking" in h["text"].lower()
               for h in hits)


def test_naming_nobody_stays_at_home():
    """Unchanged behaviour: no community named, Serenity only."""
    assert communities_of("What are the quiet hours?") == {"serenity"}
    assert communities_of("How much is the application fee?") == {"serenity"}


def test_lauderdale_never_leaks_into_a_home_question():
    for question in ("what are the rules about bins",
                     "can I park a commercial vehicle",
                     "do I need approval to paint my house"):
        assert "lauderdale lakes" not in communities_of(question), question


def test_naming_both_searches_both():
    """A fair question, and the one case where mixing is what was asked for."""
    hits = docs_index.search(
        "parking rules in Serenity and Lauderdale Lakes", k=8)
    assert {h["community"] for h in hits} == {"serenity", "lauderdale lakes"}


# ── the contradiction behaviour must survive all of this ─────────────────────

def test_both_quiet_hours_rules_are_still_retrieved_together():
    """Rule 2 says 10pm on a weekday, Rule 18 says 11:00PM. They really do
    disagree, and the assistant's job is to show both and name them, not to pick
    one. Retrieval has to hand the model both or it cannot."""
    sections = [h["section"] for h in docs_index.search("What are the quiet hours?")]
    assert any("Rule 2" in s for s in sections), sections
    assert any("Rule 18" in s for s in sections), sections


# ── routing: does the booking chat consult the documents at all ──────────────

@pytest.mark.parametrize("message", [
    "Lauderdale Lake community rules",
    "Lauderdale Lakes quiet hours",
    "Serenity parking rules",
    "community rules about pets",
    "What are the quiet hours?",
    "Three Lakes community rules",
    "What are the rules in Three Lakes?",
    "how much is the application fee",
    "hoa restrictions on fences",
    "do I need approval to paint my house",
    "trash collection days",
])
def test_a_question_about_the_community_reaches_the_documents(message):
    """A noun phrase is how people search. None of these open with a question
    word, and before this they were all catalogue searches."""
    assert _wants_documents(message), message


@pytest.mark.parametrize("message", [
    "I need someone to cut my grass",
    "book a plumber",
    "I need a boiler repair",
    "my sink is leaking",
    "send someone to fix the boiler",
    "arrange a gardener for Saturday",
    "can I book someone to cut the grass",
    "I need an electrician",
    "gardening",
    "house cleaning",
])
def test_a_request_for_a_tradesperson_still_goes_to_the_catalogue(message):
    """Booking wins outright. "Someone to cut my grass" scores 0.470 against the
    lawn rule, higher than several genuine policy questions, so score cannot
    make this call and shape has to."""
    assert not _wants_documents(message), message


@pytest.mark.parametrize("message", [
    "Lauderdale Lake community rules",
    "Lauderdale Lakes quiet hours",
    "Serenity parking rules",
    "Three Lake community rules",
    "What are the rules in Three Lakes?",
])
def test_a_named_community_question_is_owned_by_the_documents(message):
    """Both halves of the rule the booking chat applies.

    The message reaches the documents, and because it names a place, a miss
    there is reported as a miss rather than falling through to the catalogue.
    Falling through is what the client photographed: "Lauderdale Lake community
    rules" answered with "Community hall booking, from $35.00".
    """
    assert _wants_documents(message), message
    assert docs_index.named_communities(message), message


@pytest.mark.parametrize("message", [
    "I need someone to cut my grass",
    "book a plumber",
    "window cleaning please",
])
def test_a_service_request_is_never_owned_by_the_documents(message):
    assert not _wants_documents(message), message
