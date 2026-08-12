"use client";

import type { ProviderOffer } from "@/lib/api";
import { formatMoney } from "@/lib/service";
import { formatDuration } from "@/lib/datetime";
import { Button } from "@/components/ui/Button";

/**
 * One firm that can do the job, with their terms.
 *
 * The price and the duration are this provider's own. The service's guide
 * figures are deliberately not repeated beside them: two numbers for the same
 * thing on one card invites the reader to work out which one they will be
 * charged, and the answer is always this one.
 *
 * "Soonest" is a claim the backend makes, not one this card works out. The next
 * free slot arrives already computed, and if it is missing the card says so
 * rather than implying the provider is busy.
 */

interface ProviderCardProps {
  offer: ProviderOffer;
  /** Marked as the top of the ranked list, with the reason spelled out. */
  best?: boolean;
  onChoose: (offer: ProviderOffer) => void;
  onViewProfile: (offer: ProviderOffer) => void;
}

export function ProviderCard({ offer, best, onChoose, onViewProfile }: ProviderCardProps) {
  return (
    <div className="rounded-card border border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-card-hover">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-ink">{offer.business_name}</h3>
            {best && (
              <span className="rounded-full bg-positive-soft px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-positive">
                Soonest
              </span>
            )}
          </div>
          {offer.city && <p className="mt-0.5 text-xs text-ink-muted">{offer.city}</p>}
        </div>

        <div className="flex-shrink-0 text-right">
          <p className="text-base font-bold leading-tight text-ink">
            {formatMoney(offer.price)}
          </p>
          <p className="text-xs text-ink-muted">{formatDuration(offer.duration_minutes)}</p>
        </div>
      </div>

      {offer.description && (
        <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-ink-muted">
          {offer.description}
        </p>
      )}

      <p className="mt-3 text-xs">
        {offer.next_available_label ? (
          <>
            <span className="text-ink-muted">Next free: </span>
            <span className="font-semibold text-ink">{offer.next_available_label}</span>
          </>
        ) : (
          /* No slot is not the same as no provider. They may simply be fully
             booked for the period we looked at, so the card stays and says so
             rather than disappearing. */
          <span className="text-ink-muted">No free times in the next few weeks</span>
        )}
      </p>

      <div className="mt-3 flex items-center gap-2">
        <Button
          size="sm"
          onClick={() => onChoose(offer)}
          disabled={!offer.next_available}
          className="flex-1"
        >
          {offer.next_available ? "Choose a time" : "Fully booked"}
        </Button>
        <Button size="sm" variant="secondary" onClick={() => onViewProfile(offer)}>
          Profile
        </Button>
      </div>
    </div>
  );
}
