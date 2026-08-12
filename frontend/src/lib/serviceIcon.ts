/**
 * The icon for a service, when there is no photograph.
 *
 * This was a grocery list: meat, dairy, frozen, bakery. Every one of those
 * matched nothing in a catalogue of drain repairs and boiler services, so every
 * card fell through to the same wrench.
 *
 * The name is matched as well as the category, and it matters more: the
 * catalogue files a lot of work under a broad heading, but "Emergency pipe leak
 * repair" says what it is regardless of which heading it sits under.
 */
export function getServiceEmoji(text: string): string {
  const s = (text || "").toLowerCase();

  // Water and drains, which is most of what this started as.
  if (/(leak|pipe|plumb|tap|faucet|drain|blocked|sink|toilet|bathroom|shower|water)/.test(s)) return "🚰";
  if (/(boiler|heating|radiator|furnace|hvac|gas|thermostat)/.test(s)) return "🔥";
  if (/(air.?con|cooling|ventilation)/.test(s)) return "❄️";
  if (/(electric|wiring|socket|fuse|lighting|rewire|circuit)/.test(s)) return "💡";

  // Everything else the platform covers.
  if (/(vet|pet|dog|cat|vaccin|groom|animal)/.test(s)) return "🐾";
  if (/(clean|hoover|carpet|window clean|tenancy|housekeep)/.test(s)) return "🧹";
  if (/(garden|lawn|hedge|tree|landscap|waste|rubbish)/.test(s)) return "🌿";
  if (/(car|vehicle|mechanic|tyre|tire|mot|engine|brake|servicing)/.test(s)) return "🚗";
  if (/(dent|teeth|physio|optician|clinic|doctor|health|therapy|massage)/.test(s)) return "🩺";
  if (/(roof|gutter|chimney|brick|plaster|paint|decorat|carpent|joiner|build)/.test(s)) return "🧱";
  if (/(lock|security|alarm|cctv|door|window repair)/.test(s)) return "🔐";
  if (/(appliance|washing machine|dishwasher|fridge|oven)/.test(s)) return "🧺";
  if (/(pest|rodent|insect|infest)/.test(s)) return "🐜";
  if (/(class|hall|group|community|council|course|lesson)/.test(s)) return "🏘️";
  if (/(inspect|survey|report|assessment|certificate)/.test(s)) return "📋";

  // A spanner reads as "somebody will come and do something", which is true of
  // every service here even when we cannot tell which.
  return "🔧";
}
