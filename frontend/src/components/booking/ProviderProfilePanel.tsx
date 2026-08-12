"use client";

import { providersApi } from "@/lib/api";
import { useResource } from "@/hooks/useResource";
import { formatDuration } from "@/lib/datetime";
import { formatMoney } from "@/lib/service";
import { Failed, Loading } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";

/**
 * A provider's public profile.
 *
 * Public in the strict sense: this is the same endpoint anybody can call
 * without an account, and it returns only what a business would put on its own
 * shop front. Their email is in the response and is deliberately not drawn
 * here; the phone number is, because somebody deciding whether to let a
 * stranger into their house may reasonably want to ring first.
 */

interface ProviderProfilePanelProps {
  providerId: number;
  /** Highlighted in the list of what they do, since it is what brought us here. */
  serviceId?: number;
  onBook: () => void;
}

export function ProviderProfilePanel({ providerId, serviceId, onBook }: ProviderProfilePanelProps) {
  const { data: provider, error, loading, reload } = useResource(
    (signal) => providersApi.detail(providerId, signal),
    [providerId]
  );

  if (error) return <Failed detail={error} onRetry={reload} />;
  if (loading || !provider) return <Loading label="Loading profile" rows={2} />;

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-base font-semibold text-ink">{provider.business_name}</h3>
        {provider.city && <p className="mt-0.5 text-sm text-ink-muted">{provider.city}</p>}
      </div>

      {provider.description && (
        <p className="text-sm leading-relaxed text-ink-muted">{provider.description}</p>
      )}

      <dl className="space-y-1.5 text-sm">
        {provider.contact_name && (
          <div className="flex gap-2">
            <dt className="w-24 flex-shrink-0 text-ink-muted">Contact</dt>
            <dd className="text-ink">{provider.contact_name}</dd>
          </div>
        )}
        {provider.phone && (
          <div className="flex gap-2">
            <dt className="w-24 flex-shrink-0 text-ink-muted">Phone</dt>
            <dd className="text-ink">
              <a href={`tel:${provider.phone}`} className="font-medium text-brand-600 hover:underline">
                {provider.phone}
              </a>
            </dd>
          </div>
        )}
        {provider.website && (
          <div className="flex gap-2">
            <dt className="w-24 flex-shrink-0 text-ink-muted">Website</dt>
            <dd className="min-w-0 truncate">
              {/* Somebody else's site: opened in a new tab so the booking stays
                  open behind it, and with noopener so their page cannot reach
                  back into ours. */}
              <a
                href={provider.website}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-brand-600 hover:underline"
              >
                {provider.website.replace(/^https?:\/\//, "")}
              </a>
            </dd>
          </div>
        )}
        {provider.postcode && (
          <div className="flex gap-2">
            <dt className="w-24 flex-shrink-0 text-ink-muted">Area</dt>
            <dd className="text-ink">{provider.postcode}</dd>
          </div>
        )}
      </dl>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
          What they do
        </p>
        <ul className="space-y-1.5">
          {provider.services.map((row) => (
            <li
              key={row.provider_service_id}
              className={
                row.service_id === serviceId
                  ? "flex items-baseline justify-between gap-3 rounded-control border border-brand-200 bg-brand-50 px-3 py-2"
                  : "flex items-baseline justify-between gap-3 rounded-control border border-line px-3 py-2"
              }
            >
              <span className="min-w-0 text-sm text-ink">{row.name}</span>
              <span className="flex-shrink-0 text-right text-xs">
                <span className="font-semibold text-ink">{formatMoney(row.price)}</span>
                <span className="ml-2 text-ink-muted">{formatDuration(row.duration_minutes)}</span>
              </span>
            </li>
          ))}
        </ul>
        {provider.services.length === 0 && (
          <p className="text-sm text-ink-muted">They have not listed anything yet.</p>
        )}
      </div>

      <Button onClick={onBook} className="w-full" size="lg">
        Choose a time
      </Button>
    </div>
  );
}
