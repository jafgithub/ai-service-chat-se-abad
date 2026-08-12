"use client";

import Link from "next/link";

import type { Booked } from "@/lib/api";
import { formatDuration, formatTime, formatDay } from "@/lib/datetime";
import { formatMoney } from "@/lib/service";
import { Button } from "@/components/ui/Button";

/**
 * It is booked.
 *
 * Everything here came back in the booking response, so this screen makes no
 * further calls and cannot show a spinner over a booking that already exists.
 * The reference is given the most room: it is the thing somebody quotes on the
 * phone when they need to change it.
 *
 * `payment_status` is printed as the server sent it. It reads "unpaid" today,
 * which is correct and must not be dressed up: a visit that has not been paid
 * for must not look settled.
 */

interface BookingConfirmationProps {
  booking: Booked;
  onDone: () => void;
}

export function BookingConfirmation({ booking, onDone }: BookingConfirmationProps) {
  const paid = booking.payment_status === "paid";
  const cash = booking.payment_status === "cod";

  return (
    <div className="text-center">
      <span
        className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-positive-soft text-3xl"
        aria-hidden
      >
        ✅
      </span>

      <h2 className="text-lg font-bold text-ink">You are booked in</h2>
      <p className="mt-1 text-sm text-ink-muted">
        {booking.provider_name} will attend. The details are on their way to your email.
      </p>

      <p className="mt-4 inline-block rounded-control border border-dashed border-line-strong px-4 py-2">
        <span className="block text-[11px] uppercase tracking-wide text-ink-faint">
          Reference
        </span>
        <span className="text-lg font-bold tracking-wide text-ink">{booking.reference}</span>
      </p>

      <dl className="mt-5 divide-y divide-line rounded-card border border-line text-left">
        <Row label="Service" value={booking.service_name} />
        <Row label="Provider" value={booking.provider_name} sub={booking.provider_phone ?? undefined} />
        <Row label="Date" value={formatDay(booking.starts_at)} strong />
        <Row label="Time" value={formatTime(booking.starts_at)} strong />
        <Row label="How long" value={formatDuration(booking.duration_minutes)} />
        <Row label="Price" value={formatMoney(booking.price, booking.currency)} strong />
        <Row
          label="Payment"
          value={paid ? "Paid" : cash ? "Cash on the day" : "Not paid yet"}
          sub={
            paid
              ? undefined
              : cash
                ? "Settle up with the provider once the work is done"
                : "You can pay from My bookings, or on the day"
          }
        />
        {booking.address && <Row label="Address" value={booking.address} />}
      </dl>

      <div className="mt-5 flex flex-col gap-2 sm:flex-row">
        <Link
          href="/bookings"
          className="inline-flex h-11 flex-1 items-center justify-center rounded-control bg-brand-500 px-5 text-sm font-semibold text-white transition-colors hover:bg-brand-600"
        >
          View my bookings
        </Link>
        <Button variant="secondary" onClick={onDone} className="flex-1">
          Back to the assistant
        </Button>
      </div>
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
