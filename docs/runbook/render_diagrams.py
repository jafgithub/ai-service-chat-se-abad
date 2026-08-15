"""The diagrams for the handover, in the same style as the Phase E walkthrough.

Written as inline SVG so render_pages.py photographs them exactly as it
photographs the terminal pictures. Same shapes throughout:

    rounded box     a thing or a step
    dashed box      a warning, or something not done yet
    labelled arrow  what moves between them

    python3 render_diagrams.py      # writes pages/d*.html
    python3 render_pages.py         # photographs everything in pages/
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
.ll{fill:#14213a;font:700 14.5px "DejaVu Sans",sans-serif;text-anchor:start}
.ls{fill:#5b6b86;font:13px "DejaVu Sans",sans-serif;text-anchor:start}
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


# ── 1. how one machine is put together ───────────────────────────────────────
def d01():
    s = [f'<svg viewBox="0 0 1360 430">{ARROW}']
    s.append(box(40, 160, 190, 90, "out", "The customer", "phone or laptop"))
    s.append(box(320, 160, 210, 90, "sys", "nginx", "the front door"))
    s.append(box(640, 60, 220, 90, "ok", "The website", "plain files on disk"))
    s.append(box(640, 260, 220, 90, "ok", "The application", "answers /api/"))
    s.append(box(960, 260, 200, 90, "ok", "The database", "MySQL"))
    s.append(box(960, 60, 200, 90, "out", "The assistant", "Google Gemini"))
    s.append(arrow(230, 205, 315, 205, "https"))
    s.append(arrow(530, 190, 635, 120, "a page", 590, 140))
    s.append(arrow(530, 220, 635, 300, "/api/", 585, 275))
    s.append(arrow(860, 305, 955, 305, "reads"))
    s.append(arrow(860, 285, 955, 130, "asks", 930, 205))
    s.append('<rect x="300" y="20" width="880" height="360" rx="14" fill="none" '
             'stroke="#2258d4" stroke-width="1.4" stroke-dasharray="6 6"/>')
    s.append('<text class="lb" x="740" y="405">everything inside the dotted line is one Lightsail machine</text>')
    s.append("</svg>")
    write("d01_architecture", "How it fits together", "One machine, four parts",
          "The customer only ever talks to nginx. Nothing else is reachable from "
          "the internet.",
          "".join(s),
          "<b>Why this matters when you rebuild.</b> The website holds no server "
          "address. It asks for /api/ on whatever address the customer opened, so "
          "changing the subdomain needs no rebuild of the website.")


# ── 2. the journey of building a new machine ─────────────────────────────────
def d02():
    stages = [
        ("1", "Prepare", "machine, ports,\nsubdomain", "you"),
        ("2", "Install", "nginx, MySQL,\nffmpeg", "sys"),
        ("3", "Data", "create database,\ncopy the data", "sys"),
        ("4", "Application", "files, Python,\nsettings", "sys"),
        ("5", "Publish", "service, nginx,\ncertificate, website", "ok"),
        ("6", "Check", "four checks\nall pass", "you"),
    ]
    s = [f'<svg viewBox="0 0 1360 300">{ARROW}']
    x = 30
    for num, title, sub, cls in stages:
        s.append(f'<rect x="{x}" y="70" width="190" height="130" rx="12" class="{cls}"/>')
        s.append(f'<circle cx="{x+26}" cy="96" r="17" fill="#c2451b"/>')
        s.append(f'<text class="n" x="{x+26}" y="{101}">{num}</text>')
        s.append(f'<text class="t" x="{x+108}" y="101">{title}</text>')
        for i, line in enumerate(sub.split("\n")):
            s.append(f'<text class="s" x="{x+95}" y="{140+i*20}">{line}</text>')
        if x > 30:
            s.append(arrow(x - 30, 135, x - 6, 135))
        x += 220
    s.append('<text class="lb" x="680" y="245">about an hour, most of it waiting for the subdomain to answer</text>')
    s.append("</svg>")
    write("d02_journey", "Section 3.2", "Route B: building from an empty machine",
          "Six stages. Only needed when there is no machine left to copy.",
          "".join(s),
          "<b>Do these in order.</b> Stage 1 has to finish before stage 5: the "
          "certificate is only issued once the subdomain really points at the "
          "machine, and that can take a few minutes to spread.")


# ── 3. what a deploy actually moves ──────────────────────────────────────────
def d03():
    s = [f'<svg viewBox="0 0 1360 420">{ARROW}']
    s.append(box(40, 40, 240, 90, "you", "Your laptop", "the code"))
    s.append(box(40, 250, 240, 90, "you", "Your laptop", "npm run build"))
    s.append(box(430, 40, 250, 90, "sys", "backend/app/", "copied straight over"))
    s.append(box(430, 250, 250, 90, "sys", "/tmp/fe-stage/", "waiting room"))
    s.append(box(820, 40, 260, 90, "ok", "The application", "restarted"))
    s.append(box(820, 250, 260, 90, "ok", "/var/www/serviceagent", "moved in with sudo"))
    s.append(arrow(280, 85, 425, 85, "rsync"))
    s.append(arrow(680, 85, 815, 85, "restart"))
    s.append(arrow(280, 295, 425, 295, "rsync"))
    s.append(arrow(680, 295, 815, 295, "sudo rsync"))
    s.append('<text class="lb" x="160" y="160">BACKEND</text>')
    s.append('<text class="lb" x="160" y="370">FRONTEND</text>')
    s.append(box(430, 370, 650, 40, "warn", "the settings file and the database are never copied", None, 8))
    s.append("</svg>")
    write("d03_deploy", "Section 7", "What a deploy moves, and what it never touches",
          "Two paths. The backend goes straight across; the website goes via a "
          "waiting room because the web folder belongs to root.",
          "".join(s),
          "<b>The one rule.</b> A deploy only ever replaces code. The settings "
          "file and the database stay where they are, which is why a bad deploy "
          "is always safe to undo.")


# ── 4. when something is wrong ───────────────────────────────────────────────
def d04():
    s = [f'<svg viewBox="0 0 1360 380">{ARROW}']
    s.append(box(40, 150, 200, 84, "you", "Something", "is wrong"))
    s.append(box(330, 30, 250, 84, "out", "Every page 502", "the app stopped"))
    s.append(box(330, 148, 250, 84, "out", "Every page 404", "website missing"))
    s.append(box(330, 266, 250, 84, "out", "Pages fine,", "nothing works"))
    s.append(box(730, 30, 300, 84, "ok", "systemctl restart plumber", None))
    s.append(box(730, 148, 300, 84, "ok", "deploy the website again", None))
    s.append(box(730, 266, 300, 84, "ok", "check the database is up", None))
    for y in (72, 190, 308):
        s.append(arrow(240, 192, 325, y) if y != 190 else arrow(240, 190, 325, 190))
        s.append(arrow(580, y, 725, y))
    s.append(box(1080, 148, 240, 84, "warn", "still wrong?", "read the log"))
    s.append(arrow(1030, 190, 1075, 190))
    s.append("</svg>")
    write("d04_wrong", "Section 9", "Three things go wrong, and what each looks like",
          "The symptom tells you which of the three parts has stopped.",
          "".join(s),
          "<b>The log is always the next step.</b> "
          "sudo journalctl -u plumber -n 50 shows the last fifty lines the "
          "application wrote, and the reason is usually in them.")


# ── 5. the two ways to get a new machine ─────────────────────────────────────
def d05():
    s = [f'<svg viewBox="0 0 1360 420">{ARROW}']

    s.append('<text class="ll" x="24" y="72">ROUTE A</text>')
    s.append('<text class="ls" x="24" y="94">a copy of the</text>')
    s.append('<text class="ls" x="24" y="113">machine we run</text>')
    s.append('<text class="ls" x="24" y="139">about 20 minutes</text>')
    a = [("ok", "Our machine", "running now"),
         ("ok", "Snapshot", "a picture of it"),
         ("ok", "New machine", "already built"),
         ("you", "Change 5 things", "section 3.1"),
         ("ok", "Live", "on its own name")]
    x = 200
    for cls, title, sub in a:
        s.append(box(x, 45, 190, 100, cls, title, sub))
        if x > 200:
            s.append(arrow(x - 45, 95, x - 6, 95))
        x += 235

    s.append('<line x1="24" y1="205" x2="1336" y2="205" stroke="#d6dee9" stroke-width="1.4"/>')

    s.append('<text class="ll" x="24" y="272">ROUTE B</text>')
    s.append('<text class="ls" x="24" y="294">an empty machine,</text>')
    s.append('<text class="ls" x="24" y="313">built up by hand</text>')
    s.append('<text class="ls" x="24" y="339">about an hour</text>')
    b = ["Empty Ubuntu", "Install", "Database", "Code", "Publish", "Live"]
    x = 200
    for i, title in enumerate(b):
        s.append(box(x, 245, 155, 100, "ok" if i == 5 else "sys", title))
        if x > 200:
            s.append(arrow(x - 40, 295, x - 6, 295))
        x += 195

    s.append('<text class="lb" x="680" y="400">both end in exactly the same machine; route A just starts most of the way there</text>')
    s.append("</svg>")
    write("d05_routes", "Section 3", "Two ways to get a new machine",
          "A snapshot is a photograph of a whole machine, taken while it runs. "
          "Launching from one gives you a machine that is already finished.",
          "".join(s),
          "<b>Take route A.</b> Everything that is fiddly on route B, the Python "
          "environment, the database engine, ffmpeg, the nginx file, is already "
          "in the picture. Route B is kept for the day there is no machine left "
          "to copy.")


# ── 6. the snapshot journey ──────────────────────────────────────────────────
def d06():
    stages = [
        ("1", "Snapshot", "take the picture,\nnothing stops", "ok"),
        ("2", "Launch", "new machine\nfrom the picture", "ok"),
        ("3", "Address", "static IP,\nDNS record", "you"),
        ("4", "Change", "name, certificate,\ntwo passwords", "you"),
        ("5", "Clear out", "old bookings,\nthe leftovers", "warn"),
        ("6", "Check", "the same four\nchecks", "you"),
    ]
    s = [f'<svg viewBox="0 0 1360 300">{ARROW}']
    x = 30
    for num, title, sub, cls in stages:
        s.append(f'<rect x="{x}" y="70" width="190" height="130" rx="12" class="{cls}"/>')
        s.append(f'<circle cx="{x+26}" cy="96" r="17" fill="#c2451b"/>')
        s.append(f'<text class="n" x="{x+26}" y="101">{num}</text>')
        s.append(f'<text class="t" x="{x+108}" y="101">{title}</text>')
        for i, line in enumerate(sub.split("\n")):
            s.append(f'<text class="s" x="{x+95}" y="{140+i*20}">{line}</text>')
        if x > 30:
            s.append(arrow(x - 30, 135, x - 6, 135))
        x += 220
    s.append('<text class="lb" x="680" y="245">stages 1 and 2 are clicks in the Lightsail console; 3 to 6 are on the new machine</text>')
    s.append("</svg>")
    write("d06_snapshot", "Section 3.1", "Route A: the whole journey",
          "Six stages. Only stages 4 and 5 need any thought, and they are the "
          "same list every time.",
          "".join(s),
          "<b>Stage 3 before stage 4.</b> The certificate in stage 4 is only "
          "issued once the new subdomain really answers with the new address, "
          "and that can take a few minutes to spread.")


# ── 7. what the copy brings with it ──────────────────────────────────────────
def d07():
    def column(x, y, w, h, cls, band, head, items):
        out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" class="{cls}"/>',
               f'<path d="M{x} {y+46} v-34 a12 12 0 0 1 12 -12 h{w-24} a12 12 0 0 1 12 12 v34 z" '
               f'fill="{band}"/>',
               f'<text class="hd" x="{x+18}" y="{y+31}">{head}</text>']
        for i, line in enumerate(items):
            out.append(f'<text class="li" x="{x+18}" y="{y+82+i*31}">{line}</text>')
        return "".join(out)

    s = ['<svg viewBox="0 0 1360 330">']
    s.append(column(24, 20, 420, 245, "ok", "#2f6b4c", "Arrives working. Leave it.", [
        "nginx and the website",
        "Python, the code, ffmpeg",
        "MySQL and all 18 tables",
        "the plumber service, starts on boot",
        "every setting except the two below",
    ]))
    s.append(column(470, 20, 420, 245, "you", "#b1791a", "Still points at the old site.", [
        "server_name in the nginx file",
        "the certificate (it says serviceagent)",
        "DB_PASSWORD",
        "ADMIN_TOKEN",
        "the bookings already in the database",
    ]))
    s.append(column(916, 20, 420, 245, "warn", "#c2451b", "Came along. Not yours.", [
        "the aiorder-dev nginx site",
        "/var/www/ai-order  5.6 GB",
        "aidata2prd_dev database  2.5 GB",
        "the aiorder-render service",
        "other people's SSH keys",
    ]))
    s.append('<text class="lb" x="680" y="305">the snapshot also copies the two problems in section 10: the open database, and the 700 MB ceiling</text>')
    s.append("</svg>")
    write("d07_carried", "Section 3.1", "What the copy brings with it",
          "A snapshot copies the whole disk, so it copies the good, the "
          "old address, and the things that were only ever on our machine.",
          "".join(s),
          "<b>The middle column is the work.</b> Five changes, and the machine "
          "is yours. The right column is only housekeeping: nothing there is "
          "running, it is taking up room.")


if __name__ == "__main__":
    for fn in (d01, d02, d03, d04, d05, d06, d07):
        fn()
