/**
 * What is safe to show a shopper about a product.
 *
 * The catalog carries a lot of filler, and the UI used to render all of it as
 * though it were fact. Measured on the live dev catalog:
 *
 *   • every one of 634 results for "chicken" has unit "unit", so cards read
 *     "$4.85/unit" and "1000 units left"
 *   • 628 of those 634 have stock exactly 1000, so the stock line is noise
 *   • 106 sit in a category literally called "General"
 *   • descriptions include "Sp\nonsored" (renders as "Sp onsored") and a milk
 *     product carrying a coffee blurb truncated mid-word at "you cove"
 *
 * None of that is fixable from the frontend. What the frontend can do is stop
 * asserting it. Each helper below answers "do we actually know this?" and
 * returns null when the answer is no, so the component can leave it out.
 */

/** The real per-unit noun, or null when it is the placeholder "unit". */
export function displayUnit(unit: string | null | undefined): string | null {
  const value = (unit || "").trim().toLowerCase();
  if (!value || value === "unit" || value === "units" || value === "pc" || value === "piece") {
    return null;
  }
  return unit!.trim();
}

/** "$4.85" or "$4.85/kg" — never "$4.85/unit". */
export function formatPrice(price: number, unit?: string | null): string {
  const suffix = displayUnit(unit);
  return `$${price.toFixed(2)}${suffix ? `/${suffix}` : ""}`;
}

/**
 * Stock is only worth mentioning when it is low enough to influence a decision.
 * The catalog's default is 1000, so anything at or above the threshold tells
 * the shopper nothing and is left off the card entirely.
 */
const LOW_STOCK_AT = 20;

export function lowStockLabel(stock: number, unit?: string | null): string | null {
  if (!Number.isFinite(stock) || stock <= 0) return null;
  if (stock >= LOW_STOCK_AT) return null;
  const noun = displayUnit(unit);
  const n = Math.round(stock);
  return noun ? `Only ${n} ${noun}${n === 1 ? "" : "s"} left` : `Only ${n} left`;
}

export function isOutOfStock(stock: number): boolean {
  return Number.isFinite(stock) && stock <= 0;
}

/** A category worth putting on a badge, or null for the catch-all buckets. */
export function displayCategory(category: string | null | undefined): string | null {
  const value = (category || "").trim();
  if (!value) return null;
  if (/^(general|other|misc|miscellaneous|uncategori[sz]ed)$/i.test(value)) return null;
  // Cart lines fall back to the raw category id when no name has been joined
  // on, so a bare number reaches here. "7" tells a shopper nothing.
  if (/^\d+$/.test(value)) return null;
  // "Meat & Seafood" is two ideas; the badge has room for one.
  return value.split("&")[0].trim() || null;
}

/**
 * A description worth showing, or null.
 *
 * Rejects the scraper's leftovers: marketing boilerplate that is only the word
 * "sponsored", fragments too short to say anything, and blurbs cut off
 * mid-sentence by an upstream character limit (they end without punctuation and
 * read as broken). Newlines inside a word ("Sp\nonsored") are joined first,
 * because the card renders them as a space.
 */
export function cleanDescription(description: string | null | undefined): string | null {
  if (!description) return null;

  const text = description.replace(/\s+/g, " ").trim();
  if (text.length < 20) return null;
  if (/^sponsored\b/i.test(text)) return null;

  // Truncated upstream: no terminal punctuation and a chopped last word.
  if (!/[.!?]$/.test(text)) {
    const words = text.split(" ");
    words.pop();
    const trimmed = words.join(" ").trim();
    if (trimmed.length < 20) return null;
    return `${trimmed}…`;
  }
  return text;
}

/**
 * Product names come from the client's catalog with some mojibake left in
 * ("Cookies 'N Cr?me"). We cannot know the intended character, so the name is
 * shown as-is; this only collapses the whitespace so it lays out cleanly.
 */
export function displayName(name: string): string {
  return (name || "").replace(/\s+/g, " ").trim();
}
