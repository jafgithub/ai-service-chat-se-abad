"""Turning a PDF into indexable sections, at runtime as well as offline.

This was inside `scripts/build_doc_index.py`, which runs on a laptop. It moved
here when the client asked to upload documents himself: an upload has to chunk a
PDF on the server, the same way, or a document he adds would be cut up
differently from the ones we added by hand and would answer differently too.

The script still owns the two documents with hand written structure, the rules
sheet and the management pack. Everything else, including anything uploaded,
comes through here.
"""

import re
import subprocess
from pathlib import Path


def text_of(pdf: Path) -> list[str]:
    """The PDF's text, from a sidecar .txt when there is one.

    `pdftotext -layout` is the only extractor that gets these numbered lists
    right. Offline the sidecar is committed beside the PDF so the server never
    needs poppler; for an uploaded document there is no sidecar, so it is
    written on the way through and reused if the document is ever rebuilt.
    """
    sidecar = pdf.with_suffix(".txt")
    if sidecar.exists():
        return sidecar.read_text(encoding="utf-8").splitlines()
    out = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True, text=True, check=True,
    ).stdout
    sidecar.write_text(out, encoding="utf-8")
    return out.splitlines()


def has_text(pdf: Path) -> bool:
    """Is there anything to read at all?

    A scan is an image of a page. It can be stored and handed out, and the
    client asked for exactly that, but it cannot be answered from, and saying so
    at upload is kinder than a resident finding out by being refused.
    """
    return len("".join(text_of(pdf)).split()) >= 20


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


def clean(lines: list[str]) -> list[str]:
    return [ln.rstrip() for ln in lines if not NOISE.search(ln.strip())]


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
