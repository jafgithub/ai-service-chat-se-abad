"use client";

import { useEffect, useState } from "react";

import { paymentsApi } from "@/lib/api";
import type { Account, PaymentMethod, ProviderOffer, ServiceResult, Slot } from "@/lib/api";
import { formatDuration, formatWhen } from "@/lib/datetime";
import { formatMoney } from "@/lib/service";
import { Field } from "@/components/ui/Field";
import { cn } from "@/lib/utils";

/**
 * The last screen before anything is committed.
 *
 * Everything on it is what the server will actually be told, stated plainly:
 * whose diary, which service, when, how long, and what it costs. The price is
 * the provider's, taken from the offer that was chosen, never the service's
 * guide figure. If those two ever differ on screen the customer is right to
 * distrust both.
 *
 * The payment section is honest about where this stands. Payments move into the
 * booking flow in a later phase, so nothing here takes money, and the screen
 * says so rather than implying a card will be charged. It asks the server which
 * methods it can actually take, so what it promises matches what is configured.
 */

/**
 * What the customer has chosen to add for the provider.
 *
 * A union rather than a percentage and an amount side by side, because two
 * nullable numbers can express states that do not exist ("18% and also $40")
 * and this cannot. The server is told the percentage when there is one and
 * works the money out itself; the typed amount is only ever sent when they
 * actually typed one.
 */
export type TipChoice =
  | { kind: "none" }
  | { kind: "percent"; percent: number }
  | { kind: "custom"; amount: string };

/** The percentages offered. Must match job_service.TIP_PERCENTS on the server,
 *  which refuses anything else. */
export const TIP_PERCENTS = [15, 18, 20] as const;

/** Mirrors job_service.tip_cap. Shown so somebody typing 5000 finds out here
 *  rather than discovering the clamp on the confirmation screen. */
export function tipCap(price: number): number {
  return Math.round(Math.min(Math.max(price, 0) * 2, 500) * 100) / 100;
}

/** What the chosen tip is worth, for display only. The server decides the
 *  figure that is actually charged. */
export function tipValue(choice: TipChoice, price: number): number {
  if (choice.kind === "percent") {
    return Math.round(price * choice.percent) / 100;
  }
  if (choice.kind === "custom") {
    const typed = Number.parseFloat(choice.amount);
    if (!Number.isFinite(typed) || typed <= 0) return 0;
    return Math.round(Math.min(typed, tipCap(price)) * 100) / 100;
  }
  return 0;
}

interface BookingReviewProps {
  service: ServiceResult;
  offer: ProviderOffer;
  slot: Slot;
  account: Account | null;
  address: string;
  onAddressChange: (value: string) => void;
  notes: string;
  onNotesChange: (value: string) => void;
  method: PaymentMethod;
  onMethodChange: (method: PaymentMethod) => void;
  tip: TipChoice;
  onTipChange: (tip: TipChoice) => void;
  /** Set when the booking attempt failed, so the reason sits with the button. */
  failure?: string;
}

/** How each method is described to somebody who has never heard of "stripe".
 *  The same three the shop offers, worded for a visit rather than a delivery. */
const METHODS: Record<PaymentMethod, { title: string; hint: string; icon: string }> = {
  cod:    { title: "Cash on the day", hint: "Pay the provider when the work is done", icon: "💵" },
  stripe: { title: "Card",            hint: "Also Apple Pay and Google Pay",          icon: "💳" },
  paypal: { title: "PayPal",          hint: "Also Venmo",                             icon: "🅿️" },
};

export function BookingReview({
  service, offer, slot, account, address, onAddressChange, notes, onNotesChange,
  method, onMethodChange, tip, onTipChange, failure,
}: BookingReviewProps) {
  const tipping = tipValue(tip, offer.price);
  const total = Math.round((offer.price + tipping) * 100) / 100;
  const cap = tipCap(offer.price);
  const typedOver =
    tip.kind === "custom" && (Number.parseFloat(tip.amount) || 0) > cap;
  /* Cash is always offered: it needs no provider, and if the server has it
     switched off the booking call says so rather than us guessing here. The
     online ones depend on what is configured, so a deployment with no Stripe
     keys simply does not show a card option instead of showing one that fails
     at the last step. */
  const [available, setAvailable] = useState<PaymentMethod[]>(["cod"]);

  useEffect(() => {
    let dropped = false;
    paymentsApi
      .list()
      .then(({ enabled, providers }) => {
        if (dropped || !enabled) return;
        const online = providers.filter(
          (p): p is PaymentMethod => p === "stripe" || p === "paypal",
        );
        setAvailable(["cod", ...online]);
      })
      // Silent: cash still works, and an error about payment methods on a
      // screen that has not asked for money yet is noise.
      .catch(() => {});
    return () => { dropped = true; };
  }, []);

  return (
    <div className="space-y-4">
      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
          Your appointment
        </h3>
        <dl className="divide-y divide-line rounded-card border border-line">
          <Row label="Service" value={service.name} />
          <Row label="Provider" value={offer.business_name} sub={offer.city ?? undefined} />
          <Row label="When" value={formatWhen(slot.starts_at)} strong />
          <Row label="How long" value={formatDuration(offer.duration_minutes)} />
          <Row
            label="Price"
            value={formatMoney(offer.price)}
            sub="Set by this provider for this service"
            strong={tipping === 0}
          />
          {tipping > 0 && <Row label="Tip" value={formatMoney(tipping)} />}
          {tipping > 0 && (
            <Row label="Total" value={formatMoney(total)} strong />
          )}
        </dl>
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
          Add a tip
        </h3>

        <div className="rounded-card border border-line p-3">
          <p className="mb-2.5 text-xs leading-relaxed text-ink-muted">
            Optional, and all of it goes to {offer.business_name}.
          </p>

          <div className="flex flex-wrap gap-2">
            <TipButton
              label="No tip"
              chosen={tip.kind === "none"}
              onClick={() => onTipChange({ kind: "none" })}
            />
            {TIP_PERCENTS.map((percent) => (
              <TipButton
                key={percent}
                label={`${percent}%`}
                sub={formatMoney(Math.round(offer.price * percent) / 100)}
                chosen={tip.kind === "percent" && tip.percent === percent}
                onClick={() => onTipChange({ kind: "percent", percent })}
              />
            ))}
            <TipButton
              label="Other"
              chosen={tip.kind === "custom"}
              onClick={() =>
                onTipChange({
                  kind: "custom",
                  amount: tip.kind === "custom" ? tip.amount : "",
                })
              }
            />
          </div>

          {tip.kind === "custom" && (
            <div className="mt-3">
              <label
                htmlFor="tip-amount"
                className="mb-1 block text-xs font-medium text-ink-muted"
              >
                How much would you like to add?
              </label>
              <input
                id="tip-amount"
                type="number"
                inputMode="decimal"
                min={0}
                max={cap}
                step="0.01"
                value={tip.amount}
                onChange={(e) =>
                  onTipChange({ kind: "custom", amount: e.target.value })
                }
                placeholder="0.00"
                className="h-10 w-32 rounded-control border border-line bg-surface px-3 text-sm text-ink
                           focus:border-brand-500 focus:outline-none"
              />
              {typedOver && (
                <p className="mt-1.5 text-xs text-warn">
                  The most that can be added to this job is {formatMoney(cap)}, so
                  that is what will be charged.
                </p>
              )}
            </div>
          )}
        </div>
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
          You
        </h3>
        <div className="rounded-card border border-line px-3 py-2.5">
          <p className="text-sm font-medium text-ink">{account?.name || "Your account"}</p>
          {account?.email && <p className="text-xs text-ink-muted">{account.email}</p>}
        </div>
      </section>

      <Field
        label="Where the work is"
        value={address}
        onChange={onAddressChange}
        placeholder="Street, town, postcode"
        hint="Leave blank to use the address on your account."
      />

      <Field
        label="Anything they should know"
        value={notes}
        onChange={onNotesChange}
        rows={3}
        placeholder="Where to park, which door, the dog is friendly…"
      />

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
          How you will pay
        </h3>

        <div className="space-y-2">
          {available.map((id) => {
            const option = METHODS[id];
            const chosen = method === id;
            return (
              <button
                key={id}
                type="button"
                onClick={() => onMethodChange(id)}
                aria-pressed={chosen}
                className={cn(
                  "flex w-full items-center gap-3 rounded-control border px-3 py-2.5 text-left transition-colors",
                  chosen
                    ? "border-brand-500 bg-brand-50"
                    : "border-line bg-surface hover:bg-surface-hover"
                )}
              >
                <span className="text-xl" aria-hidden>{option.icon}</span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-ink">{option.title}</span>
                  <span className="block text-xs text-ink-muted">{option.hint}</span>
                </span>
                <span
                  className={cn(
                    "flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border",
                    chosen ? "border-brand-500 bg-brand-500 text-white" : "border-line-strong"
                  )}
                  aria-hidden
                >
                  {chosen && (
                    <svg className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" clipRule="evenodd"
                            d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0L3.3 9.7a1 1 0 1 1 1.4-1.4l3.3 3.3 6.8-6.8a1 1 0 0 1 1.4 0z" />
                    </svg>
                  )}
                </span>
              </button>
            );
          })}
        </div>

        <p className="mt-2 text-xs leading-relaxed text-ink-muted">
          {method === "cod"
            ? tipping > 0
              ? `Nothing is taken now. You hand ${offer.business_name} ${formatMoney(total)} once the work is done, the tip included.`
              : `Nothing is taken now. You settle up with ${offer.business_name} once the work is done.`
            : tipping > 0
              ? `Your time is held either way. We will take you to their secure payment page next for ${formatMoney(total)}, and you can still pay on the day if you change your mind.`
              : "Your time is held either way. We will take you to their secure payment page next, and you can still pay on the day if you change your mind."}
        </p>
      </section>

      {failure && (
        <p role="alert" className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
          {failure}
        </p>
      )}
    </div>
  );
}

function TipButton({
  label, sub, chosen, onClick,
}: {
  label: string;
  sub?: string;
  chosen: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={chosen}
      className={cn(
        "min-w-[68px] rounded-control border px-3 py-2 text-center transition-colors",
        chosen
          ? "border-brand-500 bg-brand-50"
          : "border-line bg-surface hover:bg-surface-hover"
      )}
    >
      <span className="block text-sm font-semibold text-ink">{label}</span>
      {sub && <span className="block text-[11px] text-ink-faint">{sub}</span>}
    </button>
  );
}

function Row({
  label, value, sub, strong,
}: {
  label: string;
  value: string;
  sub?: string;
  strong?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 px-3 py-2.5">
      <dt className="flex-shrink-0 text-xs text-ink-muted">{label}</dt>
      <dd className="min-w-0 text-right">
        <span className={strong ? "text-sm font-semibold text-ink" : "text-sm text-ink"}>
          {value}
        </span>
        {sub && <span className="mt-0.5 block text-[11px] text-ink-faint">{sub}</span>}
      </dd>
    </div>
  );
}
