"""Three pictures for the GPU setup document: where the two engines sit in the
path a question takes, the two ways the machine gets switched off, and the panel
an administrator actually uses.

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
    """Where the two engines sit in the path a question takes."""
    s = [f'<svg viewBox="0 0 1360 430">{ARROW}']

    s.append(box(30, 40, 240, 84, "you", "A resident asks",
                 '"what are the quiet hours"'))
    s.append(arrow(270, 82, 330, 82))

    s.append(box(330, 40, 290, 84, "sys", "Their documents, searched",
                 "on our server, no model at all"))
    s.append(arrow(620, 82, 680, 82))

    s.append(box(680, 40, 260, 84, "sys", "Close enough?",
                 "the honesty gate"))

    # The refusal, which never reaches a model.
    s.append(arrow(810, 124, 810, 196, "nothing matched", 900, 168))
    s.append(box(660, 196, 300, 76, "warn", "It says so, and stops",
                 "no model is called at all"))

    # The engine choice.
    s.append(arrow(940, 82, 1000, 82))
    s.append(box(1000, 40, 330, 84, "sys", "Which engine is switched on?",
                 "changed from the admin screen"))

    s.append(arrow(1165, 124, 1165, 186))
    s.append(box(1000, 186, 330, 84, "ok", "Our own GPU",
                 "NVIDIA L4, only while it is on"))

    s.append(arrow(1165, 270, 1165, 320, "or, if it is not on", 1165, 300))
    s.append(box(1000, 320, 330, 84, "out", "Gemini",
                 "always there, answers anyway"))

    s.append("</svg>")
    write("g01_where", "The path", "Where the two engines sit",
          "Only the last box on the right is a language model. Everything that "
          "decides what the answer is made of happens before it.",
          "".join(s),
          "<b>The engine is chosen last, and it never changes the facts.</b> "
          "Which passage answers the question was already decided by the search, "
          "on our own server. The engine only puts that passage into a sentence, "
          "which is why swapping it cannot change what a resident is told.")


def d02():
    """Two independent ways the machine gets switched off."""
    s = [f'<svg viewBox="0 0 1360 400">{ARROW}']

    s.append(box(490, 30, 380, 86, "ok", "The GPU is running",
                 "about $0.80 an hour, whether used or not"))

    # On the machine.
    s.append(arrow(600, 116, 380, 176))
    s.append(box(60, 176, 470, 96, "sys", "A timer on the machine itself",
                 "every 5 minutes, reads Ollama's own log"))
    s.append(box(60, 288, 470, 86, "out", "Stops after 20 idle minutes",
                 "exact, because it knows when the last question was"))
    s.append(arrow(295, 272, 295, 288))

    # Outside it.
    s.append(arrow(760, 116, 980, 176))
    s.append(box(830, 176, 470, 96, "sys", "A Lambda, outside the machine",
                 "every 5 minutes, watches processor use"))
    s.append(box(830, 288, 470, 86, "out", "Stops after 45 quiet minutes",
                 "cruder, but still works if the machine locks up"))
    s.append(arrow(1065, 272, 1065, 288))

    s.append('<text class="lb" x="455" y="140">precise</text>')
    s.append('<text class="lb" x="1120" y="140">survives a lockup</text>')

    s.append("</svg>")
    write("g02_autooff", "The safety net", "Two independent ways it switches off",
          "Neither one is a backup of the other. They are watching for different "
          "things, and they fail for different reasons.",
          "".join(s),
          "<b>A timer on a machine that has locked up does not run.</b> That is "
          "the entire reason for the second mechanism, and it is the one that "
          "catches the expensive mistake: a machine nobody is looking at.")


def d03():
    """What an administrator does, in order."""
    s = [f'<svg viewBox="0 0 1360 300">{ARROW}']

    steps = [
        ("Press start", "on the admin screen"),
        ("Wait 2 to 4 minutes", "Gemini answers meanwhile"),
        ("Switch the engine", "to our own GPU"),
        ("Hold the meeting", "answered on our hardware"),
        ("Do nothing", "it stops itself, 20 minutes"),
    ]
    for i, (title, sub) in enumerate(steps):
        x = 30 + i * 268
        s.append(box(x, 60, 228, 92, "ok" if i == 4 else "sys", title, sub))
        s.append(f'<circle cx="{x+22}" cy="82" r="13" fill="#2258d4"/>')
        s.append(f'<text class="n" x="{x+22}" y="87" style="font-size:13px">{i+1}</text>')
        if i < 4:
            s.append(arrow(x + 228, 106, x + 262, 106))

    s.append('<rect x="30" y="196" width="1300" height="72" rx="10" class="warn"/>')
    s.append('<text class="t" x="680" y="226">Step 2 is not a wait anybody sits through</text>')
    s.append('<text class="s" x="680" y="248">A question asked while the machine is starting is '
             'answered by Gemini, and the panel says so rather than hiding it</text>')

    s.append("</svg>")
    write("g03_panel", "Using it", "What an administrator actually does",
          "Five steps, and only the first three involve touching anything.",
          "".join(s),
          "<b>Step 5 is the one that keeps this affordable.</b> Forgetting to "
          "switch it off is the normal case, not the exception, which is why "
          "nothing in this design depends on somebody remembering.")


if __name__ == "__main__":
    d01()
    d02()
    d03()
