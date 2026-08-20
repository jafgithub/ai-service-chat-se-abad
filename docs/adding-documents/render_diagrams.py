"""Two pictures for the SOP: what happens to a document, and what to check first.

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
    stages = [
        ("1", "You send it", "email the PDF", "you"),
        ("2", "We check it", "readable? whose?\nstill current?", "you"),
        ("3", "We cut it up", "by rule and\nby section", "sys"),
        ("4", "We index it", "one command", "sys"),
        ("5", "It answers", "panel and\nbooking chat", "ok"),
    ]
    s = [f'<svg viewBox="0 0 1360 290">{ARROW}']
    x = 60
    for num, title, sub, cls in stages:
        s.append(f'<rect x="{x}" y="60" width="210" height="130" rx="12" class="{cls}"/>')
        s.append(f'<circle cx="{x+28}" cy="88" r="17" fill="#c2451b"/>')
        s.append(f'<text class="n" x="{x+28}" y="93">{num}</text>')
        s.append(f'<text class="t" x="{x+120}" y="93">{title}</text>')
        for i, line in enumerate(sub.split("\n")):
            s.append(f'<text class="s" x="{x+105}" y="{132+i*20}">{line}</text>')
        if x > 60:
            s.append(arrow(x - 40, 125, x - 8, 125))
        x += 250
    s.append('<text class="lb" x="680" y="235">about a day from the email arriving, most of it step 2</text>')
    s.append("</svg>")
    write("d01_journey", "How it works", "What happens to a document you send",
          "Five steps. Only the first two need anything from you.",
          "".join(s),
          "<b>Step 2 is where documents stop.</b> Two of the six sent on 20 "
          "August could not go past it, and the reasons are on the next page.")


def d02():
    def column(x, y, w, h, cls, band, head, items):
        out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" class="{cls}"/>',
               f'<path d="M{x} {y+46} v-34 a12 12 0 0 1 12 -12 h{w-24} a12 12 0 0 1 12 12 v34 z" fill="{band}"/>',
               f'<text class="hd" x="{x+18}" y="{y+31}">{head}</text>']
        for i, line in enumerate(items):
            out.append(f'<text class="li" x="{x+18}" y="{y+82+i*31}">{line}</text>')
        return "".join(out)

    s = ['<svg viewBox="0 0 1360 300">']
    s.append(column(24, 20, 420, 220, "ok", "#2f6b4c", "Send these", [
        "a PDF you can select text in",
        "the current, approved version",
        "Serenity Point's own documents",
        "rules, fees, forms, procedures",
    ]))
    s.append(column(470, 20, 420, 220, "you", "#b1791a", "Tell us as well", [
        "the date it was approved",
        "what it replaces, if anything",
        "whether it is for residents",
        "or for the office only",
    ]))
    s.append(column(916, 20, 420, 220, "warn", "#c2451b", "These cannot be used", [
        "scans and photographs of paper",
        "documents for another community",
        "drafts and superseded versions",
        "spreadsheets of personal data",
    ]))
    s.append('<text class="lb" x="680" y="275">the test for the first column: open the PDF, try to select a sentence with the mouse</text>')
    s.append("</svg>")
    write("d02_what_to_send", "Before you send", "What we can use, and what we cannot",
          "One check decides most of it, and you can do it in five seconds.",
          "".join(s),
          "<b>If you cannot select the text, neither can we.</b> A scan is a "
          "picture of words, not words. It has to be re-exported from whatever "
          "produced it, or run through text recognition first.")


if __name__ == "__main__":
    d01(); d02()
