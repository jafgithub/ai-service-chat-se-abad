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
NOISE = re.compile(
    r"L&C ROYAL MANAGEMENT|A Community Association Management Company|"
    r"13155 SW 42|MIAMI, FL 33175|T \(305\) 228|lcroyal@lcroyalmanagement|"
    # The second management company. The amenities sheet is on GRS letterhead,
    # and without this its first chunk was the office address, which is both
    # useless to a resident and the most repeated text in that document.
    r"GRS Management|15280 NW 79TH|Miami Lakes, FL 33016|\(305\) 823-|"
    r"grsmanagement\.com|Customer@grsmanagement|"
    r"^Page \d+ of \d+$|^FOR OFFICE USE ONLY$|^Updated By:|^ONE PER ADULT$|"
    # The handbook repeats its own name and the page number across the top of
    # every page. Left in, it is both noise and the most repeated text in the
    # document, which is the worst thing a chunk can open with.
    r"CITY OF LAUDERDALE LAKES CODE COMPLIANCE HANDBOOK|PAGE \| \d+|"
    # The colour sheets are browser print-outs: a date and time across the top,
    # the print URL along the bottom, and a stray "Feedback" button.
    r"^\d{1,2}/\d{1,2}/\d{2}, \d{1,2}:\d{2} [AP]M|sherwin-williams\.com/HOAPrintView|"
    r"^\s*Feedback\s*$|1-800-4-SHERWIN",
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


# Small capitals come out of the PDF with the first letter split off:
# "L AWN , S WALE" for "LAWN, SWALE". Glue them back before anything tries to
# recognise a heading, or every heading in the handbook is invisible.
_SMALL_CAPS = re.compile(r"\b([A-Z]) ([A-Z]{2,})\b")


def unmangle(line: str) -> str:
    """Glue the split letters back, but only on a line that is really small caps.

    The test is two or more splits on the same line. "A NIMALS AND P ESTS" has
    two and is small caps; "HOW TO REPORT A POSSIBLE CODE VIOLATION" has one and
    is ordinary text where "A" is simply the word "a". Gluing unconditionally
    turned that heading into "APOSSIBLE", which is how this rule earned its
    condition.
    """
    if len(_SMALL_CAPS.findall(line)) >= 2:
        line = _SMALL_CAPS.sub(r"\1\2", line)
    else:
        # A single split on the line. Only "A" and "I" are words on their own,
        # so anything else is a small capital that lost its word: "B USINESS".
        line = _SMALL_CAPS.sub(
            lambda m: m.group(0) if m.group(1) in ("A", "I") else m.group(1) + m.group(2),
            line)
    return re.sub(r"\s+([,;:])", r"\1", line).strip()


def heading_of(line: str) -> "str | None":
    """A section heading, or None.

    These documents mark a section with a line in capitals and nothing else on
    it. That is worth finding, because the heading is what a resident types:
    the client copied "DUTIES AND POWERS" straight out of the handbook.
    """
    text = unmangle(line)
    if not 4 <= len(text) <= 60:
        return None
    if text.endswith("."):
        return None
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 4 or not all(c.isupper() for c in letters):
        return None
    if not re.fullmatch(r"[A-Z0-9 &,'/()\-]+", text):
        return None
    return text


# ── the approved colour sheets: three columns that must not come apart ──────

_CELL = re.compile(r"\S+(?: \S+)*?(?=\s{2,}|$)")
_SWCODE = re.compile(r"SW \d{3,4}")


def _cells(line: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group().strip()) for m in _CELL.finditer(line) if m.group().strip()]


def chunk_colours(pdf: Path, title: str, short: str, community: str) -> list[dict]:
    """One chunk per association, with each surface paired to its own colour.

    These sheets are three columns wide: the surfaces on one line, the codes a
    few lines below, the colour names below that. Squashed into prose the way
    every other document is, they become "Body Trim Accent SW 6106 SW 6076 SW
    6119 Kilim Beige Turkish Coffee Antique White", and a resident asking what
    colour to paint their body could be told Turkish Coffee. So the columns are
    paired by their position on the page before anything else happens, and the
    chunk says "Body is SW 6106 Kilim Beige" in as many words.

    Everything a resident needs is on one page, so it stays one chunk: splitting
    it would separate a colour from the surface it belongs to, which is the very
    thing this function exists to prevent.
    """
    lines = [ln for ln in clean(text_of(pdf)) if ln.strip()]

    pairs: list[tuple[str, str, str]] = []
    #: The line above the first row of surfaces, which is where these sheets
    #: print the scheme's name: "Exterior Repaint", "Scheme 1A", "Coral Gables 1".
    scheme = ""
    i = 0
    while i < len(lines) - 2:
        if _SWCODE.search(lines[i + 1]) and not _SWCODE.search(lines[i]):
            if not scheme and i:
                scheme = lines[i - 1].strip()
            codes = [(m.start(), m.group()) for m in _SWCODE.finditer(lines[i + 1])]
            names = _cells(lines[i + 2])
            for column, label in _cells(lines[i]):
                code = min(codes, key=lambda c: abs(c[0] - column))
                # Within a column's width. A label with no code under it is a
                # heading, not a surface, and is left alone.
                if abs(code[0] - column) < 14:
                    name = min(names, key=lambda n: abs(n[0] - column))
                    pairs.append((label, code[1],
                                  name[1] if abs(name[0] - column) < 14 else ""))
            i += 3
            continue
        i += 1

    if not pairs:
        return []

    said = ". ".join(f"{label} is {code} {name}".strip() for label, code, name in pairs)
    advisory = ("These schemes were approved by the association. Colour standards can "
                "change, so check with the community manager before painting.")
    body = (f"Approved exterior paint colours"
            f"{f', scheme {scheme}' if scheme else ''}: {said}. {advisory}")

    return [{
        "id": re.sub(r"[^a-z0-9]+", "-", pdf.stem.lower()).strip("-") + "-colours",
        "document": title,
        "document_short": short,
        "community": community,
        "approved": "",
        "section": "Approved exterior colours",
        "text": body,
    }]


def chunk_generic(pdf: Path, title: str, short: str, community: str) -> list[dict]:
    """Any document without a structure worth special casing.

    Paragraph blocks under the heading they sit beneath. The two hand written
    chunkers above exist because the rules sheet and the management pack have
    real structure worth following; most documents do not, and writing a parser
    per document would not survive the client sending a fifth one.

    **The heading, not the document title, is what goes into the embedding.**
    Prepending "City of Lauderdale Lakes Code Compliance Handbook: " to all
    ninety three chunks made every one of them open with the same fifty
    characters, so "DUTIES AND POWERS of lauderdale lake" matched all of them
    about equally: the top four came back at 0.626, 0.611, 0.609 and 0.608, the
    passage that actually holds that section was not among them, and the model
    was left refusing a question it had been given no way to answer. A repeated
    prefix is not context, it is noise with the volume turned up.
    """
    lines = clean(text_of(pdf))

    # Blocks, each tagged with the heading in force when it started.
    blocks: list[tuple[str, list[str]]] = []
    current: list[str] = []
    heading = ""
    for ln in lines:
        found = heading_of(ln) if ln.strip() else None
        if found:
            if current:
                blocks.append((heading, current))
                current = []
            heading = found
            continue
        if ln.strip():
            current.append(ln)
        elif current:
            blocks.append((heading, current))
            current = []
    if current:
        blocks.append((heading, current))

    # Merge short blocks forward rather than dropping them. The first version
    # dropped anything under twelve words, which threw away the one line that
    # answers "how much are the condo docs": "Condo Docs/Bylaws Fee $25.00" is
    # six words. On a form, the short lines are the facts. Only within one
    # heading, so a stray line cannot drag the next section's text into itself.
    merged: list[tuple[str, list[str]]] = []
    for head, block in blocks:
        if merged and merged[-1][0] == head and len(" ".join(merged[-1][1]).split()) < 35:
            merged[-1] = (head, merged[-1][1] + block)
        else:
            merged.append((head, block))

    slug = re.sub(r"[^a-z0-9]+", "-", pdf.stem.lower()).strip("-")
    out: list[dict] = []
    for i, (head, block) in enumerate(merged, 1):
        text = squash(block)
        # Keep anything carrying a number: fees, dates, hours and limits are
        # what people ask about. Drop only short prose with nothing in it.
        if len(text.split()) < 8 and not re.search(r"\d", text):
            continue
        # A document with no headings at all, which is most forms, keeps the
        # short title as its label. There the title is the only context there
        # is, and with four chunks it cannot drown anything.
        label = head.title() if head else short
        for part in split_long(text):
            out.append({
                "id": f"{slug}-{i}-{len(out) + 1}",
                "document": title,
                "document_short": short,
                "community": community,
                "approved": "",
                "section": label,
                "text": f"{label}: {part}",
            })
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
