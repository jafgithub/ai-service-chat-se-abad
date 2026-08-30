# The house shell

Two things shared by every hand written document in `docs/`.

`house.css` is the stylesheet the Service Assistant's SRS grew, lifted out
verbatim so the documents written after it look like it rather than each
carrying a copy that drifts at the first fix. Everything below the marked
addendum was added for the documents that came after: a rule for a block of
code, which an SRS with no code in it never needed.

`page.py` wraps it. Give it a title, a masthead, a contents list and the
sections, and it returns the whole file. The stylesheet is inlined rather than
linked because these pages get copied one file at a time, attached to emails,
and opened from a laptop with no network.

`hub.py` builds `docs/index.html`, the page that lists everything. The list is
data in that file, so adding a document is one entry rather than a copied block
of HTML with one word changed. The same output is deployed to every machine, so
every link in it is absolute.

## Which documents use it

    community-srs/   SmartCommunity: specification
    market-srs/      SmartMarket: specification
    gpu-spinup/      Spinning up a GPU, and wiring it to FastAPI

`srs/` predates all of this and still carries its own copy of the stylesheet
inline. It is not worth touching a shipped document to save a duplicate; when
it next needs an edit, point it at `page.py` then.

## Building

    python3 docs/community-srs/build.py
    python3 docs/market-srs/build.py
    python3 docs/gpu-spinup/build.py
    python3 docs/_house/hub.py

Each writes `index.html` beside itself. There is no watcher and no bundler.
