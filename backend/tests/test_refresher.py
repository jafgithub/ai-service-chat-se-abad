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
    monkeypatch.setattr(refresher.docs_index, "stamps", lambda: (1.0, 2.0))

    did = refresher.refresh_once()

    assert did == {"catalog": False, "documents": False}
    assert catalog.builds == 0


def test_a_service_added_to_the_catalog_is_picked_up(monkeypatch):
    catalog = Recorder()
    monkeypatch.setattr(refresher.catalog_index, "build", catalog.build)
    monkeypatch.setattr(refresher.docs_index, "stamps", lambda: (1.0, 2.0))

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
    monkeypatch.setattr(refresher.docs_index, "stamps", lambda: (1.0, 2.0))

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
    monkeypatch.setattr(refresher.docs_index, "stamps", lambda: (1.0, 2.0))

    monkeypatch.setattr(refresher, "_catalog_stamp", lambda: (32, "2026-08-24 10:00:00", 0))
    refresher.refresh_once()
    monkeypatch.setattr(refresher, "_catalog_stamp", lambda: None)
    refresher.refresh_once()
    refresher.refresh_once()
    monkeypatch.setattr(refresher, "_catalog_stamp", lambda: (32, "2026-08-24 10:00:00", 0))

    assert refresher.refresh_once()["catalog"] is False
    assert catalog.builds == 0


def test_an_index_rewritten_on_disk_is_read_again(monkeypatch):
    reloaded = []
    monkeypatch.setattr(refresher.catalog_index, "build", lambda: None)
    monkeypatch.setattr(refresher, "_catalog_stamp", lambda: (32, "2026-08-24 10:00:00", 0))
    monkeypatch.setattr(refresher.docs_index, "reload_index", lambda: reloaded.append("index"))
    monkeypatch.setattr(refresher.docs_index, "reload_registry", lambda: reloaded.append("registry"))

    monkeypatch.setattr(refresher.docs_index, "stamps", lambda: (1.0, 2.0))
    refresher.refresh_once()
    monkeypatch.setattr(refresher.docs_index, "stamps", lambda: (9.0, 2.0))
    did = refresher.refresh_once()

    assert did["documents"] is True
    # The registry too: a document uploaded elsewhere may have brought a
    # community with it, and an index holding a community the registry has
    # never heard of answers nobody.
    assert reloaded == ["index", "registry"]


def test_a_new_community_alone_is_enough(monkeypatch):
    """The registry can change without the index changing, when a community is
    renamed or an alias is added."""
    reloaded = []
    monkeypatch.setattr(refresher.catalog_index, "build", lambda: None)
    monkeypatch.setattr(refresher, "_catalog_stamp", lambda: (32, "2026-08-24 10:00:00", 0))
    monkeypatch.setattr(refresher.docs_index, "reload_index", lambda: reloaded.append("index"))
    monkeypatch.setattr(refresher.docs_index, "reload_registry", lambda: reloaded.append("registry"))

    monkeypatch.setattr(refresher.docs_index, "stamps", lambda: (1.0, 2.0))
    refresher.refresh_once()
    monkeypatch.setattr(refresher.docs_index, "stamps", lambda: (1.0, 7.0))

    assert refresher.refresh_once()["documents"] is True


def test_the_stamps_survive_a_missing_file(tmp_path, monkeypatch):
    """A server without an index yet must give a reading rather than an error,
    or the refresher dies on its first pass and never runs again."""
    from app.services import docs_index

    monkeypatch.setattr(docs_index, "INDEX_PATH", tmp_path / "nothing.json")
    monkeypatch.setattr(docs_index, "REGISTRY_PATH", tmp_path / "nothing-either.json")

    assert docs_index.stamps() == (0.0, 0.0)

    (tmp_path / "nothing.json").write_text(json.dumps({"chunks": []}), encoding="utf-8")
    assert docs_index.stamps()[0] > 0.0


def test_switching_it_off_starts_no_thread(monkeypatch):
    monkeypatch.setattr(refresher.settings, "REFRESH_MINUTES", 0)
    refresher._thread = None

    refresher.start()

    assert refresher.status()["running"] is False
