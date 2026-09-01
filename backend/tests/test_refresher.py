"""
Tests for the background refresher.

What matters here is not that it rebuilds, but that it *doesn't*: rebuilding
the catalog on every pass would spend a minute of CPU every ten minutes to
arrive at the index it already had. So each test is really the same question
asked twice, once where something moved and once where nothing did.

    cd backend && .venv/bin/python -m pytest tests/test_refresher.py -q
"""

import json

import pytest

from app.services import refresher


@pytest.fixture(autouse=True)
def clean_state():
    """Each test starts with the refresher having seen nothing."""
    refresher._catalog_seen = None
    refresher._docs_seen = None
    yield
    refresher._catalog_seen = None
    refresher._docs_seen = None


class Recorder:
    """Stands in for the two things a pass can decide to rebuild."""

    def __init__(self):
        self.builds = 0

    def build(self):
        self.builds += 1
        return None


def test_the_first_pass_rebuilds_nothing(monkeypatch):
    """Start up has just built both indexes. Doing it again is pure waste."""
    catalog = Recorder()
    monkeypatch.setattr(refresher.catalog_index, "build", catalog.build)
    monkeypatch.setattr(refresher, "_catalog_stamp", lambda: (32, "2026-08-24 10:00:00", 0))

    did = refresher.refresh_once()

    assert did == {"catalog": False}
    assert catalog.builds == 0


def test_a_service_added_to_the_catalog_is_picked_up(monkeypatch):
    catalog = Recorder()
    monkeypatch.setattr(refresher.catalog_index, "build", catalog.build)

    monkeypatch.setattr(refresher, "_catalog_stamp", lambda: (32, "2026-08-24 10:00:00", 0))
    refresher.refresh_once()
    monkeypatch.setattr(refresher, "_catalog_stamp", lambda: (33, "2026-08-24 11:00:00", 1))
    did = refresher.refresh_once()

    assert did["catalog"] is True
    assert catalog.builds == 1


def test_an_edited_service_counts_even_though_the_count_is_the_same(monkeypatch):
    """A price change moves `updated_at` and nothing else. It still matters."""
    catalog = Recorder()
    monkeypatch.setattr(refresher.catalog_index, "build", catalog.build)

    monkeypatch.setattr(refresher, "_catalog_stamp", lambda: (32, "2026-08-24 10:00:00", 0))
    refresher.refresh_once()
    monkeypatch.setattr(refresher, "_catalog_stamp", lambda: (32, "2026-08-24 12:30:00", 0))

    assert refresher.refresh_once()["catalog"] is True
    assert catalog.builds == 1


def test_an_unreachable_database_is_not_a_catalog_that_changed(monkeypatch):
    """The probe returning nothing must not look like a rebuild is due, and must
    not overwrite the last good reading either."""
    catalog = Recorder()
    monkeypatch.setattr(refresher.catalog_index, "build", catalog.build)

    monkeypatch.setattr(refresher, "_catalog_stamp", lambda: (32, "2026-08-24 10:00:00", 0))
    refresher.refresh_once()
    monkeypatch.setattr(refresher, "_catalog_stamp", lambda: None)
    refresher.refresh_once()
    refresher.refresh_once()
    monkeypatch.setattr(refresher, "_catalog_stamp", lambda: (32, "2026-08-24 10:00:00", 0))

    assert refresher.refresh_once()["catalog"] is False
    assert catalog.builds == 0
