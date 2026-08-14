"""Turn captured console output into readable terminal pictures.

The first version coloured every line that contained a word like "active" or
"enabled", which was nearly all of them, so the whole window came out green: a
highlight on everything is a highlight on nothing, and green on dark green is
hard to read at any size.

So: body text is near white on near black, and exactly one line per picture is
marked, the line the reader is meant to check. Under the window, in plain
English, what that line tells you and what to do if it says something else.

    python3 render_terminals.py     # writes pages/t*.html
    python3 render_pages.py         # photographs them into build/
"""

import html
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPTURES = HERE / "captures"
PAGES = HERE / "pages"

# slug, step label, heading, the command, capture file,
# the text that marks the one line to highlight, and what it means.
SPEC = [
    ("t01_tables", "Check 1", "The database has its tables",
     "mysql -u aiorder -p plumber_assistant -e 'SHOW TABLES;'",
     "01_tables.txt", "appointments",
     "Eighteen names should be listed. If you see none, the data was never "
     "loaded: run the import again from step 3."),

    ("t02_service", "Check 2", "The application is running",
     "systemctl status plumber",
     "02_service.txt", "Active: active (running)",
     "The word to look for is running. If it says failed or inactive, the "
     "application stopped: read the log with journalctl -u plumber."),

    ("t03_certs", "Check 3", "The certificate is valid",
     "sudo certbot certificates",
     "03_certs.txt", "VALID",
     "Each certificate shows how many days it has left. Renewal is automatic, "
     "so this is only worth checking if the browser shows a warning."),

    ("t04_verify", "Check 4", "All three parts answer",
     "curl -o /dev/null -w '%{http_code}' https://serviceagent.fordev.fun/",
     "04_verify.txt", "200",
     "200 means success. The home page and the health check both returning it "
     "means the website, the application and the database are all talking."),
]

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1400px;padding:30px 34px;background:#fff;
 font-family:"DejaVu Sans","Liberation Sans",system-ui,sans-serif;color:#14213a}
.head{display:flex;align-items:baseline;gap:13px;margin-bottom:6px}
.badge{font-size:12px;font-weight:700;letter-spacing:1px;color:#fff;
 background:#c2451b;border-radius:5px;padding:4px 11px;white-space:nowrap}
h1{font-size:23px;font-weight:700;letter-spacing:-.2px}
.term{margin-top:16px;background:#0d1210;border-radius:9px;overflow:hidden}
.bar{display:flex;gap:7px;align-items:center;padding:11px 15px;background:#1a231e}
.dot{width:11px;height:11px;border-radius:50%}
.cmd{padding:15px 20px 8px;font:600 15px/1.5 "DejaVu Sans Mono",monospace;color:#8fe0ad}
.out{padding:2px 20px 20px;margin:0;font:400 15px/1.65 "DejaVu Sans Mono",monospace;
 color:#eef3ef;white-space:pre-wrap}
/* the one line that matters */
.mark{display:block;background:#f5c451;color:#1a1200;font-weight:700;
 border-radius:4px;padding:2px 8px;margin:2px -8px}
.note{margin-top:16px;font-size:15px;line-height:1.6;border-left:3px solid #c2451b;
 padding:10px 0 10px 16px;background:#fdf6f2}
.note b{color:#c2451b}
"""


def page(slug, step, title, cmd, lines, mark, note):
    body = []
    for raw in lines:
        e = html.escape(raw) or "&nbsp;"
        body.append(f'<span class="mark">{e}</span>' if mark and mark in raw else e)
    (PAGES / f"{slug}.html").write_text(f"""<!doctype html><meta charset="utf-8">
<style>{CSS}</style>
<div class="head"><span class="badge">{html.escape(step)}</span><h1>{html.escape(title)}</h1></div>
<div class="term"><div class="bar">
 <span class="dot" style="background:#f05a4f"></span>
 <span class="dot" style="background:#f5bf4f"></span>
 <span class="dot" style="background:#5fc463"></span></div>
<div class="cmd">$ {html.escape(cmd)}</div>
<pre class="out">{chr(10).join(body)}</pre></div>
<p class="note"><b>What you are looking for.</b> {html.escape(note)}</p>""",
                                        encoding="utf-8")


def build():
    PAGES.mkdir(exist_ok=True)
    for slug, step, title, cmd, cap, mark, note in SPEC:
        f = CAPTURES / cap
        if not f.exists():
            print(f"  skipped {slug}: no capture")
            continue
        lines = f.read_text(errors="replace").rstrip().splitlines()[:22]
        page(slug, step, title, cmd, lines, mark, note)
        print(f"  {slug}")


if __name__ == "__main__":
    build()
