"""Turn the captured console output into terminal-window images.

Every image in the walkthrough comes from output that was actually produced on
the development server. The files in `captures/` are the unedited runs, written
by re-running each check rather than by copying anything out of a chat log. If a
capture is missing its page is skipped rather than filled in with invented text.

Each image carries a heading, the command that produced it and a short note on
what it shows, so a reader flicking through the document still follows it.

    python3 render_terminals.py     # writes pages/*.html
    python3 render_pages.py         # photographs them into build/*.png
"""

import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAPTURES = HERE / "captures"
PAGES = HERE / "pages"

PROMPT = "ubuntu@dev-server:/var/www/ai-order/backend$"

# Lines matched here get colour. Order matters: the first match wins, so the
# failure words are listed before the general number rule.
RULES = [
    (re.compile(r"\b(passed|confirmed|accepted|True|ok|ready|active|never negative|0 \(expect 0\))\b"), "ok"),
    (re.compile(r"\b(rejected|duplicate event|Invalid|FAIL|failed|error|inactive)\b", re.I), "bad"),
    (re.compile(r"\b(\d{1,3},\d{3}|\d+\.\d+s|\d{4,})\b"), "num"),
]


def colourise(line: str) -> str:
    out = html.escape(line)
    for pattern, cls in RULES:
        if pattern.search(line):
            out = pattern.sub(lambda m: f'<span class="{cls}">{m.group(0)}</span>', out)
            break
    return out


def terminal(command: str, body: str) -> str:
    lines = [f'<span class="pr">{html.escape(PROMPT)}</span> '
             f'<span class="cmd">{html.escape(command)}</span>']
    lines += [colourise(l) for l in body.rstrip().splitlines()]
    return (
        '<div class="win">'
        '<div class="bar"><i class="d r"></i><i class="d y"></i><i class="d g"></i>'
        '<span class="wt">Terminal: development server</span></div>'
        f'<pre class="body">{chr(10).join(lines)}</pre></div>'
    )


STYLE = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { width: 1360px; padding: 26px 30px; background: #fff;
         font-family: "DejaVu Sans", "Liberation Sans", system-ui, sans-serif;
         color: #14213a; }
  .step { display: flex; align-items: baseline; gap: 13px; margin-bottom: 6px; }
  .badge { font-size: 12px; font-weight: 700; letter-spacing: 1px; color: #fff;
           background: #2258d4; border-radius: 5px; padding: 4px 11px; white-space: nowrap; }
  h1 { font-size: 23px; font-weight: 700; letter-spacing: -.2px; }
  .purpose { font-size: 14.5px; color: #5b6b86; margin-bottom: 17px; line-height: 1.5; }
  .win { border-radius: 11px; overflow: hidden; border: 1px solid #2b3648;
         box-shadow: 0 3px 14px rgba(20,33,58,.16); }
  .bar { background: #2b3648; padding: 9px 14px; display: flex; align-items: center; gap: 7px; }
  .d { width: 11px; height: 11px; border-radius: 50%; display: inline-block; }
  .d.r { background: #ff5f57; } .d.y { background: #febc2e; } .d.g { background: #28c840; }
  .wt { margin-left: 10px; font-size: 12px; color: #9fb0c9; font-weight: 600; }
  .body { background: #141c2b; color: #d6e0ee; padding: 17px 19px;
          font-family: "DejaVu Sans Mono", "Liberation Mono", monospace;
          font-size: 13.5px; line-height: 1.62; white-space: pre-wrap; word-break: break-word; }
  .pr { color: #6ee7a8; } .cmd { color: #ffd479; }
  .ok { color: #6ee7a8; font-weight: 700; }
  .bad { color: #ff8b7d; font-weight: 700; }
  .num { color: #7cc4ff; font-weight: 700; }
  .proves { margin-top: 15px; font-size: 14.5px; line-height: 1.55; color: #14213a;
            border-left: 3px solid #2258d4; padding: 9px 0 9px 15px; background: #f6f8fb; }
"""


def page(slug: str, step: str, title: str, purpose: str, command: str,
         capture: str, shows: str) -> str | None:
    path = CAPTURES / capture
    if not path.exists():
        print(f"  ! missing {capture}, page skipped")
        return None
    body = path.read_text(encoding="utf-8")
    doc = f"""<meta charset="utf-8"><style>{STYLE}</style>
<div class="step"><span class="badge">{html.escape(step)}</span><h1>{html.escape(title)}</h1></div>
<p class="purpose">{purpose}</p>
{terminal(command, body)}
<div class="proves">{shows}</div>"""
    out = PAGES / f"{slug}.html"
    out.write_text(doc, encoding="utf-8")
    print(f"  {out.name}")
    return slug


STEPS = [
    ("t01_tests", "TEST", "The automated test suite",
     "Run on every change. Each test is a rule about how the system must behave, "
     "checked automatically so a later change cannot quietly break it.",
     ".venv/bin/python -m pytest tests/ -q", "01_tests.txt",
     "<b>104 tests pass.</b> There were 38 before this work. The new ones cover "
     "stock, duplicate orders, payment webhooks, adopting a product and the wording "
     "of every reply a shopper reads."),

    ("t02_health", "CHECK", "Both services running, catalog loaded",
     "The application and the service that copies orders to the client's database. "
     "The catalog is held in memory so a search never has to read the database.",
     "systemctl is-active aiorder && curl -s .../health", "02_health.txt",
     "<b>Both services are up and the catalog of 25,631 products is loaded.</b> "
     "Building that index takes about 20 seconds and happens in the background at "
     "start up, so the site answers immediately after a restart."),

    ("t03_providers", "PHASE 1", "Which payment methods are available",
     "The checkout asks the server what it can actually take money with, rather than "
     "offering a method that turns out not to be configured.",
     "curl -s .../api/v1/payments/providers", "03_providers.txt",
     "<b>Stripe and PayPal are both live.</b> Stripe covers cards, Apple Pay and "
     "Google Pay in one integration. PayPal brings Venmo."),

    ("t04_pending", "PHASE 1", "An order is created unpaid",
     "Placing an order no longer marks it as confirmed. It waits until the payment "
     "provider says the money arrived.",
     "curl -s -X POST .../api/v1/orders", "04_order_pending.txt",
     "<b>The order is created with status \"pending\".</b> Before this work every "
     "order was written as confirmed immediately, before any money existed."),

    ("t05_idem", "PHASE 1", "A double click does not place two orders",
     "The browser sends a one-off key with each attempt. If the same request arrives "
     "twice, the second returns the original order instead of creating another.",
     "curl -s -X POST .../api/v1/orders   # the identical request, twice", "05_idempotency.txt",
     "<b>The second request returned the same order.</b> Before this, a double click, "
     "a retry or a refresh could create a second order and charge for it."),

    ("t06_oversell", "PHASE 1", "The same unit cannot be sold twice",
     "Two shoppers order the last item at the same moment. The database decides who "
     "gets it, in a single statement that cannot be interrupted.",
     ".venv/bin/python  # two orders fired concurrently", "06_oversell.txt",
     "<b>One order was accepted, the other refused, and stock landed on exactly zero.</b> "
     "Before this the stock check and the deduction were separate steps, so both "
     "shoppers could pass the check and the item sold twice."),

    ("t07_webhook", "PHASE 1", "Payment confirmations are verified and cannot be replayed",
     "The payment provider tells us the money arrived. That message is public on the "
     "internet, so it is checked three ways.",
     ".venv/bin/python tests/manual_webhook_check.py", "07_webhook.txt",
     "<b>A genuine message confirms the order. The same message sent twice is ignored. "
     "A forged message is refused.</b> Providers retry until they get an answer, so "
     "repeats are normal traffic and must never confirm an order twice."),

    ("t08_search", "PHASE 2", "Finding products we do not stock",
     "When our own catalog has nothing suitable, the assistant looks further afield. "
     "Running on sample data here so no search allowance is spent.",
     "curl -s '.../api/v1/shopping/search?q=saffron+threads'", "08_shopping_search.txt",
     "<b>Products outside our catalog, with a price and a seller.</b> Google publishes "
     "no way to search its Shopping results, so this goes through a third party. One "
     "setting switches it from sample data to live results."),

    ("t09_adopt", "PHASE 2", "Requesting one adds it to the catalog and the cart",
     "The shopper asks for one of those products. It becomes a real product in our "
     "own catalog so it can be ordered like anything else.",
     "curl -s -X POST .../api/v1/shopping/adopt", "09_adopt.txt",
     "<b>A new catalog product was created and put in the cart, and asking for it "
     "again reused the same one.</b> The id is far above the client's own numbering "
     "so it can never collide with his products."),

    ("t10_speed", "PHASE 3", "How long a search now takes",
     "The same four searches used to measure the system before any of this work began.",
     "curl -s -X POST .../api/v1/chat   # timed", "10_speed.txt",
     "<b>Between 0.07 and 0.26 seconds. These took 3.8 to 4.7 seconds before.</b> "
     "Almost all of that time was the AI rewriting a product list the system had "
     "already produced, so it is no longer asked to."),

    ("t11_names", "DATA", "Product names repaired",
     "2,292 names showed a question mark where an apostrophe belonged, so shoppers "
     "read \"Member?s Mark\". Re-run after any catalog import, which puts them back.",
     ".venv/bin/python fix_product_names.py --dry-run", "11_names.txt",
     "<b>Nothing left to repair.</b> 1,919 apostrophes were fixed. The remaining 381 "
     "are accented letters rather than apostrophes, such as Nestlé and Jalapeño, "
     "and replacing those blindly would make them worse."),

    ("t12_reply", "RESULT", "What a shopper reads now",
     "The reply for a search, exactly as it appears in the chat.",
     "curl -s -X POST .../api/v1/chat -d '{\"message\":\"milk\"}'", "12_reply.txt",
     "<b>Names read correctly and the list is numbered so the shopper can say "
     "\"add item 2\".</b> That numbering is produced by the system rather than by the "
     "AI, which is why it always matches what gets added."),

    ("t13_cleanup", "CHECK", "Test data removed afterwards",
     "Everything created while producing these screenshots was deleted, so the "
     "development database is left as it was found.",
     ".venv/bin/python  # cleanup", "13_cleanup.txt",
     "<b>The catalog is back to 25,631 products with no test data left.</b> The "
     "service that copies orders to the client's database had nothing of this queued."),
]


def build() -> list[str]:
    PAGES.mkdir(parents=True, exist_ok=True)
    return [s for s in (page(*step) for step in STEPS) if s]


if __name__ == "__main__":
    print(f"building terminal pages from {CAPTURES}")
    made = build()
    print(f"\n{len(made)} pages written to {PAGES}")
