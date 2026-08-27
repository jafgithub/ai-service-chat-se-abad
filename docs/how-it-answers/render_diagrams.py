"""Two pictures for the plain English explanation: how a document becomes
answerable, and what happens when somebody asks a question.

Same shapes as every other document we send: rounded box for a thing or a step,
dashed box for the thing to watch, labelled arrow for what moves. The wording is
deliberately not the wording in the technical reference. Nobody outside this
project should have to meet the words "chunk", "embedding" or "retrieval" to
understand what their assistant does.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGES = HERE / "pages"

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1420px;padding:26px 30px;background:#fff;
 font-family:"DejaVu Sans","Liberation Sans",system-ui,sans-serif;color:#14213a}
.head{display:flex;align-items:baseline;gap:13px;margin-bottom:6px}
.badge{font-size:12px;font-weight:700;letter-spacing:1px;color:#fff;
 background:#c2451b;border-radius:5px;padding:4px 11px;white-space:nowrap}
h1{font-size:23px;font-weight:700;letter-spacing:-.2px}
.sub{font-size:14.5px;color:#5b6b86;margin-bottom:18px;line-height:1.5}
svg{display:block;width:100%;height:auto}
.note{margin-top:14px;font-size:14.5px;line-height:1.55;border-left:3px solid #c2451b;
 padding:9px 0 9px 15px;background:#fdf6f2}
.sys{fill:#eef3fd;stroke:#2258d4;stroke-width:1.8}
.out{fill:#fff;stroke:#8494ab;stroke-width:1.8}
.ok{fill:#eaf6ef;stroke:#2f6b4c;stroke-width:1.8}
.warn{fill:#fdf1ec;stroke:#c2451b;stroke-width:1.8;stroke-dasharray:7 5}
.you{fill:#fffaf0;stroke:#b1791a;stroke-width:1.8}
.t{fill:#14213a;font:600 15px "DejaVu Sans",sans-serif;text-anchor:middle}
.s{fill:#5b6b86;font:13px "DejaVu Sans",sans-serif;text-anchor:middle}
.n{fill:#fff;font:700 15px "DejaVu Sans",sans-serif;text-anchor:middle}
.lb{fill:#5b6b86;font:600 12.5px "DejaVu Sans",sans-serif;text-anchor:middle}
.li{fill:#14213a;font:14.5px "DejaVu Sans",sans-serif;text-anchor:start}
"""
ARROW = ('<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" '
         'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
         '<path d="M0 0 L10 5 L0 10 z" fill="#5b6b86"/></marker></defs>')


def write(slug, badge, title, sub, svg, note):
    PAGES.mkdir(exist_ok=True)
    (PAGES / f"{slug}.html").write_text(f"""<!doctype html><meta charset="utf-8">
<style>{CSS}</style>
<div class="head"><span class="badge">{badge}</span><h1>{title}</h1></div>
<p class="sub">{sub}</p>
{svg}
<p class="note">{note}</p>""", encoding="utf-8")
    print(f"  {slug}")


def box(x, y, w, h, cls, title, sub=None, r=10):
    out = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" class="{cls}"/>'
    if sub:
        out += f'<text class="t" x="{x+w/2}" y="{y+h/2-4}">{title}</text>'
        out += f'<text class="s" x="{x+w/2}" y="{y+h/2+16}">{sub}</text>'
    else:
        out += f'<text class="t" x="{x+w/2}" y="{y+h/2+5}">{title}</text>'
    return out


def arrow(x1, y1, x2, y2, label=None, lx=None, ly=None):
    out = (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#5b6b86" '
           f'stroke-width="1.8" marker-end="url(#a)"/>')
    if label:
        out += f'<text class="lb" x="{lx or (x1+x2)/2}" y="{ly or (y1+y2)/2-7}">{label}</text>'
    return out


def d01():
    """Adding a document. Five steps, left to right, no jargon."""
    s = [f'<svg viewBox="0 0 1360 300">{ARROW}']

    steps = [
        ("You choose a file", "any PDF from the association"),
        ("It is read", "the words are pulled out of the page"),
        ("It is split up", "one rule or one section at a time"),
        ("It is filed", "so each piece can be found by meaning"),
        ("It is answering", "a few seconds later"),
    ]
    for i, (title, sub) in enumerate(steps):
        x = 30 + i * 268
        s.append(box(x, 60, 228, 92, "ok" if i == 4 else "sys", title, sub))
        s.append(f'<circle cx="{x+22}" cy="{82}" r="13" fill="#2258d4"/>')
        s.append(f'<text class="n" x="{x+22}" y="{87}" style="font-size:13px">{i+1}</text>')
        if i < 4:
            s.append(arrow(x + 228, 106, x + 262, 106))

    s.append('<rect x="30" y="196" width="1300" height="72" rx="10" class="warn"/>')
    s.append('<text class="t" x="680" y="226">If the page is a photograph, step 2 finds no words</text>')
    s.append('<text class="s" x="680" y="248">The document is kept for residents to download, and the '
             'assistant says plainly that it cannot answer from it</text>')

    s.append("</svg>")
    write("f01_adding", "Adding a document", "From your file to an answer",
          "One upload does all five. Nothing is retyped and nothing is "
          "summarised, so what a resident is told is what your document says.",
          "".join(s),
          "<b>Step 3 is why the answers are exact.</b> The document is split "
          "along its own headings, so a rule stays whole. The assistant quotes "
          "from those pieces rather than from a summary of them.")


def d02():
    """A question, end to end, with the two honest endings side by side.

    The endings sit next to each other rather than one above the other: routed
    vertically, the "nothing found" arrow ran straight through the answer box,
    which read as though a refusal passed through an answer on its way out.
    """
    s = [f'<svg viewBox="0 0 1360 470">{ARROW}']

    s.append(box(30, 30, 300, 74, "you", "A resident asks", '"what are the quiet hours"'))
    s.append(arrow(180, 104, 180, 140))

    s.append(box(30, 140, 300, 74, "sys", "Which community?",
                 "asked once, then remembered"))
    s.append(arrow(330, 177, 420, 177))

    s.append(box(420, 140, 340, 74, "sys", "Only their documents",
                 "no other association is looked at"))
    s.append(arrow(760, 177, 850, 177))

    s.append(box(850, 140, 340, 74, "sys", "Anything close enough?",
                 "the association's own words"))

    # The two endings, side by side under the decision.
    s.append(arrow(940, 214, 590, 306, "nothing", 700, 252))
    s.append(box(180, 306, 820, 96, "warn", "It says so, and says what it does hold",
                 "no answer is written at all, so there is nothing to be wrong about"))

    s.append(arrow(1100, 214, 1160, 306, "found", 1180, 262))
    s.append(box(1040, 306, 290, 96, "ok", "The answer",
                 "in plain words, with the document"))

    s.append("</svg>")
    write("f02_asking", "Answering a question", "What happens between the question and the answer",
          "Four steps, and two possible endings. The second ending is the one "
          "that makes the first one trustworthy.",
          "".join(s),
          "<b>The refusal is not the assistant choosing to be careful.</b> When "
          "nothing in your documents is close enough, no answer is composed at "
          "all. There is no point at which it could invent one.")


if __name__ == "__main__":
    d01()
    d02()
