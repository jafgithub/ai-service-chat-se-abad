"""One rule for the whole suite: nothing here may reach a mail relay.

This exists because the suite was sending real email to the client. Tests book
through the real endpoint, the endpoint really schedules its emails, and the
sender opens its own database session, so a test's appointment id of 1 resolved
to appointment 1 in the *live* database. That booking has no provider on it, so
its notification falls back to the address we send from, which is the client's
own inbox. He received the same BK-00001 notice once per test run, every run,
from 12 August until 24 August.

`email_service.sending_is_allowed()` is the actual stop, and it covers every
path including ones not written yet. This is the alarm behind it: if somebody
adds a sender that opens its own connection, as the parking mailer did, the
suite fails here rather than the client finding out.

The failure is reported at teardown on purpose. Every mailer in this codebase
swallows its own exceptions, quite deliberately, so that a refusing relay cannot
turn a booking that worked into an error on screen. That means raising alone
would be silently caught and the test would pass. Recording the attempt and
asserting afterwards is what makes it impossible to miss.
"""

import smtplib

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "expects_blocked_mail: this test deliberately trips the mail block, so "
        "do not fail it for having done so",
    )


@pytest.fixture(autouse=True)
def no_outgoing_mail(request, monkeypatch):
    attempted = []

    def refuse(host="", port=0, *args, **kwargs):
        attempted.append(f"{host}:{port}")
        raise AssertionError("a test tried to open an SMTP connection")

    monkeypatch.setattr(smtplib, "SMTP", refuse)
    monkeypatch.setattr(smtplib, "SMTP_SSL", refuse)
    yield
    if "expects_blocked_mail" in request.keywords:
        return
    assert not attempted, (
        "this test opened an SMTP connection to "
        + ", ".join(attempted)
        + ". Every mailer swallows its own errors, so this would have gone out "
          "for real when the suite runs with live settings. Route it through "
          "email_service, which refuses to send during a test run."
    )
