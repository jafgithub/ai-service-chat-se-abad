"use client";

import { useCallback, useEffect } from "react";
import type { RefObject } from "react";

/**
 * Fit a page drawn for a desktop into whatever width the frame actually has.
 *
 * The server renders at 1180px, because that is the layout a retailer designs
 * for and the one their product grids look right in. Inside a panel on a phone
 * the frame is about 396px, and the page then overflows by 656px: most of it
 * off the side, with a horizontal scrollbar as the only way to see it. Measured
 * on ALDI at a 420px viewport.
 *
 * Rather than force their fixed grids to reflow, which breaks them, this scales
 * the whole page down to fit, the way a browser's zoom does. `zoom` is used
 * instead of a transform because it reflows the layout and keeps scroll height
 * honest; a transform would leave the page claiming its full height and scroll
 * past the end.
 *
 * Same origin only, which is the case here: these pages come from our domain.
 */
export function useFrameFit(
  frameRef: RefObject<HTMLIFrameElement | null>,
  /** Changing this refits: a new store, or a new page. */
  key: string | null,
): () => void {
  const fit = useCallback(() => {
    const frame = frameRef.current;
    if (!frame) return;
    try {
      const doc = frame.contentDocument;
      if (!doc?.documentElement) return;

      const have = frame.clientWidth;
      if (!have) return;

      // Measure what actually happened rather than assuming from the width it
      // was drawn at. Most stores are responsive and reflow to fit once their
      // page is asked for at the right size, and zooming those would shrink a
      // page that was already correct. Only a page that genuinely runs off the
      // side gets scaled.
      doc.documentElement.style.zoom = "";
      const overflows = doc.documentElement.scrollWidth;
      if (overflows <= have * 1.02) return;

      doc.documentElement.style.zoom = String(Math.min(1, have / overflows));
    } catch {
      // Cross origin, which should not happen here.
    }
  }, [frameRef]);

  useEffect(() => {
    if (!key) return;
    // The page may not have parsed yet when this first runs, so keep trying
    // briefly rather than fitting once and hoping.
    const timer = window.setInterval(fit, 200);
    const stop = window.setTimeout(() => window.clearInterval(timer), 8000);
    const onResize = () => fit();
    window.addEventListener("resize", onResize);
    return () => {
      window.clearInterval(timer);
      window.clearTimeout(stop);
      window.removeEventListener("resize", onResize);
    };
  }, [key, fit]);

  return fit;
}
