"use client";

import { useState } from "react";

import { providersApi } from "@/lib/api";
import type { Slot } from "@/lib/api";
import { useResource } from "@/hooks/useResource";
import { formatDuration, formatTime, groupSlotsByDay } from "@/lib/datetime";
import { Failed, Loading } from "@/components/ui/States";
import { cn } from "@/lib/utils";

/**
 * Choosing when.
 *
 * Nothing here works out what is free. The backend knows the provider's hours,
 * their time off, how long this particular provider needs for this particular
 * service, and what is already booked; a browser that tried to reproduce that
 * would offer times that fail at the last step. So this fetches, groups by day,
 * and draws.
 *
 * The three empty-looking outcomes are deliberately three different screens:
 *
 *   • the diary itself failed (503), which is our problem and worth retrying
 *   • the provider genuinely has nothing free, which is their diary, not a fault
 *   • the provider does not offer this service (404), which is a dead end
 *
 * They used to be one "no times available", and the first of them silently
 * turned a broken calendar into a provider who looked fully booked.
 */

interface SlotPickerProps {
  providerId: number;
  serviceId: number;
  durationMinutes: number;
  /** The slot already chosen, so coming back from review keeps the selection. */
  selected?: Slot | null;
  onSelect: (slot: Slot) => void;
}

export function SlotPicker({
  providerId, serviceId, durationMinutes, selected, onSelect,
}: SlotPickerProps) {
  const { data, error, status, loading, reload } = useResource(
    (signal) => providersApi.availability(providerId, serviceId, undefined, signal),
    [providerId, serviceId]
  );

  const days = data ? groupSlotsByDay(data.slots) : [];

  // Which day is open, remembered against the diary it belongs to. A new
  // provider or service is a different diary, and the day that was open in the
  // last one means nothing here, so it is discarded by the comparison rather
  // than by an effect resetting state after the render.
  const diaryKey = `${providerId}:${serviceId}`;
  const [opened, setOpened] = useState<{ diary: string; day: string } | null>(null);
  const openedDay = opened?.diary === diaryKey ? opened.day : null;

  if (error) {
    if (status === 404) {
      return (
        <Failed
          title="That is no longer offered"
          detail={`${error} Go back and choose another provider.`}
        />
      );
    }
    return (
      <Failed
        title={status === 503 ? "The diary is not answering" : "Times did not load"}
        detail={
          status === 503
            ? "We could not read this provider's calendar just now. This is our problem, not a sign they are busy."
            : error
        }
        onRetry={reload}
      />
    );
  }

  if (loading || !data) return <Loading label="Finding free times" rows={2} />;

  if (days.length === 0) {
    return (
      <div className="rounded-card border border-line bg-surface px-6 py-10 text-center">
        <span className="mb-3 block text-3xl" aria-hidden>📅</span>
        <h3 className="text-base font-semibold text-ink">Nothing free at the moment</h3>
        <p className="mx-auto mt-1.5 max-w-sm text-sm leading-relaxed text-ink-muted">
          This provider has no open times in the period we can see. Go back and
          try another provider, whose next free time is shown on their card.
        </p>
      </div>
    );
  }

  // Whichever day they opened, or the day their existing choice sits on, or the
  // first day with anything free. Derived rather than stored, so it is never
  // pointing at a day from a diary we are no longer showing.
  const current =
    days.find((d) => d.key === openedDay) ??
    (selected
      ? days.find((d) => d.slots.some((s) => s.starts_at === selected.starts_at))
      : undefined) ??
    days[0];

  return (
    <div>
      <p className="mb-2 text-xs text-ink-muted">
        Each visit is about {formatDuration(data.duration_minutes || durationMinutes)}.
        Times shown are when the provider would arrive.
      </p>

      {/* Days run sideways so a fortnight fits without a calendar widget, and
          the row scrolls rather than wrapping into four lines on a phone. */}
      <div className="chat-scroll -mx-1 flex snap-x gap-2 overflow-x-auto overscroll-x-contain px-1 pb-2">
        {days.map((day) => (
          <button
            key={day.key}
            onClick={() => setOpened({ diary: diaryKey, day: day.key })}
            aria-pressed={day.key === current.key}
            className={cn(
              "flex-shrink-0 snap-start rounded-control border px-3 py-2 text-xs font-semibold transition-colors",
              day.key === current.key
                ? "border-brand-300 bg-brand-50 text-brand-700"
                : "border-line bg-surface text-ink-muted hover:bg-surface-hover"
            )}
          >
            <span className="block">{day.short}</span>
            <span className="mt-0.5 block text-[10px] font-medium text-ink-faint">
              {day.slots.length} time{day.slots.length === 1 ? "" : "s"}
            </span>
          </button>
        ))}
      </div>

      <p className="mb-2 mt-3 text-sm font-semibold text-ink">{current.label}</p>

      <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
        {current.slots.map((slot) => {
          const chosen = selected?.starts_at === slot.starts_at;
          return (
            <button
              key={slot.starts_at}
              onClick={() => onSelect(slot)}
              aria-pressed={chosen}
              className={cn(
                "h-11 rounded-control border text-sm font-semibold transition-colors",
                chosen
                  ? "border-brand-500 bg-brand-500 text-white"
                  : "border-line bg-surface text-ink hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
              )}
            >
              {formatTime(slot.starts_at)}
            </button>
          );
        })}
      </div>
    </div>
  );
}
