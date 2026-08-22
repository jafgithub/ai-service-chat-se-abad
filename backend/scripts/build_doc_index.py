"""Turn the Serenity community PDFs into a searchable index, offline.

Run on a laptop, not on the server. The output is one JSON file that ships with
the code, so the box needs no PDF library and no build step: it loads the file
into memory at startup the same way `catalog_index` loads the catalogue.

    python3 scripts/build_doc_index.py

Chunking is by structure, not by token count, because these documents are
already made of atoms. The rules sheet is nineteen numbered rules; the
management pack is a set of named sections. Cutting every 500 characters
instead would separate "Trash Days: Tuesdays and Fridays" from the heading that
says it is about garbage, and the retriever would never find it.

Two documents go in and both are kept, each chunk labelled with where it came
from, because they overlap and in two places disagree: the lease minimum is one
year in the application requirements and six months in the use restrictions,
and the rules sheet reads as a blanket ban on pets while the management pack
allows domestic ones. A grounded assistant has to be able to show both and say
which document each came from rather than silently picking a winner.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The chunking lives in the application now, because the server has to do it too
# when the client uploads a document. One implementation, so a document he adds
# is cut up exactly like the ones added by hand.
from app.services.doc_chunker import (  # noqa: E402
    chunk_colours, chunk_generic, clean, heading_of, split_long, squash, text_of,
)
from app.services.doc_chunker import (  # noqa: E402,F401  re-exported for the tests
    unmangle,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
KNOWLEDGE = ROOT / "knowledge"
SOURCE = KNOWLEDGE / "serenity"
OUT = ROOT / "app" / "data" / "serenity_docs.json"

# Everything the assistant may answer from. Adding a document is two lines here
# and a rerun; there is no code to write for an ordinary one.
#
# `community` is the thing to get right. Two of the documents the client sent
# belong to other places entirely: a City of Lauderdale Lakes code handbook,
# when Serenity Point is in Miami Lakes. Indexed, because he asked for them,
# but tagged, and `docs_index` will not search outside Serenity unless the
# question names the other community. A resident asking about their own bins
# must never be answered out of another city's ordinances.
MANIFEST = [
    # path,                                  title,                                              short,                          community
    ("other-communities/lauderdale-lakes-code-handbook.pdf",
     "City of Lauderdale Lakes Code Compliance Handbook", "Lauderdale Lakes code handbook", "lauderdale lakes"),
    ("serenity/arb-form.pdf",
     "Serenity Point Architectural Modification Form (ARB)", "ARB modification form", "serenity"),
    ("serenity/amenities-fees.pdf",
     "Serenity Point Amenities Fees", "Amenities fees", "serenity"),
    ("serenity/parking-pass.pdf",
     "Temporary Parking Pass Request", "Temporary parking pass", "serenity"),

    # Three Lakes. The design standards and the site map and drainage drawings
    # are not here: two are scans and one is a map, and none of them has text to
    # index. They belong in the download list, not the index.
    ("three-lakes/mailbox-guidelines.pdf",
     "Three Lakes Mailbox and Post Guidelines", "Mailbox guidelines", "three lakes"),
    ("three-lakes/design-review-form.pdf",
     "Three Lakes Design Review Form and Instructions", "Design review form", "three lakes"),
    ("three-lakes/direct-debit-form.pdf",
     "Three Lakes Direct Debit Enrollment Form", "Direct debit form", "three lakes"),
]

# The Sherwin-Williams colour sheets, which have their own chunker because
# their three columns must not be flattened. Same four fields.
COLOUR_SHEETS = [
    ("kendall-square/color-archive.pdf",
     "Kendall Square Homeowners Association Approved Colours",
     "Approved colour archive", "kendall square"),
    ("valencia/color-archive.pdf",
     "Valencia HOA Approved Colours", "Approved colour archive", "valencia"),
    ("enclave-old-cutler/color-archive.pdf",
     "Enclave At Old Cutler Approved Colours", "Approved colour archive", "enclave at old cutler"),
]

# Page furniture: the management company's letterhead repeats on every page and
# would otherwise be the most "relevant" text in the corpus, since it appears
# more often than anything else.
# Retrieval works on whole chunks, so an oversized one drowns its own answer:
# "Leases" runs to 675 words covering minimum terms, security deposits, guest
# occupancy and Association liability, and a question about any one of those
# matches the same undifferentiated blob. Structure comes first, then this cap.
# ── the rules sheet: nineteen numbered rules ─────────────────────────────────

RULE = re.compile(r"^\s*(\d{1,2})\.\s+([A-Z][^:]{2,60}):\s*(.*)$")


def chunk_rules(pdf: Path) -> list[dict]:
    lines = clean(text_of(pdf))
    chunks, current = [], None
    for ln in lines:
        m = RULE.match(ln)
        if m:
            if current:
                chunks.append(current)
            num, title, rest = m.group(1), m.group(2).strip(), m.group(3)
            current = {"number": int(num), "title": title, "body": [rest]}
        elif current is not None:
            current["body"].append(ln)
    if current:
        chunks.append(current)

    return [
        {
            "id": f"rules-{c['number']}",
            "document": "Serenity Point Rules and Regulations",
            "document_short": "Rules and Regulations",
            "approved": "Approved December 12, 2024",
            "section": f"Rule {c['number']}: {c['title']}",
            "text": f"Rule {c['number']} - {c['title']}: {squash(c['body'])}",
        }
        for c in chunks
    ]


# ── the management pack: requirements, then named sections ───────────────────

# An ALL CAPS line on its own is a top level heading; a short Title Case line on
# its own inside USE RESTRICTIONS is a subsection. Both were read off the real
# document rather than guessed.
TOP = re.compile(r"^[A-Z][A-Z &'’/,-]{5,45}$")
SUB = re.compile(r"^[A-Z][A-Za-z]+(?:[ ,/-]+[A-Za-z()]+){0,5}$")
REQ = re.compile(r"^\s*(\d)\)\s+(.*)$")


def chunk_application(pdf: Path) -> list[dict]:
    lines = clean(text_of(pdf))
    joined = "\n".join(lines)

    # Where the fillable form starts and where the rules half begins. Anchored
    # on text rather than page numbers so a re-export cannot silently shift it.
    form_at = joined.index("APPLICATION FORM")
    rules_at = joined.rindex("RULES AND REGULATIONS\n")
    ack_at = joined.index("I HAVE READ AND UNDERSTAND")

    head = joined[:form_at].splitlines()
    tail = joined[rules_at:ack_at].splitlines()

    chunks: list[dict] = []

    # 1. The numbered application requirements.
    current = None
    for ln in head:
        m = REQ.match(ln)
        if m:
            if current:
                chunks.append(current)
            current = {"n": int(m.group(1)), "body": [m.group(2)]}
        elif current is not None:
            current["body"].append(ln)
    if current:
        chunks.append(current)

    out = [
        {
            "id": f"apply-{c['n']}",
            "document": "Serenity Community Association Application Package",
            "document_short": "Application Package",
            "approved": "",
            "section": f"Application requirement {c['n']}",
            "text": f"Application requirement {c['n']}: {squash(c['body'])}",
        }
        for c in chunks
    ]

    # 2. The rules half, by heading.
    section, sub, body = None, None, []

    def flush():
        if not section or not body:
            return
        text = squash(body)
        if len(text) < 25:
            return
        label = f"{section}: {sub}" if sub else section
        slug = "rr-" + re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        parts = split_long(text)
        for i, part in enumerate(parts, 1):
            suffix = f" (part {i} of {len(parts)})" if len(parts) > 1 else ""
            out.append({
                "id": slug if len(parts) == 1 else f"{slug}-{i}",
                "document": "Serenity Community Association Rules and Regulations",
                "document_short": "Rules and Regulations (management pack)",
                "approved": "",
                "section": (label.title() if label.isupper() else label) + suffix,
                # The heading is repeated into every part on purpose: a part
                # that opens "no lease term shall be less than six months" has
                # to still say it is about leases, or it retrieves for nothing.
                "text": f"{label}: {part}",
            })

    for ln in tail:
        s = ln.strip()
        if not s:
            continue
        if TOP.fullmatch(s) and s not in {"SERENITY COMMUNITY", "ASSOCIATION", "FOR"}:
            flush()
            section, sub, body = s.title(), None, []
        elif section and SUB.fullmatch(s) and len(s) < 46 and not s.endswith("."):
            flush()
            sub, body = s, []
        else:
            body.append(ln)
    flush()
    return out


def main() -> None:
    rules = chunk_rules(SOURCE / "rules.pdf")
    application = chunk_application(SOURCE / "application.pdf")
    for c in rules + application:
        c["community"] = "serenity"
    chunks = rules + application

    print(f"  {len(rules):>3} chunks  rules sheet")
    print(f"  {len(application):>3} chunks  management pack")

    for rel, title, short, community in COLOUR_SHEETS:
        pdf = KNOWLEDGE / rel
        if not pdf.exists():
            sys.exit(f"missing document: {pdf}")
        got = chunk_colours(pdf, title, short, community)
        if not got:
            sys.exit(f"{pdf.name}: no colour columns found. The sheet's layout "
                     f"has changed, and guessing at it would pair a surface "
                     f"with the wrong colour.")
        chunks += got
        print(f"  {len(got):>3} chunks  {short}  [{community}]")

    for rel, title, short, community in MANIFEST:
        pdf = KNOWLEDGE / rel
        if not pdf.exists():
            sys.exit(f"missing document: {pdf}")
        got = chunk_generic(pdf, title, short, community)
        if not got:
            sys.exit(f"{pdf.name} produced no text. A scanned PDF has no text "
                     f"layer and needs OCR before it can be indexed.")
        chunks += got
        print(f"  {len(got):>3} chunks  {short}  [{community}]")

    if len(chunks) < 60:
        sys.exit(f"only {len(chunks)} chunks: the chunker did not match the document")

    if "--dry-run" in sys.argv:
        for c in chunks:
            print(f"    [{c['document_short']}] {c['section']}  ({len(c['text'].split())}w)")
        return

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    vectors = model.encode(
        [c["text"] for c in chunks],
        normalize_embeddings=True, show_progress_bar=False,
    )
    for chunk, vec in zip(chunks, vectors):
        chunk["vector"] = [round(float(x), 6) for x in vec]

    # Every community that just produced a chunk must be in the registry, or its
    # name goes unrecognised and its residents are answered from Serenity. The
    # build is the right place to notice: it is the only moment when the
    # documents and the names are both in front of us.
    registry_path = OUT.parent / "communities.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {"communities": []}
    known = {c["key"] for c in registry["communities"]}
    for key in sorted({c["community"] for c in chunks}):
        if key not in known:
            registry["communities"].append(
                {"key": key, "label": key.title(), "aliases": [key]})
            print(f"  registered a new community: {key}. Check its label and "
                  f"aliases in communities.json")
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "model": "all-MiniLM-L6-v2",
        "dimensions": len(chunks[0]["vector"]),
        "chunks": chunks,
    }), encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"  {len(chunks)} chunks -> {OUT.relative_to(ROOT)}  ({kb:.0f} KB)")


if __name__ == "__main__":
    main()
