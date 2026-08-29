"""Two pictures for the installation guide: which piece of software runs on
which machine, and how a request finds an engine once it is all wired up.

For a reader who is going to type the commands, so both are about arrangement
rather than about behaviour.

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
    """What runs where, once it is all installed."""
    s = [f'<svg viewBox="0 0 1360 380">{ARROW}']

    # The application server.
    s.append('<rect x="30" y="30" width="600" height="300" rx="12" class="out"/>')
    s.append('<text class="t" x="330" y="58" style="font-size:14px">The Service Assistant</text>')
    s.append('<text class="s" x="330" y="78">a small server, us-west-2, always on</text>')

    s.append(box(70, 100, 240, 62, "sys", "FastAPI", "the application itself"))
    s.append(box(350, 100, 240, 62, "sys", "The search", "runs here, no model"))
    s.append(box(70, 186, 240, 62, "sys", "The switch", "which engine is chosen"))
    s.append(box(350, 186, 240, 62, "sys", "The documents", "208 sections"))
    s.append(box(70, 272, 520, 44, "out", "boto3, to start and stop the machine on the right"))

    # The GPU.
    s.append('<rect x="730" y="30" width="600" height="300" rx="12" class="ok"/>')
    s.append('<text class="t" x="1030" y="58" style="font-size:14px">The GPU machine</text>')
    s.append('<text class="s" x="1030" y="78">g6.xlarge, off unless somebody switched it on</text>')

    s.append(box(770, 100, 520, 62, "sys", "Ollama", "listening on 11434, this document sections 2 to 5"))
    s.append(box(770, 186, 520, 62, "ok", "llama3.1:8b", "4.7GB of the 24GB on the card"))
    s.append(box(770, 272, 520, 44, "warn", "The idle timer, which shuts this machine down"))

    s.append(arrow(636, 131, 726, 131, "one HTTP call", 660, 116))
    s.append('<text class="lb" x="660" y="152">port 11434</text>')

    s.append("</svg>")
    write("i01_where", "The arrangement", "What runs where",
          "Two machines. The one on the left is always on and does everything "
          "except write the sentence. The one on the right is usually off.",
          "".join(s),
          "<b>The search is on the left, not the right.</b> Finding which "
          "passage answers a question happens on the small server and involves "
          "no model at all, which is why switching the machine on the right off "
          "cannot change what a resident is told.")


def d02():
    """How a request finds an engine, once it is wired up."""
    s = [f'<svg viewBox="0 0 1360 400">{ARROW}']

    s.append(box(30, 40, 250, 70, "sys", "Anything in the app", "asks for a sentence"))
    s.append(arrow(280, 75, 340, 75))

    s.append(box(340, 40, 250, 70, "sys", "llm.generate", "the only door"))
    s.append(arrow(465, 110, 465, 166))

    s.append(box(340, 166, 250, 70, "sys", "Which is chosen?", "ai_runtime reads the switch"))

    # Gemini branch.
    s.append(arrow(590, 201, 700, 201, "the cloud", 645, 188))
    s.append(box(700, 166, 250, 70, "out", "gemini_service", "always available"))

    # GPU branch.
    s.append(arrow(465, 236, 465, 292, "our GPU", 520, 268))
    s.append(box(340, 292, 250, 70, "sys", "Is it ready?", "gpu_instance, from cache"))

    s.append(arrow(590, 327, 700, 327, "yes", 645, 314))
    s.append(box(700, 292, 250, 70, "ok", "ollama_service", "our own hardware"))

    # The fallback branches from the question, not from the engine that was
    # not used. Drawn the other way round it reads as though ollama_service
    # produces the failure.
    s.append(arrow(590, 310, 700, 240))
    s.append('<text class="lb" x="632" y="262">no, or it failed</text>')
    s.append(arrow(950, 327, 1010, 240))
    s.append(arrow(950, 201, 1010, 201))
    s.append(box(1010, 166, 320, 70, "out", "The answer either way",
                 "the resident cannot tell which"))

    s.append("</svg>")
    write("i02_modules", "The wiring", "How a request finds an engine",
          "Four modules, each with one job. Nothing above the second box knows "
          "that a choice is being made at all.",
          "".join(s),
          "<b>The readiness check reads a cache, it does not test the "
          "machine.</b> Testing it would put a network round trip in front of "
          "every resident's question. The admin screen's own polling is what "
          "keeps that cache fresh.")


if __name__ == "__main__":
    d01()
    d02()
