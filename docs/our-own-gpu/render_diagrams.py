"""Two pictures for the client's version: what using it looks like, and what
stops the machine when nobody does.

Deliberately fewer and simpler than the ones in the setup document. This reader
is not going to build any of it, and the only two things they need to hold on to
are that switching it on is three steps, and that forgetting to switch it off
does not cost them anything.

Same shapes as every other document we send: rounded box for a thing or a step,
dashed box for a warning, labelled arrow for what moves. The helpers below are
copied rather than imported, which is how every other document in this repository
works, so this one builds on its own.
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
    """What using it looks like, with the reassurance attached."""
    s = [f'<svg viewBox="0 0 1360 300">{ARROW}']

    steps = [
        ("Press start", "on the admin screen"),
        ("Wait 2 to 4 minutes", "answers keep coming"),
        ("Switch the engine", "to our own hardware"),
        ("Hold your meeting", "answered on our GPU"),
        ("Walk away", "it switches itself off"),
    ]
    for i, (title, sub) in enumerate(steps):
        x = 30 + i * 268
        s.append(box(x, 60, 228, 92, "ok" if i == 4 else "sys", title, sub))
        s.append(f'<circle cx="{x+22}" cy="82" r="13" fill="#2258d4"/>')
        s.append(f'<text class="n" x="{x+22}" y="87" style="font-size:13px">{i+1}</text>')
        if i < 4:
            s.append(arrow(x + 228, 106, x + 262, 106))

    s.append('<rect x="30" y="196" width="1300" height="72" rx="10" class="warn"/>')
    s.append('<text class="t" x="680" y="226">Nobody sits through step 2</text>')
    s.append('<text class="s" x="680" y="248">A question asked while the machine is starting '
             'is answered as normal, and the screen says so</text>')

    s.append("</svg>")
    write("p01_using", "Using it", "What an administrator actually does",
          "Five steps, and only three of them involve touching anything.",
          "".join(s),
          "<b>Step 5 is the one that keeps this cheap.</b> Forgetting to switch "
          "it off is the normal thing to do, so nothing in the design depends on "
          "anybody remembering.")


def d02():
    """Why forgetting cannot cost anything."""
    s = [f'<svg viewBox="0 0 1360 380">{ARROW}']

    s.append(box(490, 30, 380, 86, "you", "You forget to switch it off",
                 "which is the normal case, not a mistake"))

    s.append(arrow(600, 116, 380, 176))
    s.append(box(60, 176, 470, 96, "sys", "The machine notices",
                 "20 minutes with no questions, it stops"))

    s.append(arrow(760, 116, 980, 176))
    s.append(box(830, 176, 470, 96, "sys", "And if it cannot",
                 "something outside it stops it instead"))

    s.append(arrow(295, 272, 640, 304))
    s.append(arrow(1065, 272, 720, 304))
    s.append(box(490, 304, 380, 60, "ok", "It is off, and costing nothing"))

    s.append("</svg>")
    write("p02_offswitch", "The bill", "Why forgetting does not cost anything",
          "Two separate mechanisms, because the first one cannot work if the "
          "machine itself has stopped responding.",
          "".join(s),
          "<b>Eighty cents an hour is only frightening if it runs unwatched.</b> "
          "Used the way it is meant to be, a few meetings a week costs about ten "
          "dollars a month.")


if __name__ == "__main__":
    d01()
    d02()
