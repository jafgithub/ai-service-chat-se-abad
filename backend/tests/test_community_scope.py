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

@pytest.fixture
def declared_but_empty(monkeypatch):
    """A community on the registry that the index holds nothing for.

    Three Lakes played this part until its documents arrived on 21 August. The
    mechanism still has to be covered, and covering it with real data means the
    test breaks every time the client sends a PDF, so it is covered with a
    community invented for the purpose.
    """
    invented = docs_index.Community("brookfield", "Brookfield",
                                    ("brookfield", "brookfield hoa"))
    monkeypatch.setattr(docs_index, "COMMUNITIES",
                        docs_index.COMMUNITIES + (invented,))
    return invented


def test_a_declared_community_with_no_documents_is_refused_by_name(declared_but_empty):
    """Declared so it can be refused by name. Answering it from Serenity is the
    failure this whole design exists to prevent."""
    missing = docs_index.unavailable("What are the rules in Brookfield?")
    assert [c.label for c in missing] == ["Brookfield"]


def test_a_declared_community_with_no_documents_is_never_searched(declared_but_empty):
    assert docs_index.search("What are the rules in Brookfield?") == []


def test_a_declared_community_with_no_documents_is_not_offered(declared_but_empty):
    """Right for a typed question, wrong for a menu: a choice that cannot be
    answered should not be on the list."""
    assert "brookfield" not in {c.key for c in docs_index.answerable()}


def test_the_shared_core_refuses_rather_than_falling_through(declared_but_empty):
    """This is what the booking chat prints. It has to be the refusal itself,
    not None: None would send the resident on to a catalogue search and their
    question would go unanswered."""
    reply = answer_from_documents("What are the rules in Brookfield?")
    assert reply is not None and "Brookfield" in reply
    assert "do not have" in reply


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
def test_a_three_lakes_question_is_answered_from_three_lakes_alone(question):
    """The client's original failure, now from the other side. It used to be
    answered out of Serenity's use restrictions; then it was refused because we
    held nothing; now it has three documents and answers from those, and from
    nothing else."""
    hits = docs_index.search(question)
    assert all(h["community"] == "three lakes" for h in hits), question
    # The exact sentence he was shown instead, from Serenity's use restrictions.
    assert not any("fishing" in h["text"].lower() for h in hits), question


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
    assert docs_index.documents_for("three lakes") == [
        "Mailbox guidelines", "Design review form", "Direct debit form"]


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


# The booking chat's routing tests used to live here. They are gone with the
# routing: the documents are no longer consulted from the booking chat at all,
# because one box answering both "what are the quiet hours" and "my sink is
# blocked" had to guess which was being asked. Every community question now
# arrives through the floating assistant, where there is nothing to guess.


# ── a heading is a request, not a question ───────────────────────────────────

from app.api.docs import _asked  # noqa: E402


@pytest.mark.parametrize("message", [
    "What are the quiet hours?",
    "How much is the application fee?",
    "Can I keep a dog?",
    "Do I need approval to paint my house",
    "is there a fine for long grass",
])
def test_a_question_is_put_to_the_model_as_a_question(message):
    assert _asked(message).startswith("Resident's question:"), message


@pytest.mark.parametrize("message", [
    "DUTIES AND POWERS of lauderdale lake",
    "quiet hours",
    "pets",
    "Serenity parking rules",
    "VIOLATIONS AND ASSOCIATION REMEDIES",
])
def test_a_heading_or_a_topic_is_put_as_a_topic(message):
    """The client copied "DUTIES AND POWERS" out of the handbook and got a
    refusal. Retrieval had found the right passage at 0.626; the model then
    judged it against a question nobody had asked."""
    framed = _asked(message)
    assert framed.startswith("Resident asked about:"), message
    assert "what the community documents say" in framed


def test_the_message_itself_is_never_altered():
    """Whatever framing is chosen, the resident's words go through intact."""
    for message in ("DUTIES AND POWERS of lauderdale lake", "What are the quiet hours?"):
        assert message in _asked(message)


# ── the community name is used for scoping, then it stops voting ─────────────

@pytest.mark.parametrize("query, expected", [
    ("DUTIES AND POWERS of lauderdale lake", "DUTIES AND POWERS"),
    ("lauderdale lakes tall grass", "tall grass"),
    ("Serenity parking rules", "parking rules"),
    ("what does Three Lakes say about fences", "what does say about fences"),
    ("rules in Serenity Point", "rules"),
])
def test_the_community_name_is_removed_before_embedding(query, expected):
    """Inside a scoped search the name cannot separate anything, because every
    chunk being scored already belongs to that community. What it does instead
    is pull the ranking towards whichever passages happen to say the word."""
    named = docs_index.named_communities(query)
    assert docs_index._without_community(query, named) == expected, query


def test_a_bare_community_name_is_left_alone():
    """Stripping it would leave nothing to search for, and "Lauderdale Lakes"
    on its own is a fair question: show them what the handbook covers."""
    for query in ("Lauderdale Lakes", "Serenity Point", "lauderdale lake"):
        named = docs_index.named_communities(query)
        assert docs_index._without_community(query, named) == query, query


def test_a_question_naming_nobody_is_untouched():
    for query in ("What are the quiet hours?", "how much is the application fee"):
        assert docs_index._without_community(query, []) == query


def test_the_section_a_resident_copied_out_of_the_handbook_is_found():
    """The client's own test: he opened the handbook, saw the heading on page 3,
    typed it in, and was told nothing matched. Retrieval had scored the mission
    statement top at 0.626 and never returned the section he named."""
    hits = docs_index.search("DUTIES AND POWERS of lauderdale lake")
    assert hits, "the section he named must come back"
    assert hits[0]["section"].lower().startswith("duties and powers"), hits[0]["section"]
    assert "code compliance officers" in hits[0]["text"].lower()


def test_headings_are_the_label_rather_than_a_part_number():
    """"Lauderdale Lakes code handbook, part 6" tells a resident nothing about
    what they are being shown, and told the retriever nothing either: every
    chunk opened with the same fifty characters."""
    sections = {c["section"] for c in docs_index._chunks
                if c["community"] == "lauderdale lakes"}
    for expected in ("Duties And Powers", "Lawn, Swale And Landscape Maintenance",
                     "Garbage, Recycling And Bulk Trash"):
        assert expected in sections, expected
    assert not any("part " in s and s.startswith("Lauderdale") for s in sections)


def test_the_running_header_is_not_indexed_as_content():
    for chunk in docs_index._chunks:
        assert "PAGE |" not in chunk["text"], chunk["section"]


# ── the two blemishes found while building the demo ──────────────────────────

from app.api.docs import _tidy  # noqa: E402
from app.services.conversation import _GREETING  # noqa: E402


@pytest.mark.parametrize("raw, gone", [
    ("- Passage 1 states loud music may not be played after 11:00PM.", "Passage"),
    ("Passage 2 says trash is collected on Tuesdays.", "Passage"),
    ("The documents differ, and Passage 3 also notes that pets must be leashed.", "Passage"),
])
def test_the_resident_never_sees_the_word_passage(raw, gone):
    """They cannot see the passages and do not know what one is. The rule
    existed; a bullet in front of it was enough to defeat the anchor."""
    assert gone not in _tidy(raw)


@pytest.mark.parametrize("message", ["hi", "Hello", "hey!", "Good morning", "howdy"])
def test_a_greeting_in_the_booking_chat_is_a_greeting(message):
    assert _GREETING.match(message), message


@pytest.mark.parametrize("message", [
    "hi, what are the quiet hours",
    "hello - how much is the application fee?",
    "my sink is blocked",
])
def test_a_greeting_carrying_a_real_message_is_not_swallowed(message):
    assert not _GREETING.match(message), message


# ── every credit says whose rules it is ──────────────────────────────────────

from app.api.docs import _credits, MAX_CREDITS  # noqa: E402


def credits_for(question: str):
    return _credits(docs_index.search(question, k=4))


def test_a_credit_names_the_community_the_document_and_the_section():
    """The client asked for all three. With several associations loaded,
    "which rules are these" is the first thing a reader needs."""
    for source in credits_for("What are the quiet hours?"):
        assert source.community == "Serenity Point", source
        assert source.document
        assert source.section


def test_a_lauderdale_answer_is_credited_to_lauderdale():
    for source in credits_for("Lauderdale Lakes tall grass"):
        assert source.community == "Lauderdale Lakes", source


def test_an_answer_from_two_documents_names_both():
    """The pets question is answered from both Serenity rulebooks, and they
    disagree. Naming one of them twice while the other goes unmentioned is the
    failure this ordering exists to prevent."""
    documents = {s.document for s in credits_for("Can I keep a dog?")}
    assert len(documents) >= 2, documents


def test_the_same_section_is_never_credited_twice():
    """A long section split into parts retrieves as several chunks under one
    label. Three identical chips is a stutter, not evidence."""
    for question in ("Lauderdale Lakes tall grass", "how long can I rent my home for",
                     "What are the quiet hours?"):
        seen = [(s.document, s.section) for s in credits_for(question)]
        assert len(seen) == len(set(seen)), (question, seen)


def test_no_more_than_three_are_named():
    for question in ("Lauderdale Lakes tall grass", "how long can I rent my home for"):
        assert len(credits_for(question)) <= MAX_CREDITS, question


# ── choosing a community, rather than being guessed at ───────────────────────

def test_every_registered_community_that_holds_documents_is_offered():
    offered = {c.key for c in docs_index.answerable()}
    for expected in ("serenity", "lauderdale lakes", "three lakes",
                     "kendall square", "valencia", "enclave at old cutler"):
        assert expected in offered, expected


def test_the_chosen_community_scopes_the_search():
    for key, expected in (("serenity", "serenity"), ("lauderdale lakes", "lauderdale lakes")):
        hits = docs_index.search("what are the rules about grass", chosen=key)
        assert hits, key
        assert {h["community"] for h in hits} == {expected}, key


def test_the_same_question_answers_differently_per_community():
    """Five inches at Serenity, six at Lauderdale Lakes. Same words, two
    associations, and a resident must only ever get their own."""
    serenity = " ".join(h["text"] for h in
                        docs_index.search("how tall can my grass be", chosen="serenity"))
    lauderdale = " ".join(h["text"] for h in
                          docs_index.search("how tall can my grass be", chosen="lauderdale lakes"))
    assert "five inches" in serenity.lower() or '5"' in serenity
    assert "six inches" in lauderdale.lower()


def test_naming_a_community_in_the_question_still_wins():
    """Somebody who types the name is asking on purpose, and the credit under
    the answer says which community it came from."""
    hits = docs_index.search("Lauderdale Lakes tall grass", chosen="serenity")
    assert {h["community"] for h in hits} == {"lauderdale lakes"}


def test_an_unknown_choice_falls_back_to_home_rather_than_nothing():
    """A stale choice, from a community whose documents were removed, must not
    scope every answer to an empty set."""
    hits = docs_index.search("What are the quiet hours?", chosen="atlantis")
    assert hits
    assert {h["community"] for h in hits} == {docs_index.HOME_COMMUNITY}


# ── the four communities added on 21 August ──────────────────────────────────

@pytest.mark.parametrize("query, expected", [
    ("what colour can I paint my door in Valencia", "valencia"),
    ("Valencia HOA colours", "valencia"),
    ("Kendall Square HOA colours", "kendall square"),
    ("Kendall Square Homeowners Association", "kendall square"),
    ("Enclave at Old Cutler paint", "enclave at old cutler"),
    ("old cutler bands colour", "enclave at old cutler"),
    ("three lakes mailbox", "three lakes"),
])
def test_the_new_communities_are_recognised(query, expected):
    assert expected in [c.key for c in docs_index.named_communities(query)], query


def test_three_lakes_now_answers_rather_than_refusing():
    """It was declared and empty on purpose while its only document was a scan.
    Three readable documents have arrived, so it is a community like any other
    and must stop saying we hold nothing for it."""
    assert docs_index.unavailable("what are the rules in Three Lakes") == []
    assert "three lakes" in {c.key for c in docs_index.answerable()}


@pytest.mark.parametrize("community, expected", [
    ("valencia", "kilim beige"),
    ("kendall square", "reliable white"),
    ("enclave at old cutler", "wool skein"),
])
def test_each_association_has_its_own_body_colour(community, expected):
    hits = docs_index.search("what colour is the body", chosen=community)
    assert hits, community
    assert {h["community"] for h in hits} == {community}
    assert expected in hits[0]["text"].lower(), community


def test_a_colour_is_never_attached_to_the_wrong_surface():
    """The sheets are three columns wide. Flattened the way every other document
    is, they read "Body Trim Accent SW 6106 SW 6076 SW 6119 Kilim Beige Turkish
    Coffee Antique White", and a resident could be told to paint their body
    Turkish Coffee. Each surface is paired to its own colour before anything
    else happens, and this is the test that says so."""
    text = docs_index.search("colours", chosen="valencia")[0]["text"]
    for surface, colour in (("Body", "SW 6106 Kilim Beige"),
                            ("Trim", "SW 6076 Turkish Coffee"),
                            ("Accent", "SW 6119 Antique White")):
        assert f"{surface} is {colour}" in text, (surface, text)

    enclave = docs_index.search("colours", chosen="enclave at old cutler")[0]["text"]
    assert "Door is SW 6142 Macadamia" in enclave
    assert "Body is SW 6148 Wool Skein" in enclave


def test_one_association_never_gets_another_ones_paint():
    for community in ("valencia", "kendall square", "enclave at old cutler"):
        hits = docs_index.search("what colour should the door be", chosen=community)
        assert {h["community"] for h in hits} == {community}, community


def test_serenity_does_not_borrow_three_lakes_mailbox_rules():
    hits = docs_index.search("mailbox post height", chosen="serenity")
    assert all(h["community"] == "serenity" for h in hits)
