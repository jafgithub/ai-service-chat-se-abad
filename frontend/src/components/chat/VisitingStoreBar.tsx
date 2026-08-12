"use client";

import type { ExternalProduct } from "@/lib/api";
import { displayName } from "@/lib/product";

/**
 * The product a shopper went off to look at, kept in reach.
 *
 * The brief asked for our Add to Cart to sit on top of the retailer's own page.
 * Browsers forbid it: Costco Same-Day, ALDI and Instacart all send
 * `frame-ancestors 'self'`, so their pages cannot be embedded in ours and no
 * script of ours can reach inside them. Only a browser extension could, and
 * every shopper would have to install one.
 *
 * So the next best thing, which needs nothing installed: the store opens in its
 * own tab, and this bar waits in ours. Coming back, adding it is one click and
 * the shopper has not lost their place.
 *
 * It stays until dismissed or added, deliberately. Someone comparing three
 * shops should still find it there several minutes later.
 */

interface VisitingStoreBarProps {
  product: ExternalProduct;
  busy: boolean;
  added: boolean;
  onAdd: (product: ExternalProduct) => void;
  onDismiss: () => void;
}

export function VisitingStoreBar({
  product, busy, added, onAdd, onDismiss,
}: VisitingStoreBarProps) {
  return (
    <div className="flex-shrink-0 border-t border-brand-200 bg-brand-50 px-4 py-2.5">
      <div className="flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs text-ink-muted">
            {added ? "Added from" : "Viewing at"}{" "}
            <span className="font-semibold text-ink">{product.seller || "another store"}</span>
          </p>
          <p className="truncate text-sm font-semibold text-ink">
            {displayName(product.name)}
            <span className="ml-2 font-normal text-ink-muted">
              ${product.price.toFixed(2)}
            </span>
          </p>
        </div>

        {added ? (
          <span className="flex-shrink-0 rounded-control bg-positive-soft px-3 py-2 text-xs font-semibold text-positive">
            In your cart
          </span>
        ) : (
          <button
            onClick={() => onAdd(product)}
            disabled={busy}
            className="h-10 flex-shrink-0 rounded-control bg-brand-500 px-5 text-sm font-semibold text-white transition-colors hover:bg-brand-600 disabled:opacity-60"
          >
            {busy ? "Adding…" : "Add to cart"}
          </button>
        )}

        <button
          onClick={onDismiss}
          aria-label="Dismiss"
          className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-surface hover:text-ink"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
