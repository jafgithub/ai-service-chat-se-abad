"use client";

import { useEffect, useState } from "react";
import type { CartItem } from "@/hooks/useCart";
import { cn } from "@/lib/utils";
import { cleanDescription, displayName, formatPrice } from "@/lib/product";
import { ProductImage } from "@/components/ui/ProductImage";
import { ProductDetailsModal } from "./ProductDetailsModal";

interface CartDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  items: CartItem[];
  subtotal?: number;
  tax?: number;
  total: number;
  onUpdateQty: (productId: number, qty: number) => void;
  onRemove: (productId: number) => void;
  onConfirmOrder: () => void;
}

export function CartDrawer({
  isOpen,
  onClose,
  items,
  subtotal,
  tax,
  total,
  onUpdateQty,
  onRemove,
  onConfirmOrder,
}: CartDrawerProps) {
  const [detailsFor, setDetailsFor] = useState<CartItem | null>(null);
  const count = items.reduce((sum, i) => sum + i.quantity, 0);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-ink/40 backdrop-blur-sm transition-opacity duration-300",
          isOpen ? "opacity-100" : "pointer-events-none opacity-0"
        )}
        onClick={onClose}
        aria-hidden
      />

      <div
        className={cn(
          "fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col bg-surface shadow-pop transition-transform duration-300 ease-out",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
        role="dialog"
        aria-modal={isOpen}
        aria-label="Your booking"
      >
        <div className="flex flex-shrink-0 items-center justify-between border-b border-line px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-ink">Your booking</h2>
            <p className="mt-0.5 text-xs text-ink-muted">
              {count === 0
                ? "Nothing added yet"
                : `${count} item${count === 1 ? "" : "s"}`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
            aria-label="Close cart"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="chat-scroll flex-1 overflow-y-auto px-4 py-4">
          {items.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-surface-sunken text-3xl">
                📅
              </div>
              <div>
                <p className="font-semibold text-ink">Your booking is empty</p>
                <p className="mt-1 text-sm text-ink-muted">
                  Ask the assistant for a product, or add one from the results.
                </p>
              </div>
              <button
                onClick={onClose}
                className="rounded-control border border-line px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-surface-hover"
              >
                Keep shopping
              </button>
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {items.map((item) => (
                <li
                  key={item.product.id}
                  className="flex gap-3 rounded-card border border-line p-2.5"
                >
                  <button
                    onClick={() => setDetailsFor(item)}
                    className="h-14 w-14 flex-shrink-0 overflow-hidden rounded-control bg-surface-sunken"
                    aria-label={`View details for ${displayName(item.product.name)}`}
                  >
                    <ProductImage
                      src={item.product.image_url}
                      alt={item.product.name}
                      category={item.product.category}
                      iconClassName="text-2xl"
                    />
                  </button>

                  <div className="flex min-w-0 flex-1 flex-col justify-between">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="line-clamp-2 text-sm font-medium leading-snug text-ink">
                          {displayName(item.product.name)}
                        </p>
                        {/* Description and seller both come from our own
                            tables, so showing them costs no provider call. */}
                        {cleanDescription(item.product.description) && (
                          <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-ink-muted">
                            {cleanDescription(item.product.description)}
                          </p>
                        )}
                        {item.seller && (
                          <p className="mt-0.5 text-[11px] text-ink-faint">
                            Sourced from {item.seller}
                          </p>
                        )}
                        <button
                          onClick={() => setDetailsFor(item)}
                          className="mt-1 text-[11px] font-semibold text-brand-600 hover:underline"
                        >
                          Show more
                        </button>
                      </div>
                      <button
                        onClick={() => onRemove(item.product.id)}
                        className="ml-auto flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-control text-ink-faint transition-colors hover:bg-danger-soft hover:text-danger"
                        aria-label={`Remove ${displayName(item.product.name)} from cart`}
                      >
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>

                    <div className="mt-1.5 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1 rounded-control border border-line">
                        <button
                          onClick={() => onUpdateQty(item.product.id, item.quantity - 1)}
                          className="flex h-8 w-8 items-center justify-center rounded-l-[0.5rem] text-base font-semibold text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
                          aria-label="Decrease quantity"
                        >
                          −
                        </button>
                        <span className="min-w-6 text-center text-sm font-semibold tabular-nums text-ink">
                          {item.quantity}
                        </span>
                        <button
                          onClick={() => onUpdateQty(item.product.id, item.quantity + 1)}
                          className="flex h-8 w-8 items-center justify-center rounded-r-[0.5rem] text-base font-semibold text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
                          aria-label="Increase quantity"
                        >
                          +
                        </button>
                      </div>

                      <div className="text-right">
                        <p className="text-sm font-semibold tabular-nums text-ink">
                          ${(item.product.price_per_unit * item.quantity).toFixed(2)}
                        </p>
                        {item.quantity > 1 && (
                          <p className="text-[11px] text-ink-faint">
                            {formatPrice(item.product.price_per_unit, item.product.unit)} each
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {items.length > 0 && (
          <div className="flex-shrink-0 border-t border-line bg-surface px-5 py-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
            <dl className="mb-4 flex flex-col gap-1.5">
              {subtotal !== undefined && (
                <div className="flex items-center justify-between text-sm">
                  <dt className="text-ink-muted">Subtotal</dt>
                  <dd className="tabular-nums text-ink">${subtotal.toFixed(2)}</dd>
                </div>
              )}
              {tax !== undefined && tax > 0 && (
                <div className="flex items-center justify-between text-sm">
                  <dt className="text-ink-muted">Tax</dt>
                  <dd className="tabular-nums text-ink">${tax.toFixed(2)}</dd>
                </div>
              )}
              <div className="flex items-center justify-between border-t border-line pt-2">
                <dt className="font-medium text-ink">Total</dt>
                <dd className="text-xl font-bold tabular-nums text-ink">${total.toFixed(2)}</dd>
              </div>
            </dl>

            <button
              onClick={() => { onClose(); onConfirmOrder(); }}
              className="h-12 w-full rounded-control bg-brand-500 text-base font-semibold text-white transition-colors hover:bg-brand-600 active:scale-[0.99]"
            >
              Checkout
            </button>
            <p className="mt-2 text-center text-xs text-ink-faint">
              Your details and a time on the next step
            </p>
          </div>
        )}
      </div>

      {detailsFor && (
        <ProductDetailsModal
          product={detailsFor.product}
          seller={detailsFor.seller}
          productUrl={detailsFor.productUrl}
          onClose={() => setDetailsFor(null)}
        />
      )}
    </>
  );
}
