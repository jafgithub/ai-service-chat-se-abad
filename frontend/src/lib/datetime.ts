/**
 * Reading and writing the times the booking API deals in.
 *
 * Every datetime the backend sends is naive: "2026-08-12T14:00:00", with no
 * offset and no Z. It is tempting to treat that as UTC and render it in the
 * reader's timezone, and that would be wrong here. Those values are built from
 * each provider's working hours (opens_at 09:00) and the server labels them
 * with its own strftime, so the string means *wall clock where the work
 * happens*. Converting it would make our picker disagree with the label the
 * same API sends for the same slot, and a customer in another timezone would be
 * shown a time nobody agreed to.
 *
 * So these functions read the string literally and never touch a timezone.
 * `new Date(iso)` is deliberately avoided for formatting: it interprets a naive
 * string as local time, which is right by accident in one timezone and wrong
 * everywhere else.
 *
 * The real fix is for the backend to carry a timezone per provider. It does not
 * today, and inventing one in the browser would only hide that.
 */

const DAYS = [
  "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
];

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export interface WallClock {
  year: number;
  month: number;   // 1-12
  day: number;     // 1-31
  hour: number;    // 0-23
  minute: number;
}

/** Pull the parts out of a naive ISO string, or null if it is not one. */
export function parseWallClock(iso: string | null | undefined): WallClock | null {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(iso.trim());
  if (!m) return null;
  return {
    year: Number(m[1]),
    month: Number(m[2]),
    day: Number(m[3]),
    hour: Number(m[4]),
    minute: Number(m[5]),
  };
}

/** Which weekday that date falls on. Uses a UTC Date purely as a calendar,
 *  never as a moment in time, so no offset can shift the answer. */
function weekdayName(w: WallClock): string {
  return DAYS[new Date(Date.UTC(w.year, w.month - 1, w.day)).getUTCDay()];
}

/** "2:00 PM" */
export function formatTime(iso: string | null | undefined): string {
  const w = parseWallClock(iso);
  if (!w) return "";
  const suffix = w.hour < 12 ? "AM" : "PM";
  const hour12 = w.hour % 12 === 0 ? 12 : w.hour % 12;
  return `${hour12}:${String(w.minute).padStart(2, "0")} ${suffix}`;
}

/** "Wednesday 12 August" */
export function formatDay(iso: string | null | undefined): string {
  const w = parseWallClock(iso);
  if (!w) return "";
  return `${weekdayName(w)} ${w.day} ${MONTHS[w.month - 1]}`;
}

/** "Wed 12 Aug", for tabs and chips where the long form will not fit. */
export function formatDayShort(iso: string | null | undefined): string {
  const w = parseWallClock(iso);
  if (!w) return "";
  return `${weekdayName(w).slice(0, 3)} ${w.day} ${MONTHS[w.month - 1].slice(0, 3)}`;
}

/** "Wednesday 12 August, 2:00 PM" — the same shape the API's own labels use, so
 *  a slot we format and a label the server sent read identically. */
export function formatWhen(iso: string | null | undefined): string {
  const day = formatDay(iso);
  return day ? `${day}, ${formatTime(iso)}` : "";
}

/** "2026-08-12", for grouping slots into days. */
export function dayKey(iso: string | null | undefined): string {
  const w = parseWallClock(iso);
  if (!w) return "";
  return `${w.year}-${String(w.month).padStart(2, "0")}-${String(w.day).padStart(2, "0")}`;
}

/** Sortable minutes since the epoch, treating the wall clock as if it were UTC.
 *  Only ever compared against another value from this same function. */
export function wallClockOrder(iso: string | null | undefined): number {
  const w = parseWallClock(iso);
  if (!w) return 0;
  return Date.UTC(w.year, w.month - 1, w.day, w.hour, w.minute);
}

export interface SlotDay<T> {
  key: string;
  /** "Wednesday 12 August" */
  label: string;
  /** "Wed 12 Aug" */
  short: string;
  slots: T[];
}

/**
 * Slots arrive as one flat list covering several days. A picker needs them by
 * day, and the grouping preserves the order the API gave rather than sorting,
 * because the API already ranked them and re-sorting here would quietly become
 * a second opinion about what is soonest.
 */
export function groupSlotsByDay<T extends { starts_at: string }>(slots: T[]): SlotDay<T>[] {
  const days: SlotDay<T>[] = [];
  const index = new Map<string, SlotDay<T>>();

  for (const slot of slots) {
    const key = dayKey(slot.starts_at);
    if (!key) continue;
    let day = index.get(key);
    if (!day) {
      day = {
        key,
        label: formatDay(slot.starts_at),
        short: formatDayShort(slot.starts_at),
        slots: [],
      };
      index.set(key, day);
      days.push(day);
    }
    day.slots.push(slot);
  }
  return days;
}

/** "90 min" stays "1 hr 30 min", because a customer books an afternoon, not
 *  ninety of anything. */
export function formatDuration(minutes: number | null | undefined): string {
  if (minutes == null || !Number.isFinite(minutes) || minutes <= 0) return "";
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  if (hours === 0) return `${mins} min`;
  if (mins === 0) return `${hours} hr`;
  return `${hours} hr ${mins} min`;
}

/** A naive datetime string for the API, from a browser date and time input.
 *  Sent back in the same wall-clock form it arrived in. */
export function toApiDateTime(date: string, time: string): string {
  return `${date}T${time.length === 5 ? `${time}:00` : time}`;
}
