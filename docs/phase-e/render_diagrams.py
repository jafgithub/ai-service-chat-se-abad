"""Flow diagrams for the Phase E walkthrough, in the style of a BPMN process map.

Written as inline SVG in HTML pages so render_pages.py photographs them the same
way it photographs the screenshots. Same shapes throughout:

    circle          start or end
    rounded box     a step
    diamond         a decision
    dashed box      something that does not exist yet
    labelled arrow  what moves, or which way a decision went

Colour says who is acting: our system, the customer, or the provider.

    python3 render_diagrams.py      # writes pages/d*.html
    python3 render_pages.py         # photographs everything in pages/
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGES = HERE / "pages"

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { width: 1420px; padding: 26px 30px; background: #fff;
       font-family: "DejaVu Sans", "Liberation Sans", system-ui, sans-serif; color: #14213a; }
.head { display: flex; align-items: baseline; gap: 13px; margin-bottom: 6px; }
.badge { font-size: 12px; font-weight: 700; letter-spacing: 1px; color: #fff;
         background: #c2451b; border-radius: 5px; padding: 4px 11px; white-space: nowrap; }
h1 { font-size: 23px; font-weight: 700; letter-spacing: -.2px; }
.sub { font-size: 14.5px; color: #5b6b86; margin-bottom: 16px; line-height: 1.5; }
svg { display: block; width: 100%; height: auto; }
.note { margin-top: 14px; font-size: 14.5px; line-height: 1.55;
        border-left: 3px solid #c2451b; padding: 9px 0 9px 15px; background: #fdf6f2; }

/* shapes */
.sys   { fill: #eef3fd; stroke: #2258d4; stroke-width: 1.8; }
.cust  { fill: #fff;    stroke: #8494ab; stroke-width: 1.8; }
.prov  { fill: #eaf6ef; stroke: #2f6b4c; stroke-width: 1.8; }
.gap   { fill: #fdf1ec; stroke: #c2451b; stroke-width: 1.8; stroke-dasharray: 7 5; }
.gate  { fill: #fffaf0; stroke: #b1791a; stroke-width: 1.8; }
.ev    { fill: #fff;    stroke: #14213a; stroke-width: 2.2; }
.evend { fill: #14213a; stroke: #14213a; stroke-width: 2.2; }
.plain { fill: #fbfbfd; stroke: #cbd3e0; stroke-width: 1.5; }

/* text */
.t  { fill: #14213a; font: 600 14px "DejaVu Sans", sans-serif; text-anchor: middle; }
.s  { fill: #5b6b86; font: 12.5px "DejaVu Sans", sans-serif; text-anchor: middle; }
.lb { fill: #5b6b86; font: 600 12px "DejaVu Sans", sans-serif; text-anchor: middle; }
.hot{ fill: #c2451b; font: 600 12.5px "DejaVu Sans", sans-serif; text-anchor: middle; }
.gd { fill: #2f6b4c; font: 600 12.5px "DejaVu Sans", sans-serif; text-anchor: middle; }
.ttl{ fill: #8494ab; font: 700 11.5px "DejaVu Sans", sans-serif; letter-spacing: 1.1px; }
.mono { fill: #14213a; font: 13px "DejaVu Sans Mono", "Liberation Mono", monospace; }
.monod{ fill: #5b6b86; font: 12px "DejaVu Sans Mono", "Liberation Mono", monospace; }
.lft { text-anchor: start; }

/* flow */
.f  { stroke: #8494ab; stroke-width: 2; fill: none; }
.fh { stroke: #c2451b; stroke-width: 2.4; fill: none; }
.fd { stroke: #8494ab; stroke-width: 2; fill: none; stroke-dasharray: 6 5; }
.rule { stroke: #e3e8f0; stroke-width: 1.5; }
"""

ARROWS = """
<defs>
  <marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7"
          orient="auto-start-reverse"><polygon points="0,0 10,5 0,10" fill="#8494ab"/></marker>
  <marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7"
          orient="auto-start-reverse"><polygon points="0,0 10,5 0,10" fill="#c2451b"/></marker>
</defs>
"""

# Rough width per character at each size, measured against DejaVu Sans. Only
# needs to be close: it exists to catch a label that plainly does not fit, which
# otherwise spills silently over the edge of its box.
_W_LABEL, _W_SUB = 7.9, 6.3


def _fits(text: str, width: float, per_char: float, where: str) -> None:
    needed = len(text) * per_char + 22
    if needed > width:
        print(f"  ! {where}: {text!r} needs about {needed:.0f}px, box is {width}px")


def box(x, y, w, h, cls, lines, sub=None):
    """A rounded step. `lines` is the label, `sub` an optional smaller line."""
    for line in lines:
        _fits(line, w, _W_LABEL, "label")
    if sub:
        _fits(sub, w, _W_SUB, "sub")
    cx, cy = x + w / 2, y + h / 2
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" class="{cls}"/>']
    total = len(lines) + (1 if sub else 0)
    start = cy - (total - 1) * 9 + 5
    for i, line in enumerate(lines):
        out.append(f'<text x="{cx}" y="{start + i * 18}" class="t">{line}</text>')
    if sub:
        out.append(f'<text x="{cx}" y="{start + len(lines) * 18}" class="s">{sub}</text>')
    return "\n".join(out)


def gateway(cx, cy, label_top, label_bottom=None, r=42):
    out = [f'<path d="M{cx} {cy - r} L{cx + r} {cy} L{cx} {cy + r} L{cx - r} {cy} Z" class="gate"/>']
    if label_bottom:
        out.append(f'<text x="{cx}" y="{cy - 2}" class="s">{label_top}</text>')
        out.append(f'<text x="{cx}" y="{cy + 13}" class="s">{label_bottom}</text>')
    else:
        out.append(f'<text x="{cx}" y="{cy + 4}" class="s">{label_top}</text>')
    return "\n".join(out)


def event(cx, cy, end=False, r=17):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" class="{"evend" if end else "ev"}"/>'


def legend(x, y, entries):
    out = []
    for i, (cls, label) in enumerate(entries):
        top = y + i * 26
        out.append(f'<rect x="{x}" y="{top}" width="16" height="16" rx="4" class="{cls}"/>')
        out.append(f'<text x="{x + 26}" y="{top + 13}" class="s lft">{label}</text>')
    return "\n".join(out)


def page(slug, badge, title, sub, svg, note):
    doc = f"""<meta charset="utf-8"><style>{CSS}</style>
<div class="head"><span class="badge">{badge}</span><h1>{title}</h1></div>
<p class="sub">{sub}</p>
{svg}
<div class="note">{note}</div>"""
    (PAGES / f"{slug}.html").write_text(doc, encoding="utf-8")
    print(f"  {slug}.html")


# ── 1. the customer, start to finish ─────────────────────────────────────────

def customer():
    s = [f'<svg viewBox="0 0 1360 470">{ARROWS}']

    s.append('<text x="0" y="14" class="ttl">FINDING WHAT IS NEEDED</text>')
    s.append(event(28, 82))
    s.append('<path d="M50 82 L86 82" class="f" marker-end="url(#a)"/>')
    s.append(box(86, 52, 190, 60, "cust", ["Describe the problem"], "typed or spoken"))
    s.append('<path d="M276 82 L312 82" class="f" marker-end="url(#a)"/>')
    s.append(box(312, 52, 200, 60, "sys", ["Match to services"], "32 services, phrase level"))
    s.append('<path d="M512 82 L548 82" class="f" marker-end="url(#a)"/>')
    s.append(gateway(584, 82, "any", "match?"))

    s.append('<path d="M620 82 L676 82" class="f" marker-end="url(#a)"/>')
    s.append('<text x="648" y="72" class="lb">yes</text>')
    s.append(box(676, 52, 196, 60, "cust", ["Pick a service"], "price shown as a guide"))

    s.append('<path d="M584 116 L584 176 L676 176" class="fh" marker-end="url(#ah)"/>')
    s.append('<text x="606" y="146" class="hot">no</text>')
    s.append(box(676, 146, 196, 60, "sys", ["Record the request"], "the office sees it unserved"))
    s.append('<path d="M872 176 L1000 176" class="fh" marker-end="url(#ah)"/>')
    s.append(event(1020, 176, end=True))

    s.append('<path d="M872 82 L910 82" class="f" marker-end="url(#a)"/>')
    s.append(box(910, 52, 230, 60, "sys", ["Who can do it, and when"], "ranked soonest, then cheapest"))

    s.append('<path d="M1140 82 L1198 82 L1198 240 L140 240 L140 292" class="f" marker-end="url(#a)"/>')

    s.append('<line x1="0" y1="216" x2="1360" y2="216" class="rule"/>')
    s.append('<text x="0" y="268" class="ttl">BOOKING IT</text>')

    s.append(box(28, 292, 224, 62, "cust", ["Pick a provider"], "their price, their slot length"))
    s.append('<path d="M252 323 L290 323" class="f" marker-end="url(#a)"/>')
    s.append(box(290, 292, 200, 62, "cust", ["Pick a time"], "real slots from their diary"))
    s.append('<path d="M490 323 L526 323" class="f" marker-end="url(#a)"/>')
    s.append(gateway(562, 323, "signed", "in?"))

    s.append('<path d="M562 357 L562 414 L640 414" class="fh" marker-end="url(#ah)"/>')
    s.append('<text x="586" y="386" class="hot">no</text>')
    s.append(box(640, 384, 224, 60, "cust", ["Sign in where you are"], "the choices are not lost"))
    s.append('<path d="M864 414 L906 414 L906 354" class="fh" marker-end="url(#ah)"/>')

    s.append('<path d="M598 323 L640 323" class="f" marker-end="url(#a)"/>')
    s.append('<text x="618" y="313" class="lb">yes</text>')
    s.append(box(640, 292, 224, 62, "cust", ["Check and confirm"], "one screen, no surprises"))
    s.append('<path d="M864 323 L902 323" class="f" marker-end="url(#a)"/>')
    s.append(box(902, 292, 230, 62, "sys", ["Booked, with a reference"], "emailed, not paid yet"))
    s.append('<path d="M1132 323 L1164 323" class="f" marker-end="url(#a)"/>')
    s.append(event(1184, 323, end=True))

    s.append(legend(1214, 292, [("cust", "the customer"), ("sys", "our system")]))
    s.append("</svg>")

    page("d01_customer", "CUSTOMER", "One customer, start to finish",
         "Every step from describing a problem to holding a booking reference.",
         "\n".join(s),
         "<b>The provider is chosen before the time, and that order is deliberate.</b> "
         "The price and the length of a visit belong to the provider, so a slot cannot "
         "even be sized until one is picked. Signing in happens at the last step, so "
         "somebody can see who is available and what they charge before giving an email "
         "address.")


# ── 2. the provider ──────────────────────────────────────────────────────────

def provider():
    s = [f'<svg viewBox="0 0 1360 400">{ARROWS}']

    s.append('<text x="0" y="14" class="ttl">JOINING</text>')
    s.append(event(28, 78))
    s.append('<path d="M50 78 L86 78" class="f" marker-end="url(#a)"/>')
    s.append(box(86, 48, 210, 62, "prov", ["Register the business"], "with services and prices"))
    s.append('<path d="M296 78 L332 78" class="f" marker-end="url(#a)"/>')
    s.append(box(332, 48, 190, 62, "sys", ["Account created"], "status: pending"))
    s.append('<path d="M522 78 L558 78" class="f" marker-end="url(#a)"/>')
    s.append(gateway(594, 78, "approved?", r=48))

    s.append('<path d="M630 78 L686 78" class="f" marker-end="url(#a)"/>')
    s.append('<text x="658" y="68" class="lb">yes</text>')
    s.append(box(686, 48, 210, 62, "sys", ["Visible to customers"], "status: active"))

    s.append('<path d="M594 112 L594 168 L686 168" class="fh" marker-end="url(#ah)"/>')
    s.append('<text x="616" y="140" class="hot">not yet</text>')
    s.append(box(686, 140, 210, 58, "gap", ["Cannot be booked"], "and the dashboard says so"))

    s.append('<line x1="0" y1="212" x2="1360" y2="212" class="rule"/>')
    s.append('<text x="0" y="262" class="ttl">RUNNING THE BUSINESS, APPROVED OR NOT</text>')

    s.append(box(28, 286, 206, 62, "prov", ["Services and prices"], "own price, own slot length"))
    s.append('<path d="M234 317 L268 317" class="f" marker-end="url(#a)"/>')
    s.append(box(268, 286, 196, 62, "prov", ["Working week"], "a day with no hours is shut"))
    s.append('<path d="M464 317 L498 317" class="f" marker-end="url(#a)"/>')
    s.append(box(498, 286, 176, 62, "prov", ["Time off"], "holidays, closures"))
    s.append('<path d="M674 317 L708 317" class="f" marker-end="url(#a)"/>')
    s.append(box(708, 286, 200, 62, "sys", ["Slots are generated"], "hours minus what is booked"))
    s.append('<path d="M908 317 L942 317" class="f" marker-end="url(#a)"/>')
    s.append(box(942, 286, 190, 62, "prov", ["The diary fills"], "grouped by day"))
    s.append('<path d="M1132 317 L1164 317" class="f" marker-end="url(#a)"/>')
    s.append(event(1184, 317, end=True))

    s.append(legend(1214, 286, [("prov", "the provider"), ("sys", "our system"), ("gap", "blocked")]))
    s.append("</svg>")

    page("d02_provider", "PROVIDER", "A business joining and running itself",
         "What a provider does, and what the office controls.",
         "\n".join(s),
         "<b>A pending provider can set everything up but cannot be found or booked.</b> "
         "That is the one thing approval gates. Every provider screen repeats it, because "
         "a business that thinks it is live and is not will blame us for the silence.")


# ── 3. where it runs ─────────────────────────────────────────────────────────

def deployment():
    s = [f'<svg viewBox="0 0 1360 440">{ARROWS}']

    s.append('<rect x="20" y="40" width="250" height="120" rx="10" class="cust"/>')
    s.append('<text x="145" y="76" class="t">Browser</text>')
    s.append('<text x="145" y="98" class="s">phone, tablet or desktop</text>')
    s.append('<text x="145" y="126" class="s">dev.agent.fordev.fun</text>')

    # Singapore
    s.append('<rect x="330" y="20" width="440" height="400" rx="12" class="plain"/>')
    s.append('<text x="550" y="46" class="ttl" style="text-anchor:middle">SERVER 1, SINGAPORE</text>')
    s.append('<text x="550" y="66" class="s">54.255.130.57</text>')

    s.append(box(360, 86, 380, 58, "sys", ["nginx"], "TLS, routing, static files"))
    s.append('<path d="M270 100 L360 115" class="f" marker-end="url(#a)"/>')
    s.append('<text x="312" y="98" class="lb">https</text>')

    s.append('<path d="M470 144 L470 180" class="f" marker-end="url(#a)"/>')
    s.append(box(360, 180, 200, 74, "sys", ["/plumber/", "Next.js pages"], "static export, 15 routes"))

    s.append('<path d="M660 144 L660 180" class="f" marker-end="url(#a)"/>')
    s.append(box(580, 180, 160, 74, "sys", ["/plumber-api/"], "proxied onward"))

    s.append(box(360, 292, 380, 62, "plain", ["Also on this box"],
                 "the grocery assistant, unchanged and separate"))

    # Oregon
    s.append('<rect x="830" y="20" width="510" height="400" rx="12" class="plain"/>')
    s.append('<text x="1085" y="46" class="ttl" style="text-anchor:middle">SERVER 2, OREGON</text>')
    s.append('<text x="1085" y="66" class="s">52.25.174.57</text>')

    s.append('<path d="M740 217 L830 217" class="f" marker-end="url(#a)"/>')
    s.append('<text x="785" y="207" class="lb">http</text>')

    s.append(box(860, 86, 450, 58, "sys", ["FastAPI, port 8100"], "systemd unit: plumber.service"))
    s.append('<path d="M1085 144 L1085 178" class="f" marker-end="url(#a)"/>')

    s.append(box(860, 178, 214, 66, "sys", ["MySQL"], "services, providers, jobs"))
    s.append(box(1096, 178, 214, 66, "sys", ["Embeddings"], "in memory at startup"))

    s.append(box(860, 268, 450, 58, "prov", ["Gemini"], "speech to text, replies, spoken answers"))
    s.append('<path d="M1085 244 L1085 266" class="fd"/>')

    s.append(box(860, 348, 450, 52, "plain", ["Also on this box"], "the grocery render service"))
    s.append("</svg>")

    page("d03_deployment", "DEPLOYMENT", "Two servers, and what each one does",
         "The browser only ever talks to Singapore. Everything else is behind it.",
         "\n".join(s),
         "The booking system runs entirely on the Oregon box. Singapore serves the pages "
         "and forwards anything under <b>/plumber-api/</b> onward, which is why the "
         "browser needs no second address and no cross origin rules. "
         "<b>That hop between the two servers is still plain HTTP</b>, restricted by an "
         "address rule; a certificate for it is outstanding.")


# ── 4. one booking through the stack ─────────────────────────────────────────

def request_path():
    s = [f'<svg viewBox="0 0 1360 360">{ARROWS}']

    s.append('<text x="0" y="14" class="ttl">ONE BOOKING, EVERY LAYER IT TOUCHES</text>')

    s.append(event(28, 90))
    s.append('<path d="M50 90 L84 90" class="f" marker-end="url(#a)"/>')
    s.append(box(84, 60, 200, 62, "cust", ["Book appointment"], "one button, one request"))
    s.append('<path d="M284 90 L320 90" class="f" marker-end="url(#a)"/>')
    s.append(box(320, 60, 210, 62, "sys", ["POST /booking/book"], "with the bearer token"))
    s.append('<path d="M530 90 L566 90" class="f" marker-end="url(#a)"/>')
    s.append(gateway(602, 90, "checks", "pass?"))

    s.append('<path d="M602 124 L602 196 L700 196" class="fh" marker-end="url(#ah)"/>')
    s.append(box(700, 166, 300, 60, "gap", ["409, and why"],
                 "slot taken, provider pending, not offered"))
    s.append('<path d="M1000 196 L1052 196" class="fh" marker-end="url(#ah)"/>')
    s.append(box(1052, 166, 232, 60, "cust", ["Back to the times"], "nothing was created"))

    s.append('<path d="M638 90 L700 90" class="f" marker-end="url(#a)"/>')
    s.append('<text x="668" y="80" class="lb">yes</text>')
    s.append(box(700, 60, 300, 62, "sys", ["One transaction"],
                 "job, appointment, request, all or none"))
    s.append('<path d="M1000 90 L1052 90" class="f" marker-end="url(#a)"/>')
    s.append(box(1052, 60, 232, 62, "sys", ["Everything comes back"],
                 "the screen makes no second call"))

    s.append('<line x1="0" y1="256" x2="1360" y2="256" class="rule"/>')
    s.append('<text x="0" y="292" class="ttl">WHAT THE ANSWER CARRIES</text>')

    fields = ["reference", "provider and phone", "service", "date and time",
              "how long", "price and currency", "payment status", "the request it answers"]
    for i, field in enumerate(fields):
        x = 20 + (i % 4) * 340
        y = 306 + (i // 4) * 30
        s.append(f'<text x="{x}" y="{y}" class="monod lft">- {field}</text>')

    s.append("</svg>")

    page("d04_request", "UNDER THE BONNET", "What happens when Book is pressed",
         "The checks, the single transaction, and what the answer contains.",
         "\n".join(s),
         "<b>The customer is taken from the token, never from the form</b>, so a booking "
         "cannot be made in somebody else's name. Payment status is carried today and "
         "always reads unpaid, because nothing takes money yet: a visit that has not "
         "been paid for must never look settled.")


# ── 5. what it is built from ─────────────────────────────────────────────────

def stack():
    s = ['<svg viewBox="0 0 1360 400">']

    rows = [
        ("IN THE BROWSER", "cust", [
            ("Next.js 16", "React 19, static export"),
            ("TypeScript", "strict"),
            ("Tailwind CSS 4", "design tokens"),
            ("Web Audio", "recording for voice"),
        ]),
        ("ON THE SERVER", "sys", [
            ("FastAPI", "Python 3.12"),
            ("SQLAlchemy", "MySQL 8"),
            ("Uvicorn", "behind nginx"),
            ("PBKDF2", "480,000 rounds"),
        ]),
        ("THE INTELLIGENT PART", "prov", [
            ("Sentence embeddings", "384 dimensions, in memory"),
            ("Phrase matching", "each phrase scored on its own"),
            ("Gemini", "speech in, speech out"),
            ("Deterministic replies", "written by us, not the model"),
        ]),
    ]

    y = 30
    for title, cls, cells in rows:
        s.append(f'<text x="0" y="{y}" class="ttl">{title}</text>')
        for i, (name, sub) in enumerate(cells):
            s.append(box(0 + i * 344, y + 14, 320, 66, cls, [name], sub))
        y += 130

    s.append("</svg>")

    page("d05_stack", "TECHNOLOGY", "What the system is built from",
         "Nothing here was added for this phase except the parts marked in the walkthrough.",
         "\n".join(s),
         "The stack is unchanged from the assistant this grew out of. <b>Two choices are "
         "worth naming.</b> Passwords use PBKDF2 from the Python standard library rather "
         "than bcrypt, because neither bcrypt nor argon2 is installed and the box has "
         "1.9 GB of memory with an embedding model already in it. The catalogue is held "
         "in memory, which is what makes a search take milliseconds rather than seconds.")


# ── 6. the code ──────────────────────────────────────────────────────────────

TREE = [
    ("plumber-assistant/", 0, "the repository", "b"),
    ("backend/", 1, "FastAPI, the whole booking system", "b"),
    ("app/api/", 2, "auth, providers, booking, requests, chat, voice", ""),
    ("app/models/", 2, "provider, account, service_request, job, appointment", ""),
    ("app/services/", 2, "discovery, booking, rag, rate_limit, calendars", ""),
    ("migrations/", 2, "three, all re-runnable", ""),
    ("tests/", 2, "154 tests", ""),
    ("API.md", 2, "every endpoint, its auth and its errors", ""),
    ("frontend/", 1, "Next.js, what people see", "b"),
    ("src/app/", 2, "the 15 routes, one folder each", ""),
    ("src/components/booking/", 2, "service card, providers, slots, review, confirmation", ""),
    ("src/components/provider/", 2, "the dashboard shell", ""),
    ("src/components/auth/", 2, "who is signed in, and the sign in panel", ""),
    ("src/components/ui/", 2, "button, field, sheet, states, images", ""),
    ("src/lib/", 2, "the API client, dates, money, icons", ""),
    ("tests/", 2, "35 unit tests, 33 flow tests", ""),
    ("docs/phase-e/", 1, "this document", "b"),
]


def structure():
    height = 90 + len(TREE) * 30
    s = [f'<svg viewBox="0 0 1360 {height}">']

    s.append('<text x="0" y="16" class="ttl">FOLDERS THAT MATTER</text>')
    s.append(f'<rect x="0" y="30" width="1360" height="{len(TREE) * 30 + 20}" rx="10" class="plain"/>')

    for i, (name, depth, what, weight) in enumerate(TREE):
        y = 58 + i * 30
        x = 24 + depth * 34
        if depth > 0:
            s.append(f'<text x="{x - 20}" y="{y}" class="monod lft">|-</text>')
        style = ' style="font-weight:700"' if weight == "b" else ""
        s.append(f'<text x="{x}" y="{y}" class="mono lft"{style}>{name}</text>')
        s.append(f'<text x="470" y="{y}" class="s lft">{what}</text>')

    s.append("</svg>")

    page("d06_structure", "THE CODE", "Where everything lives",
         "Two applications in one repository, deployed to two different servers.",
         "\n".join(s),
         "<b>The backend and the frontend are separate deployments</b> and can be released "
         "independently. The document you are reading is built from the same repository, "
         "so it cannot describe a version of the code that no longer exists.")


def main() -> None:
    PAGES.mkdir(parents=True, exist_ok=True)
    customer()
    provider()
    deployment()
    request_path()
    stack()
    structure()


if __name__ == "__main__":
    main()
