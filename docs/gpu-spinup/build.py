"""Spinning up a GPU and wiring it to FastAPI, step by step.

There are already two documents about the GPU. `our-own-gpu` argues why, in
plain words, and `gpu-setup` explains the machine with the reasoning and the
screenshots. Neither is the thing somebody at a keyboard actually wants, which
is one ordered list that starts at nothing and ends with a resident's question
answered by our own model.

This is that list, and it is written from a real attempt rather than from the
plan: everything below either worked on 30 August 2026 or is recorded as the
reason it did not.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "_house"))
import page  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent

TOC = [
    ("s0", "0", "Before you start", ()),
    ("s1", "1", "Clear the two things that block everything", ()),
    ("s2", "2", "Make the machine", ()),
    ("s3", "3", "Shut the door", ()),
    ("s4", "4", "Install the model", ()),
    ("s5", "5", "Make it switch itself off", ()),
    ("s6", "6", "Wire it to FastAPI", ()),
    ("s7", "7", "Prove it, in five checks", ()),
    ("s8", "8", "When it goes wrong", ()),
    ("s9", "9", "What it costs", ()),
]


def steps(items):
    """A numbered run of instructions, each with a why."""
    out = []
    for n, (head, detail) in enumerate(items, 1):
        out.append(
            '          <li><span class="id">{n}</span><span class="txt">'
            '<strong>{head}</strong><br>{detail}</span></li>'.format(n=n, head=head, detail=detail)
        )
    return '        <ul class="reqs">\n' + "\n".join(out) + "\n        </ul>"


def code(text):
    return f'<pre class="code"><code>{text}</code></pre>'


BODY = f"""
      <section id="s0">
        <h2 class="sec"><span class="n">0</span>Before you start</h2>
        <p class="lede">
          This takes you from an AWS account with nothing in it to a resident's
          question answered by a model on hardware we control, with the
          application falling back to Gemini whenever that hardware is off. It
          is one ordered list. Follow it top to bottom.
        </p>
        <p>
          Every step below was carried out for real in the client's own account
          on 30 August 2026. Where something failed, the failure is written down
          here rather than smoothed over, because two of them will happen to
          anybody who repeats this.
        </p>
        <div class="callout">
          <p>
            The single most important sentence in this document:
            <strong>Ollama has no authentication of any kind.</strong> Anything
            that can reach port 11434 can use the model, read what is being asked
            and run the bill up. Section 3 is not optional and it is not last.
          </p>
        </div>
        <p>What you need in front of you:</p>
        <table class="spec">
          <thead><tr><th>Thing</th><th>Why</th></tr></thead>
          <tbody>
            <tr><td>An AWS account on a paid plan</td><td>Section 1 explains why the Free Tier plan blocks this outright</td></tr>
            <tr><td>An access key with EC2 rights</td><td>To make the machine and, later, to start and stop it</td></tr>
            <tr><td>The public addresses of the application machines</td><td>They are the only addresses allowed near the model</td></tr>
            <tr><td>Python with boto3</td><td>The scripts under <span class="mono">deploy/gpu/</span> use it</td></tr>
          </tbody>
        </table>
      </section>

      <section id="s1">
        <h2 class="sec"><span class="n">1</span>Clear the two things that block everything</h2>
        <p>
          Both of these are account level, both take time, and neither can be
          worked around by anybody except the account owner. Start them first and
          do the rest while they clear.
        </p>

        <h3 class="sub">The Free Tier plan</h3>
        <p>
          A new AWS account is on the Free Tier <em>plan</em>, which is not the
          same thing as the free tier allowance. On that plan, launching anything
          outside a small list of types is refused outright:
        </p>
        {code("InvalidParameterCombination: The specified instance type is not\neligible for Free Tier.")}
        <p>
          On the account this was tried in, the only launchable types were
          <span class="mono">t3.micro</span>, <span class="mono">t3.small</span>,
          <span class="mono">t4g.micro</span>, <span class="mono">t4g.small</span>,
          <span class="mono">c7i-flex.large</span> and
          <span class="mono">m7i-flex.large</span>. No GPU type is on that list,
          so no quota increase can help until the account is moved to a paid plan
          in Billing. This surprises people because the error names the instance
          type, and the instance type is not the problem.
        </p>

        <h3 class="sub">The G quota</h3>
        <p>
          Separately, a new account has a quota of <strong>0</strong> running
          on-demand G instances. A <span class="mono">g6.xlarge</span> needs
          <strong>4</strong> vCPUs of it. Request the increase in Service Quotas,
          in the region you will actually use, against "Running On-Demand G and
          VT instances". Approval is usually hours and can be two days.
        </p>
        {code("$ .venv/bin/python deploy/gpu/quota.py\n  current   0\n  requested 4\n  status    PENDING")}
        <div class="callout">
          <p>
            Both must clear. Clearing one and not the other looks identical from
            the command line, which is why they are listed as two steps rather
            than one.
          </p>
        </div>
      </section>

      <section id="s2">
        <h2 class="sec"><span class="n">2</span>Make the machine</h2>
{steps([
  ("Pick the AMI",
   "Deep Learning Base OSS Nvidia Driver GPU AMI, Ubuntu 22.04. It brings the "
   "NVIDIA driver with it, which is the part that is tedious to install by hand."),
  ("Pick the type",
   "<span class='mono'>g6.xlarge</span>. One L4, which is the smallest card that "
   "answers a retrieval prompt in a few seconds rather than a few minutes."),
  ("100GB of gp3 storage",
   "The model, the driver and the AMI together do not fit comfortably in less."),
  ("Set shutdown behaviour to <em>stop</em>, not terminate",
   "This is the one setting that is unrecoverable if it is wrong. The machine "
   "shuts itself down when it is idle, and with terminate set, the idle timer "
   "deletes it."),
  ("Tag it <span class='mono'>AutoStop = true</span>",
   "The safety net in section 5 finds the machine by this tag rather than by an "
   "id written into it."),
  ("Paste the user data",
   "<span class='mono'>deploy/gpu/userdata.sh</span>. It installs Ollama, pulls "
   "the model and installs the idle timer, unattended."),
])}
        <p>
          It does not have to be in the same account as the applications, and in
          this case it is not: the applications live in one account and the GPU in
          another. That rules out private networking between them, so the model is
          reached over the public internet and the firewall in section 3 is the
          only thing in front of it.
        </p>
      </section>

      <section id="s3">
        <h2 class="sec"><span class="n">3</span>Shut the door</h2>
        <p>
          Before the model is installed, not after. A machine with Ollama running
          and an open 11434 is a free GPU for whoever scans for it, and they scan
          continuously.
        </p>
        <table class="spec">
          <thead><tr><th>Port</th><th>From</th><th>Never</th></tr></thead>
          <tbody>
            <tr><td class="mono">11434</td><td>The application addresses, as /32</td><td class="mono">0.0.0.0/0</td></tr>
            <tr><td class="mono">22</td><td>Your own address, as /32</td><td class="mono">0.0.0.0/0</td></tr>
            <tr><td>Anything else</td><td>Nobody</td><td>Ever</td></tr>
          </tbody>
        </table>
        {code("security group  sg-06ad9397831595b43   ollama-gpu\n  11434  from 35.91.251.211/32, 54.188.207.85/32, 54.254.25.0/32\n  22     from the operator's own address\n  and nothing else")}
        <p>
          Three addresses because there are three agents and each one asks the
          model directly. Adding a fourth agent means adding a fourth rule, which
          is a small piece of friction worth keeping.
        </p>
      </section>

      <section id="s4">
        <h2 class="sec"><span class="n">4</span>Install the model</h2>
        <p>
          If the user data ran, this is already done and the check at the end of
          the section confirms it. By hand:
        </p>
        {code("curl -fsSL https://ollama.com/install.sh | sh\nsystemctl enable --now ollama")}
        <p>
          Then pull the model <strong>through the HTTP API</strong>, not through
          the command line:
        </p>
        {code('curl -s http://127.0.0.1:11434/api/pull \\\n  -d \'{"name": "llama3.1:8b"}\'')}
        <div class="callout">
          <p>
            This is the bug that cost an afternoon. Running
            <span class="mono">ollama pull</span> from cloud-init dies with
            <span class="mono">panic: $HOME is not defined</span>: the CLI reads
            <span class="mono">$HOME</span> to find its model directory and
            cloud-init has none. The first unattended build finished with Ollama
            running and no model in it, which from the outside is
            indistinguishable from a download that failed. The HTTP API has no
            such dependency. The idle check in section 5 had the same problem and
            was moved to the API for the same reason.
          </p>
        </div>
        <p>The model must be the one the application is configured for:</p>
        {code("$ curl -s localhost:11434/api/tags\n{\"models\":[{\"name\":\"llama3.1:8b\", ...}]}")}
      </section>

      <section id="s5">
        <h2 class="sec"><span class="n">5</span>Make it switch itself off</h2>
        <p>
          Two mechanisms, because they fail differently. This is the whole
          difference between roughly $580 a month and roughly $8.
        </p>
        <table class="spec">
          <thead><tr><th></th><th>Timer on the machine</th><th>Lambda outside it</th></tr></thead>
          <tbody>
            <tr><td>Knows when the last question was</td><td>Yes, from Ollama's journal</td><td>No, only CPU</td></tr>
            <tr><td>Survives the machine wedging</td><td><strong>No</strong></td><td><strong>Yes</strong></td></tr>
            <tr><td>Fires at</td><td>20 idle minutes</td><td>45 minutes running under 5% CPU</td></tr>
          </tbody>
        </table>
        <p>
          The on-box timer does the day to day work and is precise. The Lambda
          catches the machine that has hung, or that somebody started from the
          console and forgot, and that is the failure that actually costs money,
          because a timer on a hung machine does not run.
        </p>
        {code("systemctl list-timers ollama-idle-off.timer\nsudo /usr/local/bin/ollama-idle-off.sh   # says why it is or is not stopping")}
      </section>

      <section id="s6">
        <h2 class="sec"><span class="n">6</span>Wire it to FastAPI</h2>
        <p>
          Four modules, and they are deliberately small. Nothing else in the
          application knows a GPU exists.
        </p>
        <table class="spec">
          <thead><tr><th>Module</th><th>Its one job</th></tr></thead>
          <tbody>
            <tr><td class="mono">ai_runtime</td><td>Which engine is switched on. A file, not a database row, so it survives a restart and is readable by eye</td></tr>
            <tr><td class="mono">gpu_instance</td><td>Where the machine is and whether it is answering. Starts and stops it</td></tr>
            <tr><td class="mono">ollama_service</td><td>Talks to the model</td></tr>
            <tr><td class="mono">llm</td><td>The router. Everything that wants a sentence written asks this and nothing else</td></tr>
          </tbody>
        </table>
        <p>The routing is three lines and the third one is the design:</p>
        {code("switch says gemini                     -> Gemini\nswitch says gpu, and the GPU is ready  -> Ollama, on our own hardware\nswitch says gpu, and it is not         -> Gemini, and the panel says so")}
        <p>
          A resident does not care whose hardware answered and must never see a
          broken assistant because a machine was still booting. What matters is
          that the panel tells the truth, so nobody demonstrates "our own GPU" to
          a room while Gemini is quietly doing the work. The panel therefore
          reports two separate facts: what is switched on, and what actually
          answered the last question.
        </p>

        <h3 class="sub">Two ways to point at the model</h3>
        <p>
          <strong>By instance id</strong>, which is the normal one. The public
          address changes every time the machine stops and starts, so it is read
          from the AWS API rather than written down:
        </p>
        {code("GPU_INSTANCE_ID=i-...\nAWS_REGION=us-west-2\nAWS_ACCESS_KEY_ID=...\nAWS_SECRET_ACCESS_KEY=...")}
        <p>
          <strong>By hand</strong>, which is for a model at a fixed address, such
          as one on a tunnel or a laptop:
        </p>
        {code("OLLAMA_URL=http://10.8.0.1:11434")}
        <div class="callout">
          <p>
            <span class="mono">OLLAMA_URL</span> did not work until 30 August
            2026. The readiness check returned "not configured" whenever AWS
            credentials were absent, so a perfectly good model at a hand written
            address was never asked, and every question quietly went to Gemini.
            Both the state and the health check now short-circuit on
            <span class="mono">OLLAMA_URL</span> before they look at AWS at all,
            with four tests holding it there.
          </p>
        </div>
        <p>Set one or the other, never both. Then restart the application.</p>
      </section>

      <section id="s7">
        <h2 class="sec"><span class="n">7</span>Prove it, in five checks</h2>
        <p>
          In this order. Each one can fail on its own and each failure means
          something different.
        </p>
{steps([
  ("The firewall is real",
   "From a machine that is not one of the three, <span class='mono'>curl</span> "
   "port 11434 and get nothing. From each of the three, get an answer. Assumed "
   "boundaries are not boundaries."),
  ("The model generates",
   "A trivial prompt, straight to the model, timed. On a CPU-only stand-in this "
   "took 19 seconds, which is the number that told us the card mattered."),
  ("A real question, answered by our model",
   "Switch the panel to the GPU and ask a resident's question. It must come back "
   "grounded and cited, with the panel saying <span class='mono'>served_by: gpu</span> "
   "and <span class='mono'>fell_back: false</span>."),
  ("The timeout does what it should",
   "On the CPU stand-in the first three questions exceeded the 45 second timeout "
   "and fell back to Gemini with <em>The GPU stopped answering mid-question</em>. "
   "Three residents got correct answers and the panel said who wrote them. That "
   "is the design working, not a fault, and 45 seconds stays because an L4 "
   "answers in a few."),
  ("Stop the machine and ask again",
   "The one that matters, because it is what happens in front of a client when "
   "somebody forgets to press start. Measured: a correct answer in 1.6 seconds "
   "from Gemini, with the panel reporting the fallback and naming the reason."),
])}
      </section>

      <section id="s8">
        <h2 class="sec"><span class="n">8</span>When it goes wrong</h2>
        <table class="spec">
          <thead><tr><th>What you see</th><th>What it is</th></tr></thead>
          <tbody>
            <tr><td>Launch refused, naming the instance type</td><td>Almost certainly the Free Tier plan, not the type and not the quota. Section 1</td></tr>
            <tr><td>Ollama running, no model in it</td><td>The <span class="mono">$HOME</span> panic in cloud-init. Pull through the HTTP API. Section 4</td></tr>
            <tr><td>Everything answered by Gemini, no error anywhere</td><td>The application does not think the GPU is ready. Check the switch, then the health check, then the firewall from the application machine itself</td></tr>
            <tr><td>Answers time out then arrive from Gemini</td><td>Working as designed. If it happens on a real GPU rather than a stand-in, the model is too big for the card</td></tr>
            <tr><td>The machine is gone rather than stopped</td><td>Shutdown behaviour was left at terminate. It cannot be undone. Section 2</td></tr>
            <tr><td>A bill nobody expected</td><td>A machine started from the console and forgotten, with the timer wedged. That is what the Lambda is for. Section 5</td></tr>
          </tbody>
        </table>
      </section>

      <section id="s9">
        <h2 class="sec"><span class="n">9</span>What it costs</h2>
        <table class="spec">
          <thead><tr><th>State</th><th>Roughly</th></tr></thead>
          <tbody>
            <tr><td>Running</td><td class="num">$0.80 an hour</td></tr>
            <tr><td>Stopped</td><td class="num">$8 a month, for the disk</td></tr>
            <tr><td>Left running all month</td><td class="num">$580</td></tr>
          </tbody>
        </table>
        <p>
          The entire gap between the second row and the third is the auto-off,
          which is why it has two mechanisms rather than one. Compute is not
          billed while an instance is stopped; the volume is, whether it runs or
          not.
        </p>
      </section>
"""

html = page.render(
    title="Spinning Up a GPU",
    badge="Step by step",
    h1="Spinning up a GPU, and wiring it to FastAPI",
    standfirst=(
        "From an empty AWS account to a resident's question answered by our own "
        "model, in nine steps. Written from a real attempt, including the two "
        "things that stopped it."
    ),
    docmeta=[
        ("Document", "OPS-GPU-1"),
        ("Version", "1.0"),
        ("Date", "31 August 2026"),
        ("Status", "Current"),
        ("Author", "Abad Naseer"),
    ],
    toc=TOC,
    body=BODY,
)

out = HERE / "index.html"
out.write_text(html)
print(f"wrote {out} ({len(html):,} bytes)")
