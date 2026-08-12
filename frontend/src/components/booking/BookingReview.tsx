"use client";

import { useEffect, useState } from "react";

import { paymentsApi } from "@/lib/api";
import type { Account, ProviderOffer, ServiceResult, Slot } from "@/lib/api";
import { formatDuration, formatWhen } from "@/lib/datetime";
import { formatMoney } from "@/lib/service";
import { Field } from "@/components/ui/Field";

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

interface BookingReviewProps {
  service: ServiceResult;
  offer: ProviderOffer;
  slot: Slot;
  account: Account | null;
  address: string;
  onAddressChange: (value: string) => void;
  notes: string;
  onNotesChange: (value: string) => void;
  /** Set when the booking attempt failed, so the reason sits with the button. */
  failure?: string;
}

const METHOD_NAMES: Record<string, string> = {
  cod: "cash on the day",
  stripe: "card",
  paypal: "PayPal",
};

export function BookingReview({
  service, offer, slot, account, address, onAddressChange, notes, onNotesChange, failure,
}: BookingReviewProps) {
  const [methods, setMethods] = useState<string[]>([]);

  useEffect(() => {
    let dropped = false;
    paymentsApi
      .list()
      .then(({ enabled, providers }) => {
        if (!dropped && enabled) setMethods(providers);
      })
      // Silent: how payment will work is worth saying when we know, and not
      // worth an error message when we do not.
      .catch(() => {});
    return () => { dropped = true; };
  }, []);

  const online = methods.filter((m) => m !== "cod").map((m) => METHOD_NAMES[m] ?? m);

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
            strong
          />
        </dl>
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
          Payment
        </h3>
        <div className="rounded-card border border-line bg-surface-sunken px-3 py-2.5">
          <p className="text-sm text-ink">
            Nothing is taken now. You settle up with {offer.business_name} for the
            work itself.
          </p>
          {online.length > 0 && (
            <p className="mt-1 text-xs text-ink-muted">
              Paying by {online.join(" or ")} through this app is coming shortly.
            </p>
          )}
        </div>
      </section>

      {failure && (
        <p role="alert" className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
          {failure}
        </p>
      )}
    </div>
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
