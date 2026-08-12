"use client";

import { useState } from "react";
import Link from "next/link";

import { ApiError, requestsApi } from "@/lib/api";
import type { ServiceRequest } from "@/lib/api";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/components/auth/AuthProvider";
import { PageShell } from "@/components/layout/PageShell";
import { Empty, Failed, Loading, SignInRequired } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { formatDay } from "@/lib/datetime";
import { URGENCY_LABELS } from "@/lib/service";
import { cn } from "@/lib/utils";

/**
 * What the customer asked for, in their own words.
 *
 * This is not the conversation. The transcript is a record of how somebody was
 * helped and is full of the assistant's guesses; a request is the problem
 * itself, and it survives whether or not anybody could take it on. Which is
 * exactly why the ones that came to nothing are here too, rather than being
 * quietly dropped when no provider covered them.
 */
export default function RequestsPage() {
  const { status, expired } = useAuth();
  const [closing, setClosing] = useState<number | null>(null);
  const [actionFailure, setActionFailure] = useState("");

  const { data: rows, error, loading, reload } = useResource(
    (signal) => requestsApi.mine(signal),
    [],
    { enabled: status === "signed-in" }
  );

  const close = async (row: ServiceRequest) => {
    if (closing) return;
    setClosing(row.id);
    setActionFailure("");
    try {
      await requestsApi.close(row.id);
      reload();
    } catch (err) {
      setActionFailure(err instanceof ApiError ? err.detail : "We could not close that just now.");
    } finally {
      setClosing(null);
    }
  };

  if (status === "loading") {
    return (
      <PageShell title="My requests">
        <Loading label="Checking your account" />
      </PageShell>
    );
  }

  if (status === "signed-out") {
    return (
      <PageShell title="My requests">
        <SignInRequired what="what you have asked for" expired={expired} />
      </PageShell>
    );
  }

  return (
    <PageShell
      title="My requests"
      subtitle="What you have asked for, and what came of it."
      action={
        <Link
          href="/chat"
          className="inline-flex h-11 items-center rounded-control bg-brand-500 px-5 text-sm font-semibold text-white transition-colors hover:bg-brand-600"
        >
          Ask for something
        </Link>
      }
    >
      {actionFailure && (
        <p role="alert" className="mb-3 rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
          {actionFailure}
        </p>
      )}

      {error ? (
        <Failed detail={error} onRetry={reload} />
      ) : loading || rows === null ? (
        <Loading label="Loading your requests" />
      ) : rows.length === 0 ? (
        <Empty
          icon="📝"
          title="Nothing asked for yet"
          body="Describe a problem to the assistant and it will be recorded here, whether or not it turns into a booking."
          secondary={{ label: "Talk to the assistant", href: "/chat" }}
        />
      ) : (
        <ul className="space-y-3">
          {rows.map((row) => (
            <li key={row.id} className="rounded-card border border-line bg-surface p-4 shadow-card">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  {/* Their words, never rewritten. The matched service is shown
                      underneath as our reading of it, which is a different
                      claim and should look like one. */}
                  <p className="text-sm leading-relaxed text-ink">{row.description}</p>
                  <p className="mt-1 text-xs text-ink-muted">
                    {row.service_name ? `Matched to ${row.service_name}` : "Not matched to a service yet"}
                    {row.provider_name && ` · ${row.provider_name}`}
                  </p>
                </div>
                <StatusPill status={row.status} />
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-ink-faint">
                <span>Asked {formatDay(row.created_at)}</span>
                <span>{URGENCY_LABELS[row.urgency] ?? row.urgency}</span>
                {row.postcode && <span>{row.postcode}</span>}
              </div>

              {row.status !== "closed" && row.status !== "booked" && (
                <div className="mt-3">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => close(row)}
                    disabled={closing === row.id}
                  >
                    {closing === row.id ? "Closing…" : "No longer needed"}
                  </Button>
                </div>
              )}

              {row.status === "booked" && (
                <p className="mt-3 text-xs text-ink-muted">
                  This one became a booking.{" "}
                  <Link href="/bookings" className="font-semibold text-brand-600 hover:underline">
                    See it in my bookings
                  </Link>
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </PageShell>
  );
}

function StatusPill({ status }: { status: string }) {
  const tone =
    status === "booked" ? "bg-positive-soft text-positive"
      : status === "closed" ? "bg-surface-hover text-ink-muted"
        : status === "unserved" ? "bg-danger-soft text-danger"
          : "bg-warn-soft text-warn";
  return (
    <span className={cn("flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide", tone)}>
      {status}
    </span>
  );
}
