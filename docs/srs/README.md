# The Service Assistant: specification

A short SRS with a table of contents, ending in a live console that models the
system under load, under failure and under attack.

Live at `serviceagent.fordev.fun/docs/srs/`, deployed 29 August 2026.

`index.html` is the whole document. There is no `source.md` and no build step,
so the file in this directory is exactly the file on the server.

## Why this one is hand written

Every other document set here is generated: `source.md` plus
`render_diagrams.py`, `render_pages.py` and `render_html.py` produce a static
page with PNG diagrams. That pipeline cannot carry a running simulation, so
this is a single hand written `index.html` instead.

Everything else about it follows the house rules. Same palette as the generated
sets, no em or en dashes, and every measured number cited from the code rather
than invented.

## The one rule that matters

**The console is a model of the design, not a measurement of the server**, and
the page says so twice. Section 5.1 carries a conformance note stating where
production actually sits: one process, 1GB, at the top of its memory
allowance. An SRS specifies what is required, including what is not yet met.
Quietly demonstrating 150 concurrent residents without that note would be a
claim the deployment cannot back, and it is the kind of thing that gets found
out in a room.

If the deployment changes, update section 5.1 and A-3 together.

## The five, and where they live

The non-functional sections and the scenario buttons are the same list. If you
add a quality, it needs both a numbered `NFR` and a button, or the document and
the picture stop agreeing.

| Section | Button |
|---|---|
| 5.1 Scalability | A hundred at once |
| 5.2 Fallback | The GPU dies, and Both engines slow |
| 5.3 Availability | watch dropped and uptime, throughout |
| 5.4 Security | Someone probes it |
| 5.5 Observability | the console itself |

## Two things worth knowing before editing the simulation

**The model runs on an interval, the animation on frames.** Browsers throttle
`requestAnimationFrame` hard for anything they treat as offscreen, including an
embedded viewer. The first version drove the model from frames and ran at about
a sixteenth speed in the artifact viewer while every counter quietly lied. Keep
`step()` on its `setInterval` and leave only `movePips()` on frames.

**The breaker restarts its cooldown when a probe is taken.** Without that, a
failed probe leaves the original trip time in place, the cooldown has already
elapsed, and it probes again on the very next tick.

## Rebuilding and deploying

There is no build step. Edit `index.html` and deploy it.

```bash
KEY=~/Downloads/sailagentecsdevkey.pem
ssh -i $KEY ubuntu@35.91.251.211 'mkdir -p /tmp/srs-stage'
rsync -az -e "ssh -i $KEY" index.html ubuntu@35.91.251.211:/tmp/srs-stage/
ssh -i $KEY ubuntu@35.91.251.211 \
  'sudo rsync -a --delete /tmp/srs-stage/ /var/www/serviceagent-docs/srs/ \
   && sudo chown -R www-data:www-data /var/www/serviceagent-docs'
```

Listed in the hub at `AI-Orders-main/docs/hub/documents.py` under `SERVICE`.

## Checking it still works

Open it, jump to section 8, and press each scenario. The two numbers that must
hold through every one of them are **requests dropped**, which stays at 0, and
**uptime**, which stays at 100%. Those two are the claim the whole document
rests on.

Push the residents slider past 400 to see the queue build and load actually
shed. That limit is deliberate: a simulation that scales forever is not
credible, and NFR-2 requires shedding to be visible rather than silent.
