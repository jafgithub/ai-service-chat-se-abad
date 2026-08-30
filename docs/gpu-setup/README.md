# Running the AI on our own GPU: setup

The technical half. Everything needed to create the GPU machine and wire it to
the Service Assistant, written to be followed by somebody who is not us.

Live at `servicez.smartzees.com/docs/gpu-setup/`.

The client's half of the same subject is `../our-own-gpu/`. That one has no
commands in it and does not mention AWS.

## Files

| | |
|---|---|
| `source.md` | The document. The only file to edit |
| `render_diagrams.py` | Three pictures, as inline SVG, written to `pages/` |
| `render_pages.py` | Photographs those pages into PNGs with headless Chrome |
| `render_html.py` | Turns `source.md` plus the PNGs into `build/web/index.html` |

The renderers are copied from `../community-rag/`, which is how every document
in this repository works. They are not imported from anywhere and are not kept
in sync automatically.

## Rebuilding

```bash
python3 render_diagrams.py
python3 render_pages.py
python3 render_html.py
```

`render_pages.py` needs `google-chrome` or `chromium` on the path, and Pillow.

## Deploying

```bash
KEY=~/Downloads/sailagentecsdevkey.pem
rsync -az --delete -e "ssh -i $KEY" build/web/ ubuntu@35.91.251.211:/tmp/gpusetup-stage/
ssh -i $KEY ubuntu@35.91.251.211 \
  'sudo rsync -a --delete /tmp/gpusetup-stage/ /var/www/serviceagent-docs/gpu-setup/ \
   && sudo chown -R www-data:www-data /var/www/serviceagent-docs'
```

`/docs/` is already served from that folder, and it sits outside the
application's own web root on purpose, so a frontend deploy cannot wipe it.

Both documents are listed in the hub at
`AI-Orders-main/docs/hub/documents.py`. Rebuild and redeploy the hub after
changing either title.

## Rules

**No em or en dashes.** The client reads them as machine written. Use a colon, a
comma, a full stop, or "to" for a range.

Check the masthead in `render_html.py` if you ever copy it somewhere else. Two
documents in this repository have shipped carrying another document's title,
because that block is the easiest thing in the world to forget.

## What is deliberately not here

The screenshots of the admin panel. Section 9 refers to it in words but shows a
drawing rather than a photograph, because the panel does not exist on the live
server until this milestone is deployed. Replace `g03_panel.png` with a real
capture once it does, in the same way `../community-rag/shots/` holds real
screenshots of the interface.
