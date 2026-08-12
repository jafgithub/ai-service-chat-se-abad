"use client";

import Link from "next/link";

import { providerMeApi } from "@/lib/api";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/components/auth/AuthProvider";
import { ProviderShell } from "@/components/provider/ProviderShell";
import { Failed, Loading } from "@/components/ui/States";
import { formatDay, formatTime } from "@/lib/datetime";
import { formatMoney } from "@/lib/service";

/**
 * What a provider sees first.
 *
 * Deliberately three counts and the next few jobs, rather than a wall of
 * numbers. The counts exist because each of them is a way of not getting work:
 * no services listed means nobody can find you, no hours set means nobody can
 * book you, and both are silent failures the provider would otherwise have to
 * infer from an empty diary.
 */
export default function ProviderDashboardPage() {
  const { status, account } = useAuth();
  const isProvider = status === "signed-in" && account?.role === "provider";

  // One call would be tidier, and there is no endpoint for it. Three in
  // parallel is what the API offers, and they either all arrive or the page
  // says it could not load; showing two thirds of a dashboard would leave a
  // provider reading a zero that is not true.
  const { data, error, loading, reload } = useResource(
    (signal) => Promise.all([
      providerMeApi.services(signal),
      providerMeApi.hours(signal),
      providerMeApi.appointments(true, signal),
    ]),
    [],
    { enabled: isProvider }
  );

  const [services, hours, diary] = data ?? [null, null, null];
  const active = services?.filter((s) => s.active) ?? [];

  return (
    <ProviderShell
      title={account?.name || "My business"}
      subtitle="Everything you need to start taking bookings."
    >
      {error ? (
        <Failed detail={error} onRetry={reload} />
      ) : loading || !services || !hours || !diary ? (
        <Loading label="Loading your business" />
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Tile
              label="Services listed"
              value={active.length}
              href="/provider/services"
              warn={active.length === 0}
              warning="Nobody can find you until you list at least one."
            />
            <Tile
              label="Days you work"
              value={hours.length}
              href="/provider/availability"
              warn={hours.length === 0}
              warning="Nobody can book you until you set your hours."
            />
            <Tile
              label="Upcoming jobs"
              value={diary.length}
              href="/provider/appointments"
            />
          </div>

          <section className="rounded-card border border-line bg-surface p-5 shadow-card">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold text-ink">Next few jobs</h2>
              <Link href="/provider/appointments" className="text-xs font-semibold text-brand-600 hover:underline">
                See the whole diary
              </Link>
            </div>

            {diary.length === 0 ? (
              <p className="text-sm text-ink-muted">
                Nothing booked at the moment. Bookings appear here as soon as a
                customer takes one of your times.
              </p>
            ) : (
              <ul className="divide-y divide-line">
                {diary.slice(0, 5).map((row) => (
                  <li key={row.appointment_id} className="flex items-baseline justify-between gap-3 py-2.5">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-ink">
                        {row.customer_name || "Customer"}
                      </p>
                      {row.address && (
                        <p className="truncate text-xs text-ink-muted">{row.address}</p>
                      )}
                    </div>
                    <p className="flex-shrink-0 text-right text-xs">
                      <span className="block font-semibold text-ink">{formatTime(row.starts_at)}</span>
                      <span className="block text-ink-muted">{formatDay(row.starts_at)}</span>
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {active.length > 0 && (
            <section className="rounded-card border border-line bg-surface p-5 shadow-card">
              <div className="mb-3 flex items-center justify-between gap-3">
                <h2 className="text-sm font-semibold text-ink">What you charge</h2>
                <Link href="/provider/services" className="text-xs font-semibold text-brand-600 hover:underline">
                  Change
                </Link>
              </div>
              <ul className="divide-y divide-line">
                {active.slice(0, 6).map((row) => (
                  <li key={row.provider_service_id} className="flex items-baseline justify-between gap-3 py-2">
                    <span className="min-w-0 truncate text-sm text-ink">{row.name}</span>
                    <span className="flex-shrink-0 text-xs">
                      <span className="font-semibold text-ink">
                        {formatMoney(row.price ?? row.guide_price)}
                      </span>
                      <span className="ml-2 text-ink-muted">
                        {row.duration_minutes ?? row.guide_duration ?? 60} min
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </ProviderShell>
  );
}

function Tile({
  label, value, href, warn, warning,
}: {
  label: string;
  value: number;
  href: string;
  warn?: boolean;
  warning?: string;
}) {
  return (
    <Link
      href={href}
      className="block rounded-card border border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-card-hover"
    >
      <p className="text-xs text-ink-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums text-ink">{value}</p>
      {warn && warning && (
        <p className="mt-1.5 text-xs font-medium text-warn">{warning}</p>
      )}
    </Link>
  );
}
