"""Build the web version of the walkthrough.

Same content as the Word file, from the same source.md, so the two cannot drift.
Screenshots are downscaled on the way out: they are captured at 2x for print and
that is more than a browser needs.

    python3 render_html.py          # -> build/web/index.html + build/web/img/

Deploy is an rsync of build/web/ to the server; see README.md.
"""

import html
import re
import shutil
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source.md"
OUT = HERE / "build" / "web"
IMG_WIDTH = 1500          # plenty for a 760px column on a high density screen

STYLE = """
:root {
  --bg:#FFFFFF; --ink:#14130F; --muted:#77726A; --faint:#A8A29A;
  --line:#E9E6E1; --sunk:#FAF8F5; --accent:#C25317; --good:#2F6B4C;
}
@media (prefers-color-scheme: dark) {
  :root { --bg:#131211; --ink:#F0EDE7; --muted:#A29C93; --faint:#736D65;
          --line:#2B2926; --sunk:#1B1917; --accent:#E8905A; --good:#71C295; }
}
:root[data-theme="dark"] {
  --bg:#131211; --ink:#F0EDE7; --muted:#A29C93; --faint:#736D65;
  --line:#2B2926; --sunk:#1B1917; --accent:#E8905A; --good:#71C295;
}
:root[data-theme="light"] {
  --bg:#FFFFFF; --ink:#14130F; --muted:#77726A; --faint:#A8A29A;
  --line:#E9E6E1; --sunk:#FAF8F5; --accent:#C25317; --good:#2F6B4C;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
h1, h2 { scroll-margin-top: 22px; }
.toc {
  margin: 30px 0 8px; padding: 20px 22px 14px;
  background: var(--sunk); border: 1px solid var(--line); border-radius: 12px;
}
.toc .toch {
  margin: 0 0 10px; font-size: 12px; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--faint);
}
.toc a {
  display: block; text-decoration: none; color: var(--ink);
  padding: 4px 0; font-size: 15.5px; line-height: 1.45;
  border-bottom: 1px solid transparent;
}
.toc a:hover { color: var(--accent); }
.toc a.t2 { padding-left: 20px; font-size: 14.5px; color: var(--muted); }

/* One click back to the index, from every document. */
.back {
  display: inline-block; margin: 0 0 30px; text-decoration: none;
  font-size: 14.5px; font-weight: 600; color: var(--muted);
  border: 1px solid var(--line); border-radius: 999px; padding: 6px 14px;
  background: var(--sunk);
}
.back:hover { color: var(--accent); border-color: var(--accent); }
.back::before { content: "\\2190"; margin-right: 7px; }

body {
  margin: 0 auto; max-width: 820px; padding: 64px 28px 120px;
  background: var(--bg); color: var(--ink);
  font: 17px/1.62 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
}
h1 {
  font-size: 30px; line-height: 1.2; letter-spacing: -0.022em; font-weight: 650;
  margin: 68px 0 18px; padding-top: 26px; border-top: 1px solid var(--line);
  text-wrap: balance;
}
h1:first-of-type { margin-top: 0; padding-top: 0; border-top: none; }
h2 {
  font-size: 19px; font-weight: 650; margin: 38px 0 12px; letter-spacing: -0.01em;
}
p { margin: 0 0 16px; }
strong { font-weight: 650; }
code {
  font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: 0.87em;
  background: var(--sunk); border: 1px solid var(--line); padding: 1px 5px; border-radius: 4px;
}
hr { border: none; border-top: 1px solid var(--line); margin: 46px 0; }
ul, ol { margin: 0 0 16px; padding-left: 22px; }
li { margin-bottom: 6px; }
figure { margin: 26px 0; }
figure img {
  display: block; width: 100%; height: auto;
  border: 1px solid var(--line); border-radius: 10px;
}
.tw { overflow-x: auto; margin: 22px 0; border: 1px solid var(--line); border-radius: 10px; }
table { border-collapse: collapse; width: 100%; font-size: 15px; }
th, td { padding: 9px 14px; text-align: left; border-bottom: 1px solid var(--line); vertical-align: top; }
th {
  background: var(--sunk); font-size: 11px; letter-spacing: 0.07em;
  text-transform: uppercase; color: var(--muted); font-weight: 650; white-space: nowrap;
}
tbody tr:last-child td { border-bottom: none; }
.masthead { margin-bottom: 40px; }
.masthead .eyebrow {
  font-size: 11.5px; letter-spacing: 0.13em; text-transform: uppercase;
  color: var(--accent); font-weight: 650; margin: 0 0 12px;
}
.masthead .title {
  font-size: clamp(30px, 4.2vw, 40px); line-height: 1.13; letter-spacing: -0.025em;
  font-weight: 650; margin: 0 0 14px; text-wrap: balance;
}
.masthead .sub { color: var(--muted); font-size: 18px; margin: 0 0 18px; }
.masthead .by { color: var(--faint); font-size: 14px; margin: 0; }
@media (max-width: 640px) {
  body { padding: 40px 18px 80px; font-size: 16px; }
  h1 { font-size: 25px; }
}
"""


def slug(text: str) -> str:
    """A heading's anchor: "3. Retrieval and scoping" -> "s3-retrieval-and-scoping".

    Built from the text rather than a counter, so an anchor someone has
    bookmarked survives a section being inserted above it.
    """
    out = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return "s" + out


def inline(text: str) -> str:
    out = html.escape(text)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    return out


def render(md: str, images: dict[str, str]) -> tuple[str, list[tuple[int, str, str]]]:
    lines = md.splitlines()
    out: list[str] = []
    toc: list[tuple[int, str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            out.append("<hr>")
            i += 1
            continue

        image = re.match(r"!\[(.*?)\]\((.+?)\)", stripped)
        if image:
            src = images.get(Path(image.group(2)).name)
            if src:
                alt = html.escape(image.group(1))
                out.append(f'<figure><img src="{src}" alt="{alt}" loading="lazy"></figure>')
            i += 1
            continue

        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                head, *body = rows
                # A leading empty header means the table is a two-column layout
                # rather than a real header row, so do not render one.
                has_head = any(c for c in head)
                out.append('<div class="tw"><table>')
                if has_head:
                    out.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead>")
                else:
                    body = rows
                out.append("<tbody>")
                for row in body:
                    out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
                out.append("</tbody></table></div>")
            continue

        heading = re.match(r"(#{1,3})\s+(.*)", stripped)
        if heading:
            level = min(len(heading.group(1)), 2)
            text = heading.group(2)
            anchor = slug(text)
            toc.append((level, anchor, text))
            out.append(f'<h{level} id="{anchor}">{inline(text)}</h{level}>')
            i += 1
            continue

        if re.match(r"[-*]\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"[-*]\s+", lines[i].strip()):
                items.append(inline(re.sub(r"^[-*]\s+", "", lines[i].strip())))
                i += 1
            out.append("<ul>" + "".join(f"<li>{t}</li>" for t in items) + "</ul>")
            continue

        if re.match(r"\d+\.\s+", stripped):
            items = []
            while i < len(lines) and re.match(r"\d+\.\s+", lines[i].strip()):
                items.append(inline(re.sub(r"^\d+\.\s+", "", lines[i].strip())))
                i += 1
            out.append("<ol>" + "".join(f"<li>{t}</li>" for t in items) + "</ol>")
            continue

        block = []
        while i < len(lines) and lines[i].strip() and not re.match(
                r"(#{1,3}\s|[-*]\s|\d+\.\s|\||>|```|!\[|---$)", lines[i].strip()):
            block.append(lines[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(block))}</p>")

    return "\n".join(out), toc


def contents(toc: list[tuple[int, str, str]]) -> str:
    """The clickable table of contents, built from the headings themselves."""
    rows = []
    for level, anchor, text in toc:
        cls = "t1" if level == 1 else "t2"
        rows.append(f'<a class="{cls}" href="#{anchor}">{inline(text)}</a>')
    return ('<nav class="toc" aria-label="Contents">'
            '<p class="toch">Contents</p>' + "".join(rows) + "</nav>")


def main() -> None:
    web = OUT
    img_dir = web / "img"
    if web.exists():
        shutil.rmtree(web)
    img_dir.mkdir(parents=True)

    images: dict[str, str] = {}
    total = 0
    for src in sorted((HERE / "build").glob("*.png")):
        image = Image.open(src).convert("RGB")
        if image.width > IMG_WIDTH:
            height = round(image.height * IMG_WIDTH / image.width)
            image = image.resize((IMG_WIDTH, height), Image.LANCZOS)
        # Screenshots use a handful of real colours, but resizing smears them
        # into tens of thousands, which PNG then cannot compress. Reducing to a
        # palette takes each file to roughly a third with nothing visible lost.
        image = image.quantize(colors=256, method=Image.MEDIANCUT)
        dest = img_dir / src.name
        image.save(dest, optimize=True)
        images[src.name] = f"img/{src.name}"
        total += dest.stat().st_size
    print(f"{len(images)} images, {total / 1024:.0f} KB after downscaling")

    md = SOURCE.read_text()
    body, toc = render(md, images)

    toc_html = contents(toc)
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Service Assistant: the booking platform</title>
<style>{STYLE}</style>
</head>
<body>
<a class="back" href="https://dev.agent.fordev.fun/docs/">All documents</a>
<div class="masthead">
  <p class="eyebrow">Development walkthrough</p>
  <p class="title">Service Assistant: the booking platform</p>
  <p class="sub">Describe a problem, see who can do it, pick a time, book it. How it works, where it runs, and the result of every test.</p>
  <p class="by">Abad Naseer &nbsp;&middot;&nbsp; 12 August 2026 &nbsp;&middot;&nbsp; captured on the development server, 32 services</p>
</div>
{toc_html}
{body}
</body>
</html>
"""
    (web / "index.html").write_text(page, encoding="utf-8")
    size = (web / "index.html").stat().st_size
    print(f"-> {web / 'index.html'}  ({size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
