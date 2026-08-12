"use client";

import { useEffect, useMemo, useState } from "react";
import type { CustomerIn, PaymentMethod } from "@/lib/api";
import { paymentsApi } from "@/lib/api";
import type { CartItem } from "@/hooks/useCart";
import type { GeoPosition } from "@/hooks/useGeolocation";
import { cn } from "@/lib/utils";
import { displayName } from "@/lib/product";

/** Delivery slots offered at checkout. Stored verbatim so the timezone is never ambiguous. */
const TIME_SLOTS = ["5:00 PM EST", "8:00 PM EST"];

export interface DeliverySlot {
  delivery_date: string;  // "YYYY-MM-DD"
  delivery_time: string;  // one of TIME_SLOTS
  delivery_notes: string; // optional free text, "" when not filled in
}

/**
 * Earliest selectable delivery day — tomorrow, in the user's own timezone.
 * "en-CA" formats as YYYY-MM-DD; toISOString() would shift the day for anyone
 * behind UTC and could offer today by mistake.
 */
function tomorrowISO(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toLocaleDateString("en-CA");
}

/** How each method is described to a shopper, who has never heard of "stripe". */
const METHOD_LABELS: Record<PaymentMethod, { title: string; hint: string; icon: string }> = {
  cod:    { title: "Cash on delivery", hint: "Pay the driver when your order arrives", icon: "💵" },
  stripe: { title: "Card", hint: "Also Apple Pay and Google Pay", icon: "💳" },
  paypal: { title: "PayPal", hint: "Also Venmo", icon: "🅿️" },
};

interface CustomerInfoFormProps {
  items: CartItem[];
  subtotal?: number;
  tax?: number;
  total: number;
  position: GeoPosition | null;
  onSubmit: (customer: CustomerIn, delivery: DeliverySlot, method: PaymentMethod) => void;
  onCancel: () => void;
  isLoading: boolean;
}

export function CustomerInfoForm({
  items,
  subtotal,
  tax,
  total,
  position,
  onSubmit,
  onCancel,
  isLoading,
}: CustomerInfoFormProps) {
  const [form, setForm] = useState<CustomerIn>({
    name: "",
    email: "",
    phone: "",
    address: "",
    latitude: position?.latitude,
    longitude: position?.longitude,
  });
  const [delivery, setDelivery] = useState<DeliverySlot>({
    delivery_date: "",
    delivery_time: "",
    delivery_notes: "",
  });
  type FieldKey = keyof CustomerIn | keyof DeliverySlot;
  const [errors, setErrors] = useState<Partial<Record<FieldKey, string>>>({});

  /* Which methods this shop can actually take. Cash is always offered: it needs
     no provider, and if the server has it switched off the order endpoint says
     so rather than us guessing here. The online ones depend on what is
     configured, so a shop with no Stripe keys simply does not show a card
     option instead of showing one that fails at the last step. */
  const [methods, setMethods] = useState<PaymentMethod[]>(["cod"]);
  const [method, setMethod] = useState<PaymentMethod>("cod");
  useEffect(() => {
    let dropped = false;
    paymentsApi
      .list()
      .then(({ enabled, providers }) => {
        if (dropped || !enabled) return;
        const online = providers.filter(
          (p): p is PaymentMethod => p === "stripe" || p === "paypal",
        );
        setMethods(["cod", ...online]);
      })
      .catch(() => {});
    return () => { dropped = true; };
  }, []);

  const minDate = useMemo(() => tomorrowISO(), []);
  const itemCount = items.reduce((sum, i) => sum + i.quantity, 0);

  const validate = (): boolean => {
    const errs: Partial<Record<FieldKey, string>> = {};
    if (!form.name.trim()) errs.name = "Name is required";
    if (!form.email.trim()) errs.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email))
      errs.email = "Enter a valid email";
    if (!form.phone?.trim()) errs.phone = "Phone is required";

    // `min` on the input is only a browser hint — a typed date can bypass it.
    if (!delivery.delivery_date) errs.delivery_date = "Pick a day";
    else if (delivery.delivery_date < minDate)
      errs.delivery_date = "The earliest we can attend is tomorrow";
    if (!delivery.delivery_time) errs.delivery_time = "Pick a time";

    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    onSubmit(
      { ...form, latitude: position?.latitude, longitude: position?.longitude },
      delivery,
      method
    );
  };

  const controlClass = (hasError: boolean) =>
    cn(
      "h-11 w-full rounded-control border bg-surface px-3 text-sm text-ink transition-colors placeholder:text-ink-faint",
      hasError ? "border-danger" : "border-line focus:border-brand-300"
    );

  const field = (
    id: keyof CustomerIn,
    label: string,
    type = "text",
    placeholder = "",
    optional = false
  ) => (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-ink-muted">
        {label}
        {optional && <span className="ml-1 font-normal text-ink-faint">(optional)</span>}
      </label>
      <input
        id={id}
        type={type}
        value={(form[id] as string) ?? ""}
        onChange={(e) => setForm((p) => ({ ...p, [id]: e.target.value }))}
        placeholder={placeholder}
        aria-invalid={Boolean(errors[id])}
        className={controlClass(Boolean(errors[id]))}
      />
      {errors[id] && <p className="mt-1 text-xs text-danger">{errors[id]}</p>}
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur-sm sm:items-center sm:p-4">
      {/* dvh, not vh: on mobile `vh` measures the viewport with the browser's
          address bar hidden, so a 90vh sheet is taller than what can actually
          be seen and the pinned buttons fall below the fold. `dvh` tracks the
          visible height, so Confirm stays on screen. Only the middle scrolls. */}
      <div className="flex max-h-[92dvh] w-full max-w-md flex-col overflow-hidden rounded-sheet bg-surface shadow-pop">

        <div className="flex shrink-0 items-center justify-between border-b border-line px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-ink">Checkout</h2>
            <p className="mt-0.5 text-xs text-ink-muted">
              {itemCount} item{itemCount === 1 ? "" : "s"} · ${total.toFixed(2)}
            </p>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="flex h-9 w-9 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink"
            aria-label="Back to cart"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
          <div className="chat-scroll flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-5 py-4">

            <section>
              <h3 className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                Contact
              </h3>
              <div className="flex flex-col gap-3">
                {field("name", "Full name", "text", "Your name")}
                {field("email", "Email", "email", "you@example.com")}
                {field("phone", "Phone", "tel", "Your phone number")}
              </div>
              <p className="mt-2 text-xs text-ink-faint">
                Your receipt goes to this email address.
              </p>
            </section>

            <section>
              <h3 className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                Delivery
              </h3>
              <div className="flex flex-col gap-3">
                {field("address", "Address", "text", "Building, street, area", true)}

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="delivery_date" className="mb-1 block text-xs font-medium text-ink-muted">
                      Date
                    </label>
                    <input
                      id="delivery_date"
                      type="date"
                      min={minDate}
                      value={delivery.delivery_date}
                      onChange={(e) => setDelivery((p) => ({ ...p, delivery_date: e.target.value }))}
                      aria-invalid={Boolean(errors.delivery_date)}
                      className={controlClass(Boolean(errors.delivery_date))}
                    />
                    {errors.delivery_date && (
                      <p className="mt-1 text-xs text-danger">{errors.delivery_date}</p>
                    )}
                  </div>

                  <div>
                    <label htmlFor="delivery_time" className="mb-1 block text-xs font-medium text-ink-muted">
                      Time
                    </label>
                    <select
                      id="delivery_time"
                      value={delivery.delivery_time}
                      onChange={(e) => setDelivery((p) => ({ ...p, delivery_time: e.target.value }))}
                      aria-invalid={Boolean(errors.delivery_time)}
                      className={controlClass(Boolean(errors.delivery_time))}
                    >
                      <option value="" disabled>Choose</option>
                      {TIME_SLOTS.map((slot) => (
                        <option key={slot} value={slot}>{slot}</option>
                      ))}
                    </select>
                    {errors.delivery_time && (
                      <p className="mt-1 text-xs text-danger">{errors.delivery_time}</p>
                    )}
                  </div>
                </div>

                <div>
                  <label htmlFor="delivery_notes" className="mb-1 block text-xs font-medium text-ink-muted">
                    Notes <span className="font-normal text-ink-faint">(optional)</span>
                  </label>
                  <textarea
                    id="delivery_notes"
                    rows={2}
                    value={delivery.delivery_notes}
                    onChange={(e) => setDelivery((p) => ({ ...p, delivery_notes: e.target.value }))}
                    placeholder="Gate code, apartment number, leave at door"
                    className="w-full resize-none rounded-control border border-line bg-surface px-3 py-2.5 text-sm text-ink transition-colors placeholder:text-ink-faint focus:border-brand-300"
                  />
                </div>

                {position && (
                  <p className="flex items-center gap-1.5 text-xs text-ink-muted">
                    <svg className="h-3.5 w-3.5 text-positive" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a2 2 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    Your location was captured to help the driver find you.
                  </p>
                )}
              </div>
            </section>

            <section>
              <h3 className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                Order summary
              </h3>
              <div className="rounded-card border border-line">
                <div className="flex flex-col gap-1.5 px-4 py-3">
                  {items.map((item) => (
                    <div key={item.product.id} className="flex justify-between gap-3 text-sm">
                      <span className="min-w-0 text-ink-muted">
                        <span className="line-clamp-1">{displayName(item.product.name)}</span>
                      </span>
                      <span className="flex-shrink-0 tabular-nums text-ink">
                        <span className="text-ink-faint">×{item.quantity}</span>{" "}
                        ${(item.product.price_per_unit * item.quantity).toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="flex flex-col gap-1 border-t border-line px-4 py-3">
                  {subtotal !== undefined && (
                    <div className="flex justify-between text-sm">
                      <span className="text-ink-muted">Subtotal</span>
                      <span className="tabular-nums text-ink">${subtotal.toFixed(2)}</span>
                    </div>
                  )}
                  {tax !== undefined && tax > 0 && (
                    <div className="flex justify-between text-sm">
                      <span className="text-ink-muted">Tax</span>
                      <span className="tabular-nums text-ink">${tax.toFixed(2)}</span>
                    </div>
                  )}
                  <div className="flex justify-between pt-1 text-base font-semibold">
                    <span className="text-ink">Total</span>
                    <span className="tabular-nums text-ink">${total.toFixed(2)}</span>
                  </div>
                </div>
              </div>

            </section>

            {/* The choice itself, not a note about what is coming. Radios rather
                than a dropdown: three options that each need a line of
                explanation, and hiding them behind a tap is how a shopper ends
                up on a card page they did not want. */}
            <section>
              <h3 className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-ink-faint">
                Payment
              </h3>
              <div className="flex flex-col gap-2" role="radiogroup" aria-label="Payment method">
                {methods.map((m) => {
                  const label = METHOD_LABELS[m];
                  const selected = method === m;
                  return (
                    <button
                      key={m}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      onClick={() => setMethod(m)}
                      className={cn(
                        "flex items-center gap-3 rounded-card border p-3 text-left transition-colors",
                        selected
                          ? "border-brand-400 bg-brand-50"
                          : "border-line hover:bg-surface-hover"
                      )}
                    >
                      <span className="text-xl" aria-hidden>{label.icon}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-semibold text-ink">{label.title}</span>
                        <span className="block text-xs text-ink-muted">{label.hint}</span>
                      </span>
                      <span
                        className={cn(
                          "flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border-2",
                          selected ? "border-brand-500" : "border-line-strong"
                        )}
                        aria-hidden
                      >
                        {selected && <span className="h-2.5 w-2.5 rounded-full bg-brand-500" />}
                      </span>
                    </button>
                  );
                })}
              </div>
              {method === "cod" && (
                <p className="mt-2 text-xs text-ink-muted">
                  Please have ${total.toFixed(2)} ready for the driver.
                </p>
              )}
            </section>
          </div>

          {/* Pinned below the scroll area so it stays on screen at any height. */}
          <div className="flex shrink-0 gap-3 border-t border-line bg-surface px-5 py-3">
            <button
              type="button"
              onClick={onCancel}
              className="h-11 flex-1 rounded-control border border-line text-sm font-medium text-ink transition-colors hover:bg-surface-hover"
            >
              Back
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="h-11 flex-[2] rounded-control bg-brand-500 text-sm font-semibold text-white transition-colors hover:bg-brand-600 disabled:opacity-60"
            >
              {isLoading
                ? "Placing order…"
                : method === "cod"
                  ? `Place order · $${total.toFixed(2)}`
                  : `Continue to payment · $${total.toFixed(2)}`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
