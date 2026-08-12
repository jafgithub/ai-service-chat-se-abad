"use client";

import type { ExternalProduct } from "@/lib/api";

/**
 * Products we do not stock, found elsewhere.
 *
 * Kept visibly separate from our own results, because these are different in
 * kind: the price came off a search results page and is a snapshot, and we do
 * not hold the stock. Adding one records it as a request to source, which a
 * person confirms before anyone is charged. Saying that plainly in the UI is
 * better than letting it look like ordinary stock.
 */

interface SourcedPanelProps {
  query: string;
  products: ExternalProduct[];
  loading: boolean;
  adoptingId: string | null;
  adoptedIds: string[];
  onAdd: (product: ExternalProduct) => void;
  /** The provider is returning invented sample data, not real listings. */
  sample?: boolean;
  onBackToOurs?: () => void;
  /** Show more: opens our own rendering of that vendor's product page. */
  onOpenProduct?: (product: ExternalProduct) => void;
}

export function SourcedPanel({
  query, products, loading, adoptingId, adoptedIds, onAdd,
  sample = false, onBackToOurs, onOpenProduct,
}: SourcedPanelProps) {
  if (!loading && products.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-surface-sunken text-3xl">
          🌐
        </div>
        <div>
          <p className="font-semibold text-ink">Nothing found in other stores</p>
          <p className="mt-1 text-sm text-ink-muted">
            {query ? `We looked beyond our own shelves for “${query}”.` : "Search for a product first."}
          </p>
        </div>
        {onBackToOurs && (
          <button
            onClick={onBackToOurs}
            className="rounded-control border border-line px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-surface-hover"
          >
            Back to our store
          </button>
        )}
      </div>
    );
  }

  return (
    <section>
      <div className="mb-3">
        <p className="text-xs text-ink-muted">
          {loading
            ? "Looking further afield…"
            : `Not stocked by us${query ? `, sourced for “${query}”` : ""}. A person confirms the price before you pay.`}
        </p>

        {/* Sample results are otherwise indistinguishable from real listings:
            same card, same price, invented seller. Someone demonstrating this
            could show the client fabricated products believing they were live. */}
        {sample && !loading && (
          <div className="mt-2 rounded-card border border-warn/40 bg-warn-soft px-3.5 py-2.5">
            <p className="text-xs font-semibold text-warn">
              Sample data, not real listings
            </p>
            <p className="mt-0.5 text-xs text-ink-muted">
              These products are examples so the feature can be demonstrated. Each one
              links to that store&rsquo;s own search, so the journey works end to end.
              Connect a search provider to replace them with real products.
            </p>
          </div>
        )}
      </div>

      {true && (
        <div>
          {loading ? (
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-3 2xl:grid-cols-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="animate-pulse rounded-card border border-line bg-surface p-3">
                  <div className="mb-2 h-3 w-3/4 rounded bg-surface-hover" />
                  <div className="h-3 w-1/2 rounded bg-surface-hover" />
                  <div className="mt-3 h-8 w-full rounded-control bg-surface-hover" />
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-3 2xl:grid-cols-4">
              {products.map((p) => {
                const added = adoptedIds.includes(p.source_id);
                const busy = adoptingId === p.source_id;
                return (
                  <article
                    key={p.source_id}
                    className="flex snap-start flex-col rounded-card border border-dashed border-line-strong bg-surface p-3"
                  >
                    {p.image_url ? (
                      // eslint-disable-next-line @next/next/no-img-element -- remote host, and next/image is unoptimized in a static export anyway
                      <img
                        src={p.image_url}
                        alt={p.name}
                        className="mb-2 h-20 w-full object-contain"
                        loading="lazy"
                      />
                    ) : (
                      <div className="mb-2 flex h-20 w-full items-center justify-center text-3xl" aria-hidden>
                        📦
                      </div>
                    )}

                    <p className="line-clamp-2 text-xs font-semibold leading-snug text-ink">
                      {p.name}
                    </p>
                    {p.seller && (
                      <p className="mt-0.5 truncate text-[11px] text-ink-faint">{p.seller}</p>
                    )}
                    <p className="mt-1 text-sm font-bold tabular-nums text-ink">
                      ${p.price.toFixed(2)}
                    </p>

                    {/* The brief asked for our Add to Cart panel to open on top
                        of the store's own page. Browsers forbid embedding one
                        site inside another (Walmart, Amazon, Target and eBay all
                        send X-Frame-Options SAMEORIGIN), so instead the shopper
                        adds to our cart from here and this opens the original
                        listing in its own tab to check. */}
                    {/* Opens our own rendering of the vendor's product page,
                        with every store selling it and Add to cart at the
                        bottom. Their page cannot be embedded, so this is the
                        product page and their site is one click further on. */}
                    <button
                      type="button"
                      onClick={() => onOpenProduct?.(p)}
                      className="mt-1 inline-flex items-center gap-1 text-[11px] font-semibold text-brand-600 hover:underline"
                    >
                      Show more
                    </button>

                    {/* Withheld on sample data. Requesting one writes a real,
                        orderable product into the catalog at a price the stub
                        invented. The server refuses it too; this is so the
                        button is not offered and then rejected. */}
                    {sample ? (
                      <p className="mt-2 rounded-control bg-surface-sunken px-2 py-2 text-center text-[11px] text-ink-faint">
                        Example only
                      </p>
                    ) : (
                      <button
                        onClick={() => onAdd(p)}
                        disabled={busy || added}
                        className={`mt-2 h-9 w-full rounded-control text-xs font-semibold transition-colors ${
                          added
                            ? "cursor-default bg-positive-soft text-positive"
                            : "bg-ink text-white hover:bg-ink/90 disabled:opacity-60"
                        }`}
                      >
                        {added ? "In your cart" : busy ? "Adding…" : "Request this"}
                      </button>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
