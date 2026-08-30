# Our own GPU, in plain words

The client's half. What running the AI on our own hardware means, what it costs,
and why forgetting to switch it off does not matter. No commands, no AWS, no
jargon.

Live at `servicez.smartzees.com/docs/our-own-gpu/`.

The technical half is `../gpu-setup/`, which is the one to send to whoever
builds it.

## Files

Same four as every other document set here: `source.md`, `render_diagrams.py`,
`render_pages.py`, `render_html.py`. The renderers are copies, not imports.

Two diagrams rather than the usual three, deliberately. This reader is not going
to build any of it, and only needs to hold on to two things: switching it on is
three steps, and forgetting to switch it off costs nothing.

## Rebuilding and deploying

```bash
python3 render_diagrams.py
python3 render_pages.py
python3 render_html.py
```

```bash
KEY=~/Downloads/sailagentecsdevkey.pem
rsync -az --delete -e "ssh -i $KEY" build/web/ ubuntu@35.91.251.211:/tmp/ourgpu-stage/
ssh -i $KEY ubuntu@35.91.251.211 \
  'sudo rsync -a --delete /tmp/ourgpu-stage/ /var/www/serviceagent-docs/our-own-gpu/ \
   && sudo chown -R www-data:www-data /var/www/serviceagent-docs'
```

## Rules

**No em or en dashes.** The client reads them as machine written.

Section 6 points at the interactive simulation. Keep that link current if the
simulation is ever republished at a different address.

## The simulation

`../gpu-simulation/index.html` is the working model referred to in section 6. It
is a single self-contained page: no build step, no network calls, and it runs
with the real machine switched off. That is on purpose, because a live
demonstration fails in exactly the room where it matters.
