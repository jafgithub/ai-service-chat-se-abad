// Fallback icon for a product when no image is available.
export function getCategoryEmoji(category: string): string {
  const lower = (category || "").toLowerCase();
  if (lower.includes("meat") || lower.includes("poultry") || lower.includes("chicken") || lower.includes("halal")) return "🥩";
  if (lower.includes("dairy") || lower.includes("beverage") || lower.includes("milk") || lower.includes("cheese")) return "🥛";
  if (lower.includes("grocery") || lower.includes("produce") || lower.includes("vegetable") || lower.includes("fruit")) return "🥦";
  if (lower.includes("egg")) return "🥚";
  if (lower.includes("seafood") || lower.includes("fish")) return "🐟";
  if (lower.includes("bread") || lower.includes("bakery")) return "🍞";
  if (lower.includes("frozen")) return "🧊";
  if (lower.includes("rice") || lower.includes("atta") || lower.includes("dal")) return "🌾";
  if (lower.includes("pizza")) return "🍕";
  return "🔧";
}
