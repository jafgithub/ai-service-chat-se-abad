"use client";

import { useEffect, useRef, useState } from "react";
import type { BrowseStore } from "@/lib/api";
import { shoppingApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useFrameReady } from "@/hooks/useFrameReady";
import { useFrameFit } from "@/hooks/useFrameFit";
import { useFrameWidth } from "@/hooks/useFrameWidth";

/**
 * The eleven stores, browsable inside our app.
 *
 * Each one opens at its own search for whatever the shopper asked for, drawn on
 * our server and served from our domain so it can be framed at all. Links
 * inside are rewritten to come back through us, so following a search result to
 * a product page keeps the shopper here.
 *
 * Stores that cannot be drawn are still listed, marked, and open on a card with
 * a link out. Hiding them would be tidier and less honest: the client named
 * eleven, and a strip showing four invites the question of where the rest went.
 */

interface StoreBrowserModalProps {
  /** What the shopper searched for, which is what each store will be asked. */
  query: string;
  onClose: () => void;
}

export function StoreBrowserModal({ query, onClose }: StoreBrowserModalProps) {
  const [stores, setStores] = useState<BrowseStore[] | null>(null);
  const [active, setActive] = useState<BrowseStore | null>(null);
  const [address, setAddress] = useState<string | null>(null);
  const [trail, setTrail] = useState<string[]>([]);
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const [ready, markReady] = useFrameReady(frameRef, active?.key ?? null);
  // Measured once the panel has laid out, and used to ask the store for
  // the layout that fits. A phone gets their phone site rather than their
  // desktop one squeezed to a third of its width.
  const frameWidth = useFrameWidth();
  // Their page is drawn for a desktop; the panel is whatever the shopper has.
  const fitToFrame = useFrameFit(frameRef, address);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    let dropped = false;
    shoppingApi
      .stores(query)
      .then((list) => {
        if (dropped) return;
        setStores(list);
        // Open on the first store that can actually be drawn, so the panel
        // starts with something to look at rather than an apology.
        const first = list.find((s) => s.renders) ?? list[0] ?? null;
        setActive(first);
        setAddress(first ? first.search_url : null);
      })
      .catch(() => { if (!dropped) setStores([]); });
    return () => { dropped = true; };
  }, [query]);

  const open = (store: BrowseStore) => {
    setActive(store);
    setAddress(store.search_url);
    setTrail([]);
  };

  const onFrameLoad = () => {
    markReady();
    fitToFrame();
    try {
      const here = frameRef.current?.contentWindow?.location.href;
      if (!here) return;
      const now = new URL(here, window.location.origin).searchParams.get("u");
      if (!now) return;
      setAddress((was) => {
        if (was && was !== now) setTrail((t) => [...t, was]);
        return now;
      });
    } catch {
      // Cross origin. Should not happen; not worth a crash if it does.
    }
  };

  const goBack = () => {
    setTrail((t) => {
      if (!t.length) return t;
      const previous = t[t.length - 1];
      if (frameRef.current) frameRef.current.src = shoppingApi.browseUrl(previous);
      setAddress(previous);
      return t.slice(0, -1);
    });
  };

  const shown = (() => {
    try {
      const u = new URL(address || "");
      return u.hostname.replace(/^www\./, "") + u.pathname;
    } catch {
      return "";
    }
  })();

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center bg-ink/50 p-3 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Browse stores"
    >
      <div
        className="flex h-[92dvh] w-full max-w-6xl flex-col overflow-hidden rounded-sheet bg-surface shadow-pop"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-shrink-0 items-center justify-between gap-3 border-b border-line px-5 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink">Browse stores</p>
            <p className="mt-0.5 truncate text-xs text-ink-muted">
              Searching {query ? `"${query}"` : "the stores"} without leaving the app
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* The eleven. Ones we can draw first, the rest marked rather than hidden. */}
        <div className="chat-scroll flex flex-shrink-0 items-center gap-2 overflow-x-auto border-b border-line bg-surface-sunken px-4 py-2">
          {(stores ?? []).map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => open(s)}
              aria-pressed={active?.key === s.key}
              title={s.renders ? s.name : `${s.name} does not allow their pages to be shown here`}
              className={cn(
                "flex flex-shrink-0 items-center gap-1.5 rounded-control border px-3 py-1.5 text-xs font-medium transition-colors",
                active?.key === s.key
                  ? "border-brand-400 bg-surface text-ink shadow-sm"
                  : "border-line bg-surface text-ink-muted hover:bg-surface-hover",
                !s.renders && "opacity-60"
              )}
            >
              {s.name}
              {!s.renders && <span className="text-[10px] text-ink-faint">link only</span>}
            </button>
          ))}
          {stores === null && (
            <span className="text-xs text-ink-faint">Loading stores...</span>
          )}
        </div>

        {active && active.renders && !active.searches && (
          <p className="flex-shrink-0 border-b border-line bg-brand-50 px-4 py-1.5 text-xs text-ink-muted">
            {active.name}{" "}runs its search in the shopper&apos;s own browser,
            which we cannot do here, so this opens their catalogue instead.
            Their own search still works through Open at store.
          </p>
        )}

        <div className="flex flex-shrink-0 items-center gap-1.5 border-b border-line bg-surface px-3 py-1.5">
          <button
            type="button"
            onClick={goBack}
            disabled={trail.length === 0}
            aria-label="Back"
            className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink disabled:opacity-30 disabled:hover:bg-transparent"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="flex min-w-0 flex-1 items-center gap-1.5 rounded-full bg-surface-sunken px-3 py-1">
            <span className="truncate text-xs text-ink-muted" title={address || undefined}>
              {shown}
            </span>
          </div>
          {address && (
            <a
              href={address}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-shrink-0 rounded-control px-2 py-1 text-xs font-medium text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
            >
              Open at store
            </a>
          )}
        </div>

        <div className="relative min-h-0 flex-1 bg-white">
          {active && active.renders && address && (
            <iframe
              ref={frameRef}
              key={active.key}
              src={shoppingApi.browseUrl(active.search_url, frameWidth)}
              title={`${active.name} inside the app`}
              onLoad={onFrameLoad}
              sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
              className="h-full w-full border-0 bg-white"
            />
          )}

          {active && !active.renders && (
            <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
              <p className="text-sm font-semibold text-ink">
                {active.name} does not allow their pages to be shown inside another site
              </p>
              <p className="max-w-md text-xs text-ink-faint">
                Their server refuses automated visitors. Their own site still works
                normally, so this opens there instead.
              </p>
              <a
                href={active.search_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 rounded-control bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-600"
              >
                Open {active.name}
              </a>
            </div>
          )}

          {active && active.renders && !ready && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-surface">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-line border-t-brand-500" />
              <p className="text-sm font-medium text-ink">Opening {active.name}...</p>
              <p className="max-w-xs text-center text-xs text-ink-faint">
                Their page is loading on our server. Once loaded it opens instantly.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
