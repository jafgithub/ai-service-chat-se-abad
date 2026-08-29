"use client";

import { useState } from "react";

import { providerMeApi } from "@/lib/api";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/components/auth/AuthProvider";
import { ProviderShell } from "@/components/provider/ProviderShell";
import { Empty, Failed, Loading } from "@/components/ui/States";
import { formatTime, groupSlotsByDay } from "@/lib/datetime";
import { formatMoney } from "@/lib/service";
import { cn } from "@/lib/utils";

/**
 * The diary.
 *
 * Grouped by day rather than listed flat, because that is how somebody plans a
 * morning: what is on Wednesday, in order, with the addresses together. The
 * customer's phone number is a link, so it can be tapped on the way there.
 *
 * There is no cancel button. The API gives providers no way to cancel somebody
 * else's booking, and drawing a button that always fails would be worse than
 * not drawing one. Provider-side cancellation is a real gap and is listed as
 * one.
 */
export default function ProviderAppointmentsPage() {
  const { status, account } = useAuth();
  const [upcomingOnly, setUpcomingOnly] = useState(true);

  const { data: rows, error, loading, reload } = useResource(
    (signal) => providerMeApi.appointments(upcomingOnly, signal),
    [upcomingOnly],
    { enabled: status === "signed-in" && account?.role === "provider" }
  );

  const days = rows ? groupSlotsByDay(rows) : [];

  return (
    <ProviderShell title="My diary" subtitle="Everything customers have booked with you.">
      <div className="mb-4 flex gap-1 rounded-control border border-line bg-surface p-0.5">
        {[
          { id: true, label: "Upcoming" },
          { id: false, label: "Everything" },
        ].map((t) => (
          <button
            key={String(t.id)}
            onClick={() => setUpcomingOnly(t.id)}
            aria-pressed={upcomingOnly === t.id}
            className={cn(
              "h-9 flex-1 rounded-[0.5rem] text-xs font-semibold transition-colors",
              upcomingOnly === t.id ? "bg-brand-50 text-brand-700" : "text-ink-muted hover:bg-surface-hover"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error ? (
        <Failed detail={error} onRetry={reload} />
      ) : loading || rows === null ? (
        <Loading label="Loading your diary" />
      ) : rows.length === 0 ? (
        <Empty
          icon="📖"
          title={upcomingOnly ? "Nothing booked yet" : "Nothing in the diary"}
          body="Bookings appear here the moment a customer takes one of your times. Make sure your services and hours are set."
          secondary={{ label: "Check my hours", href: "/provider/availability" }}
        />
      ) : (
        <div className="space-y-5">
          {days.map((day) => (
            <section key={day.key}>
              <h2 className="mb-2 text-sm font-semibold text-ink">{day.label}</h2>
              <ul className="space-y-2">
                {day.slots.map((row) => (
                  <li
                    key={row.appointment_id}
                    className={cn(
                      "rounded-card border bg-surface p-4 shadow-card",
                      row.status === "cancelled" ? "border-danger/30 opacity-70" : "border-line"
                    )}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-sm font-semibold text-ink">
                            {row.customer_name || "Customer"}
                          </h3>
                          {row.status !== "booked" && (
                            <span className={cn(
                              "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                              row.status === "cancelled"
                                ? "bg-danger-soft text-danger"
                                : "bg-surface-hover text-ink-muted"
                            )}>
                              {row.status}
                            </span>
                          )}
                        </div>
                        {row.address && (
                          <p className="mt-0.5 text-sm text-ink-muted">{row.address}</p>
                        )}
                        {row.notes && (
                          <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">{row.notes}</p>
                        )}
                      </div>

                      <div className="flex-shrink-0 text-right">
                        <p className="text-sm font-bold text-ink">{formatTime(row.starts_at)}</p>
                        <p className="text-[11px] text-ink-muted">to {formatTime(row.ends_at)}</p>
                        {row.total > 0 && (
                          <p className="mt-1.5 text-sm font-semibold text-ink">
                            {formatMoney(row.total, row.currency)}
                          </p>
                        )}
                        {row.tip > 0 && (
                          <p className="text-[11px] text-positive">
                            includes {formatMoney(row.tip, row.currency)} tip
                          </p>
                        )}
                        {/* The one operational fact: whether to ask for money
                            at the door. Everything else on this card is about
                            getting there. */}
                        {row.total > 0 && (
                          <p className="text-[11px] text-ink-muted">
                            {row.payment_status === "paid"
                              ? "Paid online"
                              : row.payment_method === "cod"
                                ? "Collect on the day"
                                : "Not paid yet"}
                          </p>
                        )}
                      </div>
                    </div>

                    {row.customer_phone && (
                      <a
                        href={`tel:${row.customer_phone}`}
                        className="mt-3 inline-flex h-9 items-center rounded-control border border-line px-4 text-sm font-semibold text-ink transition-colors hover:bg-surface-hover"
                      >
                        Call {row.customer_phone}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </ProviderShell>
  );
}
