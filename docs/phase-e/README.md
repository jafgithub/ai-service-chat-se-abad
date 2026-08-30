# Service Assistant: the booking platform

A walkthrough of the booking platform: what a customer does, what a provider
does, what it is built from, where it runs, and the result of every test.
Written to be shown to the client and to be edited by hand.

**Live:** https://marketz.smartzees.com/docs/phase-e/
**Word:** `build/Service_Assistant_Booking_Platform.docx`, also at
https://marketz.smartzees.com/docs/Service_Assistant_Booking_Platform.docx

## Editing it

`source.md` is the document. Edit that, then rebuild. Both outputs come from
that one file, so the Word version and the web version cannot describe different
things.

**No em or en dashes.** The build fails on one, because the client reads them as
machine written. Use a colon, a comma, a full stop, or "to" for a range.

## Files

| File | What it is |
|---|---|
| `source.md` | The document text. This is the thing to edit. |
| `shots/*.jpg` | The interface, photographed through a real browser while the flow was driven by hand. Nothing is mocked up. |
| `render_diagrams.py` | The six flow diagrams, as inline SVG. The wording lives in here. |
| `render_pages.py` | Photographs `pages/*.html` into `build/*.png` at 2x. |
| `render_html.py` | The web version, into `build/web/`. |
| `build_docx.py` | The Word version, reusing `build_docs.py` so every client document looks the same. |
| `build_docs.py` | The shared renderer, copied from the grocery repository so this one builds on its own. |

## Rebuilding

```bash
python3 render_diagrams.py       # -> pages/d*.html
python3 render_pages.py          # -> build/d*.png
uv venv .venv && uv pip install --python .venv/bin/python python-docx pillow
.venv/bin/python build_docx.py   # -> build/Service_Assistant_Booking_Platform.docx
.venv/bin/python render_html.py  # -> build/web/
```

Changing only the words in `source.md` needs just the last two lines.

The screenshots live in `shots/` as JPEG and are converted into `build/*.png`,
because both builders look for PNGs in `build/`:

```python
from PIL import Image
Image.open("shots/ui_assistant.jpg").convert("RGB").save("build/s02_assistant.png")
```

## Redeploying

```bash
KEY=~/Downloads/sailagentecsdevkey.pem
rsync -az --delete -e "ssh -i $KEY" build/web/ ubuntu@54.255.130.57:/tmp/phase-e-web/
rsync -az -e "ssh -i $KEY" build/Service_Assistant_Booking_Platform.docx ubuntu@54.255.130.57:/tmp/
ssh -i $KEY ubuntu@54.255.130.57 '
  sudo rsync -a --delete /tmp/phase-e-web/ /var/www/ai-order/docs/phase-e/ &&
  sudo cp /tmp/Service_Assistant_Booking_Platform.docx /var/www/ai-order/docs/ &&
  sudo chown -R www-data:www-data /var/www/ai-order/docs'
```

No nginx change is needed: `/docs/` is already served from that folder.

## Refreshing the screenshots

They were taken by driving the real interface: describe a problem, pick a
provider, pick a time, sign in, book, then sign in again as a provider. To
refresh them, do the same and replace the files in `shots/`. The booking
reference in the document is a real one, so refreshing will change it.

## What the document deliberately says

Four things are stated plainly rather than glossed over, because they will be
asked about and the honest answer is better coming from us:

- The phone layout has not been checked on a device.
- No real payment has been taken, by design.
- There are no screen by screen tests of the interface, only the logic
  underneath and whole flows against a live server.
- The system keeps no timezone per provider, which is correct today and will
  not be once providers are spread out.

Four faults found during the work are also recorded, including the one where
voice had been failing on every request.
