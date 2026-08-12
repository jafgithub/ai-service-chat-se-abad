"use client";

import { useEffect } from "react";
import type { ProductResult } from "@/lib/api";
import {
  cleanDescription,
  displayCategory,
  displayName,
  formatPrice,
  isOutOfStock,
  lowStockLabel,
} from "@/lib/product";
import { ProductImage } from "@/components/ui/ProductImage";

interface ProductDetailsModalProps {
  product: ProductResult;
  onClose: () => void;
  onAdd?: (product: ProductResult) => void;
  /** The retailer, for a product we do not stock ourselves. */
  seller?: string | null;
  /** Their own product page. Opens in a new tab.
   *
   *  The brief asked for our Add to Cart panel to sit on top of the store's
   *  page. Browsers forbid that: Walmart, Amazon, Target and eBay all send
   *  X-Frame-Options SAMEORIGIN, so their pages cannot be embedded in ours and
   *  no script of ours can reach inside them. So the shopper adds to our cart
   *  from this sheet, and the link is there for checking the original listing. */
  productUrl?: string | null;
  /** True when the price came from a stored search rather than a live one. */
  stored?: boolean;
}

/** Full product details, shared by the result card and the cart. */
export function ProductDetailsModal({
  product, onClose, onAdd, seller, productUrl, stored,
}: ProductDetailsModalProps) {
  const description = cleanDescription(product.description);
  const category = displayCategory(product.category);
  const lowStock = lowStockLabel(product.stock, product.unit);
  const soldOut = isOutOfStock(product.stock);

  // Escape closes, matching every other dismissible layer in the app.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center bg-ink/50 p-3 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={displayName(product.name)}
    >
      <div
        className="flex max-h-[88dvh] w-full max-w-md flex-col overflow-hidden rounded-sheet bg-surface shadow-pop"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="relative h-56 flex-shrink-0 bg-surface-sunken">
          <ProductImage
            src={product.image_url}
            alt={product.name}
            category={product.category}
            iconClassName="text-7xl"
            priority
          />
          <button
            onClick={onClose}
            aria-label="Close"
            className="absolute right-3 top-3 flex h-9 w-9 items-center justify-center rounded-full bg-ink/50 text-white transition-colors hover:bg-ink/70"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="overflow-y-auto p-5">
          {category && (
            <p className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-faint">
              {category}
            </p>
          )}
          <h2 className="text-lg font-semibold leading-snug text-ink">
            {displayName(product.name)}
          </h2>

          <div className="mt-2 flex items-center gap-3">
            <span className="text-2xl font-bold text-ink">
              {formatPrice(product.price_per_unit, product.unit)}
            </span>
            {soldOut ? (
              <span className="rounded-full bg-danger-soft px-2 py-0.5 text-xs font-semibold text-danger">
                Out of stock
              </span>
            ) : lowStock ? (
              <span className="rounded-full bg-warn-soft px-2 py-0.5 text-xs font-semibold text-warn">
                {lowStock}
              </span>
            ) : (
              <span className="rounded-full bg-positive-soft px-2 py-0.5 text-xs font-semibold text-positive">
                Available
              </span>
            )}
          </div>

          {description && (
            <p className="mt-4 text-sm leading-relaxed text-ink-muted">{description}</p>
          )}

          {seller && (
            <div className="mt-4 rounded-card border border-warn/30 bg-warn-soft px-3.5 py-3">
              <p className="text-xs font-semibold text-warn">
                Provided by {seller}, not stocked by us
              </p>
              <p className="mt-0.5 text-xs text-ink-muted">
                This price is a snapshot{stored ? " from a recent search" : ""} and a
                person confirms it before you are charged.
              </p>
            </div>
          )}

          <div className="mt-5 flex flex-col gap-2">
            {onAdd && (
              <button
                onClick={() => { onAdd(product); onClose(); }}
                className="h-11 w-full rounded-control bg-brand-500 text-sm font-semibold text-white transition-colors hover:bg-brand-600 active:scale-[0.99]"
              >
                Book this
              </button>
            )}

            {productUrl && (
              /* noreferrer as well as noopener: the destination is a third
                 party and has no business knowing which page sent the shopper. */
              <a
                href={productUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex h-11 w-full items-center justify-center gap-1.5 rounded-control border border-line text-sm font-medium text-ink transition-colors hover:bg-surface-hover"
              >
                View on {seller || "the store"}
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
