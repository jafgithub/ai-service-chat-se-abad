# Community documents: the technical reference

How the document assistant works end to end: the two front doors, the routing
gate in the booking chat, retrieval and grounding, community detection and
scoping, the Three Lakes OCR limitation, the contradictions, and the procedure
for adding a new community.

**Live:** https://servicez.smartzees.com/docs/community-rag/

Written for whoever works on this next, not for the client. The client facing
version of the same subject is `docs/adding-documents/`, which covers what to
send us and what happens to it.

## Editing it

`source.md` is the document. The table of contents is generated from its
headings by `render_html.py`, so sections are numbered in the source and never
listed twice.

**No em or en dashes.** The client reads them as machine written.

## Files

| File | What it is |
|---|---|
| `source.md` | The document text. This is the thing to edit. |
| `render_diagrams.py` | The three diagrams, as inline SVG. The wording lives in here. |
| `render_pages.py` | Photographs `pages/*.html` into `build/*.png` at 2x. |
| `render_html.py` | The web version, into `build/web/`. Generates the contents. |
| `shots/*.jpg` | Real screenshots, taken through a browser against the live server. |

## Rebuilding

```bash
python3 render_diagrams.py     # -> pages/d*.html
python3 render_pages.py        # -> build/d*.png
python3 render_html.py         # -> build/web/
```

Changing only the words in `source.md` needs just the last line.

The screenshots live in `shots/` as JPEG and are copied into `build/` as PNG,
because the builder looks for PNGs there:

```python
from PIL import Image
Image.open("shots/s01_threelakes.jpg").convert("RGB").save("build/s01_threelakes.png")
```

## Deploying

```bash
KEY=~/Downloads/sailagentecsdevkey.pem
rsync -az --delete -e "ssh -i $KEY" build/web/ ubuntu@35.91.251.211:/tmp/ragdoc-stage/
ssh -i $KEY ubuntu@35.91.251.211 \
  'sudo rsync -a --delete /tmp/ragdoc-stage/ /var/www/serviceagent-docs/community-rag/ \
   && sudo chown -R www-data:www-data /var/www/serviceagent-docs'
```

`/docs/` is an alias onto `/var/www/serviceagent-docs/`, deliberately outside
the site root, which the frontend deploy rsyncs with `--delete` and would
otherwise remove.
