"""Parking passes: who may have one, what the code carries, and when it stops.

The rules that matter here are not about parking. They are that a pass belongs
to a person, that the code on a windscreen gives nothing away, and that a pass
stops working when the car leaves rather than when the clock says so.
"""

from datetime import datetime, timedelta

import pytest

from app.models.parking import EXPIRED, ISSUED, ParkingPass
from app.services import parking


def a_pass(**kwargs) -> ParkingPass:
    now = datetime.utcnow()
    fields = dict(
        id=1, account_id=1, community="serenity", vehicle_registration="ABC 1234",
        token=parking.new_token(), status=ISSUED, issued_at=now,
        expires_at=now + timedelta(days=5), exited_at=None,
    )
    fields.update(kwargs)
    return ParkingPass(**fields)


# ── the token ────────────────────────────────────────────────────────────────

def test_tokens_are_random_and_not_a_sequence():
    """A token is the whole credential. Knowing one must say nothing about the
    next, so they come from `secrets` rather than from a counter."""
    tokens = {parking.new_token() for _ in range(500)}
    assert len(tokens) == 500
    assert all(len(t) == 32 for t in tokens)


def test_the_code_carries_a_token_and_nothing_else():
    """A QR on a windscreen can be photographed by anyone walking past. It must
    not carry the resident's name, their unit or their registration."""
    # A distinctive account id, because "1" appears inside a hex token by
    # chance and an assertion that fails at random is worse than none.
    pass_ = a_pass(account_id=987654, vehicle_registration="XY 55 KLM",
                   visiting="Unit 3B")
    url = parking.verify_url(pass_.token)
    assert pass_.token in url
    for private in ("XY 55 KLM", "Unit 3B", "serenity", "987654"):
        assert private not in url, private


def test_the_code_is_a_url_a_phone_can_open():
    url = parking.verify_url("abc123")
    assert url.startswith("https://")
    assert url.endswith("/parking/check?t=abc123")


# ── drawing it ───────────────────────────────────────────────────────────────

def test_the_pass_draws_as_an_svg():
    svg = parking.qr_svg("abc123")
    assert svg.lstrip().startswith("<?xml") or svg.lstrip().startswith("<svg")
    assert "</svg>" in svg


def test_the_pass_also_draws_as_a_png():
    """Outlook has never rendered inline SVG, and the emailed copy has to be a
    raster or the resident opens a message with a hole in it."""
    png = parking.qr_png("abc123")
    assert png.startswith(b"\x89PNG\r\n\x1a\n")


# ── when a pass stops working ────────────────────────────────────────────────

def test_a_fresh_pass_is_valid():
    assert a_pass().state() == "valid"


def test_leaving_spends_the_pass_whatever_the_clock_says():
    """The expiry the client asked for. A pass that still opens the barrier
    after the car has gone is a pass that can be handed to somebody else."""
    pass_ = a_pass(expires_at=datetime.utcnow() + timedelta(days=4))
    parking.mark_exit(None, pass_)
    assert pass_.state() == "used"
    assert not pass_.is_live()


def test_time_running_out_is_the_backstop():
    assert a_pass(expires_at=datetime.utcnow() - timedelta(minutes=1)).state() == "expired"


def test_the_office_can_cancel_one():
    pass_ = a_pass()
    parking.cancel(None, pass_)
    assert pass_.state() == "cancelled"
    assert not pass_.is_live()


def test_the_three_ways_of_stopping_are_told_apart():
    """Somebody at a barrier needs to know which, not just that it failed."""
    left = a_pass(); parking.mark_exit(None, left)
    ran_out = a_pass(expires_at=datetime.utcnow() - timedelta(hours=1))
    cancelled = a_pass(status=EXPIRED)
    assert {left.state(), ran_out.state(), cancelled.state()} == {"used", "expired", "cancelled"}


def test_leaving_twice_keeps_the_first_time():
    """A double scan at the barrier must not move the record."""
    pass_ = a_pass()
    parking.mark_exit(None, pass_)
    first = pass_.exited_at
    parking.mark_exit(None, pass_)
    assert pass_.exited_at == first


# ── how long a pass lasts ────────────────────────────────────────────────────

def test_the_default_is_the_only_written_rule_we_have():
    """Serenity's own form allows five days. It is the only rule any of these
    associations has put in writing, so it is the default everywhere until
    somebody says otherwise."""
    assert parking.DEFAULT_DAYS == 5
