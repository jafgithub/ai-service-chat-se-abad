"""One page shell, shared by every hand written document in this set.

The generated sets (source.md plus render_*.py) already share a look through
render_html.py. The hand written ones did not: the Service Assistant's SRS
carried its own 390 line stylesheet, and the next document to be written by
hand would either have imported nothing and looked different, or copied that
block and drifted from it at the first fix.

So the stylesheet lives in `house.css` and this module wraps it. It is inlined
rather than linked because these pages are copied around one file at a time,
sent as attachments, and opened from a laptop with no network.
"""

import pathlib

HERE = pathlib.Path(__file__).resolve().parent

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=IBM+Plex+Mono:wght@400;500;600&'
    'family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&'
    'family=Public+Sans:wght@400;500;600;700&display=swap">'
)

#: Where "All documents" goes. The hub is deployed to every box, so this is a
#: relative path: a copy of the page opened from the community site must not
#: send the reader to the service site to find its own index.
HUB = "../"


def render(*, title, badge, h1, standfirst, docmeta, toc, body, hub=HUB):
    """The whole file, as a string.

    `docmeta` is a list of (label, value). `toc` is a list of
    (anchor, number, text, children), children being the same shape or ().
    `body` is the sections, already HTML.
    """
    css = (HERE / "house.css").read_text()

    meta_html = "\n".join(
        f"      <div><dt>{label}</dt><dd>{value}</dd></div>"
        for label, value in docmeta
    )

    def toc_items(items):
        out = []
        for anchor, number, text, children in items:
            inner = f'<a href="#{anchor}"><span class="n">{number}</span> {text}</a>'
            if children:
                inner += "\n          <ol>\n" + toc_items(children) + "\n          </ol>"
            out.append(f"        <li>{inner}</li>")
        return "\n".join(out)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{title}</title>
{FONTS}

<style>
{css}
</style>
</head>
<body>

<div class="shell">

  <a class="back" href="{hub}">All documents</a>

  <div class="masthead">
    <span class="badge">{badge}</span>
    <h1>{h1}</h1>
    <p class="standfirst">
      {standfirst}
    </p>
    <dl class="docmeta">
{meta_html}
    </dl>
  </div>

  <div class="layout">

    <nav class="toc" aria-label="Contents">
      <h2>Contents</h2>
      <ol>
{toc_items(toc)}
      </ol>
    </nav>

    <div class="body">
{body}
    </div>
  </div>

  <div class="foot">
    <p>
      Written by Abad Naseer. Every measured number in this document is cited
      from the running system or from the code, and every target says that it
      is a target. Where the two disagree, the document says so rather than
      choosing the flattering one.
    </p>
  </div>
</div>
</body>
</html>
"""
