"use client";

import { useState } from "react";

import { ApiError, providerMeApi } from "@/lib/api";
import type { WorkingDay } from "@/lib/api";
import { useResource } from "@/hooks/useResource";
import { useAuth } from "@/components/auth/AuthProvider";
import { ProviderShell } from "@/components/provider/ProviderShell";
import { Failed, Loading } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { toApiDateTime } from "@/lib/datetime";
import { cn } from "@/lib/utils";

/**
 * When this business works.
 *
 * The week is drawn as seven rows, always, including the days they are closed.
 * A list of only the open days looks the same whether Sunday is closed or
 * whether Sunday was never set up, and the difference is the difference between
 * a deliberate weekend and a provider losing a day's bookings without noticing.
 *
 * Weekday 0 is Monday, which is the API's convention and not JavaScript's. That
 * mismatch is exactly the kind of thing that silently shifts a whole week, so
 * the labels are indexed by the API's numbering here and nowhere else.
 */

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function ProviderAvailabilityPage() {
  const { status, account } = useAuth();
  const [busyDay, setBusyDay] = useState<number | null>(null);
  const [actionFailure, setActionFailure] = useState("");

  const { data: hours, error, loading, reload } = useResource(
    (signal) => providerMeApi.hours(signal),
    [],
    { enabled: status === "signed-in" && account?.role === "provider" }
  );

  // Time off
  const [offFrom, setOffFrom] = useState("");
  const [offTo, setOffTo] = useState("");
  const [offReason, setOffReason] = useState("");
  const [offSaving, setOffSaving] = useState(false);
  const [offSaved, setOffSaved] = useState("");
  const [offFailure, setOffFailure] = useState("");

  const save = async (weekday: number, opens: string, closes: string) => {
    if (closes <= opens) {
      setActionFailure("Closing time has to be after opening time.");
      return;
    }
    setBusyDay(weekday);
    setActionFailure("");
    try {
      await providerMeApi.saveHours(weekday, opens, closes);
      reload();
    } catch (err) {
      setActionFailure(err instanceof ApiError ? err.detail : "We could not save that just now.");
    } finally {
      setBusyDay(null);
    }
  };

  const close = async (weekday: number) => {
    setBusyDay(weekday);
    setActionFailure("");
    try {
      await providerMeApi.closeDay(weekday);
      reload();
    } catch (err) {
      setActionFailure(err instanceof ApiError ? err.detail : "We could not save that just now.");
    } finally {
      setBusyDay(null);
    }
  };

  const addTimeOff = async (e: React.FormEvent) => {
    e.preventDefault();
    if (offSaving) return;
    if (!offFrom || !offTo) {
      setOffFailure("Both dates are needed.");
      return;
    }
    if (offTo < offFrom) {
      setOffFailure("That period ends before it starts.");
      return;
    }

    setOffSaving(true);
    setOffFailure("");
    setOffSaved("");
    try {
      // Whole days: from the start of the first to the end of the last. Sending
      // midnight to midnight would leave the final day bookable, which is not
      // what somebody entering a holiday means.
      await providerMeApi.addTimeOff(
        toApiDateTime(offFrom, "00:00"),
        toApiDateTime(offTo, "23:59"),
        offReason
      );
      setOffSaved(`Blocked out ${offFrom} to ${offTo}.`);
      setOffFrom("");
      setOffTo("");
      setOffReason("");
    } catch (err) {
      setOffFailure(err instanceof ApiError ? err.detail : "We could not save that just now.");
    } finally {
      setOffSaving(false);
    }
  };

  return (
    <ProviderShell
      title="My hours"
      subtitle="When you work, and when you are away. This is what customers can book."
    >
      {actionFailure && (
        <p role="alert" className="mb-4 rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
          {actionFailure}
        </p>
      )}

      {error ? (
        <Failed detail={error} onRetry={reload} />
      ) : loading || hours === null ? (
        <Loading label="Loading your week" />
      ) : (
        <div className="space-y-5">
          <section className="rounded-card border border-line bg-surface p-5 shadow-card">
            <h2 className="mb-3 text-sm font-semibold text-ink">Your working week</h2>
            <ul className="divide-y divide-line">
              {DAYS.map((label, weekday) => (
                <DayRow
                  /* The saved hours in the key, so a row remounts with the
                     values that came back rather than an effect copying them
                     over what is being typed. */
                  key={`${weekday}:${hours.find((h) => h.weekday === weekday)?.opens_at ?? "-"}-${hours.find((h) => h.weekday === weekday)?.closes_at ?? "-"}`}
                  label={label}
                  weekday={weekday}
                  row={hours.find((h) => h.weekday === weekday) ?? null}
                  busy={busyDay === weekday}
                  onSave={save}
                  onClose={close}
                />
              ))}
            </ul>
          </section>

          <section className="rounded-card border border-line bg-surface p-5 shadow-card">
            <h2 className="text-sm font-semibold text-ink">Time off</h2>
            <p className="mt-1 text-xs leading-relaxed text-ink-muted">
              A holiday or a closure. Nothing can be booked in this period, even
              on days you normally work.
            </p>

            <form onSubmit={addTimeOff} className="mt-3 max-w-md space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="From" type="date" value={offFrom} onChange={setOffFrom} />
                <Field label="To" type="date" value={offTo} onChange={setOffTo} />
              </div>
              <Field label="Reason" value={offReason} onChange={setOffReason}
                     hint="Optional, and only for your own records." />

              {offFailure && (
                <p role="alert" className="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger">
                  {offFailure}
                </p>
              )}
              {offSaved && (
                <p role="status" className="rounded-control border border-positive/30 bg-positive-soft px-3 py-2 text-sm text-positive">
                  {offSaved}
                </p>
              )}

              <Button type="submit" disabled={offSaving}>
                {offSaving ? "Saving…" : "Block out these dates"}
              </Button>
            </form>
          </section>
        </div>
      )}
    </ProviderShell>
  );
}

function DayRow({
  label, weekday, row, busy, onSave, onClose,
}: {
  label: string;
  weekday: number;
  row: WorkingDay | null;
  busy: boolean;
  onSave: (weekday: number, opens: string, closes: string) => void;
  onClose: (weekday: number) => void;
}) {
  // Times come back as "09:00:00"; the input wants "09:00". The defaults are a
  // sensible working day for a business that has not opened this one yet.
  const [opens, setOpens] = useState(row?.opens_at.slice(0, 5) ?? "09:00");
  const [closes, setCloses] = useState(row?.closes_at.slice(0, 5) ?? "17:00");

  const open = Boolean(row);

  return (
    <li className="flex flex-wrap items-center gap-3 py-3">
      <span className={cn("w-24 flex-shrink-0 text-sm font-medium", open ? "text-ink" : "text-ink-faint")}>
        {label}
      </span>

      <div className="flex items-center gap-2">
        <input
          type="time"
          value={opens}
          onChange={(e) => setOpens(e.target.value)}
          aria-label={`${label} opening time`}
          className="h-10 rounded-control border border-line bg-surface px-2 text-sm text-ink focus:border-brand-300 focus:outline-none"
        />
        <span className="text-xs text-ink-faint">to</span>
        <input
          type="time"
          value={closes}
          onChange={(e) => setCloses(e.target.value)}
          aria-label={`${label} closing time`}
          className="h-10 rounded-control border border-line bg-surface px-2 text-sm text-ink focus:border-brand-300 focus:outline-none"
        />
      </div>

      <div className="ml-auto flex items-center gap-2">
        <Button size="sm" disabled={busy} onClick={() => onSave(weekday, opens, closes)}>
          {busy ? "…" : open ? "Update" : "Open this day"}
        </Button>
        {open && (
          /* "Close this day", not "Closed": beside an Update button, a lone
             "Closed" reads as a label saying the day is shut rather than the
             control that shuts it. */
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => onClose(weekday)}>
            Close this day
          </Button>
        )}
      </div>

      {!open && (
        <span className="w-full text-xs text-ink-faint sm:w-auto">Closed</span>
      )}
    </li>
  );
}
