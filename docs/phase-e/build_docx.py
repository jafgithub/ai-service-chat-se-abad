"""Build the walkthrough as a Word document.

Reuses the renderer written for the speed documents, so every document handed to
the client looks the same. Google Drive converts the result to a Google Doc
cleanly and keeps the screenshots, and it stays editable either way.

Setup (once):
    uv venv .venv && uv pip install --python .venv/bin/python python-docx pillow

Then:
    python3 render_terminals.py     # pages from the captured output
    python3 render_pages.py         # photograph them
    .venv/bin/python build_docx.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# build_docs.py is copied in beside this file so the document builds
# without reaching into the grocery repository.
sys.path.insert(0, str(HERE))

import build_docs as bd  # noqa: E402
from docx import Document  # noqa: E402
from docx.shared import Inches  # noqa: E402

# add_image resolves paths against bd.HERE, which points at the speed documents.
bd.HERE = HERE

SOURCE = HERE / "source.md"
OUT = HERE / "build" / "Service_Assistant_Booking_Platform.docx"


def main() -> None:
    if not SOURCE.exists():
        sys.exit(f"missing {SOURCE.name}")

    text = SOURCE.read_text()
    problems = bd.check_dashes(SOURCE.name, text)
    if problems:
        print("\n".join(problems))
        sys.exit(f"\n{len(problems)} banned dash(es) found. Fix them and re-run.")

    doc = Document()
    bd.setup_styles(doc)
    for section in doc.sections:
        section.left_margin = section.right_margin = Inches(0.9)
        section.top_margin = section.bottom_margin = Inches(0.9)

    bd.cover(
        doc,
        "Service Assistant: the booking platform",
        "Describe a problem, see who can do it, pick a time, book it. How it works, "
        "where it runs, and the result of every test.",
        [
            "**Prepared by:** Abad Naseer",
            "**Project:** Service Assistant, conversational service booking",
            "**Environment:** Development, dev.agent.fordev.fun/plumber",
            "**Catalogue:** 32 services, 8 seeded providers",
            "**Captured:** 12 August 2026",
            "",
            "Every screenshot is the running system on the development server, "
            "photographed on the day this was written.",
        ],
    )

    bd.render(text, doc)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"-> {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
