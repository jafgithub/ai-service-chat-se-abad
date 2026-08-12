/**
 * What is safe to show about a service.
 *
 * This was `lib/product.ts` and most of it was about stock: how many are left,
 * whether it is sold out, what the unit is. None of that survives the move to
 * booking. A service is not stocked, and the backend gives every one of them a
 * stock of 999,999 precisely so that the shop's code paths stop hiding them.
 * Reading that number and printing "999999 left" would be the shop leaking
 * through.
 *
 * What is left is the same principle the original had, which is worth keeping:
 * each helper answers "do we actually know this?" and returns null when the
 * answer is no, so the card can leave it out instead of asserting it.
 */

const SYMBOLS: Record<string, string> = { USD: "$", GBP: "£", EUR: "€" };

/**
 * "$95.00". An unknown currency code is printed rather than guessed at, so
 * nobody is ever shown a pound sign over a dollar amount.
 */
export function formatMoney(amount: number | null | undefined, currency = "USD"): string {
  if (amount == null || !Number.isFinite(amount)) return "";
  const code = (currency || "USD").toUpperCase();
  const symbol = SYMBOLS[code];
  return symbol ? `${symbol}${amount.toFixed(2)}` : `${amount.toFixed(2)} ${code}`;
}

/** A category worth putting on a badge, or null for the catch-all buckets. */
export function displayCategory(category: string | null | undefined): string | null {
  const value = (category || "").trim();
  if (!value) return null;
  if (/^(general|other|misc|miscellaneous|uncategori[sz]ed)$/i.test(value)) return null;
  // A bare category id reaches here when no name has been joined on. "7" tells
  // nobody anything.
  if (/^\d+$/.test(value)) return null;
  // "Home & Repairs" is two ideas; the badge has room for one.
  return value.split("&")[0].trim() || null;
}

/**
 * A description worth showing, or null.
 *
 * Rejects fragments too short to say anything and blurbs cut off mid-sentence
 * by an upstream character limit: they end without punctuation and read as
 * broken. Newlines inside a word are joined first, because the card renders
 * them as a space.
 */
export function cleanDescription(description: string | null | undefined): string | null {
  if (!description) return null;

  const text = description.replace(/\s+/g, " ").trim();
  if (text.length < 20) return null;

  if (!/[.!?]$/.test(text)) {
    const words = text.split(" ");
    words.pop();
    const trimmed = words.join(" ").trim();
    if (trimmed.length < 20) return null;
    return `${trimmed}…`;
  }
  return text;
}

/** Collapses whitespace so a name lays out cleanly. Nothing else: the name is
 *  the client's own and is shown as written. */
export function displayName(name: string): string {
  return (name || "").replace(/\s+/g, " ").trim();
}

/** How to describe how quickly somebody needs help. The values are the ones the
 *  API accepts; the labels are what a person would say. */
export const URGENCY_LABELS: Record<string, string> = {
  whenever: "Whenever suits",
  this_week: "Some time this week",
  urgent: "Urgent",
};
