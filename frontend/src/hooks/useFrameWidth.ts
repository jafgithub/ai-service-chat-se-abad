"use client";

import { useSyncExternalStore } from "react";

/**
 * Which layout to ask a store for: their phone one, or their desktop one.
 *
 * Taken from the window rather than the frame, because the frame does not exist
 * on the first render and its width is only known once it has laid out. That is
 * too late: the iframe has already been given a src by then, and the shopper
 * gets the desktop page shrunk to a third of its size instead of the phone page
 * the store designed. Measured on ALDI at 390px: rendered at 1180, then zoomed
 * to 0.38 to fit.
 *
 * Two buckets, matching the two the server renders. The width is part of the
 * request and therefore part of the cache key, so a value that moved with every
 * pixel of a window drag would render the same page over and over.
 */
const MOBILE_UP_TO = 640;

function subscribe(onChange: () => void) {
  window.addEventListener("resize", onChange);
  return () => window.removeEventListener("resize", onChange);
}

export function useFrameWidth(): number {
  return useSyncExternalStore(
    subscribe,
    () => (window.innerWidth < MOBILE_UP_TO ? 400 : 1180),
    // On the server there is no window. The desktop bucket is the safer guess:
    // it is what every existing snapshot was rendered at.
    () => 1180,
  );
}
