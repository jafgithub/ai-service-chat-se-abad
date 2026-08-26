"""What the conversation remembers between messages.

Written from a transcript. On 26 August the client asked Kendall Square for the
quiet hours, was told correctly that the association holds only the Approved
colour archive, and replied "can you download the color archive for me ?". He
got back "Are you asking about your community's rules, or do you need someone
to come out?" Two things were wrong and both are covered here: nothing was
keeping the archive that had just been named, and `color` never matched
`colour`.

    cd backend && .venv/bin/python -m pytest tests/test_conversation_memory.py -q
"""

import pytest

from app.services import conversation, doc_library


class BareSession:
    """The session as the older tests fake it: two attributes and nothing else.

    This class is the point of the first test. Every read of the new columns
    goes through `getattr` with a default precisely so that a fake like this,
    and a row created before the migration, and a NULL column, all behave the
    same way instead of raising.
    """
    last_shown_json = []
    last_referenced_item_id = None


def test_a_session_that_predates_the_columns_does_not_raise():
    session = BareSession()

    assert conversation._mode(session) == ""
    assert conversation._remembered_documents(session) == []
    assert conversation._remembered_community(session, "") == ""


def test_what_the_interface_sends_beats_what_was_remembered():
    """A resident who has just changed community in the picker means it."""
    session = BareSession()
    session.community = "serenity"

    assert conversation._remembered_community(session, "valencia") == "valencia"
    assert conversation._remembered_community(session, "") == "serenity"


def test_entering_the_documents_forgets_the_service_list():
    """`intent.parse` resolves a bare "the first one" against `last_shown_json`
    before anything else looks at it. Left in place, somebody who searched for a
    plumber, moved on to the rules and said "download the first one" would have
    been sold a boiler service."""
    session = BareSession()
    session.last_shown_json = [{"position": 1, "id": 20, "name": "Blocked drain cleared"}]
    session.last_referenced_item_id = 20

    conversation._enter_documents(session, "serenity", [
        {"id": "s-rules", "title": "Rules and Regulations", "community": "Serenity Point"},
    ])

    assert session.last_shown_json == []
    assert session.last_referenced_item_id is None
    assert conversation._mode(session) == conversation.DOCUMENTS
    assert conversation._remembered_documents(session)[0]["title"] == "Rules and Regulations"


def test_only_a_name_and_an_id_are_remembered():
    """Not the whole record. A document withdrawn mid conversation must not be
    servable out of memory, so everything except the identity is re-read from
    the library when it is next used."""
    session = BareSession()

    conversation._remember(session, documents=[
        {"id": "s-rules", "title": "Rules and Regulations", "community": "Serenity Point",
         "answerable": True, "download_url": "/somewhere"},
    ])

    assert session.last_documents_json == [
        {"id": "s-rules", "title": "Rules and Regulations", "community": "Serenity Point"},
    ]


def test_the_switch_to_services_is_announced():
    assert conversation.SWITCHING_TO_SERVICES
    assert "—" not in conversation.SWITCHING_TO_SERVICES
    assert "–" not in conversation.SWITCHING_TO_SERVICES


# ── pointing at a document rather than naming it ─────────────────────────────

SHELF = [
    {"id": "k-colour", "title": "Approved colour archive", "community": "Kendall Square"},
    {"id": "k-rules", "title": "Rules and Regulations", "community": "Kendall Square"},
]


def test_the_clients_own_sentence_resolves():
    """The whole reason any of this exists."""
    found = doc_library.resolve_remembered(
        "can you download the color archive for me ?", SHELF)

    assert [d["id"] for d in found] == ["k-colour"]


@pytest.mark.parametrize("said, expected", [
    ("can you download that", "k-colour"),
    ("send it to me", "k-colour"),
    ("the first one", "k-colour"),
    ("the second one", "k-rules"),
    ("the last one", "k-rules"),
])
def test_pointing_back_resolves(said, expected):
    assert doc_library.resolve_remembered(said, SHELF)[0]["id"] == expected


def test_nothing_remembered_resolves_to_nothing():
    assert doc_library.resolve_remembered("download that", []) == []


def test_a_question_is_not_a_reference():
    """"what are the quiet hours" names no document and points at none. It must
    reach the retrieval, not be answered with whatever was last on screen."""
    assert doc_library.resolve_remembered("what are the quiet hours", SHELF) == []
