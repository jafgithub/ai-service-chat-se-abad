"""The suite must not be able to send email, whatever a test does.

Written after the suite spent twelve days emailing the client. Every one of
those emails was the same booking, BK-00001, because the sender opens its own
database session and a test's appointment id of 1 resolves to a real row.

    cd backend && .venv/bin/python -m pytest tests/test_no_mail_from_tests.py -q
"""

import os

import pytest

from app.services import email_service, parking_emails


def test_a_test_run_is_recognised_as_one():
    assert os.environ.get("PYTEST_CURRENT_TEST")
    assert email_service.sending_is_allowed() is False


def test_the_sender_refuses_rather_than_connecting(monkeypatch):
    """No socket, no relay, no exception. The callers treat sending as best
    effort, so refusing has to look like an ordinary quiet success."""
    def explode(*args, **kwargs):
        raise AssertionError("it tried to open a connection")

    monkeypatch.setattr(email_service.smtplib, "SMTP", explode)

    assert email_service._send("someone@example.com", "Subject", "<p>body</p>") is None


def test_the_parking_mailer_refuses_too(monkeypatch):
    """It builds its own message and opens its own connection, so the guard in
    `_send` does not cover it. That is exactly how the booking path leaked."""
    def explode(*args, **kwargs):
        raise AssertionError("it tried to open a connection")

    monkeypatch.setattr(parking_emails.smtplib, "SMTP", explode)

    class Pass:
        id = 1
        token = "abc123"
        vehicle_registration = "ABC 1234"
        expires_at = None

    assert parking_emails.send_pass(Pass(), to="someone@example.com") is False


def test_outside_a_test_run_it_would_send(monkeypatch):
    """The guard must be the test run and nothing else, or production stops
    sending and nobody notices until a customer asks where their booking went."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert email_service.sending_is_allowed() is True


@pytest.mark.expects_blocked_mail
def test_the_alarm_fires_when_something_opens_a_connection():
    """The autouse fixture in conftest is the backstop. Prove it is armed:
    reaching smtplib at all has to raise, even though every caller in this
    codebase swallows exceptions."""
    import smtplib

    with pytest.raises(AssertionError):
        smtplib.SMTP("smtp.example.com", 587)
