"use client";

import { useState } from "react";
import Link from "next/link";

import { ApiError, bookingApi } from "@/lib/api";
import type { BookingSummary } from "@/lib/api";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/components/auth/AuthProvider";
import { PageShell } from "@/components/layout/PageShell";
import { Empty, Failed, Loading, SignInRequired } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { formatDay, formatDuration, formatTime } from "@/lib/datetime";
import { formatMoney } from "@/lib/service";
import { cn } from "@/lib/utils";

type Tab = "upcoming" | "past" | "cancelled";

const TABS: { id: Tab; label: string }[] = [
  { id: "upcoming", label: "Upcoming" },
  { id: "past", label: "Past" },
  { id: "cancelled", label: "Cancelled" },
];

/**
 * What is booked.
 *
 * The three tabs are three calls, because the server decides what counts as
 * past: it knows its own clock, and a browser working it out from a naive
 * datetime would disagree with it by however many hours the reader is from the
 * server. Filtering here would also quietly redefine "cancelled", which is a
 * status rather than a date.
 */
export default function BookingsPage() {
  const { status, expired } = useAuth();
  const [tab, setTab] = useState<Tab>("upcoming");
  const [cancelling, setCancelling] = useState<number | null>(null);
  // A cancellation that failed. Kept apart from the load failure, because one
  // means "we could not show your bookings" and the other means "your booking
  // is still on", and they must not read the same.
  const [actionFailure, setActionFailure] = useState("");

  const { data: rows, error, loading, reload } = useResource(
    (signal) => bookingApi.mine(tab, signal),
    [tab],
    { enabled: status === "signed-in" }
  );

  const cancel = async (row: BookingSummary) => {
    if (cancelling) return;
    setCancelling(row.appointment_id);
    setActionFailure("");
    try {
      await bookingApi.cancel(row.appointment_id);
      reload();
    } catch (err) {
      setActionFailure(
        err instanceof ApiError
          ? `${err.detail} Your booking has not been cancelled.`
          : "We could not reach the server, so your booking has not been cancelled."
      );
    } finally {
      setCancelling(null);
    }
  };

  if (status === "loading") {
    return (
      <PageShell title="My bookings">
        <Loading label="Checking your account" />
      </PageShell>
    );
  }

  if (status === "signed-out") {
    return (
      <PageShell title="My bookings">
        <SignInRequired what="your bookings" expired={expired} />
      </PageShell>
    );
  }

  return (
    <PageShell
      title="My bookings"
      subtitle="Everything you have booked, and what happened to it."
      action={
        <Link
          href="/chat"
          className="inline-flex h-11 items-center rounded-control bg-brand-500 px-5 text-sm font-semibold text-white transition-colors hover:bg-brand-600"
        >
          Book something
        </Link>
      }
    >
      <div className="mb-4 flex gap-1 rounded-control border border-line bg-surface p-0.5">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            aria-pressed={tab === t.id}
            className={cn(
              "h-9 flex-1 rounded-[0.5rem] text-xs font-semibold transition-colors",
              tab === t.id ? "bg-brand-50 text-brand-700" : "text-ink-muted hover:bg-surface-hover"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {actionFailure && (
        <p role="alert" className="mb-3 rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
          {actionFailure}
        </p>
      )}

      {error ? (
        <Failed detail={error} onRetry={reload} />
      ) : loading || rows === null ? (
        <Loading label="Loading your bookings" />
      ) : rows.length === 0 ? (
        <Empty
          icon={tab === "upcoming" ? "📅" : "🗂️"}
          title={
            tab === "upcoming"
              ? "Nothing booked yet"
              : tab === "past" ? "Nothing in the past" : "Nothing cancelled"
          }
          body={
            tab === "upcoming"
              ? "When you book somebody, it will show up here with the time and the reference."
              : undefined
          }
          secondary={tab === "upcoming" ? { label: "Find a service", href: "/chat" } : undefined}
        />
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => (
            <li key={row.appointment_id} className="rounded-card border border-line bg-surface p-4 shadow-card">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-sm font-semibold text-ink">
                      {row.service || "Service"}
                    </h2>
                    <StatusPill status={row.status} />
                  </div>
                  <p className="mt-0.5 text-sm text-ink-muted">{row.provider_name || "Provider"}</p>
                </div>

                <div className="flex-shrink-0 text-right">
                  <p className="text-sm font-bold text-ink">{formatMoney(row.price, row.currency)}</p>
                  <p className="text-[11px] text-ink-faint">
                    {row.payment_status === "paid" ? "Paid" : "Not paid yet"}
                  </p>
                </div>
              </div>

              <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-4">
                <Cell label="Date" value={formatDay(row.starts_at)} />
                <Cell label="Time" value={formatTime(row.starts_at)} />
                <Cell label="How long" value={durationOf(row)} />
                <Cell label="Reference" value={row.reference} />
              </dl>

              {row.notes && (
                <p className="mt-2 text-xs leading-relaxed text-ink-muted">{row.notes}</p>
              )}

              <div className="mt-3 flex flex-wrap items-center gap-2">
                {row.provider_phone && (
                  <a
                    href={`tel:${row.provider_phone}`}
                    className="inline-flex h-9 items-center rounded-control border border-line px-4 text-sm font-semibold text-ink transition-colors hover:bg-surface-hover"
                  >
                    Call {row.provider_phone}
                  </a>
                )}
                {/* Only shown where the backend would actually allow it. An
                    action that always fails is worse than no action. */}
                {row.status !== "cancelled" && row.status !== "completed" && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => cancel(row)}
                    disabled={cancelling === row.appointment_id}
                  >
                    {cancelling === row.appointment_id ? "Cancelling…" : "Cancel"}
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </PageShell>
  );
}

function durationOf(row: BookingSummary): string {
  const start = Date.parse(`${row.starts_at}Z`);
  const end = Date.parse(`${row.ends_at}Z`);
  // Both ends are naive, so pinning both to UTC cancels out: the difference is
  // right even though neither instant is.
  if (!Number.isFinite(start) || !Number.isFinite(end)) return "";
  return formatDuration(Math.round((end - start) / 60000));
}

function Cell({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div>
      <dt className="text-ink-faint">{label}</dt>
      <dd className="font-medium text-ink">{value}</dd>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const tone =
    status === "cancelled" ? "bg-danger-soft text-danger"
      : status === "completed" ? "bg-surface-hover text-ink-muted"
        : "bg-positive-soft text-positive";
  return (
    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide", tone)}>
      {status}
    </span>
  );
}
