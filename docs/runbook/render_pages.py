"""Photograph the terminal pages into PNGs for the Word document.

Headless Chrome at 2x, then cropped back to the content, so the images stay
sharp when Word scales them to the page width.

    python3 render_terminals.py     # build the pages first
    python3 render_pages.py
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
PAGES = HERE / "pages"
BUILD = HERE / "build"
# Must be at least as wide as the widest page body, or the render is cut off
# horizontally rather than just padded. Terminal pages are 1360, diagrams 1420.
WIDTH = 1420
TALL = 1600      # generous; cropped back afterwards
SCALE = 2


def chrome() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    sys.exit("Google Chrome or Chromium is required.")


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    binary = chrome()
    pages = sorted(PAGES.glob("*.html"))
    if not pages:
        sys.exit("No pages found. Run render_terminals.py first.")

    for src in pages:
        with tempfile.TemporaryDirectory() as tmp:
            shot = Path(tmp) / "shot.png"
            subprocess.run(
                [binary, "--headless=new", "--disable-gpu", "--no-sandbox",
                 "--hide-scrollbars", f"--force-device-scale-factor={SCALE}",
                 f"--window-size={WIDTH},{TALL}",
                 f"--screenshot={shot}", "--virtual-time-budget=2500",
                 src.as_uri()],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
            )
            image = Image.open(shot).convert("RGB")

        # Trim the empty canvas below the content.
        grey = image.convert("L")
        # 252, not 247: the note panels use a very pale background that a
        # higher threshold reads as blank page and trims, cutting off text.
        box = grey.point(lambda v: 0 if v > 252 else 255).getbbox()
        if box:
            pad = 8 * SCALE
            image = image.crop((
                max(box[0] - pad, 0), max(box[1] - pad, 0),
                min(box[2] + pad, image.width), min(box[3] + pad, image.height),
            ))

        out = BUILD / f"{src.stem}.png"
        image.save(out)
        print(f"  {out.name}  {image.width}x{image.height}")

    print(f"\n{len(pages)} images in {BUILD}")


if __name__ == "__main__":
    main()
