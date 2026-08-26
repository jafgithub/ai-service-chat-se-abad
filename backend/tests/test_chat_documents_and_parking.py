"""The two things the client asked to be reachable from the conversation.

His words: "users ask for create parking permit in the chat, it opens up a
form ... similarly users asking for certain documents in the chat, like can you
get me Application for occupancy for serenity point, it shows link to the
document."

The interesting cases here are the ones where the two overlap. "Temporary
parking pass" is the name of a document *and* a thing a resident asks to be
issued, so the same three words mean opposite things depending on one other
word in the sentence.

    cd backend && .venv/bin/python -m pytest tests/test_chat_documents_and_parking.py -q
"""

import pytest

from app.services import doc_library, intent as intent_svc, response


class Session:
    """Enough of a session for the parser. Nothing here touches the catalogue."""
    last_shown_json = []
    last_referenced_item_id = None


def parse(text):
    return intent_svc.parse(text, Session(), None).type


# ── asking for a pass ────────────────────────────────────────────────────────

@pytest.mark.parametrize("said", [
    "I need a parking pass",
    "create a parking permit",
    "can I get a visitor pass",
    "I want a guest parking pass for tomorrow",
    "register a parking pass for my visitor",
    "how do I get a parking permit",
])
def test_asking_for_a_pass_opens_the_form(said):
    assert parse(said) == "parking"


@pytest.mark.parametrize("said", [
    # A question about the rules, which belongs to the documents. The word
    # "parking" appears in both and decides nothing on its own.
    "can I park a boat at my house",
    "what are the parking rules",
    "where are visitors allowed to park",
    # And a plain job, which belongs to the catalogue.
    "my sink is blocked",
])
def test_asking_about_parking_is_not_asking_for_a_pass(said):
    assert parse(said) != "parking"


def test_the_parking_pass_form_is_a_document_not_a_pass():
    """"Temporary parking pass" is a document Serenity holds. Asking for the
    *form* must hand over the file, not start issuing a pass."""
    assert parse("get me the temporary parking pass form") == "document"
    assert parse("can you send me a copy of the parking pass document") == "document"


# ── asking for a document ────────────────────────────────────────────────────

@pytest.mark.parametrize("said", [
    "can you get me the Application for occupancy for serenity point",
    "send me the design review form",
    "I need a copy of the mailbox guidelines",
    "download the site map",
])
def test_asking_for_a_document_is_recognised(said):
    assert parse(said) == "document"


def test_a_rules_question_is_not_a_document_request():
    """It reads like one and is not. The answer belongs to the assistant that
    can quote a section, not to a link."""
    assert parse("what are the quiet hours") != "document"
    assert parse("am I allowed a dog") != "document"


# ── finding it by name ───────────────────────────────────────────────────────

def test_titles_are_matched_not_contents(monkeypatch):
    """The client's own example names a scan. It has no readable text at all,
    so nothing inside it can match and the title is the only way in."""
    monkeypatch.setattr(doc_library, "all_documents", lambda include_withdrawn=False: [
        {"id": "s-app", "community": "serenity", "title": "Application for occupancy",
         "kind": doc_library.DOWNLOAD_ONLY},
        {"id": "s-rules", "community": "serenity", "title": "Rules and Regulations",
         "kind": doc_library.ANSWERABLE},
    ])

    found = doc_library.search_titles("can you get me the application for occupancy")

    assert [d["id"] for d in found] == ["s-app"]


def test_a_plural_still_finds_it(monkeypatch):
    monkeypatch.setattr(doc_library, "all_documents", lambda include_withdrawn=False: [
        {"id": "v", "community": "valencia", "title": "Approved colour archive",
         "kind": doc_library.ANSWERABLE},
    ])

    assert doc_library.search_titles("the approved colours")[0]["id"] == "v"


def test_one_word_in_common_is_not_a_match(monkeypatch):
    """Otherwise "the form" returns every form we hold and the resident has to
    read the list we were supposed to save them reading."""
    monkeypatch.setattr(doc_library, "all_documents", lambda include_withdrawn=False: [
        {"id": "a", "community": "three lakes", "title": "Design review form and instructions",
         "kind": doc_library.ANSWERABLE},
    ])

    assert doc_library.search_titles("design") == []


def test_the_community_scopes_it(monkeypatch):
    """A resident must not be handed another association's paperwork, which is
    the same failure as being answered from it."""
    monkeypatch.setattr(doc_library, "all_documents", lambda include_withdrawn=False: [
        {"id": "k", "community": "kendall square", "title": "Approved colour archive",
         "kind": doc_library.ANSWERABLE},
        {"id": "v", "community": "valencia", "title": "Approved colour archive",
         "kind": doc_library.ANSWERABLE},
    ])

    found = doc_library.search_titles("approved colour archive", community="valencia")

    assert [d["id"] for d in found] == ["v"]


# ── what the resident reads ──────────────────────────────────────────────────

def test_a_scan_says_it_cannot_be_asked_about():
    said = response.documents_reply([
        {"title": "Site map", "answerable": False},
    ])
    assert "Site map" in said
    assert "cannot answer" in said


def test_a_readable_document_does_not_labour_the_point():
    said = response.documents_reply([
        {"title": "Mailbox guidelines", "answerable": True},
    ])
    assert said == "Here is the Mailbox guidelines."


# ── asking a community for everything it holds ───────────────────────────────

def test_asking_for_a_community_s_documents_is_a_document_request():
    """"See what it holds" sends this, and so does anybody who types it."""
    assert parse("show me the Kendall Square documents") == "document"


def test_a_community_name_matches_no_title_by_design(monkeypatch):
    """The reason the shelf needs its own path. No document is called "Kendall
    Square", so title matching finds nothing for the most natural way to ask."""
    monkeypatch.setattr(doc_library, "all_documents", lambda include_withdrawn=False: [
        {"id": "k", "community": "kendall square", "title": "Approved colour archive",
         "kind": doc_library.ANSWERABLE},
    ])

    assert doc_library.search_titles("show me the Kendall Square documents") == []


def test_the_shelf_reply_says_how_much_there_is():
    """The count is the part that is not obvious from the list underneath. One
    colour sheet is a different proposition from six documents."""
    one = response.shelf_reply("Kendall Square", [{"title": "Approved colour archive"}])
    many = response.shelf_reply("Serenity Point", [{}] * 7)

    assert one == "Kendall Square has one document loaded. Here it is."
    assert "7 documents" in many
