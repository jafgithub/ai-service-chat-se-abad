"""SmartMarket: specification.

The grocery assistant had walkthroughs, a speed study and a runbook, and no
specification. This is that document, written to the same shape as the Service
Assistant's and the community agent's so the three can be read against each
other.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "_house"))
import page  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent

TOC = [
    ("s1", "1", "Purpose and scope", ()),
    ("s2", "2", "The system in one picture", ()),
    ("s3", "3", "Who uses it", ()),
    ("s4", "4", "What it does", ()),
    ("s5", "5", "How it must behave", (
        ("s51", "5.1", "Search latency", ()),
        ("s52", "5.2", "Correctness of money", ()),
        ("s53", "5.3", "Getting orders to the shop", ()),
        ("s54", "5.4", "Fallback", ()),
        ("s55", "5.5", "Security", ()),
        ("s56", "5.6", "Observability", ()),
    )),
    ("s6", "6", "Where it runs", ()),
    ("s7", "7", "Assumptions and limits", ()),
    ("s8", "8", "Out of scope", ()),
]

DIAGRAM = """
<svg class="flow" viewBox="0 0 900 320" role="img"
     aria-label="A shopper's sentence becomes a search over an in-memory catalogue,
                 then a cart, then a paid order, which is written locally and
                 pushed to the shop's own database through an outbox.">
  <defs>
    <marker id="b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0 L10 5 L0 10 z" fill="currentColor"/>
    </marker>
  </defs>
  <g fill="none" stroke="currentColor" stroke-width="1.4" marker-end="url(#b)" opacity=".55">
    <path d="M140 62 H196"/>
    <path d="M336 62 H392"/>
    <path d="M532 62 H588"/>
    <path d="M652 90 V152"/>
    <path d="M652 214 V252"/>
  </g>
  <g font-family="IBM Plex Mono, monospace" font-size="12.5">
    <g>
      <rect x="12" y="36" width="128" height="52" rx="8" fill="var(--sunken)" stroke="var(--rule)"/>
      <text x="76" y="59" text-anchor="middle" fill="var(--ink)">&#8220;cheapest</text>
      <text x="76" y="76" text-anchor="middle" fill="var(--ink)">eggs&#8221;</text>
    </g>
    <g>
      <rect x="196" y="36" width="140" height="52" rx="8" fill="var(--card)" stroke="var(--rule)"/>
      <text x="266" y="59" text-anchor="middle" fill="var(--ink)">Catalogue in</text>
      <text x="266" y="76" text-anchor="middle" fill="var(--ink)">memory, 8 ms</text>
    </g>
    <g>
      <rect x="392" y="36" width="140" height="52" rx="8" fill="var(--card)" stroke="var(--rule)"/>
      <text x="462" y="59" text-anchor="middle" fill="var(--ink)">Cart, tax</text>
      <text x="462" y="76" text-anchor="middle" fill="var(--ink)">and tip</text>
    </g>
    <g>
      <rect x="588" y="36" width="128" height="52" rx="8" fill="var(--ours-soft)" stroke="var(--ours)"/>
      <text x="652" y="59" text-anchor="middle" fill="var(--ours)">Paid, and</text>
      <text x="652" y="76" text-anchor="middle" fill="var(--ours)">written here</text>
    </g>
    <g>
      <rect x="588" y="162" width="128" height="52" rx="8" fill="var(--card)" stroke="var(--rule)"/>
      <text x="652" y="185" text-anchor="middle" fill="var(--ink)">Outbox row,</text>
      <text x="652" y="202" text-anchor="middle" fill="var(--ink)">pending</text>
    </g>
    <g>
      <rect x="572" y="262" width="160" height="46" rx="8" fill="var(--cloud-soft)" stroke="var(--cloud)"/>
      <text x="652" y="290" text-anchor="middle" fill="var(--cloud)">The shop's database</text>
    </g>
    <g>
      <rect x="756" y="36" width="132" height="52" rx="8" fill="var(--warn-soft)" stroke="var(--warn)"/>
      <text x="822" y="59" text-anchor="middle" fill="var(--warn)">Not stocked?</text>
      <text x="822" y="76" text-anchor="middle" fill="var(--warn)">source it</text>
    </g>
  </g>
  <g fill="none" stroke="currentColor" stroke-width="1.4" marker-end="url(#b)" opacity=".55">
    <path d="M716 62 H748"/>
  </g>
</svg>
"""


def reqs(items):
    rows = "\n".join(
        f'          <li><span class="id">{rid}</span><span class="txt">{text}</span></li>'
        for rid, text in items
    )
    return f'        <ul class="reqs">\n{rows}\n        </ul>'


BODY = f"""
      <section id="s1">
        <h2 class="sec"><span class="n">1</span>Purpose and scope</h2>
        <p class="lede">
          SmartMarket takes a shopper's own words, finds the products a shop
          actually stocks, builds a basket, takes the money, and puts the order
          into the shop's own database in the shape that shop's existing systems
          already read. The conversation is the shopfront; everything behind it
          is ordinary retail plumbing that has to be exactly right.
        </p>
        <p>
          This document specifies what it is required to do and how it is
          required to behave. Two things dominate it and neither is the language
          model. The first is <strong>latency</strong>, because a shopper
          abandons a search that takes six seconds. The second is
          <strong>the correctness of money</strong>, because an order that
          reports a tip as sales tax is a bookkeeping problem for somebody else
          to find months later.
        </p>
      </section>

      <section id="s2">
        <h2 class="sec"><span class="n">2</span>The system in one picture</h2>
        <p>
          A sentence becomes a search, a search becomes a basket, a basket
          becomes a paid order. The order is written locally first and reaches
          the shop's own database afterwards, through an outbox, and that
          ordering is the whole of section 5.3.
        </p>
        <div class="figure">
          <div class="scroller">{DIAGRAM}</div>
          <p class="figcap">
            Fig. 1 &middot; from a sentence to a row in the shop's database
          </p>
        </div>
      </section>

      <section id="s3">
        <h2 class="sec"><span class="n">3</span>Who uses it</h2>
        <table class="spec">
          <thead><tr><th>Who</th><th>What they come for</th></tr></thead>
          <tbody>
            <tr><td>A shopper</td><td>A week's groceries, described rather than
              navigated. Often on a phone, often by voice, often while doing
              something else.</td></tr>
            <tr><td>The shop</td><td>Orders arriving in its own database, in its
              own shape, without anybody rekeying them.</td></tr>
            <tr><td>The office</td><td>What was ordered, what was paid, what was
              sourced from outside the catalogue, and what failed.</td></tr>
          </tbody>
        </table>
      </section>

      <section id="s4">
        <h2 class="sec"><span class="n">4</span>What it does</h2>

        <h3 class="sub">Finding things</h3>
{reqs([
  ("F-1", "Understand a whole sentence, not a keyword. &#8220;Cheapest eggs&#8221; and "
          "&#8220;best deal on coffee&#8221; are price intents and are ranked as such, not "
          "matched as strings."),
  ("F-2", "Rank against what the shop stocks, from an index held in memory, "
          "without reading the catalogue out of the database for every search."),
  ("F-3", "Return results whose ordering is stable, so the same question asked "
          "twice does not reshuffle the shelf under the shopper."),
  ("F-4", "Where the shop does not stock something, offer to source it from "
          "outside the catalogue rather than saying no."),
])}

        <h3 class="sub">Buying</h3>
{reqs([
  ("F-5", "Add, change and remove basket lines from inside the conversation, "
          "without leaving it for a separate cart screen."),
  ("F-6", "Compute tax on the goods, and a tip on the goods before tax, and show "
          "the three numbers separately at every step."),
  ("F-7", "Take payment by card or PayPal, and support cash on delivery where the "
          "shop offers it."),
  ("F-8", "Confirm by email, itemised, with the same three numbers the checkout "
          "showed."),
])}

        <h3 class="sub">Speaking</h3>
{reqs([
  ("F-9", "Accept a spoken order and answer aloud, with speech handled on the "
          "server so no provider key ever reaches a browser."),
  ("F-10", "Continue listening across turns, so a shopper can dictate a list "
           "rather than press a button per item."),
])}

        <h3 class="sub">The office</h3>
{reqs([
  ("F-11", "List orders and payments, with what each one actually collected."),
  ("F-12", "Show sourcing outcomes, including what was sourced from outside the "
           "catalogue and by which provider."),
])}
      </section>

      <section id="s5">
        <h2 class="sec"><span class="n">5</span>How it must behave</h2>

        <h3 class="sub" id="s51"><span class="n">5.1</span>Search latency</h3>
        <p>
          The catalogue barely changes and used to be re-read in full on every
          single search: roughly 25,600 rows of embedding text pulled out of
          MySQL, re-parsed and stacked into a fresh matrix, in order to run one
          dot product that takes microseconds. The loading was the response time.
          It is now loaded once at startup and held in memory, and a search is a
          matrix multiply, a threshold and a sort.
        </p>
        <table class="spec">
          <thead><tr><th>Query</th><th>Before</th><th>After</th><th>Change</th></tr></thead>
          <tbody>
            <tr><td>milk</td><td class="num">6,558 ms</td><td class="num">6.50 ms</td><td class="num">1,009x</td></tr>
            <tr><td>eggs</td><td class="num">6,434 ms</td><td class="num">4.58 ms</td><td class="num">1,405x</td></tr>
            <tr><td>cheese</td><td class="num">6,428 ms</td><td class="num">11.11 ms</td><td class="num">579x</td></tr>
            <tr><td>cheapest eggs</td><td class="num">6,444 ms</td><td class="num">26.91 ms</td><td class="num">240x</td></tr>
            <tr><td>best deal on coffee</td><td class="num">6,468 ms</td><td class="num">27.33 ms</td><td class="num">237x</td></tr>
            <tr><td><strong>Median</strong></td><td class="num"><strong>6,456 ms</strong></td><td class="num"><strong>8.21 ms</strong></td><td class="num"><strong>787x</strong></td></tr>
          </tbody>
        </table>
        <div class="callout">
          <p>
            Two rules governed that change and remain requirements. The results
            must be <strong>identical</strong>, which is asserted against the
            live database by a parity check rather than asserted in prose. And it
            must be <strong>never worse</strong>: if the index is missing, still
            building or switched off, search falls back to the database path
            silently.
          </p>
        </div>

        <h3 class="sub" id="s52"><span class="n">5.2</span>Correctness of money</h3>
{reqs([
  ("N-1", "Tax is computed on the goods. The tip is computed on the goods before "
          "tax, because tipping a percentage of sales tax is not a thing anybody "
          "means to do."),
  ("N-2", "The tip percentage is decided on the server from a fixed set of "
          "offered values. A percentage arriving from a browser that is not one "
          "of them is a client that has been edited, not a shopper being "
          "generous."),
  ("N-3", "Tax is never derived by subtracting the goods from the total. That is "
          "how it was written before tips existed, and left alone it would have "
          "reported every tip as sales tax, in the order record and in the "
          "confirmation email both."),
  ("N-4", "Goods, tax and tip appear as three separate numbers wherever a total "
          "appears: the basket, the checkout, the order record and the email."),
])}
        <p>
          N-3 is stated as a requirement rather than a fixed bug because it is the
          kind of fault that is invisible while it is happening. It was found by
          checking that a $5 tip left the tax at 1.93, not by anything failing.
        </p>

        <h3 class="sub" id="s53"><span class="n">5.3</span>Getting orders to the shop</h3>
        <p>
          Orders are written to this application's own database first, and pushed
          to the shop's afterwards by a separate process draining an outbox. The
          shopper's confirmation does not wait on a network hop to somebody
          else's server, and a shop database that is briefly unreachable delays
          delivery of an order rather than losing it.
        </p>
{reqs([
  ("N-5", "An order is complete and confirmed on this side before any attempt to "
          "push it. The push is retried and its failures are recorded per row."),
  ("N-6", "Local identities are mapped to the shop's identities and the mapping "
          "is kept, so a retry updates rather than duplicates."),
  ("N-7", "Exactly one machine drains the outbox. This is a requirement rather "
          "than a convention: it has been violated three times by cloned "
          "machines that came up with the sync running, and each time two "
          "machines were writing the same rows into a live shop database."),
])}
        <div class="callout">
          <p>
            The check for N-7 is one command and belongs in every handover: the
            sync must be active on the grocery machine and on no other. Checked
            by asking each machine, not by assuming.
          </p>
        </div>

        <h3 class="sub" id="s54"><span class="n">5.4</span>Fallback</h3>
{reqs([
  ("N-8", "Sourcing from outside the catalogue goes through a provider "
          "interface. When a provider is unavailable or unconfigured, sourcing "
          "degrades and the rest of the shop keeps working."),
  ("N-9", "Speech failing in either direction leaves the written path intact. A "
          "failed transcription asks the shopper to repeat themselves; a failed "
          "voice is read by the browser."),
  ("N-10", "A payment provider being unavailable must not create an order that "
           "nobody paid for."),
])}

        <h3 class="sub" id="s55"><span class="n">5.5</span>Security</h3>
{reqs([
  ("N-11", "No provider key reaches a browser. Speech runs on the server "
           "specifically because an earlier version called a speech provider "
           "from the front end with an exposed key."),
  ("N-12", "Prices, tax, tips and totals are computed on the server. Nothing "
           "that decides what is charged is taken from the client."),
  ("N-13", "Office functions require an admin token."),
  ("N-14", "Test and demonstration data must never reach the shop's live "
           "database. The sync is stopped before any test that creates orders, "
           "and this has already been necessary."),
])}

        <h3 class="sub" id="s56"><span class="n">5.6</span>Observability</h3>
{reqs([
  ("N-15", "Search timing is logged per query, so a slow answer can be "
           "attributed to retrieval or to the engine rather than guessed at."),
  ("N-16", "The outbox reports its own state: pending, done, attempts, and the "
           "last error per row. A stuck order is a row somebody can look at."),
  ("N-17", "Sourcing records which provider answered and what it returned, so an "
           "item that arrived from outside the catalogue can be traced."),
])}
      </section>

      <section id="s6">
        <h2 class="sec"><span class="n">6</span>Where it runs</h2>
        <table class="spec">
          <thead><tr><th>Part</th><th>What</th></tr></thead>
          <tbody>
            <tr><td>Address</td><td>marketz.smartzees.com</td></tr>
            <tr><td>Application</td><td>FastAPI, one process</td></tr>
            <tr><td>Screens</td><td>Next.js, exported as static files and served by nginx</td></tr>
            <tr><td>Database</td><td>Its own MySQL schema, plus an outbox to the shop's</td></tr>
            <tr><td>Catalogue index</td><td>About 25,600 products, 384 dimensions, held in memory</td></tr>
            <tr><td>Region</td><td>Its own, separate from the other two agents</td></tr>
          </tbody>
        </table>
        <p>
          It is the only one of the three agents in its region, which means it
          cannot reach the other two privately and does not need to. It shares
          nothing with them except the engine switch and the hardware behind it.
        </p>
      </section>

      <section id="s7">
        <h2 class="sec"><span class="n">7</span>Assumptions and limits</h2>
{reqs([
  ("A-1", "The catalogue is the shop's. Products that are missing, mispriced or "
          "out of date in it are missing, mispriced or out of date here."),
  ("A-2", "The in-memory index assumes a catalogue that changes rarely. It is "
          "rebuilt rather than updated in place, and a shop that reprices hourly "
          "would need that reconsidered."),
  ("A-3", "Sourcing from outside the catalogue depends on a third party, whose "
          "availability and terms are outside this system."),
  ("A-4", "English only, for the same reason as the other two agents: the "
          "retrieval model is an English model."),
])}
      </section>

      <section id="s8">
        <h2 class="sec"><span class="n">8</span>Out of scope</h2>
        <table class="spec">
          <thead><tr><th>Not here</th><th>Why not</th></tr></thead>
          <tbody>
            <tr><td>Stock levels and reservations</td><td>The shop's own systems own stock. This orders from a catalogue, it does not hold inventory</td></tr>
            <tr><td>Delivery routing and drivers</td><td>An order reaches the shop's database and the shop's existing operation takes it from there</td></tr>
            <tr><td>Refunds and returns</td><td>Handled by the shop, through the payment provider, outside this application</td></tr>
            <tr><td>Community documents and bookings</td><td>Separate products, on separate machines, with separate databases</td></tr>
          </tbody>
        </table>
      </section>
"""

html = page.render(
    title="SmartMarket Specification",
    badge="Specification",
    h1="SmartMarket",
    standfirst=(
        "What the grocery assistant does, and the two things it is actually "
        "judged on: how fast it finds something, and whether the money is right."
    ),
    docmeta=[
        ("Document", "SRS-SM-1"),
        ("Version", "1.0"),
        ("Date", "31 August 2026"),
        ("Status", "For review"),
        ("Author", "Abad Naseer"),
    ],
    toc=TOC,
    body=BODY,
)

out = HERE / "index.html"
out.write_text(html)
print(f"wrote {out} ({len(html):,} bytes)")
