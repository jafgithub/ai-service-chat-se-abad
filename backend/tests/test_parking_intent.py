"""Asking for a parking pass in the conversation.

The client's words: "users ask for create parking permit in the chat, it opens
up a form". The interesting cases are the near misses. "Parking" appears in a
request for a pass, in a question about the rules, and in the name of a form,
and on its own it decides nothing.

This file used to test the document half as well. Documents moved to the
community agent, which has its own tests for them.

    cd backend && .venv/bin/python -m pytest tests/test_parking_intent.py -q
"""

import pytest

from app.services import intent as intent_svc


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
    # Reported live: every one of these went to the catalogue instead, because
    # the matcher demanded a verb. A noun phrase with no verb in it is how
    # people actually ask for a pass.
    "visitor parking",
    "guest parking",
    "visitor parking pass",
    "parking for my visitor",
    "I need parking for a visitor",
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


def test_asking_for_the_form_does_not_start_issuing_a_pass():
    """Asking for the paperwork is not asking to be issued with a pass. The
    form itself now lives with the community agent, so what matters here is
    only that these do not open the issuing flow."""
    assert parse("get me the temporary parking pass form") != "parking"
    assert parse("can you send me a copy of the parking pass document") != "parking"
