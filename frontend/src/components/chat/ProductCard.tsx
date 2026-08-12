"use client";

import { useState } from "react";
import type { ProductResult } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  cleanDescription,
  displayCategory,
  displayName,
  formatPrice,
  isOutOfStock,
  lowStockLabel,
} from "@/lib/product";
import { ProductImage } from "@/components/ui/ProductImage";
import { ProductDetailsModal } from "./ProductDetailsModal";
import { ProductHoverCard } from "./ProductHoverCard";

interface ProductCardProps {
  product: ProductResult;
  quantity: number;
  onAdd: (product: ProductResult) => void;
  onRemove: (productId: number) => void;
  onUpdateQty: (productId: number, qty: number) => void;
  /** For the phone's sideways strip: shorter image, tighter padding. Same card,
      so the two never drift apart in behaviour. */
  compact?: boolean;
}

/**
 * One result in the grid.
 *
 * The card shows four things in a fixed order: photo, name, price, action.
 * Anything the catalog cannot actually support (the placeholder "unit", a stock
 * count of 1000, a "General" category, scraped description fragments) is left
 * out by the helpers in lib/product rather than printed as fact.
 */
export function ProductCard({
  product,
  quantity,
  onAdd,
  onUpdateQty,
  compact = false,
}: ProductCardProps) {
  const [showDetails, setShowDetails] = useState(false);

  const inCart = quantity > 0;
  const soldOut = isOutOfStock(product.stock);
  const category = displayCategory(product.category);
  const lowStock = lowStockLabel(product.stock, product.unit);
  const description = cleanDescription(product.description);

  /* What pointing at a card reveals. Everything here came down with the search
     results, so nothing is fetched and nothing is charged for. */
  const hoverPanel = (
    <>
      {category && (
        <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-ink-faint">
          {category}
        </p>
      )}
      <p className="text-sm font-semibold leading-snug text-ink">
        {displayName(product.name)}
      </p>
      <p className="mt-1.5 text-base font-bold text-ink">
        {formatPrice(product.price_per_unit, product.unit)}
      </p>
      {description ? (
        <p className="mt-2 line-clamp-6 text-xs leading-relaxed text-ink-muted">
          {description}
        </p>
      ) : (
        <p className="mt-2 text-xs italic text-ink-faint">
          No description for this product.
        </p>
      )}
      <p className="mt-2.5 text-[11px] text-ink-faint">
        {soldOut ? "Out of stock" : lowStock || "Available"}
        {" · click for the full details"}
      </p>
    </>
  );

  return (
    <ProductHoverCard panel={hoverPanel} className="h-full">
    <div
      className={cn(
        "group relative flex h-full flex-col overflow-hidden rounded-card border bg-surface transition-shadow",
        inCart
          ? "border-brand-300 shadow-card-hover"
          : "border-line shadow-card hover:shadow-card-hover"
      )}
    >
      {/* The whole tile opens details. A button rather than a div so it is
          reachable by keyboard; the add controls below sit outside it. */}
      <button
        type="button"
        onClick={() => setShowDetails(true)}
        className="text-left"
        aria-label={`View details for ${displayName(product.name)}`}
      >
        <div className={cn("relative w-full overflow-hidden bg-surface p-2", compact ? "h-24" : "h-32")}>
          <ProductImage
            src={product.image_url}
            alt={product.name}
            category={product.category}
            iconClassName={compact ? "text-4xl" : "text-5xl"}
            className="transition-transform duration-300 group-hover:scale-105"
          />

          {inCart && (
            <span className="absolute right-2 top-2 flex items-center gap-1 rounded-full bg-brand-500 px-2 py-0.5 text-[11px] font-semibold text-white">
              <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
                <path
                  fillRule="evenodd"
                  d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0L3.3 9.7a1 1 0 1 1 1.4-1.4l3.3 3.3 6.8-6.8a1 1 0 0 1 1.4 0z"
                  clipRule="evenodd"
                />
              </svg>
              In cart
            </span>
          )}

          {soldOut && (
            <div className="absolute inset-0 flex items-center justify-center bg-surface/75">
              <span className="rounded-full bg-ink px-3 py-1 text-xs font-semibold text-white">
                Out of stock
              </span>
            </div>
          )}
        </div>

        {/* A fixed two-line block. Letting the title run to its natural height
            put the price and the button at a different height on every card,
            so a grid of them had no horizontal line to read along. The
            description lives in the details sheet: on this catalog it is a
            scraped fragment more often than it is useful. */}
        <div className="px-3 pt-2.5">
          {/* Always rendered, even when there is no category worth showing, so
              the titles of the cards in a row start on the same line. Leaving
              it out on the "General" products pushed their titles up and broke
              the horizontal rhythm of the grid. */}
          <p className="mb-0.5 truncate text-[11px] font-medium uppercase tracking-wide text-ink-faint">
            {category || " "}
          </p>
          <h3 className="line-clamp-2 min-h-[2.5rem] text-sm font-semibold leading-snug text-ink">
            {displayName(product.name)}
          </h3>
        </div>
      </button>

      {/* The whole tile above opens the same sheet, but an invisible click
          target is not a button: with nothing on the card saying so, the
          details looked like they had been removed. This is the affordance. */}
      <button
        type="button"
        onClick={() => setShowDetails(true)}
        className={cn(
          "px-3 pt-1 text-left font-semibold text-brand-600 hover:underline",
          compact ? "text-[11px]" : "text-xs"
        )}
      >
        See more details
      </button>

      <div className="mt-auto flex flex-col gap-2 p-3 pt-2">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-base font-bold text-ink">
            {formatPrice(product.price_per_unit, product.unit)}
          </span>
          {lowStock && (
            <span className="text-[11px] font-medium text-warn">{lowStock}</span>
          )}
        </div>

        {inCart ? (
          <div className="flex items-center justify-between rounded-control border border-brand-200 bg-brand-50 p-1">
            <button
              onClick={() => onUpdateQty(product.id, quantity - 1)}
              className="flex h-9 w-9 items-center justify-center rounded-[0.5rem] bg-surface text-lg font-semibold text-brand-600 shadow-card transition-colors hover:bg-brand-100"
              aria-label={`Remove one ${displayName(product.name)}`}
            >
              −
            </button>
            <span className="min-w-8 text-center text-sm font-semibold tabular-nums text-ink">
              {quantity}
            </span>
            <button
              onClick={() => onUpdateQty(product.id, quantity + 1)}
              className="flex h-9 w-9 items-center justify-center rounded-[0.5rem] bg-surface text-lg font-semibold text-brand-600 shadow-card transition-colors hover:bg-brand-100"
              aria-label={`Add one more ${displayName(product.name)}`}
            >
              +
            </button>
          </div>
        ) : (
          /* Soft rather than solid. Twenty four solid orange bars on one screen
             is the same mistake the gradient header made: if everything shouts,
             the actual primary action (Checkout) has nothing left to shout
             with. It fills in on hover, so it still reads as the button. */
          <button
            onClick={() => onAdd(product)}
            disabled={soldOut}
            className="h-10 w-full rounded-control border border-brand-200 bg-brand-50 text-sm font-semibold text-brand-700 transition-colors hover:bg-brand-500 hover:text-white active:scale-[0.98] disabled:cursor-not-allowed disabled:border-line disabled:bg-surface-sunken disabled:text-ink-faint"
          >
            {soldOut ? "Not offered" : "Book this"}
          </button>
        )}
      </div>

      {showDetails && (
        <ProductDetailsModal
          product={product}
          onClose={() => setShowDetails(false)}
          onAdd={soldOut ? undefined : onAdd}
        />
      )}
    </div>
    </ProductHoverCard>
  );
}
