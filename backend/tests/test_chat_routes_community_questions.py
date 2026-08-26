"""Which of the two jobs a message belongs to, decided in the main chat.

The client asked for the booking chat to answer community questions itself
rather than sending residents to the floating button. That puts one box in
front of two unrelated jobs again, so the rule that separates them is the
thing worth testing: shape decides what kind of message it is, and retrieval's
own floor decides whether the documents actually cover it.

The case that keeps coming back: "someone to cut my grass" is both a service we
book and a thing the rules have an opinion about, and the two score about the
same. Score cannot separate them. Shape can.

    cd backend && .venv/bin/python -m pytest tests/test_chat_routes_community_questions.py -q
"""

import pytest

from app.api import docs
from app.services import conversation


@pytest.mark.parametrize("said", [
    "what are the quiet hours",
    "am I allowed a dog",
    "can I park a boat at my house",
    "do I need approval to paint my front door",
    # A noun phrase, no verb, no question mark. This is how the client actually
    # typed it, and it used to be answered with a community hall to hire.
    "Lauderdale Lake community rules",
    "serenity parking rules",
    "trash days",
])
def test_a_community_question_goes_to_the_documents(said):
    assert conversation._wants_documents(said) is True


@pytest.mark.parametrize("said", [
    "my sink is blocked",
    "I need a plumber",
    "book someone to cut the grass",
    "my boiler has stopped",
    "send someone to fix the leak",
    # The one that makes shape necessary. It opens with "can I", carries the
    # documents' own vocabulary, and is still a request for a gardener.
    "can I book someone to cut the grass",
])
def test_a_job_goes_to_the_catalogue(said):
    assert conversation._wants_documents(said) is False


def test_the_documents_get_first_refusal_but_not_the_last_word():
    """Being wrong towards the documents is cheap: they return None and the
    catalogue runs exactly as it did. Being wrong towards the catalogue is what
    the client photographed."""
    assert conversation._wants_documents("what are the pet rules") is True
    assert conversation._wants_documents("I need a vet") is False


# ── what a resident is handed with the answer ────────────────────────────────

class Source:
    """The shape `answer_from_documents` appends to its `sources` list."""
    def __init__(self, document, section, community):
        self.document, self.section, self.community = document, section, community


def test_one_row_per_document_however_many_sections_were_quoted(monkeypatch):
    """Three rules out of one handbook is one thing to download. Listing it
    three times reads as three documents."""
    from app.services import doc_library

    monkeypatch.setattr(doc_library, "all_documents", lambda include_withdrawn=False: [
        {"id": "s-rules", "community": "serenity", "title": "Rules and Regulations",
         "kind": doc_library.ANSWERABLE},
    ])

    rows = conversation._documents_behind([
        Source("Rules and Regulations", "Rule 18: Noise", "Serenity Point"),
        Source("Rules and Regulations", "Rule 2: Nuisances", "Serenity Point"),
        Source("Rules and Regulations", "Rule 40: Pets", "Serenity Point"),
    ])

    assert len(rows) == 1
    # The first section, because it is the one the answer leant on hardest and
    # it tells a reader where to look once the PDF is open.
    assert rows[0]["section"] == "Rule 18: Noise"


def test_a_row_offers_both_reading_and_keeping(monkeypatch):
    from app.services import doc_library

    monkeypatch.setattr(doc_library, "all_documents", lambda include_withdrawn=False: [
        {"id": "s-arb", "community": "serenity", "title": "ARB modification form",
         "kind": doc_library.ANSWERABLE},
    ])

    row = conversation._documents_behind([
        Source("ARB modification form", "Architectural Modification Form", "Serenity Point"),
    ])[0]

    assert row["download_url"].endswith("/file")
    assert row["view_url"].endswith("?view=1")


def test_a_document_with_no_file_is_left_out(monkeypatch):
    """Cited but not in the library means there is nothing to open. A row that
    cannot be clicked is worse than no row."""
    from app.services import doc_library

    monkeypatch.setattr(doc_library, "all_documents", lambda include_withdrawn=False: [])

    assert conversation._documents_behind([
        Source("Something We Do Not Hold", "A section", "Serenity Point"),
    ]) == []


# ── a cut off answer must never reach a resident ─────────────────────────────

def test_an_unfinished_last_line_is_dropped():
    """Measured on the live site: three replies in four were being cut mid
    clause once the prompt started producing numbered steps. A resident cannot
    tell whether the missing words were a condition or a deadline."""
    cut = ("1. Provide specifications of the modification.\n"
           "2. Obtain any necessary permits from the appropriate Building and Zoning Department and")

    assert docs._drop_unfinished(cut) == "1. Provide specifications of the modification."


def test_a_finished_answer_is_left_alone():
    whole = ("1. Complete the form.\n"
             "2. Submit it to the office.")
    assert docs._drop_unfinished(whole) == whole


def test_a_single_unfinished_line_is_still_the_whole_answer():
    """Dropping it would leave nothing, and the caller reads an empty reply as
    a failure. A partial answer beats no answer."""
    only = "Quiet hours are from 11:00 PM to"
    assert docs._drop_unfinished(only) == only


# ── asking which community, once, and only when it matters ───────────────────

class Session:
    last_shown_json = []
    last_referenced_item_id = None


def test_a_plumber_is_never_asked_which_hoa_they_belong_to(monkeypatch):
    """Most people who open this want a tradesperson. Asking them which
    association they live in first is a toll on the common case, and the
    question cannot be answered by somebody who is not a resident at all."""
    assert conversation._wants_documents("my sink is blocked") is False


def test_the_question_is_only_asked_when_the_answer_is_needed():
    """By the time this branch runs, the message is known to be about the rules
    and the answer genuinely cannot be given without knowing where they live."""
    assert conversation._wants_documents("what are the quiet hours") is True
    assert conversation.PICK_COMMUNITY_REPLY.endswith("?")


def test_naming_a_community_answers_without_asking(monkeypatch):
    """"what are the Three Lakes mailbox rules" says where. Asking anyway would
    be asking a question the resident has already answered."""
    from app.services import docs_index

    named = docs_index.named_communities("what are the Three Lakes mailbox rules")

    assert [c.key for c in named] == ["three lakes"]
