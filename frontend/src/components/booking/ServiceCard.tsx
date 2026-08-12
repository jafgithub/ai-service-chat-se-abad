"use client";

import type { ServiceResult } from "@/lib/api";
import { cleanDescription, displayCategory, displayName, formatMoney } from "@/lib/service";
import { formatDuration } from "@/lib/datetime";
import { ServiceImage } from "@/components/ui/ServiceImage";
import { HoverCard } from "@/components/ui/HoverCard";
import { cn } from "@/lib/utils";

/**
 * One thing that could be done, as a card.
 *
 * The card is deliberately not the booking target. Its price and duration are
 * the service's guide figures, and every provider sets their own: two firms
 * offering "Emergency pipe leak repair" differ by an hour and thirty pounds in
 * the seed data alone. So the action is "Find providers", and the numbers here
 * are labelled as a guide rather than quoted as a price. Presenting them as the
 * price and then showing a different one at the review step is how a booking
 * flow loses somebody's trust two screens before it takes their money.
 */

interface ServiceCardProps {
  service: ServiceResult;
  onChoose: (service: ServiceResult) => void;
  /** True while this card's providers are being fetched. */
  busy?: boolean;
  /** The phone's sideways strip: shorter, tighter, same behaviour. */
  compact?: boolean;
}

export function ServiceCard({ service, onChoose, busy, compact }: ServiceCardProps) {
  const category = displayCategory(service.category);
  const description = cleanDescription(service.description);
  const duration = formatDuration(service.duration_minutes);
  const name = displayName(service.name);

  const hoverPanel = (
    <>
      {category && (
        <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-ink-faint">
          {category}
        </p>
      )}
      <p className="text-sm font-semibold leading-snug text-ink">{name}</p>
      <p className="mt-1.5 text-xs text-ink-muted">
        From {formatMoney(service.price_per_unit)}
        {duration && ` · about ${duration}`}
      </p>
      {description ? (
        <p className="mt-2 line-clamp-6 text-xs leading-relaxed text-ink-muted">
          {description}
        </p>
      ) : (
        <p className="mt-2 text-xs italic text-ink-faint">No description for this one.</p>
      )}
      <p className="mt-2.5 text-[11px] text-ink-faint">
        Click to see who can do it and when
      </p>
    </>
  );

  return (
    <HoverCard panel={hoverPanel} className="h-full">
      <div className="group flex h-full flex-col overflow-hidden rounded-card border border-line bg-surface shadow-card transition-shadow hover:shadow-card-hover">
        <div className={cn("relative w-full overflow-hidden bg-surface p-2", compact ? "h-20" : "h-24")}>
          <ServiceImage
            src={service.image_url}
            alt={name}
            category={service.category}
            iconClassName={compact ? "text-3xl" : "text-4xl"}
            className="transition-transform duration-300 group-hover:scale-105"
          />

          {service.emergency && (
            /* Only where it is true. A badge on everything says nothing, and
               "emergency" on a routine inspection would be a lie that costs
               somebody a call-out rate. */
            <span className="absolute left-2 top-2 rounded-full bg-danger px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
              Out of hours
            </span>
          )}
        </div>

        <div className="px-3 pt-2.5">
          {/* Always rendered, even when empty, so the titles of the cards in a
              row all start on the same line. */}
          <p className="mb-0.5 truncate text-[11px] font-medium uppercase tracking-wide text-ink-faint">
            {category || " "}
          </p>
          <h3 className="line-clamp-2 min-h-[2.5rem] text-sm font-semibold leading-snug text-ink">
            {name}
          </h3>
          {description && !compact && (
            <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-ink-muted">
              {description}
            </p>
          )}
        </div>

        <div className="mt-auto flex flex-col gap-2 p-3 pt-2">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-sm font-bold text-ink">
              {/* "From", because this is the guide and the provider sets the
                  real one. */}
              From {formatMoney(service.price_per_unit)}
            </span>
            {duration && (
              <span className="text-[11px] font-medium text-ink-muted">{duration}</span>
            )}
          </div>

          <button
            onClick={() => onChoose(service)}
            disabled={busy}
            className="h-10 w-full rounded-control border border-brand-200 bg-brand-50 text-sm font-semibold text-brand-700 transition-colors hover:bg-brand-500 hover:text-white active:scale-[0.98] disabled:cursor-wait disabled:opacity-70"
          >
            {busy ? "Finding providers…" : "Find providers"}
          </button>
        </div>
      </div>
    </HoverCard>
  );
}
