"""The documentation hub: one page listing everything, for all three agents.

It used to have two sections and hard coded fordev.fun addresses. There are
three products now, on three smartzees.com names, so the list is data and the
page is generated from it. That way a new document is one entry rather than a
copy of a block of HTML with one word changed.

The same file is deployed to all three machines, so every link is absolute:
somebody who opens the hub from the community site still has to be able to
reach a grocery document.
"""

import pathlib

HERE = pathlib.Path(__file__).resolve().parent

MARKET = "https://marketz.smartzees.com"
SERVICE = "https://servicez.smartzees.com"
COMMUNITY = "https://livz.smartzees.com"

#: (name, kind, description, date, url, search words)
SECTIONS = [
    {
        "id": "smartmarket",
        "title": "SmartMarket, the grocery assistant",
        "blurb": "Ordering a week's shopping by describing it: search, cart, "
                 "checkout, sourcing and delivery, and the machine it runs on.",
        "docs": [
            ("SmartMarket: specification", "Specification",
             "What it does, and the two things it is actually judged on: how fast it "
             "finds something, and whether the money is right",
             "31 August 2026", f"{SERVICE}/docs/market-srs/",
             "srs specification requirements grocery market search latency tip tax "
             "outbox sync money correctness scalability security observability catalogue"),
            ("What it does, what holds it back, where it can go", "Brief",
             "The brief: what the product does today, what makes it slow, what it "
             "would take to sell it, and what to build next",
             "8 August 2026", f"{MARKET}/docs/next-phase/",
             "brief roadmap future voice speed google api keys recommendations proposal next phase"),
            ("Setting up your own copy", "Setup guide",
             "Start a new machine from a snapshot, give it its own address, and check "
             "it in a browser. Written for somebody who has never used a server",
             "17 August 2026", f"{MARKET}/docs/runbook/",
             "install setup server snapshot lightsail nginx domain address deploy new machine copy"),
            ("Product search and cart", "Milestone",
             "The search and cart milestone: what was asked for, what was built, and "
             "the result of every test",
             "10 August 2026", f"{MARKET}/docs/milestone-search-cart/",
             "search cart basket checkout quantity milestone products"),
            ("The interface redesign", "Walkthrough",
             "A redesign of the shopper's screens, and the four faults it uncovered",
             "8 August 2026", f"{MARKET}/docs/ui-redesign/",
             "design ui screens layout mobile look shopper redesign"),
            ("Payment, sourcing and speed", "Walkthrough",
             "What was built across three phases, how it was done, and what each "
             "change did to the numbers",
             "8 August 2026", f"{MARKET}/docs/three-phases/",
             "payment stripe paypal sourcing google shopping speed index phases"),
        ],
        "word": [
            ("The brief", f"{MARKET}/docs/AI_Order_Brief.docx"),
            ("Payment, sourcing and speed", f"{MARKET}/docs/AI_Order_Three_Phases.docx"),
            ("The interface redesign", f"{MARKET}/docs/AI_Order_Interface_Redesign.docx"),
            ("Product search and cart", f"{MARKET}/docs/AI_Order_Search_And_Cart.docx"),
            ("Speed, part 1: summary", f"{MARKET}/docs/speed/01_Summary.docx"),
            ("Speed, part 2: how it works", f"{MARKET}/docs/speed/02_How_It_Works.docx"),
            ("Speed, part 3: what we did", f"{MARKET}/docs/speed/03_What_We_Did.docx"),
            ("Speed, part 4: results", f"{MARKET}/docs/speed/04_Results.docx"),
            ("Speed, part 5: technical reference", f"{MARKET}/docs/speed/05_Technical_Reference.docx"),
        ],
    },
    {
        "id": "smartservice",
        "title": "SmartService, the booking platform",
        "blurb": "Describing a problem and ending up with a tradesperson booked, "
                 "paid and confirmed. Also where parking passes and the hardware "
                 "switch live.",
        "docs": [
            ("The Service Assistant: specification", "Specification",
             "What the system does, who uses it, and how it must behave under load and "
             "under failure, ending in a live console you can run",
             "29 August 2026", f"{SERVICE}/docs/srs/",
             "srs specification requirements functional non functional scalability fallback "
             "availability security observability simulation stakeholders circuit breaker uptime"),
            ("Break the assistant", "Interactive",
             "Our AI infrastructure under load, as something you can drag: turn the "
             "traffic past a million requests a day, starve the cache, kill a card, and "
             "watch what the design does about it",
             "29 August 2026", f"{SERVICE}/docs/lab/",
             "load scale throughput simulation gpu cards batching cache queue capacity "
             "million requests pitch demo infrastructure autoscale breaker"),
            ("The booking platform", "Walkthrough",
             "Describe a problem, see who can do it, pick a time, book it. What a "
             "customer does, what a provider does, and where it runs",
             "12 August 2026", f"{MARKET}/docs/phase-e/",
             "booking appointment provider calendar slots payment customer journey plumber"),
            ("Requirements, for approval", "Requirements",
             "What the booking assistant was going to be, before it was built. Kept so "
             "the finished thing can be checked against it",
             "11 August 2026", f"{MARKET}/docs/plumber-system/",
             "requirements scope quote price approval plumber specification"),
            ("Spin-off and plumbing handover", "Handover",
             "Two applications from one codebase: what differs between them, and how to "
             "stand either one up on a new machine",
             "14 August 2026", f"{SERVICE}/docs/runbook/",
             "handover server setup snapshot deploy nginx rollback security spin off new instance"),
        ],
        "word": [
            ("The booking platform", f"{MARKET}/docs/Service_Assistant_Booking_Platform.docx"),
            ("Requirements, for approval", f"{MARKET}/docs/Plumber_Assistant_Requirements.docx"),
        ],
    },
    {
        "id": "smartcommunity",
        "title": "SmartCommunity, the association assistant",
        "blurb": "Answering a resident out of their own association's documents, "
                 "and naming the page it came from. Its own site since August 2026.",
        "docs": [
            ("SmartCommunity: specification", "Specification",
             "What it answers, what it refuses, and how one association is never "
             "answered from another's rules",
             "31 August 2026", f"{SERVICE}/docs/community-srs/",
             "srs specification requirements community association hoa rules grounding "
             "refusal scoping citation retrieval threshold voice livz residents"),
            ("How the community assistant answers", "Explainer",
             "In plain language: where the answers come from, what happens between a "
             "question and the reply, and what it does when your documents do not cover it",
             "27 August 2026", f"{SERVICE}/docs/how-it-answers/",
             "how it works rag explain plain english answers documents refuse grounding "
             "trust board residents simple overview"),
            ("Community documents: how the assistant answers", "Technical reference",
             "Uploading a document yourself, downloading one, parking passes, and how a "
             "resident's question is routed so that one community is never answered from "
             "another's rules",
             "26 August 2026", f"{SERVICE}/docs/community-rag/",
             "rag rules quiet hours parking pets lease trash serenity lauderdale three lakes "
             "ocr scoping technical upload admin download qr visitor pass refresher picker"),
            ("Adding a community document", "How to",
             "How to add one yourself in a minute, what can and cannot be used, and what "
             "happens to a document once it is in",
             "26 August 2026", f"{SERVICE}/docs/adding-documents/",
             "documents pdf send upload rules association sop how to scanned ocr contradictions admin"),
        ],
        "word": [],
    },
    {
        "id": "hardware",
        "title": "The hardware underneath",
        "blurb": "Running the model on a machine we control, what it costs, and how "
                 "the applications carry on when it is switched off. Shared by all three agents.",
        "docs": [
            ("Spinning up a GPU, and wiring it to FastAPI", "Step by step",
             "From an empty AWS account to a resident's question answered by our own "
             "model, in nine steps. Written from a real attempt, including the two "
             "things that stopped it",
             "31 August 2026", f"{SERVICE}/docs/gpu-spinup/",
             "gpu spin up step by step guide aws ec2 g6 xlarge l4 ollama llama fastapi "
             "integration wiring quota free tier security group idle auto stop lambda "
             "cloud-init home panic ollama_url fallback checklist troubleshooting cost"),
            ("Our own GPU, in plain words", "Explainer",
             "What it means to run the AI on hardware we control, what it costs when it "
             "is on and when it is off, and why forgetting to switch it off does not "
             "cost anything",
             "29 August 2026", f"{SERVICE}/docs/our-own-gpu/",
             "gpu own hardware ollama open model gemini google switch cost saving instance "
             "off on plain english client seminar demo privacy"),
            ("Running the AI on our own GPU: setup", "Technical setup",
             "Creating the machine and wiring it to the Service Assistant: the quota that "
             "blocks everything else, the AWS permissions, the two mechanisms that stop it "
             "when nobody is using it, and how to check each one works",
             "29 August 2026", f"{SERVICE}/docs/gpu-setup/",
             "gpu setup aws ec2 g6 xlarge l4 ollama llama iam policy lambda cron idle auto "
             "stop quota security group cloud-init instance runbook boto3"),
            ("Installing the open model, and wiring it to FastAPI", "Installation",
             "The software half: installing Ollama, choosing a model, making it reachable, "
             "the four modules that decide where a question goes, and how to run the whole "
             "thing with no GPU at all",
             "29 August 2026", f"{SERVICE}/docs/llm-fastapi/",
             "install ollama llama model fastapi integration wiring setup steps developer gpu "
             "engine switch localhost laptop troubleshooting keep alive"),
        ],
        "word": [],
    },
]


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&#x27;"))


def build():
    total = sum(len(s["docs"]) for s in SECTIONS)
    parts = [HERE.joinpath("hub_head.html").read_text(), "<body>"]

    parts.append('<p class="eyebrow">Documentation</p>')
    parts.append("<h1>Everything we have written for you</h1>")
    parts.append(
        f'<p class="lede">{total} documents, in four groups: one for each of the '
        "three assistants, and one for the hardware they share. Every one opens in "
        "your browser, and every one has its own contents list at the top so you can "
        "jump straight to a section.</p>"
    )

    jump = "".join(f'<a href="#{s["id"]}">{esc(s["title"].split(",")[0])}</a>' for s in SECTIONS)
    parts.append(f'<div class="jump">{jump}</div>')

    parts.append(
        '<input class="find" id="find" type="search" '
        'placeholder="Type to find a document: parking, gpu, speed, setup, sourcing..." '
        'aria-label="Find a document">'
    )
    parts.append('<p class="count" id="count"></p>')
    parts.append(
        f'<p class="empty" id="empty">Nothing matches that. Clear the box to see all {total} again.</p>'
    )

    for s in SECTIONS:
        parts.append(f'<section id="{s["id"]}">')
        parts.append(f'<h2>{esc(s["title"])}</h2>')
        parts.append(f'<p class="blurb">{esc(s["blurb"])}</p>')
        for name, kind, desc, when, url, words in s["docs"]:
            find = esc(" ".join((name, desc, kind, when, words)).lower())
            parts.append(
                f'<a class="card" href="{url}" data-find="{find}">\n'
                f'  <span class="top"><span class="name">{esc(name)}</span>'
                f'<span class="kind">{esc(kind)}</span></span>\n'
                f'  <p class="desc">{esc(desc)}</p>\n'
                f'  <p class="when">{when}</p>\n'
                f"</a>"
            )
        if s["word"]:
            items = "".join(f'<li><a href="{u}">{esc(t)}</a></li>' for t, u in s["word"])
            parts.append(f'<div class="word"><p>Word versions</p><ul>{items}</ul></div>')
        parts.append("</section>")

    parts.append(
        "<footer>Kept up to date as work is delivered. If something you were sent is "
        "not listed here, tell us and it will be added.</footer>"
    )
    parts.append("""<script>
const find = document.getElementById('find');
const cards = [...document.querySelectorAll('a.card')];
const count = document.getElementById('count');
const empty = document.getElementById('empty');
find.addEventListener('input', () => {
  const q = find.value.trim().toLowerCase();
  let shown = 0;
  for (const card of cards) {
    const hit = !q || card.dataset.find.includes(q);
    card.style.display = hit ? '' : 'none';
    if (hit) shown++;
  }
  for (const section of document.querySelectorAll('section')) {
    const any = [...section.querySelectorAll('a.card')].some(c => c.style.display !== 'none');
    section.style.display = any ? '' : 'none';
  }
  count.textContent = q ? `${shown} of ${cards.length} documents` : '';
  empty.style.display = shown ? 'none' : 'block';
});
</script>""")
    parts.append("</body>\n</html>")
    return "\n".join(parts)


if __name__ == "__main__":
    out = HERE.parent / "index.html"
    out.write_text(build())
    print(f"wrote {out} ({out.stat().st_size:,} bytes), "
          f"{sum(len(s['docs']) for s in SECTIONS)} documents")
