# Installing the open model, and wiring it to FastAPI

The software half of running the AI ourselves. `../gpu-setup/` is the AWS half:
quota, permissions, the instance, and keeping it from running up a bill. This
one is for somebody with a machine in front of them and a terminal open.

Live at `serviceagent.fordev.fun/docs/llm-fastapi/`.

## The section that earns its place

Section 9 runs the whole arrangement against Ollama on a laptop, with
`OLLAMA_URL` set and no AWS account involved at all. That is how the integration
gets checked before anybody spends eighty cents an hour, and it is the section
to point somebody at first.

Keep it accurate. If `OLLAMA_URL` ever stops being the manual override, that
section becomes wrong and the document stops being useful.

## Files

`source.md` is the only file to edit. `render_diagrams.py` writes two pictures
into `pages/`, `render_pages.py` photographs them with headless Chrome, and
`render_html.py` assembles `build/web/index.html`. The renderers are copies, not
imports, which is how every document set in this repository works.

```bash
python3 render_diagrams.py
python3 render_pages.py
python3 render_html.py
```

## Deploying

```bash
KEY=~/Downloads/sailagentecsdevkey.pem
rsync -az --delete -e "ssh -i $KEY" build/web/ ubuntu@35.91.251.211:/tmp/llmdoc-stage/
ssh -i $KEY ubuntu@35.91.251.211 \
  'sudo rsync -a --delete /tmp/llmdoc-stage/ /var/www/serviceagent-docs/llm-fastapi/ \
   && sudo chown -R www-data:www-data /var/www/serviceagent-docs'
```

## Rules

**No em or en dashes.** The client reads them as machine written.

Check the masthead in `render_html.py` if you copy it anywhere. The hub's README
records that two documents have already shipped carrying another document's
title, and this file was copied from `community-rag`.
