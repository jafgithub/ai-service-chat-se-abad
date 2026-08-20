"""Three pictures for the technical reference: the two front doors, the routing
gate, and what "scope" means when a community is named.

Same shapes as every other document we send: rounded box for a thing or a step,
dashed box for a warning, labelled arrow for what moves.
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
.hd{fill:#fff;font:700 15px "DejaVu Sans",sans-serif;text-anchor:start}
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
    """The two front doors and the one core."""
    s = [f'<svg viewBox="0 0 1360 400">{ARROW}']

    s.append(box(60, 40, 300, 96, "you", "Floating panel", "every page, bottom right"))
    s.append(box(60, 210, 300, 96, "you", "Booking chat", "text and voice"))

    s.append(box(450, 40, 300, 96, "sys", "POST /docs/ask", "no catalogue in front"))
    s.append(box(450, 210, 300, 96, "sys", "POST /chat", "booking pipeline first"))

    s.append(arrow(360, 88, 442, 88))
    s.append(arrow(360, 258, 442, 258))

    s.append('<rect x="450" y="330" width="300" height="52" rx="10" class="warn"/>')
    s.append('<text class="t" x="600" y="362">intent = search, and the gate</text>')
    s.append(arrow(600, 306, 600, 326))

    s.append(box(860, 118, 320, 110, "ok", "answer_from_documents()",
                 "retrieve, ground, or refuse"))
    s.append(arrow(750, 88, 852, 130, "always", 800, 76))
    s.append(arrow(750, 356, 852, 222, "only if the gate says so", 830, 300))

    s.append(box(1240, 118, 90, 110, "sys", "index", None))
    s.append(arrow(1180, 173, 1234, 173))

    s.append('<text class="lb" x="1020" y="262">189 chunks, one matrix multiply</text>')
    s.append("</svg>")
    write("d01_doors", "Architecture", "Two ways in, one place that answers",
          "The panel asks the documents directly. The booking chat asks them "
          "only when the message looks like a question about the rules.",
          "".join(s),
          "<b>One core on purpose.</b> The same question gets the same answer "
          "whichever way a resident asks it, and a wrong answer has one place "
          "to be fixed.")


def d02():
    """The routing gate inside the booking chat."""
    s = [f'<svg viewBox="0 0 1360 430">{ARROW}']

    s.append(box(40, 30, 260, 80, "you", "Message arrives", "intent = search"))

    s.append('<rect x="370" y="20" width="270" height="100" rx="12" class="warn"/>')
    s.append('<text class="t" x="505" y="58">Booking words?</text>')
    s.append('<text class="s" x="505" y="82">book, hire, I need a,</text>')
    s.append('<text class="s" x="505" y="100">my X is leaking</text>')
    s.append(arrow(300, 70, 362, 70))

    s.append(box(710, 20, 300, 100, "ok", "Service catalogue", "never asks the documents"))
    s.append(arrow(640, 70, 702, 70, "yes", 671, 58))

    s.append('<rect x="370" y="165" width="270" height="100" rx="12" class="warn"/>')
    s.append('<text class="t" x="505" y="203">Question shape, or</text>')
    s.append('<text class="t" x="505" y="225">rules vocabulary?</text>')
    s.append('<text class="s" x="505" y="248">what, can I ... rules, pets, lease</text>')
    s.append(arrow(505, 120, 505, 159, "no", 528, 145))

    s.append(box(710, 300, 300, 90, "ok", "Service catalogue", "with a documents fallback"))
    s.append(arrow(505, 265, 700, 340, "no", 590, 300))

    s.append(box(710, 165, 300, 100, "sys", "Ask the documents", "retrieve, then ground"))
    s.append(arrow(640, 215, 702, 215, "yes", 671, 203))

    s.append(box(1070, 100, 260, 84, "ok", "Answer", "with the rule it came from"))
    s.append(box(1070, 220, 260, 84, "warn", "Named a community?", "then say it is a miss"))
    s.append(arrow(1010, 200, 1062, 150, "grounded", 1040, 130))
    s.append(arrow(1010, 232, 1062, 250, "nothing", 1040, 232))

    s.append("</svg>")
    write("d02_routing", "Routing", "Which question reaches the documents",
          "Booking wins outright. Past that, either a question shape or the "
          "documents' own vocabulary is enough.",
          "".join(s),
          "<b>The middle box is what was missing.</b> "
          "“Lauderdale Lake community rules” opens with no question word, so it "
          "was a service search, and one weak catalogue match hid the documents "
          "entirely.")


def d03():
    """What scope means, and what happens to a community we hold nothing for."""
    s = [f'<svg viewBox="0 0 1360 360">{ARROW}']

    def stack(x, title, sub, cls, rows, badge):
        out = [f'<rect x="{x}" y="60" width="380" height="230" rx="12" class="{cls}"/>',
               f'<text class="t" x="{x+190}" y="98">{title}</text>',
               f'<text class="s" x="{x+190}" y="122">{sub}</text>']
        for i, row in enumerate(rows):
            out.append(f'<text class="li" x="{x+30}" y="{162+i*30}">{row}</text>')
        out.append(f'<rect x="{x+24}" y="242" width="332" height="34" rx="8" fill="{badge[0]}"/>')
        out.append(f'<text class="n" x="{x+190}" y="265">{badge[1]}</text>')
        return "".join(out)

    s.append(stack(30, "Serenity Point", "the home community", "ok", [
        "96 chunks, six documents",
        "searched when nobody is named",
    ], ("#2f6b4c", "answers")))

    s.append(stack(470, "Lauderdale Lakes", "another city entirely", "sys", [
        "93 chunks, one handbook",
        "searched only when named",
    ], ("#2258d4", "answers, when asked for by name")))

    s.append(stack(910, "Three Lakes", "declared, not indexed", "warn", [
        "0 chunks: the PDF is a scan",
        "recognised so it can be refused",
    ], ("#c2451b", "says it does not hold them")))

    s.append('<text class="lb" x="680" y="325">naming a community scopes to it, '
             'and only those rows are scored at all</text>')
    s.append("</svg>")
    write("d03_scope", "Isolation", "Whose rules a question may be answered from",
          "Scope is applied before ranking, so a document from another "
          "community cannot appear however well it matches.",
          "".join(s),
          "<b>Declared but empty is the important column.</b> A name that was "
          "never declared is not recognised at all, and the question is "
          "answered from Serenity.")


if __name__ == "__main__":
    d01()
    d02()
    d03()
