"""Deployment and handover: where everything lives, and how it gets there.

Written to be followed by somebody who did not build any of it. Every path,
unit name and command in here was read off the running machines rather than
remembered, on 1 September 2026.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "_house"))
import page  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent

TOC = [
    ("s1", "1", "The map", ()),
    ("s2", "2", "The four repositories", ()),
    ("s3", "3", "Deploying each one", (
        ("s31", "3.1", "SmartService", ()),
        ("s32", "3.2", "SmartMarket", ()),
        ("s33", "3.3", "SmartCommunity", ()),
        ("s34", "3.4", "The landing page", ()),
        ("s35", "3.5", "The documents", ()),
    )),
    ("s4", "4", "What the code files do", ()),
    ("s5", "5", "The model, and the switch", ()),
    ("s6", "6", "Rules that are not optional", ()),
    ("s7", "7", "Checking a deploy worked", ()),
    ("s8", "8", "Leftovers on the machines", ()),
]


def code(text):
    return f'<pre class="code"><code>{text}</code></pre>'


def rows(header, data):
    head = "".join(f"<th>{h}</th>" for h in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in data
    )
    return f'<table class="spec"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


BODY = f"""
      <section id="s1">
        <h2 class="sec"><span class="n">1</span>The map</h2>
        <p class="lede">
          Three products, four repositories, four machines. Everything below was
          read off the running systems rather than remembered, so where this
          document and your memory disagree, believe this document and then
          check the machine.
        </p>
        {rows(["What", "Address", "Machine", "Region"], [
          ["SmartMarket", "marketz.smartzees.com", "54.254.25.0", "ap-southeast-1"],
          ["SmartService", "servicez.smartzees.com", "35.91.251.211", "us-west-2"],
          ["SmartCommunity", "livz.smartzees.com", "54.188.207.85", "us-west-2"],
          ["The landing page", "smartzees.com", "35.91.251.211", "shares the Service box"],
          ["The documents", "servicez.smartzees.com/docs/", "35.91.251.211", "and mirrored on Market"],
          ["The open model", "184.34.122.122", "i-0c9e7a485d54e4e92", "us-west-2, another AWS account"],
        ])}
        <div class="callout">
          <p>
            The three application machines are Lightsail, in AWS account
            952427475294. The model is plain EC2 in the client's own account,
            253918336085. That is why it is reached over the public internet and
            why a security group, not a private network, is the only thing in
            front of it.
          </p>
        </div>
        <p>Getting in:</p>
        {code("ssh -i ~/Downloads/sailagentecsdevkey.pem ubuntu@35.91.251.211   # Service, landing, docs\nssh -i ~/Downloads/sailagentecsdevkey.pem ubuntu@54.254.25.0    # Market\nssh -i ~/Downloads/sailagentecsdevkey.pem ubuntu@54.188.207.85  # Community")}
        <p>
          The model machine has its own key and is normally reached from the AWS
          console instead, through EC2 Instance Connect, so nobody has to be
          sent a private key.
        </p>
      </section>

      <section id="s2">
        <h2 class="sec"><span class="n">2</span>The four repositories</h2>
        {rows(["Local folder", "Remote", "Branch", "Product"], [
          ["<span class='mono'>plumber-assistant</span>", "jafgithub/ai-service-chat-se-abad", "master", "SmartService"],
          ["<span class='mono'>AI-Orders-main</span>", "jafgithub/aichat-v2-abad", "main", "SmartMarket"],
          ["<span class='mono'>community-assistant</span>", "AbadNaseer/ai-agent-smartcommunity", "master", "SmartCommunity"],
          ["<span class='mono'>smartzees-landing</span>", "AbadNaseer/ai-agent-landingpage-smartzees", "master", "smartzees.com"],
        ])}
        <p>
          The last two are staged under a personal account because write access
          on the organisation copies has not been granted yet. When it is, the
          remote changes and nothing else does.
        </p>
        <p>
          Each repository has the same shape: <span class="mono">backend/</span>
          is FastAPI, <span class="mono">frontend/</span> is Next.js exported to
          static files, and <span class="mono">docs/</span> holds the written
          documents. The landing page has only a frontend.
        </p>
        <p>
          Node is not on the system path on the build machine. Every frontend
          command below needs this first:
        </p>
        {code('export PATH="$HOME/.local/node/bin:$PATH"')}
      </section>

      <section id="s3">
        <h2 class="sec"><span class="n">3</span>Deploying each one</h2>
        <p>
          The pattern is the same everywhere and it is deliberate. Build locally,
          rsync to a staging directory in the deploy user's home, then move it
          into place with sudo. Never build on the server: these machines have
          under 2GB of memory and a Next.js build will take one down.
        </p>

        <h3 class="sub" id="s31"><span class="n">3.1</span>SmartService</h3>
        <p><strong>Backend</strong>, at <span class="mono">/home/ubuntu/plumber/backend</span>, unit <span class="mono">plumber</span>, port 8100.</p>
        {code("rsync -az --exclude '__pycache__' --exclude '.venv' --exclude '.env' \\\n  plumber-assistant/backend/app/ ubuntu@35.91.251.211:/home/ubuntu/plumber/backend/app/\nssh ubuntu@35.91.251.211 'sudo systemctl restart plumber'")}
        <p><strong>Frontend</strong>, served from <span class="mono">/var/www/serviceagent</span>.</p>
        {code("cd plumber-assistant/frontend && npm run build:serviceagent\nrsync -az --delete out/ ubuntu@35.91.251.211:/home/ubuntu/deploy-serviceagent/\nssh ubuntu@35.91.251.211 \\\n  'sudo rsync -a --delete /home/ubuntu/deploy-serviceagent/ /var/www/serviceagent/'")}
        <p>
          <span class="mono">build:serviceagent</span> rather than
          <span class="mono">build</span>: it sets an empty base path and an
          empty API url, because the app sits at the root of its own subdomain
          and the API is same origin.
        </p>

        <h3 class="sub" id="s32"><span class="n">3.2</span>SmartMarket</h3>
        <p><strong>Backend</strong>, at <span class="mono">/var/www/ai-order/backend</span>, unit <span class="mono">aiorder</span>.</p>
        {code("rsync -az --exclude '__pycache__' --exclude '.env' \\\n  AI-Orders-main/backend/app/ ubuntu@54.254.25.0:/home/ubuntu/deploy-market-app/\nssh ubuntu@54.254.25.0 \\\n  'sudo rsync -a /home/ubuntu/deploy-market-app/ /var/www/ai-order/backend/app/ && sudo systemctl restart aiorder'")}
        <p><strong>Frontend</strong>, served from <span class="mono">/var/www/ai-order/frontend-dist</span>.</p>
        {code("cd AI-Orders-main/ai-order && npm run build:deploy\nrsync -az --delete out/ ubuntu@54.254.25.0:/home/ubuntu/deploy-market/\nssh ubuntu@54.254.25.0 \\\n  'sudo rsync -a --delete /home/ubuntu/deploy-market/ /var/www/ai-order/frontend-dist/'")}
        <div class="callout">
          <p>
            The web root is <span class="mono">frontend-dist</span>, not
            <span class="mono">frontend</span>. There is a
            <span class="mono">frontend</span> directory beside it that is not
            served. Deploying into it looks like a successful deploy that
            changes nothing, and it has cost an afternoon before.
          </p>
        </div>

        <h3 class="sub" id="s33"><span class="n">3.3</span>SmartCommunity</h3>
        <p><strong>Backend</strong>, at <span class="mono">/home/ubuntu/community/backend</span>, unit <span class="mono">community</span>, port 8200.</p>
        {code("rsync -az --exclude '__pycache__' --exclude '.venv' --exclude '.env' \\\n  community-assistant/backend/app/ ubuntu@54.188.207.85:/home/ubuntu/community/backend/app/\nssh ubuntu@54.188.207.85 'sudo systemctl restart community'")}
        <p><strong>Frontend</strong>, served from <span class="mono">/var/www/community</span>.</p>
        {code("cd community-assistant/frontend && npm run build\nrsync -az --delete out/ ubuntu@54.188.207.85:/home/ubuntu/deploy-community/\nssh ubuntu@54.188.207.85 \\\n  'sudo rsync -a --delete /home/ubuntu/deploy-community/ /var/www/community/ && sudo chown -R www-data:www-data /var/www/community'")}
        <p>
          Port 8200 rather than 8100 is deliberate. This machine was cloned from
          the Service Assistant, and a stray request meant for that product must
          not find something listening here and be answered by it.
        </p>

        <h3 class="sub" id="s34"><span class="n">3.4</span>The landing page</h3>
        <p>Static only, served from <span class="mono">/var/www/smartzees</span> on the Service machine.</p>
        {code("cd smartzees-landing/app && npm run build\nrsync -az --delete out/ ubuntu@35.91.251.211:/home/ubuntu/deploy-smartzees/\nssh ubuntu@35.91.251.211 \\\n  'sudo rsync -a --delete /home/ubuntu/deploy-smartzees/ /var/www/smartzees/'")}

        <h3 class="sub" id="s35"><span class="n">3.5</span>The documents</h3>
        <p>
          Served from <span class="mono">/var/www/serviceagent-docs</span>, which
          is outside the site root on purpose: the frontend deploy above uses
          <span class="mono">--delete</span> and would otherwise remove them.
        </p>
        {code("python3 docs/_house/hub.py            # rebuilds docs/index.html from its list\npython3 docs/deployment/build.py      # this document\nrsync -az docs/<name>/ ubuntu@35.91.251.211:/home/ubuntu/deploy-docs/<name>/\nssh ubuntu@35.91.251.211 \\\n  'sudo rsync -a /home/ubuntu/deploy-docs/ /var/www/serviceagent-docs/'")}
        <p>
          Generated document sets (<span class="mono">source.md</span> plus the
          <span class="mono">render_*.py</span> scripts) deploy their
          <span class="mono">build/web/</span> directory. Hand written ones
          (<span class="mono">srs</span>, <span class="mono">lab</span>,
          <span class="mono">deployment</span>, the two specifications) deploy the
          <span class="mono">index.html</span> beside the builder.
        </p>
      </section>

      <section id="s4">
        <h2 class="sec"><span class="n">4</span>What the code files do</h2>
        <p>
          Only the ones somebody unfamiliar would otherwise have to read to
          understand. The rest are named for what they do.
        </p>

        <h3 class="sub">Shared by all three products</h3>
        {rows(["File", "What it is for"], [
          ["<span class='mono'>services/llm.py</span> (Market: <span class='mono'>services/ai.py</span>)", "The router. Everything wanting a sentence written asks this, and it decides whether our own model or Gemini answers, and falls back when the first cannot"],
          ["<span class='mono'>services/gemini_service.py</span>", "Google's model. Also does speech to text and text to speech"],
          ["<span class='mono'>services/ollama_service.py</span>", "Our own model over HTTP"],
          ["<span class='mono'>services/tracing.py</span>", "Measures each stage of a request and keeps the last 50, which is what the live diagram reads"],
          ["<span class='mono'>api/ai_public.py</span>", "Two read only routes with no token: which engine is switched on, and the recent traces. No question or reply text ever appears here"],
          ["<span class='mono'>services/rag.py</span>", "The embedding model, all-MiniLM-L6-v2, 384 dimensions, loaded once"],
        ])}

        <h3 class="sub">SmartService only</h3>
        {rows(["File", "What it is for"], [
          ["<span class='mono'>services/ai_runtime.py</span>", "The engine switch itself, a small JSON file. This machine owns it for the whole platform"],
          ["<span class='mono'>services/gpu_instance.py</span>", "Finds, starts and stops the model machine. Needs boto3 and AWS keys"],
          ["<span class='mono'>api/ai_admin.py</span>", "The admin panel's engine controls, including start and stop"],
          ["<span class='mono'>services/conversation.py</span>", "Turns what somebody said into a search, a booking step or a parking request"],
          ["<span class='mono'>services/catalog_index.py</span>, <span class='mono'>phrase_index.py</span>", "The service catalogue, held in memory so a search is a matrix multiply"],
          ["<span class='mono'>services/parking.py</span>, <span class='mono'>api/parking.py</span>", "Visitor passes and the QR code the gate reads"],
          ["<span class='mono'>services/booking_service.py</span>, <span class='mono'>booking_emails.py</span>", "Appointments, and the confirmations that go with them"],
        ])}

        <h3 class="sub">SmartCommunity only</h3>
        {rows(["File", "What it is for"], [
          ["<span class='mono'>services/community_chat.py</span>", "The whole pipeline: scope to one association, retrieve, answer or refuse"],
          ["<span class='mono'>services/docs_index.py</span>", "209 passages in memory, and the 0.30 threshold under which no model is called at all"],
          ["<span class='mono'>services/doc_library.py</span>, <span class='mono'>doc_chunker.py</span>", "Which documents exist, and cutting a PDF into passages"],
          ["<span class='mono'>services/platform_switch.py</span>", "Reads the engine switch from SmartService. This agent never writes it"],
          ["<span class='mono'>api/documents.py</span>", "Upload, list, withdraw, download. The office screen talks to this"],
        ])}

        <h3 class="sub">SmartMarket only</h3>
        {rows(["File", "What it is for"], [
          ["<span class='mono'>services/catalog_index.py</span>", "About 25,600 products in memory. This is the 787x search improvement"],
          ["<span class='mono'>sync_to_remote.py</span>", "Drains <span class='mono'>sync_outbox</span> into the client's own database. See section 6"],
          ["<span class='mono'>services/shopping/</span>", "Sourcing items the shop does not stock, through a provider interface"],
          ["<span class='mono'>services/order_service.py</span>", "Totals, tax and tips. Tax is computed on the goods and the tip on the goods before tax"],
        ])}
      </section>

      <section id="s5">
        <h2 class="sec"><span class="n">5</span>The model, and the switch</h2>
        <p>
          One switch decides which engine answers, for all three products, and it
          lives on <span class="mono">servicez.smartzees.com/admin</span> under
          AI runtime. The other two read it over HTTP and never write it.
        </p>
        <p>Settings on the Service machine, in <span class="mono">.env</span>:</p>
        {code("GPU_INSTANCE_ID=i-0c9e7a485d54e4e92\nAWS_REGION=us-west-2\nAWS_ACCESS_KEY_ID=...\nAWS_SECRET_ACCESS_KEY=...\nOLLAMA_MODEL=llama3.2:3b\nOLLAMA_TIMEOUT_SECONDS=45")}
        <p>
          The other two only need <span class="mono">OLLAMA_URL</span> and
          <span class="mono">OLLAMA_MODEL</span>, because they never start or stop
          anything.
        </p>
        <div class="callout">
          <p>
            <span class="mono">OLLAMA_URL</span> and
            <span class="mono">GPU_INSTANCE_ID</span> are two different modes and
            the first one wins. Set both on the Service machine and the panel
            will show a healthy engine it cannot stop. It also needs
            <span class="mono">boto3</span> installed in its virtual environment,
            or every AWS call fails and the panel says the machine is unknown.
          </p>
        </div>
      </section>

      <section id="s6">
        <h2 class="sec"><span class="n">6</span>Rules that are not optional</h2>
        {rows(["Rule", "Why"], [
          ["<strong>Exactly one machine may run <span class='mono'>aiorder-sync</span></strong>, and it is 54.254.25.0. The same for <span class='mono'>plumber-sync</span> on 35.91.251.211.",
           "These push rows into the client's live database. Cloned machines come up with the sync running, and two machines writing the same rows has happened three times"],
          ["<strong>Stop <span class='mono'>aiorder-sync</span> before any test that creates a customer or an order.</strong>",
           "Test data reaches the client's production system otherwise. Start it again afterwards"],
          ["<strong>Never widen port 11434 beyond the three application addresses.</strong>",
           "Ollama has no authentication of any kind. The security group is the whole of its protection"],
          ["<strong>Never build on a server.</strong>",
           "Under 2GB of memory. A Next.js build will take the machine down"],
          ["<strong>The model machine's shutdown behaviour must stay <span class='mono'>stop</span>.</strong>",
           "It switches itself off when idle. Set to terminate, the idle timer deletes it"],
        ])}
        <p>Checking the first rule takes one command and belongs in every handover:</p>
        {code("for h in 35.91.251.211 54.254.25.0 54.188.207.85; do\n  echo -n \"$h \"\n  ssh ubuntu@$h 'systemctl is-active plumber-sync aiorder-sync | tr \"\\n\" \" \"'\n  echo\ndone")}
      </section>

      <section id="s7">
        <h2 class="sec"><span class="n">7</span>Checking a deploy worked</h2>
        <p>Not "it returned 200", which a stale page also does. Ask it something.</p>
        {code("curl -s -X POST https://servicez.smartzees.com/api/v1/chat \\\n  -H 'Content-Type: application/json' \\\n  -d '{{\"message\":\"my boiler is leaking\",\"session_id\":\"check\"}}'\n\ncurl -s -X POST https://marketz.smartzees.com/api/v1/chat \\\n  -H 'Content-Type: application/json' \\\n  -d '{{\"message\":\"milk\",\"session_id\":\"check\"}}'\n\ncurl -s -X POST https://livz.smartzees.com/api/v1/chat \\\n  -H 'Content-Type: application/json' \\\n  -d '{{\"message\":\"quiet hours\",\"session_id\":\"check\",\"community\":\"serenity\"}}'")}
        <p>
          A good answer from the third names a document. If it does not, the
          index did not load, whatever the status code said.
        </p>
        <p>And the platform switch, which the other two agents depend on:</p>
        {code("curl -s https://servicez.smartzees.com/api/v1/ai/provider")}
      </section>

      <section id="s8">
        <h2 class="sec"><span class="n">8</span>Leftovers on the machines</h2>
        <p>
          Written down because they look important and are not. Every one is a
          copy left behind when a machine was cloned.
        </p>
        {rows(["Machine", "Leftover", "Status"], [
          ["54.188.207.85", "<span class='mono'>/var/www/serviceagent</span>, <span class='mono'>/var/www/ai-order</span>", "Not served. From the clone this machine was made from"],
          ["54.254.25.0", "<span class='mono'>/var/www/plumber</span>, <span class='mono'>/var/www/plumber.prev</span>", "Not served"],
          ["35.91.251.211", "<span class='mono'>/var/www/ai-order</span>", "Serves the documents mirror only, not the shop"],
          ["Both app machines", "<span class='mono'>plumber_assistant</span> and <span class='mono'>ai_order</span> databases where the product does not run", "Unused. Left rather than dropped, because dropping a database to reclaim nothing is a bad trade"],
        ])}
        <p>
          None of these are served by nginx. If you are editing something and
          nothing changes, check you are on the right machine before you check
          anything else.
        </p>
      </section>
"""

html = page.render(
    title="Deployment and Handover",
    badge="Handover",
    h1="Deployment and handover",
    standfirst=(
        "Where every part of the platform lives, the command that puts it there, "
        "and what each piece of the code is for. Written to be followed by "
        "somebody who did not build it."
    ),
    docmeta=[
        ("Document", "OPS-DEP-1"),
        ("Version", "1.0"),
        ("Date", "1 September 2026"),
        ("Status", "Current"),
        ("Author", "Abad Naseer"),
    ],
    toc=TOC,
    body=BODY,
)

out = HERE / "index.html"
out.write_text(html)
print(f"wrote {out} ({len(html):,} bytes)")
