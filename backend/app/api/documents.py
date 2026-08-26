"""Uploading, listing, withdrawing and downloading community documents.

What used to be an email to me and a rebuild on my laptop. The client asked to
do it himself, so the whole path runs on the server: read the PDF, cut it into
sections, embed them, put them into the live index, and let residents download
the file.

Two rules run through it.

  * **A document is answerable only if we can read it.** A scan is an image of a
    page. It is stored, listed and downloadable, because the client asked for
    exactly that and a site map is useful to have, but nothing is ever answered
    from it and the interface says so.
  * **Everything is scoped to a community.** Uploading, listing and downloading
    all carry it. A resident downloading another association's paperwork is the
    same failure as being answered from it.
"""

import logging
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import require_admin
from app.services import doc_chunker, doc_library, docs_index

logger = logging.getLogger("docs")

router = APIRouter(prefix="/documents", tags=["documents"])

#: Big enough for a scanned handbook, small enough that a mistake is not a
#: denial of service. The largest document the client has sent is 1.5 MB.
MAX_BYTES = 25 * 1024 * 1024


class DocumentOut(BaseModel):
    id: str
    community: str
    community_label: str
    title: str
    kind: str
    sections: int
    added_at: str
    #: True when the assistant can answer from it. False for scans and drawings,
    #: which are downloadable and nothing more.
    answerable: bool
    download_url: str
    #: The same file served inline, for reading rather than saving.
    view_url: str = ""


def _out(doc: dict) -> DocumentOut:
    return DocumentOut(
        id=doc["id"],
        community=doc["community"],
        community_label=docs_index.label_for(doc["community"]),
        title=doc["title"],
        kind=doc["kind"],
        sections=doc.get("sections", 0),
        added_at=doc.get("added_at", ""),
        answerable=doc["kind"] == doc_library.ANSWERABLE,
        download_url=f"/api/v1/documents/{doc['id']}/file",
        view_url=f"/api/v1/documents/{doc['id']}/file?view=1",
    )


def _register_community(key: str, label: str) -> None:
    """Make sure the community is a name the assistant knows.

    The single most important line in this file. A document indexed under a
    community that is not in the registry is a document whose residents get
    Serenity's rules, silently, which is the bug the client reported in August.
    So the name is registered in the same request that stores the document, and
    never in a later step somebody might skip.
    """
    import json
    path = docs_index.REGISTRY_PATH
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"communities": []}
    if any(c["key"] == key for c in data["communities"]):
        return
    aliases = {key, label.lower()}
    data["communities"].append(
        {"key": key, "label": label, "aliases": sorted(aliases)})
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    docs_index.reload_registry()
    logger.info("[DOCS] registered community %r as %r", key, label)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED,
             summary="Upload a document and put it into service")
async def upload(
    file: UploadFile = File(...),
    community: str = Form(...),
    title: str = Form(""),
    community_label: str = Form(""),
    _: bool = Depends(require_admin),
) -> DocumentOut:
    key = " ".join(community.lower().split())
    if not key:
        raise HTTPException(status_code=400, detail="Which community is this for?")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files can be added.")

    label = community_label.strip() or docs_index.label_for(key)
    name = title.strip() or Path(file.filename).stem.replace("-", " ").replace("_", " ").strip()

    folder = doc_library.UPLOADS / key.replace(" ", "-")
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{doc_library.slug(name)}-{doc_library.slug(file.filename)[:24]}.pdf"

    size = 0
    with stored.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_BYTES:
                out.close()
                stored.unlink(missing_ok=True)
                raise HTTPException(status_code=413,
                                    detail="That file is larger than 25 MB.")
            out.write(chunk)
    if not size:
        stored.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="That file was empty.")

    _register_community(key, label)

    # Can it be read at all? A scan cannot, and the client asked for those to be
    # kept anyway so residents can download them.
    try:
        readable = doc_chunker.has_text(stored)
    except Exception:  # noqa: BLE001 - a broken PDF is a bad upload, not a 500
        logger.exception("[DOCS] could not read %s", stored.name)
        stored.unlink(missing_ok=True)
        raise HTTPException(status_code=400,
                            detail="That PDF could not be opened.")

    if not readable:
        doc = doc_library.record(community=key, title=name, filename=stored.name,
                                 kind=doc_library.DOWNLOAD_ONLY, sections=0)
        logger.info("[DOCS] %s stored as download only: no text layer", doc["id"])
        return _out(doc)

    sections = doc_chunker.chunk_generic(stored, name, name, key)
    if not sections:
        doc = doc_library.record(community=key, title=name, filename=stored.name,
                                 kind=doc_library.DOWNLOAD_ONLY, sections=0)
        return _out(doc)

    doc = doc_library.record(community=key, title=name, filename=stored.name,
                             kind=doc_library.ANSWERABLE, sections=len(sections))
    for i, section in enumerate(sections):
        section["doc_id"] = doc["id"]
        section["id"] = f"{doc['id']}-{i}"

    from app.services import rag
    vectors = [rag.embed_text(s["text"]) for s in sections]
    docs_index.add_chunks(sections, vectors)
    return _out(doc)


@router.get("", response_model=list[DocumentOut], summary="Every document in service")
def listing(community: str = "", _: bool = Depends(require_admin)) -> list[DocumentOut]:
    docs = doc_library.all_documents()
    if community:
        docs = [d for d in docs if d["community"] == community]
    return [_out(d) for d in sorted(docs, key=lambda d: d.get("added_at", ""), reverse=True)]


@router.delete("/{doc_id}", summary="Take a document out of service")
def withdraw(doc_id: str, _: bool = Depends(require_admin)) -> dict:
    doc = doc_library.withdraw(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="No such document.")
    # Out of the live index in the same breath, or the interface would say it is
    # gone while the assistant carried on quoting it.
    removed = docs_index.drop_document(doc_id)
    return {"removed": doc_id, "sections_removed": removed}


@router.get("/for/{community}", response_model=list[DocumentOut],
            summary="What a resident of this community may download")
def for_community(community: str) -> list[DocumentOut]:
    key = " ".join(community.lower().split())
    return [_out(d) for d in doc_library.for_community(key)]


@router.get("/{doc_id}/file", summary="Download the document itself")
def download(doc_id: str, view: bool = False):
    """The file. `?view=1` opens it in the browser instead of saving it.

    Both from one endpoint rather than two, because it is one file and the only
    difference is a header. A resident checking one line of a rule should not
    have to put a 900KB PDF in their downloads to read it, and a resident who
    wants the blank form to print does want it saved.
    """
    doc = doc_library.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="No such document.")
    path = doc_library.path_for(doc)
    if not path.exists():
        logger.error("[DOCS] %s is in the library but not on disk: %s", doc_id, path)
        raise HTTPException(status_code=404, detail="That file is missing.")
    filename = re.sub(r"[^A-Za-z0-9 ._-]", "", doc["title"])[:80] or "document"
    if view:
        # `filename=` on FileResponse forces an attachment disposition, so the
        # inline case sets the header itself and leaves the name on it: a tab
        # showing a PDF still gets titled, and Save from the viewer keeps it.
        return FileResponse(path, media_type="application/pdf", headers={
            "Content-Disposition": f'inline; filename="{filename}.pdf"',
        })
    return FileResponse(path, media_type="application/pdf",
                        filename=f"{filename}.pdf")
