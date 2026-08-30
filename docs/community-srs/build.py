"""SmartCommunity: specification.

Hand written, like the Service Assistant's SRS, and for the same reason: an SRS
is argued rather than generated. It shares that document's stylesheet through
`_house/page.py` so the set reads as one set.
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
        ("s51", "5.1", "Grounding and refusal", ()),
        ("s52", "5.2", "Community scoping", ()),
        ("s53", "5.3", "Fallback", ()),
        ("s54", "5.4", "Latency and scale", ()),
        ("s55", "5.5", "Security", ()),
        ("s56", "5.6", "Observability", ()),
    )),
    ("s6", "6", "Where it runs", ()),
    ("s7", "7", "Assumptions and limits", ()),
    ("s8", "8", "Out of scope", ()),
]

DIAGRAM = """
<svg class="flow" viewBox="0 0 900 240" role="img"
     aria-label="A question travels from a resident through community scoping and
                 retrieval, and either reaches an engine with the passages it found
                 or is refused without one.">
  <defs>
    <marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0 0 L10 5 L0 10 z" fill="currentColor"/>
    </marker>
  </defs>
  <g fill="none" stroke="currentColor" stroke-width="1.4" marker-end="url(#a)" opacity=".55">
    <path d="M132 60 H196"/>
    <path d="M320 60 H384"/>
    <path d="M508 60 H572"/>
    <path d="M636 88 V150"/>
    <path d="M448 88 V196 H572"/>
  </g>

  <g font-family="IBM Plex Mono, monospace" font-size="12.5">
    <g>
      <rect x="8" y="34" width="124" height="52" rx="8" fill="var(--sunken)" stroke="var(--rule)"/>
      <text x="70" y="57" text-anchor="middle" fill="var(--ink)">A resident,</text>
      <text x="70" y="74" text-anchor="middle" fill="var(--ink)">typing or aloud</text>
    </g>
    <g>
      <rect x="196" y="34" width="124" height="52" rx="8" fill="var(--card)" stroke="var(--rule)"/>
      <text x="258" y="57" text-anchor="middle" fill="var(--ink)">Which</text>
      <text x="258" y="74" text-anchor="middle" fill="var(--ink)">association?</text>
    </g>
    <g>
      <rect x="384" y="34" width="124" height="52" rx="8" fill="var(--card)" stroke="var(--rule)"/>
      <text x="446" y="57" text-anchor="middle" fill="var(--ink)">Retrieval,</text>
      <text x="446" y="74" text-anchor="middle" fill="var(--ink)">that shelf only</text>
    </g>
    <g>
      <rect x="572" y="34" width="128" height="52" rx="8" fill="var(--ours-soft)" stroke="var(--ours)"/>
      <text x="636" y="57" text-anchor="middle" fill="var(--ours)">Passages found</text>
      <text x="636" y="74" text-anchor="middle" fill="var(--ours)">score &#8805; 0.30</text>
    </g>
    <g>
      <rect x="572" y="170" width="128" height="52" rx="8" fill="var(--refuse-soft)" stroke="var(--refuse)"/>
      <text x="636" y="193" text-anchor="middle" fill="var(--refuse)">Nothing found</text>
      <text x="636" y="210" text-anchor="middle" fill="var(--refuse)">no engine called</text>
    </g>
    <g>
      <rect x="748" y="34" width="144" height="52" rx="8" fill="var(--cloud-soft)" stroke="var(--cloud)"/>
      <text x="820" y="57" text-anchor="middle" fill="var(--cloud)">An engine words</text>
      <text x="820" y="74" text-anchor="middle" fill="var(--cloud)">only those passages</text>
    </g>
    <g>
      <rect x="748" y="170" width="144" height="52" rx="8" fill="var(--sunken)" stroke="var(--rule)"/>
      <text x="820" y="193" text-anchor="middle" fill="var(--ink)">&#8220;It is not in</text>
      <text x="820" y="210" text-anchor="middle" fill="var(--ink)">your documents&#8221;</text>
    </g>
  </g>
  <g fill="none" stroke="currentColor" stroke-width="1.4" marker-end="url(#a)" opacity=".55">
    <path d="M700 60 H740"/>
    <path d="M700 196 H740"/>
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
          SmartCommunity answers a resident's questions about the place they
          live, out of that association's own documents, and names the document
          and the section every answer came from. It does nothing else. It does
          not book a tradesperson, take a payment, or issue a parking pass, and
          the reason it does not is the subject of section 8.
        </p>
        <p>
          It began as a floating panel inside the Service Assistant. It is now
          its own application, on its own machine, with its own database and its
          own address, and this document specifies it as that. Section 6 says
          what is still shared and what is not.
        </p>
        <p>
          The qualities this system is judged on are
          <strong>grounding, scoping, fallback, latency, security and
          observability</strong>. Grounding and scoping come first, and that
          ordering is deliberate: an assistant that answers a rules question
          wrongly is worse than one that declines, because a resident will act
          on it.
        </p>
      </section>

      <section id="s2">
        <h2 class="sec"><span class="n">2</span>The system in one picture</h2>
        <p>
          One path, with one place where it can branch. Retrieval happens before
          any engine is called, and it is scoped to one association before it
          ranks anything. If nothing in that association's documents clears the
          threshold, no engine is called at all: there is nothing for it to
          ground an answer in, and asking it anyway is asking it to invent.
        </p>
        <div class="figure">
          <div class="scroller">{DIAGRAM}</div>
          <p class="figcap">
            Fig. 1 &middot; a question, and the only two things that can happen to it
          </p>
        </div>
        <div class="callout">
          <p>
            The refusal path is not an error path. It is the second of the two
            correct outcomes, and it is drawn differently on screen from an
            answer because the difference is real.
          </p>
        </div>
      </section>

      <section id="s3">
        <h2 class="sec"><span class="n">3</span>Who uses it</h2>
        <table class="spec">
          <thead><tr><th>Who</th><th>What they come for</th><th>Signed in?</th></tr></thead>
          <tbody>
            <tr>
              <td>A resident</td>
              <td>One question about a rule, a fee, a date, or a form. Usually
                  once, usually on a phone, usually not in the mood to read a
                  90 page PDF.</td>
              <td>No</td>
            </tr>
            <tr>
              <td>A resident with an account</td>
              <td>The same, with their association remembered across visits.</td>
              <td>Yes</td>
            </tr>
            <tr>
              <td>The management office</td>
              <td>Adding a document, replacing one, seeing what each association
                  currently holds, and choosing which engine words the answers.</td>
              <td>Admin token</td>
            </tr>
          </tbody>
        </table>
        <p>
          There is no provider role and no office staff role beyond the admin
          token. Both exist on the Service Assistant and neither was carried
          across, because neither has anything to do with reading a rule.
        </p>
      </section>

      <section id="s4">
        <h2 class="sec"><span class="n">4</span>What it does</h2>

        <h3 class="sub">Asking</h3>
{reqs([
  ("F-1", "Accept a question in ordinary language, typed or spoken, and answer it "
          "from the asking resident's association's documents."),
  ("F-2", "Name the document and the section behind every answer, and offer both "
          "ways into it: opening it to read, and saving it."),
  ("F-3", "Where the documents contradict each other, say so and quote both, "
          "rather than silently picking one. The quiet hours question does this "
          "today: Rule 2 and Rule 18 disagree, and the answer says they disagree."),
  ("F-4", "Where nothing in the documents covers the question, say so, name what "
          "the documents do cover, and call no engine."),
  ("F-5", "Ask which association the resident belongs to when it is not known, "
          "remember the answer across visits, and let it be changed in one tap "
          "from beside any answer."),
])}

        <h3 class="sub">Asking out loud</h3>
{reqs([
  ("F-6", "Hold a spoken conversation: listen, answer aloud, and listen again "
          "until it is stopped. One microphone permission for the whole "
          "conversation, not one per question."),
  ("F-7", "Show what was heard as the resident's own turn. A misheard question "
          "is a common failure and otherwise an invisible one."),
  ("F-8", "Speak the short form of an answer, not the long one. A list of seven "
          "documents is useful to read and unbearable to hear."),
  ("F-9", "Where speech synthesis is unavailable, fall back to the browser's own "
          "voice rather than answering a spoken question in silence."),
])}

        <h3 class="sub">Documents</h3>
{reqs([
  ("F-10", "List everything the resident's association holds, alongside the "
           "conversation rather than behind a second navigation."),
  ("F-11", "Serve any document two ways: inline, for checking one line, and as a "
           "download, for a form somebody has to fill in."),
  ("F-12", "Say on the card when a document cannot be quoted from. Several are "
           "scans with no readable text, and somebody who saves a site map and "
           "then asks a question about it should not learn this from a refusal."),
])}

        <h3 class="sub">The office</h3>
{reqs([
  ("F-13", "Upload a document against an association, and have it answerable "
           "without a restart."),
  ("F-14", "Report what each association currently holds and how much of it is "
           "indexed."),
  ("F-15", "Choose which engine words the answers. It reports the hardware's "
           "state and never changes it: starting and stopping the GPU belongs to "
           "exactly one panel, and it is not this one."),
])}
      </section>

      <section id="s5">
        <h2 class="sec"><span class="n">5</span>How it must behave</h2>

        <h3 class="sub" id="s51"><span class="n">5.1</span>Grounding and refusal</h3>
        <p>
          Every sentence of every answer is required to come from a passage that
          retrieval returned. The engine is given those passages and told to use
          nothing else; it is never asked what it knows.
        </p>
        <table class="spec">
          <thead><tr><th>Requirement</th><th>Value</th><th>Measured or target</th></tr></thead>
          <tbody>
            <tr><td>Retrieval threshold</td><td class="num">0.30 cosine</td><td>Measured, in the code</td></tr>
            <tr><td>Below threshold</td><td>No engine call at all</td><td>Measured</td></tr>
            <tr><td>Answer without a citation</td><td class="num">0</td><td>Required</td></tr>
          </tbody>
        </table>
        <div class="callout">
          <p>
            The threshold is doing real work rather than decorating. An
            unanswerable question costs nothing and reveals nothing, because the
            question never leaves the machine.
          </p>
        </div>

        <h3 class="sub" id="s52"><span class="n">5.2</span>Community scoping</h3>
        <p>
          Scoping is applied before ranking, not after. The candidate set is
          narrowed to one association's passages and the search runs over that
          slice, so a passage belonging to a neighbouring association cannot
          place first and then be filtered out: it is never a candidate.
        </p>
        <table class="spec">
          <thead><tr><th>Fact</th><th>Value</th></tr></thead>
          <tbody>
            <tr><td>Associations</td><td class="num">6</td></tr>
            <tr><td>Documents</td><td class="num">20</td></tr>
            <tr><td>Indexed passages</td><td class="num">209</td></tr>
            <tr><td>Embedding model</td><td>all-MiniLM-L6-v2, 384 dimensions</td></tr>
          </tbody>
        </table>
        <p>
          The associations are not evenly stocked, and the specification has to
          admit it: Serenity Point has 98 passages and Lauderdale Lakes 92, while
          Kendall Square, Valencia and Enclave at Old Cutler have one each. Those
          three can be searched and can be downloaded from, and a rules question
          asked against them will usually and correctly be refused. That is a
          content gap, not a defect, and it closes by uploading documents.
        </p>
        <p>
          Where an answer does come from another association, because a resident
          asked for it deliberately, the citation strip says so in the resident's
          own words. It must not say so when it is not true: comparing an
          internal key against a printed label made that warning fire on a
          resident's own association, which is a warning that gets believed. It
          now compares like with like.
        </p>

        <h3 class="sub" id="s53"><span class="n">5.3</span>Fallback</h3>
        <p>
          Two engines can word an answer: Gemini, and an open model on hardware
          we control. The switch chooses which is tried. Whichever answers, the
          passages it was given are the same, so the answer is grounded either
          way and the citations do not move.
        </p>
{reqs([
  ("N-1", "When the chosen engine does not answer, the other one answers, within "
          "the same request. The resident is not shown an error and is not asked "
          "to try again."),
  ("N-2", "The panel reports which engine actually answered, and says when that "
          "was not the one selected, and why."),
  ("N-3", "Retrieval never falls back to anything. If the documents do not cover "
          "it, both engines are equally not asked."),
])}
        <p>
          This is the property that was proved end to end on 30 August 2026,
          against a real model in the client's own AWS account: with the switch
          set to the open model and the machine stopped, a resident's question was
          answered correctly in 1.6 seconds by Gemini, and the panel reported the
          fallback and named the reason.
        </p>

        <h3 class="sub" id="s54"><span class="n">5.4</span>Latency and scale</h3>
        <table class="spec">
          <thead><tr><th>Stage</th><th>Time</th><th>Note</th></tr></thead>
          <tbody>
            <tr><td>Retrieval</td><td class="num">Single digit ms</td><td>209 vectors held in memory, one matrix multiply</td></tr>
            <tr><td>Refusal</td><td class="num">Retrieval only</td><td>No engine is called, so no network hop</td></tr>
            <tr><td>Answer, Gemini</td><td class="num">1 to 3 s</td><td>Measured</td></tr>
            <tr><td>Answer, open model on a CPU</td><td class="num">70 s</td><td>Measured, and the reason the timeout exists</td></tr>
            <tr><td>Engine timeout</td><td class="num">45 s</td><td>Then the other engine answers</td></tr>
          </tbody>
        </table>
        <p>
          The honest conformance note: this runs as one process on a machine with
          under 2GB of memory, and the embedding model is most of that. It is
          sized for one association's residents, not for a portfolio of them. The
          index is small enough that retrieval is not the constraint and will not
          become one at this scale; memory is the constraint, and the first thing
          that fixes it is a bigger machine rather than a change to this design.
        </p>

        <h3 class="sub" id="s55"><span class="n">5.5</span>Security</h3>
{reqs([
  ("N-4", "A resident's association scopes retrieval on the server. It is never "
          "taken from anything the browser could edit into a different answer."),
  ("N-5", "Office functions require an admin token. Without one, every one of "
          "them returns 401 rather than a partial answer."),
  ("N-6", "No question and no document leaves the machine unless an engine is "
          "called, and an engine is only called with the passages retrieval "
          "already selected."),
  ("N-7", "Where the open model is used, the port it listens on is reachable "
          "only from the three application addresses. It has no authentication "
          "of its own, so the network boundary is the whole of its protection "
          "and is treated that way."),
])}

        <h3 class="sub" id="s56"><span class="n">5.6</span>Observability</h3>
{reqs([
  ("N-8", "Every question is logged with the association it was scoped to and "
          "the time it took, so a slow answer can be attributed to a stage."),
  ("N-9", "The panel reports the index: how many passages, how many documents, "
          "per association. A document that was uploaded but not indexed is "
          "visible as a number rather than as a refusal in front of a resident."),
  ("N-10", "The panel reports what answered the last question, separately from "
           "what is switched on. Those are two different facts and conflating "
           "them hides every fallback."),
])}
      </section>

      <section id="s6">
        <h2 class="sec"><span class="n">6</span>Where it runs</h2>
        <table class="spec">
          <thead><tr><th>Part</th><th>What</th></tr></thead>
          <tbody>
            <tr><td>Address</td><td>livz.smartzees.com</td></tr>
            <tr><td>Application</td><td>FastAPI on port 8200, one process</td></tr>
            <tr><td>Screens</td><td>Next.js, exported as static files and served by nginx</td></tr>
            <tr><td>Database</td><td>Its own MySQL schema, on its own machine</td></tr>
            <tr><td>Index</td><td>209 passages, held in memory, rebuilt on upload</td></tr>
            <tr><td>Engines</td><td>Gemini, or the open model over the network</td></tr>
          </tbody>
        </table>
        <p>
          Port 8200 rather than 8100 is deliberate. This machine was cloned from
          the Service Assistant's, and a stray request meant for that product must
          not find something listening here and be answered by it.
        </p>
        <p>
          What is shared with the other two agents: the engine switch setting, and
          the hardware behind it. What is not shared: the database, the accounts,
          the sessions, the documents, the index, the process and the address. An
          outage of either of the other two agents does not reach this one.
        </p>
        <div class="callout">
          <p>
            One item is outstanding at the time of writing. Port 443 is not yet
            open in this machine's firewall, so the site is served over http. Two
            consequences follow and both are visible: the address bar says the
            connection is not private, and browsers will not hand out a
            microphone outside a secure context, so the spoken conversation
            cannot start. Both clear the moment the port is opened. Nothing in
            the application needs to change.
          </p>
        </div>
      </section>

      <section id="s7">
        <h2 class="sec"><span class="n">7</span>Assumptions and limits</h2>
{reqs([
  ("A-1", "The documents are the authority. Where they are wrong, out of date or "
          "silent, the answers are wrong, out of date or absent, and no amount of "
          "engine quality changes that."),
  ("A-2", "A scanned document with no readable text can be downloaded and cannot "
          "be quoted. The screen says which is which."),
  ("A-3", "English only. The retrieval model is an English model, and a question "
          "in another language will usually and correctly be refused rather than "
          "answered badly."),
  ("A-4", "One association per resident at a time. Asking as a different one is "
          "deliberate, one tap, and visibly labelled."),
  ("A-5", "Speech is best effort in both directions. A failed transcription asks "
          "the resident to repeat themselves and a failed voice hands the reply to "
          "the browser; neither takes the written answer away."),
])}
      </section>

      <section id="s8">
        <h2 class="sec"><span class="n">8</span>Out of scope</h2>
        <p>
          Named rather than left to be assumed, because every one of these exists
          on a sibling product and could reasonably be expected here.
        </p>
        <table class="spec">
          <thead><tr><th>Not here</th><th>Where it is</th><th>Why not here</th></tr></thead>
          <tbody>
            <tr><td>Booking a tradesperson</td><td>SmartService</td><td>A different job, a different diary, and a different set of people to pay</td></tr>
            <tr><td>Payments</td><td>SmartService, SmartMarket</td><td>Nothing here costs money</td></tr>
            <tr><td>Parking passes</td><td>SmartService</td><td>Kept with the product that already issues them, by decision, so one gate has one source of truth</td></tr>
            <tr><td>Provider accounts</td><td>SmartService</td><td>No tradesperson has a reason to sign in here</td></tr>
            <tr><td>Starting and stopping the GPU</td><td>SmartService</td><td>Two panels able to stop one card is a way to stop it mid answer</td></tr>
            <tr><td>Legal advice</td><td>Nowhere</td><td>It quotes the documents and names the section. Deciding what that means for a dispute is a person's job</td></tr>
          </tbody>
        </table>
      </section>
"""

html = page.render(
    title="SmartCommunity Specification",
    badge="Specification",
    h1="SmartCommunity",
    standfirst=(
        "What it answers, what it refuses, and how one association is never "
        "answered from another's rules. Written to be read by somebody who will "
        "not read the code."
    ),
    docmeta=[
        ("Document", "SRS-SC-1"),
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
