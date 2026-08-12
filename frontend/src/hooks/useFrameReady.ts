"use client";

import { useCallback, useEffect, useState } from "react";
import type { RefObject } from "react";

/**
 * When a framed page is worth showing, which is well before it has finished.
 *
 * An iframe's `load` event waits for every last image, and a retailer's page
 * carries hundreds from their own CDN. Measured on ALDI: the document was
 * complete and readable, with all 110 links in place, while `load` had still
 * not fired eighteen seconds later. The shopper sat behind a spinner looking at
 * a page that was already there.
 *
 * So this watches the document instead. As soon as the frame has stopped
 * parsing and has something in its body, the page is shown; images arriving
 * afterwards fill in as they always do on the web.
 *
 * Readiness is stored as *which page* is ready rather than a boolean, so moving
 * to another store is not ready by default and nothing has to be reset. A reset
 * would mean setting state inside an effect, which is a cascading render.
 *
 * Same origin only, which is exactly the case here: these pages are served from
 * our own domain, which is the whole reason the feature works at all.
 */
export function useFrameReady(
  /** The ref itself, not its value: reading a ref during render is not allowed,
      and the effect below is the right place to look at it. */
  frameRef: RefObject<HTMLIFrameElement | null>,
  /** Identifies the page being waited for: a store key, or an address. */
  key: string | null,
): [boolean, () => void] {
  const [readyKey, setReadyKey] = useState<string | null>(null);

  useEffect(() => {
    if (!key) return;

    let stopped = false;
    const check = () => {
      if (stopped) return;
      try {
        const doc = frameRef.current?.contentDocument;
        if (doc && doc.readyState !== "loading" && doc.body?.childElementCount) {
          stopped = true;
          setReadyKey(key);
        }
      } catch {
        // Cross origin, which should not happen here.
      }
    };

    const timer = window.setInterval(check, 150);
    return () => { stopped = true; window.clearInterval(timer); };
  }, [key, frameRef]);

  const markReady = useCallback(() => setReadyKey(key), [key]);

  return [readyKey !== null && readyKey === key, markReady];
}
