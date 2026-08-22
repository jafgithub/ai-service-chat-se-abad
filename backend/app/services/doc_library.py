"""What documents exist, where their files are, and which may be answered from.

The index knows about *sections*. This knows about *documents*: the PDF a
resident downloads, who it belongs to, when it arrived, and whether the
assistant may answer from it at all.

That last one is the reason this file exists. The client asked to upload scans,
which cannot be read, so that residents can still download them: a site map and
a drainage drawing are useful to have and impossible to answer from. A document
is therefore one of two kinds.

    answerable     text came out of it, it is in the index, answers cite it
    download only  a scan or a drawing, stored and served, never answered from

Kept as JSON beside the index rather than in the database, because the index it
describes is a file too, and one of the two being restored from a backup while
the other is not would leave the assistant citing documents that are not there.
"""

import json
import logging
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("docs")

DATA = Path(__file__).resolve().parent.parent / "data"
LIBRARY_PATH = DATA / "documents.json"
#: Where uploaded PDFs live. Outside `knowledge/`, which holds the ones that
#: came by email and are committed to the repository.
UPLOADS = Path(__file__).resolve().parent.parent.parent / "uploads"

ANSWERABLE = "answerable"
DOWNLOAD_ONLY = "download_only"

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read() -> dict:
    try:
        return json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"documents": []}
    except Exception:  # noqa: BLE001 - a broken file must not take the app down
        logger.exception("[DOCS] document library unreadable")
        return {"documents": []}


def _write(data: dict) -> None:
    LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LIBRARY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    # Replace in one step. A half written library read by another request would
    # be a list of documents that do not exist.
    tmp.replace(LIBRARY_PATH)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "document"


def all_documents(include_withdrawn: bool = False) -> list[dict]:
    docs = _read().get("documents", [])
    if include_withdrawn:
        return docs
    return [d for d in docs if not d.get("withdrawn_at")]


def for_community(community: str) -> list[dict]:
    """Everything a resident of this community may download, newest first.

    Scoped, like everything else here. A resident downloading another
    association's paperwork is the same failure as being answered from it.
    """
    return sorted(
        [d for d in all_documents() if d["community"] == community],
        key=lambda d: d.get("added_at", ""), reverse=True,
    )


def find(community: str, title: str) -> Optional[dict]:
    """The document a retrieved section came from, so it can be offered.

    Matched on community and title because that is what a chunk carries. An
    uploaded document also carries its library id directly, and that is used
    when it is there; this is for the ones that arrived by email before the
    library existed.
    """
    for doc in all_documents():
        if doc["community"] == community and doc["title"] == title:
            return doc
    return None


def get(doc_id: str, include_withdrawn: bool = False) -> Optional[dict]:
    for doc in all_documents(include_withdrawn):
        if doc["id"] == doc_id:
            return doc
    return None


def record(*, community: str, title: str, filename: str, kind: str,
           sections: int, source: str = "upload") -> dict:
    """Add a document to the library and return it."""
    doc = {
        "id": f"{slug(community)}-{slug(title)}-{uuid.uuid4().hex[:6]}",
        "community": community,
        "title": title,
        "filename": filename,
        "kind": kind,
        "sections": sections,
        "source": source,
        "added_at": _now(),
        "withdrawn_at": None,
    }
    with _lock:
        data = _read()
        data.setdefault("documents", []).append(doc)
        _write(data)
    logger.info("[DOCS] library: added %s (%s, %s)", doc["id"], community, kind)
    return doc


def withdraw(doc_id: str) -> Optional[dict]:
    """Take a document out of service.

    Marked rather than deleted, and the file is left on disk. A document that
    was the only source of an answer changes what residents are told the moment
    it goes, and being able to put it back matters more than the disk space.
    """
    with _lock:
        data = _read()
        for doc in data.get("documents", []):
            if doc["id"] == doc_id and not doc.get("withdrawn_at"):
                doc["withdrawn_at"] = _now()
                _write(data)
                logger.info("[DOCS] library: withdrew %s", doc_id)
                return doc
    return None


def restore(doc_id: str) -> Optional[dict]:
    with _lock:
        data = _read()
        for doc in data.get("documents", []):
            if doc["id"] == doc_id and doc.get("withdrawn_at"):
                doc["withdrawn_at"] = None
                _write(data)
                logger.info("[DOCS] library: restored %s", doc_id)
                return doc
    return None


def path_for(doc: dict) -> Path:
    """Where the file actually is.

    Uploads live under `uploads/`; the documents that arrived by email are
    committed under `knowledge/` and are recorded here with their repository
    path so both kinds download the same way.
    """
    if doc.get("source") == "repo":
        return Path(__file__).resolve().parent.parent.parent / doc["filename"]
    return UPLOADS / doc["community"].replace(" ", "-") / doc["filename"]
