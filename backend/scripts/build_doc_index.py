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
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "knowledge" / "serenity"
OUT = ROOT / "app" / "data" / "serenity_docs.json"

# Page furniture: the management company's letterhead repeats on every page and
# would otherwise be the most "relevant" text in the corpus, since it appears
# more often than anything else.
NOISE = re.compile(
    r"L&C ROYAL MANAGEMENT|A Community Association Management Company|"
    r"13155 SW 42|MIAMI, FL 33175|T \(305\) 228|lcroyal@lcroyalmanagement|"
    r"^Page \d+ of \d+$|^FOR OFFICE USE ONLY$|^Updated By:|^ONE PER ADULT$",
    re.IGNORECASE,
)


def text_of(pdf: Path) -> list[str]:
    """The PDF's text, from a sidecar .txt when there is one.

    `pdftotext -layout` is what produced these sidecars and it is the only tool
    that gets the numbered lists right, but poppler is not installed on the
    server and adding it there to read a file that never changes would be silly.
    So extraction happens once on a laptop, the .txt is committed beside the
    PDF, and the server only ever embeds. Delete a sidecar to re-extract.
    """
    sidecar = pdf.with_suffix(".txt")
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8").splitlines()
    out = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True, text=True, check=True,
    ).stdout
    sidecar.write_text(out, encoding="utf-8")
    print(f"  extracted {sidecar.name}")
    return out.splitlines()


def clean(lines: list[str]) -> list[str]:
    return [ln.rstrip() for ln in lines if not NOISE.search(ln.strip())]


# Retrieval works on whole chunks, so an oversized one drowns its own answer:
# "Leases" runs to 675 words covering minimum terms, security deposits, guest
# occupancy and Association liability, and a question about any one of those
# matches the same undifferentiated blob. Structure comes first, then this cap.
MAX_WORDS = 190


def split_long(text: str) -> list[str]:
    """One section into parts, cutting between bullets rather than mid-thought.

    These sections are bulleted lists, so the bullet is the natural seam. A
    section with no bullets falls back to sentence boundaries, and a single
    bullet longer than the cap is left alone rather than cut in half.
    """
    if len(text.split()) <= MAX_WORDS:
        return [text]

    pieces = re.split(r"\n(?=\s*[•·])", text) if "•" in text else re.split(r"(?<=\.)\s+", text)
    parts, current = [], []
    for piece in pieces:
        candidate = current + [piece]
        if current and len(" ".join(candidate).split()) > MAX_WORDS:
            parts.append("\n".join(current).strip())
            current = [piece]
        else:
            current = candidate
    if current:
        parts.append("\n".join(current).strip())
    return [p for p in parts if p.strip()]


def squash(body: list[str]) -> str:
    """Join a chunk's lines back into prose.

    `pdftotext -layout` keeps the column padding, which is what makes the
    numbered lists readable here, so indentation is collapsed rather than
    preserved and blank runs become single breaks.
    """
    text = "\n".join(ln.strip() for ln in body)
    text = re.sub(r"\n{2,}", "\n", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


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
    chunks = rules + application

    print(f"  {len(rules):>3} chunks from the rules sheet")
    print(f"  {len(application):>3} chunks from the management pack")

    if len(chunks) < 40:
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
