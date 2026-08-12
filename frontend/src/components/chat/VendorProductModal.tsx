"use client";

import { useEffect, useRef, useState } from "react";
import type { ExternalProduct, ProductDetail, StoreOffer } from "@/lib/api";
import { shoppingApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { displayName } from "@/lib/product";
import { ProductImage } from "@/components/ui/ProductImage";
import { useFrameReady } from "@/hooks/useFrameReady";
import { useFrameFit } from "@/hooks/useFrameFit";
import { useFrameWidth } from "@/hooks/useFrameWidth";

/**
 * A vendor's product, two ways.
 *
 * By default the page is drawn from the data we hold: the product's images,
 * brand, rating, reviews, and every store selling it with its price. That is
 * what /chat shows.
 *
 * With `browserView`, /v1/chat shows the retailer's own page instead. A browser
 * will not let our page frame theirs (Target sends `frame-ancestors 'self'`,
 * Walmart and Amazon send `X-Frame-Options`), but those headers bind whoever
 * serves the page, so our server renders it and serves the result from our own
 * domain.
 *
 * An earlier version of this comment said a server-side fetch is refused with a
 * "Robot or human?" page. That was wrong: it happens with default headers, not
 * with a browser's. What is true, and was measured, is that several retailers
 * refuse us anyway, and that Walmart went from rendering to blocking between
 * two consecutive days.
 *
 * Add to cart sits at the bottom in both, which is what the requirement was for.
 */

interface VendorProductModalProps {
  product: ExternalProduct;
  onClose: () => void;
  /** Adds to our cart the product as the shopper chose it: the store, that
      store's price, and that store's page. Passing only the URL would charge
      them whatever the search happened to quote, which is a different shop. */
  onAdd: (product: ExternalProduct) => void;
  adding?: boolean;
  added?: boolean;
  /** Sample data cannot be ordered, so the action becomes a note. */
  sample?: boolean;
  /**
   * Show the retailer's own page in a frame instead of drawing it ourselves.
   *
   * Only /v1/chat sets this. It works because our server renders their page and
   * serves it from our domain, which their framing headers cannot reach. It is
   * a demonstration: their scripts are stripped, so what a shopper sees is a
   * still of their page, and the Add to cart underneath is ours. See
   * `app/services/browser/snapshot.py` for the conditions that come with it.
   */
  browserView?: boolean;
}

/**
 * Reads the address the frame is actually showing.
 *
 * Links inside a rendered page point back at our own endpoint, so the shopper
 * can follow a search result to a product page without leaving. That means the
 * frame moves on its own, and the toolbar has to follow it rather than assume
 * it is still showing what we opened.
 *
 * Same origin, so this is readable. It is the whole reason the pages are served
 * from our domain rather than the retailer's.
 */
function framedAddress(frame: HTMLIFrameElement | null): string | null {
  try {
    const here = frame?.contentWindow?.location.href;
    if (!here) return null;
    const u = new URL(here, window.location.origin);
    return u.searchParams.get("u");
  } catch {
    // Cross origin, which should not happen, but a toolbar is not worth a crash.
    return null;
  }
}

/**
 * The retailer's page, in a frame, with the chrome a browser needs.
 *
 * A store switcher, an address bar showing where the shopper actually is, back
 * and reload, and a way out to the real site. The address bar earns its place:
 * links inside the page are rewritten to come back through our own endpoint, so
 * the shopper genuinely moves from a search page to a product page to a
 * category without leaving, and needs to see where that has taken them.
 *
 * `sandbox` withholds `allow-scripts` deliberately. The snapshot has no scripts
 * of its own, so nothing is lost, and a retailer page carries a great deal of
 * third-party code we have no reason to run inside our origin. `allow-popups`
 * stays so links out can still open the real store in a new tab.
 */
function BrowserView({
  url, storeName, stores, chosen, onChoose, loading,
}: {
  url: string | null;
  /** Named while it loads, so the wait says what it is waiting for. */
  storeName: string | null;
  stores: StoreOffer[];
  chosen: string | null;
  onChoose: (url: string) => void;
  loading: boolean;
}) {
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  // Where the shopper has been inside the frame. Their browser's own history is
  // no use here: going back in it would leave the shop entirely.
  //
  // Both start from `url` and are never reset by an effect. The parent gives
  // this component `key={url}`, so choosing a different store remounts it and
  // the visit starts clean, which is what an effect would have been faking.
  const [trail, setTrail] = useState<string[]>([]);
  const [here, setHere] = useState<string | null>(url);
  // `load` waits for every image on a retailer's page, which takes far longer
  // than the page takes to become readable. See the hook.
  const [frameShown, markShown] = useFrameReady(frameRef, here);
  // Measured once the panel has laid out, and used to ask the store for
  // the layout that fits. A phone gets their phone site rather than their
  // desktop one squeezed to a third of its width.
  const frameWidth = useFrameWidth();
  const fitToFrame = useFrameFit(frameRef, here);

  const onFrameLoad = () => {
    markShown();
    fitToFrame();
    const now = framedAddress(frameRef.current);
    if (!now) return;
    setHere((was) => {
      if (was && was !== now) setTrail((t) => [...t, was]);
      return now;
    });
  };

  const goBack = () => {
    setTrail((t) => {
      if (!t.length) return t;
      const previous = t[t.length - 1];
      // Set directly rather than through history, so this does not push the
      // page being left onto the trail again.
      if (frameRef.current) {
        frameRef.current.src = shoppingApi.browseUrl(previous);
      }
      setHere(previous);
      return t.slice(0, -1);
    });
  };

  const reload = () => {
    if (frameRef.current && here) {
      frameRef.current.src = shoppingApi.browseUrl(here);
    }
  };

  const shownAddress = (() => {
    try {
      const u = new URL(here || url || "");
      return u.hostname.replace(/^www\./, "") + u.pathname;
    } catch {
      return "";
    }
  })();
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* A browser's chrome: which store you are in, and the way out to the
          real one. Kept to one row so the page itself gets the height. */}
      <div className="chat-scroll flex flex-shrink-0 items-center gap-2 overflow-x-auto border-b border-line bg-surface-sunken px-4 py-2">
        {stores.length > 1 && (
          <span className="flex-shrink-0 text-xs font-semibold uppercase tracking-wide text-ink-faint">
            Store
          </span>
        )}
        {stores.map((s, i) => (
          <button
            key={s.url}
            type="button"
            onClick={() => onChoose(s.url)}
            aria-pressed={s.url === chosen}
            className={cn(
              "flex flex-shrink-0 items-center gap-1.5 rounded-control border px-3 py-1.5 text-xs font-medium transition-colors",
              s.url === chosen
                ? "border-brand-400 bg-surface text-ink shadow-sm"
                : "border-line bg-surface text-ink-muted hover:bg-surface-hover"
            )}
          >
            {s.name}
            {s.price != null && (
              <span className="font-bold tabular-nums">${s.price.toFixed(2)}</span>
            )}
            {i === 0 && stores.length > 1 && (
              <span className="text-[10px] font-semibold text-positive">Best</span>
            )}
          </button>
        ))}

        <span className="flex-1" />
      </div>

      {/* The address bar. Not decoration: links inside the page come back
          through us, so the shopper really is moving around the store, and
          they need to see where they are and a way back. */}
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
        <button
          type="button"
          onClick={reload}
          aria-label="Reload"
          className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>

        <div className="flex min-w-0 flex-1 items-center gap-1.5 rounded-full bg-surface-sunken px-3 py-1">
          <svg className="h-3 w-3 flex-shrink-0 text-positive" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
          <span className="truncate text-xs text-ink-muted" title={here || undefined}>
            {shownAddress}
          </span>
        </div>

        {(here || url) && (
          <a
            href={here || url || "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="flex flex-shrink-0 items-center gap-1 rounded-control px-2 py-1 text-xs font-medium text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
          >
            Open at store
            <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        )}
      </div>

      <div className="relative min-h-0 flex-1 bg-white">
        {url && (
          <iframe
            ref={frameRef}
            src={shoppingApi.browseUrl(url, frameWidth)}
            title="Store product page"
            onLoad={onFrameLoad}
            sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
            className="h-full w-full border-0 bg-white"
          />
        )}

        {(loading || !frameShown || !url) && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-surface">
            {/* A page-shaped skeleton rather than a bare spinner, so the wait
                looks like a page arriving instead of nothing happening. */}
            <div className="flex w-full max-w-md gap-4 px-6" aria-hidden>
              <div className="h-32 w-32 flex-shrink-0 animate-pulse rounded-card bg-surface-hover" />
              <div className="flex flex-1 flex-col gap-2 pt-2">
                <div className="h-3 w-3/4 animate-pulse rounded bg-surface-hover" />
                <div className="h-3 w-1/2 animate-pulse rounded bg-surface-hover" />
                <div className="mt-2 h-6 w-24 animate-pulse rounded bg-surface-hover" />
                <div className="mt-1 h-9 w-full animate-pulse rounded-control bg-surface-hover" />
              </div>
            </div>
            <p className="text-sm font-medium text-ink">
              {storeName ? `Opening ${storeName}...` : "Opening the store page..."}
            </p>
            <p className="max-w-xs text-center text-xs text-ink-faint">
              Loading their page on our server. Once loaded it opens instantly.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export function VendorProductModal({
  product, onClose, onAdd, adding = false, added = false, sample = false,
  browserView = false,
}: VendorProductModalProps) {
  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);
  // Which store the shopper is buying from. Defaults to the cheapest.
  const [chosen, setChosen] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  /* Fetched once, on open. `loading` starts true rather than being set here:
     the modal is mounted per product, so there is no second run to reset for,
     and setting state synchronously in an effect is a cascading render. */
  useEffect(() => {
    let dropped = false;
    shoppingApi
      .product(product.source_id)
      .then((d) => {
        if (dropped) return;
        setDetail(d);
        setChosen(d.best_url ?? null);
      })
      .catch(() => { if (!dropped) setDetail(null); })
      .finally(() => { if (!dropped) setLoading(false); });
    return () => { dropped = true; };
  }, [product.source_id]);

  const stores = detail?.stores ?? [];
  const selected = stores.find((s) => s.url === chosen) ?? stores[0];
  const price = selected?.price ?? detail?.best_price ?? product.price;
  const images = detail?.images?.length ? detail.images : (product.image_url ? [product.image_url] : []);
  const title = displayName(detail?.title || product.name);

  // The page to frame: whichever store is chosen, falling back to whatever the
  // search gave us so the view still has somewhere to go before detail arrives.
  const framedUrl = selected?.url ?? detail?.best_url ?? product.product_url ?? null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center bg-ink/50 p-3 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className={cn(
          "flex w-full flex-col overflow-hidden rounded-sheet bg-surface shadow-pop",
          // The framed view is a whole web page, so it gets the room for one.
          browserView ? "h-[92dvh] max-w-5xl" : "max-h-[92dvh] max-w-2xl"
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-shrink-0 items-start justify-between gap-3 border-b border-line px-5 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink">{title}</p>
            <p className="mt-0.5 text-xs text-ink-muted">
              {detail?.brand ? `${detail.brand} · ` : ""}
              {detail?.rating
                ? `${detail.rating}★${detail.reviews ? ` (${detail.reviews})` : ""}`
                : "Sold by another store"}
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

        {browserView ? (
          <BrowserView
            key={framedUrl}
            url={framedUrl}
            storeName={selected?.name ?? detail?.best_store ?? product.seller ?? null}
            stores={stores}
            chosen={chosen}
            onChoose={(url) => setChosen(url)}
            loading={loading}
          />
        ) : (
        <div className="chat-scroll flex-1 overflow-y-auto px-5 py-4">
          {/* Photographs, sideways: a product page's first job. */}
          <div className="chat-scroll -mx-1 flex gap-2 overflow-x-auto overscroll-x-contain px-1 pb-2">
            {images.length > 0 ? (
              images.map((src, i) => (
                <div key={i} className="h-40 w-40 flex-shrink-0 overflow-hidden rounded-card border border-line bg-surface p-2">
                  <ProductImage src={src} alt={title} category={null} priority={i === 0} />
                </div>
              ))
            ) : (
              <div className="h-40 w-40 flex-shrink-0 overflow-hidden rounded-card border border-line">
                <ProductImage src={null} alt={title} category={null} iconClassName="text-5xl" />
              </div>
            )}
          </div>

          <section className="mt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
              {loading ? "Finding the stores selling this…" : `Available at ${stores.length || "no"} store${stores.length === 1 ? "" : "s"}`}
            </p>

            {loading ? (
              <div className="flex flex-col gap-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-14 animate-pulse rounded-card border border-line bg-surface-hover" />
                ))}
              </div>
            ) : stores.length > 0 ? (
              <div className="flex flex-col gap-2">
                {stores.map((s, i) => (
                  <div
                    key={s.url}
                    className={cn(
                      "flex items-center gap-3 rounded-card border p-3 transition-colors",
                      s.url === chosen ? "border-brand-400 bg-brand-50" : "border-line"
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => setChosen(s.url)}
                      aria-pressed={s.url === chosen}
                      className="flex min-w-0 flex-1 items-center gap-3 text-left"
                    >
                      <span
                        className={cn(
                          "flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border-2",
                          s.url === chosen ? "border-brand-500" : "border-line-strong"
                        )}
                        aria-hidden
                      >
                        {s.url === chosen && <span className="h-2.5 w-2.5 rounded-full bg-brand-500" />}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold text-ink">{s.name}</span>
                        {i === 0 && stores.length > 1 && (
                          <span className="text-[11px] font-medium text-positive">Best price</span>
                        )}
                      </span>
                      <span className="flex-shrink-0 text-sm font-bold tabular-nums text-ink">
                        {s.price != null ? `$${s.price.toFixed(2)}` : s.price_text || ""}
                      </span>
                    </button>

                    {/* Their page, in their own tab. */}
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex h-9 flex-shrink-0 items-center gap-1 rounded-control border border-line px-3 text-xs font-medium text-ink transition-colors hover:bg-surface-hover"
                    >
                      View
                      <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                    </a>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-ink-muted">
                We could not reach the stores for this product just now.
              </p>
            )}
          </section>

          {detail?.description && (
            <section className="mt-5">
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                About this product
              </p>
              <p className="text-sm leading-relaxed text-ink-muted">{detail.description}</p>
            </section>
          )}

          {detail?.review_snippets && detail.review_snippets.length > 0 && (
            <section className="mt-5">
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                What shoppers say
              </p>
              <div className="flex flex-col gap-2">
                {detail.review_snippets.map((r, i) => (
                  <p key={i} className="rounded-card border border-line px-3 py-2 text-xs leading-relaxed text-ink-muted">
                    {r}
                  </p>
                ))}
              </div>
            </section>
          )}

          <p className="mt-5 text-xs text-ink-faint">
            Not stocked by us. The price comes from {selected?.name || "the store"} and is
            confirmed by a person before you are charged.
          </p>
        </div>
        )}

        {/* Add to cart, at the bottom, as asked. */}
        <div className="flex-shrink-0 border-t border-line bg-surface px-5 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          {sample ? (
            <p className="rounded-control bg-surface-sunken py-3 text-center text-xs text-ink-faint">
              Example product, not orderable
            </p>
          ) : added ? (
            <p className="rounded-control bg-positive-soft py-3 text-center text-sm font-semibold text-positive">
              In your cart
            </p>
          ) : (
            <button
              onClick={() => onAdd({
                ...product,
                // The chosen shop, whole. The shopper picked Target at $6.39;
                // adding Walmart's $8.71 because that is what the search
                // returned would charge them for a different offer.
                vendor_url: selected?.url ?? detail?.best_url ?? product.product_url ?? null,
                price: price,
                seller: selected?.name ?? detail?.best_store ?? product.seller,
              })}
              disabled={adding || loading}
              className="h-12 w-full rounded-control bg-brand-500 text-base font-semibold text-white transition-colors hover:bg-brand-600 disabled:opacity-60"
            >
              {adding
                ? "Adding…"
                : `Add to cart${price ? ` · $${price.toFixed(2)}` : ""}`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
