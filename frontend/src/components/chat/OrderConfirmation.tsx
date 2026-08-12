"use client";

import Link from "next/link";
import type { PlaceOrderResponse } from "@/lib/api";
import { displayName } from "@/lib/product";

interface OrderConfirmationProps {
  /** The order, once it has been read back. Null when only the number is known. */
  order: PlaceOrderResponse | null;
  /** Always known: it is either the order we placed or the id in the return URL. */
  orderId: number;
  /** True when payment succeeded but the provider's webhook has not landed yet. */
  awaitingConfirmation?: boolean;
  /** True when we arrived here from a payment provider rather than a free checkout. */
  paid?: boolean;
  onStartNewOrder: () => void;
}

export function OrderConfirmation({
  order,
  orderId,
  awaitingConfirmation = false,
  paid = false,
  onStartNewOrder,
}: OrderConfirmationProps) {
  const items = order?.items ?? [];
  // Cash orders are confirmed without any money changing hands, so this screen
  // must not imply it has been. It is also the last chance to tell them how
  // much to have ready.
  const isCash = order?.payment_method === "cod";

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-3 backdrop-blur-sm sm:items-center sm:p-4">
      <div className="flex max-h-[92dvh] w-full max-w-md flex-col overflow-hidden rounded-sheet bg-surface shadow-pop">
        <div className="flex-shrink-0 border-b border-line px-6 py-6 text-center">
          <div
            className={
              awaitingConfirmation
                ? "mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-warn-soft"
                : "mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-positive-soft"
            }
          >
            {awaitingConfirmation ? (
              <svg className="h-7 w-7 animate-spin text-warn" viewBox="0 0 24 24" fill="none" aria-hidden>
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" opacity="0.25" />
                <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
              </svg>
            ) : (
              <svg className="h-7 w-7 text-positive" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path
                  d="M5 13l4 4L19 7"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </div>

          <h2 className="text-xl font-semibold text-ink">
            {awaitingConfirmation
              ? "Payment received"
              : isCash
                ? "Order confirmed"
                : paid
                  ? "Payment complete"
                  : "Order confirmed"}
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            Order #{orderId}
            {awaitingConfirmation && " · confirming with your bank"}
          </p>
        </div>

        <div className="chat-scroll flex flex-col gap-4 overflow-y-auto px-6 py-5">
          {items.length > 0 ? (
            <div className="rounded-card border border-line">
              <p className="border-b border-line px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                What you ordered
              </p>
              <div className="flex flex-col gap-2 px-4 py-3">
                {items.map((item) => (
                  <div key={item.product_id} className="flex justify-between gap-3 text-sm">
                    <span className="text-ink-muted">
                      {displayName(item.product_name)}
                      <span className="text-ink-faint"> × {item.quantity}</span>
                    </span>
                    <span className="flex-shrink-0 tabular-nums font-medium text-ink">
                      ${item.subtotal.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex flex-col gap-1 border-t border-line px-4 py-3">
                {order?.subtotal !== undefined && (
                  <div className="flex justify-between text-sm">
                    <span className="text-ink-muted">Subtotal</span>
                    <span className="tabular-nums text-ink">${order.subtotal.toFixed(2)}</span>
                  </div>
                )}
                {order?.tax !== undefined && order.tax > 0 && (
                  <div className="flex justify-between text-sm">
                    <span className="text-ink-muted">Tax</span>
                    <span className="tabular-nums text-ink">${order.tax.toFixed(2)}</span>
                  </div>
                )}
                <div className="flex justify-between pt-1 text-base font-semibold">
                  <span className="text-ink">{isCash ? "To pay on delivery" : paid ? "Paid" : "Total"}</span>
                  <span className="tabular-nums text-ink">
                    ${(order?.total_amount ?? 0).toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            /* We know they paid, because the provider sent them here, but the
               key that identifies the order was not available. Say what is
               certainly true and nothing more. */
            <p className="rounded-card border border-line bg-surface-sunken px-4 py-3 text-sm text-ink-muted">
              Your payment went through and order #{orderId} is with the shop. The
              receipt is on its way to your email.
            </p>
          )}

          {(order?.delivery_date || order?.delivery_time) && (
            <div className="rounded-card border border-line px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
                Delivery
              </p>
              <p className="mt-1 text-sm font-medium text-ink">
                {[order.delivery_date, order.delivery_time].filter(Boolean).join(" · ")}
              </p>
              {order.delivery_notes && (
                <p className="mt-1 text-xs text-ink-muted">{order.delivery_notes}</p>
              )}
            </div>
          )}

          {isCash && (
            <div className="rounded-card border border-warn/30 bg-warn-soft px-4 py-3">
              <p className="text-sm font-semibold text-warn">
                Have ${(order?.total_amount ?? 0).toFixed(2)} ready for the driver
              </p>
              <p className="mt-0.5 text-xs text-ink-muted">
                You are paying in cash when your order arrives. Nothing has been charged.
              </p>
            </div>
          )}

          <p className="text-sm text-ink-muted">
            The shop has been notified and will contact you to arrange delivery.
          </p>
        </div>

        <div className="flex flex-shrink-0 gap-3 border-t border-line px-6 py-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
          <Link
            href="/"
            className="flex h-11 flex-1 items-center justify-center rounded-control border border-line text-sm font-medium text-ink transition-colors hover:bg-surface-hover"
          >
            Home
          </Link>
          <button
            onClick={onStartNewOrder}
            className="h-11 flex-1 rounded-control bg-brand-500 text-sm font-semibold text-white transition-colors hover:bg-brand-600"
          >
            Start a new order
          </button>
        </div>
      </div>
    </div>
  );
}
