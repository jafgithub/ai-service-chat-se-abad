# Service Agent: application spin-off and plumbing handover

Twelve sections. How the booking platform was built from the shop, what changed
between them file by file, the procedure for standing either one up on a new
machine, and the operational detail: verification, rollback, security notes.

**Live:** https://servicez.smartzees.com/docs/runbook/

Written for the client to work from himself, so every step is a command he can
paste, and every figure was taken from the live server rather than from memory.

## Editing it

`source.md` is the document. Edit that and rebuild.

**No em or en dashes.** The client reads them as machine written. Use a colon, a
comma, a full stop, or "to" for a range.

## Files

| File | What it is |
|---|---|
| `source.md` | The document text. This is the thing to edit. |
| `captures/*.txt` | Unedited console output from the live server. Re-run the command to refresh one. |
| `pages/*.html` | The captures dressed as terminal windows, and the diagrams. |
| `build/*.png` | Those pages photographed, plus the app screenshot. |
| `render_terminals.py` | Captures into terminal windows. One highlighted line each. |
| `render_diagrams.py` | The seven diagrams, as inline SVG. |
| `render_pages.py` | Photographs `pages/` into `build/`. |
| `render_html.py` | The web version, into `build/web/`. Understands fenced code blocks. |

## Rebuilding

```bash
python3 render_pages.py          # -> build/t*.png   (then crop, see below)
python3 render_html.py           # -> build/web/
```

`render_pages.py` does not crop to content, so the images come out 2840x3200
with a large blank area. Crop them before rendering the HTML:

```python
from PIL import Image, ImageChops
from pathlib import Path
for p in sorted(Path("build").glob("t0*.png")):
    im = Image.open(p).convert("RGB")
    bg = Image.new("RGB", im.size, im.getpixel((im.width - 2, im.height - 2)))
    box = ImageChops.difference(im, bg).getbbox()
    if box:
        pad = 24
        im.crop((max(0, box[0] - pad), max(0, box[1] - pad),
                 min(im.width, box[2] + pad), min(im.height, box[3] + pad))).save(p)
```

## Deploying

```bash
KEY=~/Downloads/sailagentecsdevkey.pem
rsync -az --delete -e "ssh -i $KEY" build/web/ ubuntu@52.25.174.57:/tmp/doc-stage/
ssh -i $KEY ubuntu@52.25.174.57 \
  'sudo rsync -a --delete /tmp/doc-stage/ /var/www/serviceagent-docs/runbook/ \
   && sudo chown -R www-data:www-data /var/www/serviceagent-docs'
```

Served from `/var/www/serviceagent-docs/`, deliberately outside the site root:
the frontend deploy rsyncs `/var/www/serviceagent/` with `--delete` and would
otherwise remove the documents.
