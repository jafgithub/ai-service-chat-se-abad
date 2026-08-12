import { test, describe } from "node:test";
import assert from "node:assert/strict";

import {
  formatMoney,
  displayCategory,
  cleanDescription,
  displayName,
  URGENCY_LABELS,
} from "../src/lib/service.ts";
import { getServiceEmoji } from "../src/lib/serviceIcon.ts";

describe("prices", () => {
  test("two decimal places, with the right symbol", () => {
    assert.equal(formatMoney(95, "USD"), "$95.00");
    assert.equal(formatMoney(95, "GBP"), "£95.00");
    assert.equal(formatMoney(9.5, "EUR"), "€9.50");
  });

  test("an unknown currency prints its code rather than guessing a symbol", () => {
    // Showing a dollar sign over a PKR amount is worse than showing the code:
    // one is unfamiliar, the other is wrong by a factor of 280.
    assert.equal(formatMoney(95, "PKR"), "95.00 PKR");
  });

  test("lower case codes still resolve", () => {
    assert.equal(formatMoney(95, "usd"), "$95.00");
  });

  test("free is a price; unknown is not", () => {
    assert.equal(formatMoney(0), "$0.00");
    assert.equal(formatMoney(null), "");
    assert.equal(formatMoney(undefined), "");
  });
});

describe("what is worth showing on a card", () => {
  test("a real category is kept, split at the ampersand", () => {
    assert.equal(displayCategory("Home & Repairs"), "Home");
    assert.equal(displayCategory("Plumbing"), "Plumbing");
  });

  test("the catch-all buckets are left off entirely", () => {
    for (const junk of ["General", "general", "Other", "Miscellaneous", "Uncategorised", "", null]) {
      assert.equal(displayCategory(junk), null);
    }
  });

  test("a bare category id tells nobody anything", () => {
    assert.equal(displayCategory("7"), null);
  });

  test("a usable description survives", () => {
    const text = "We attend leaks under sinks and behind appliances, day or night.";
    assert.equal(cleanDescription(text), text);
  });

  test("a fragment too short to say anything is dropped", () => {
    assert.equal(cleanDescription("Leak."), null);
    assert.equal(cleanDescription(null), null);
  });

  test("a blurb chopped mid-sentence loses the broken last word", () => {
    const cut = "Our engineers attend the same day and carry the parts for most jobs on the va";
    const cleaned = cleanDescription(cut);
    assert.ok(cleaned?.endsWith("…"));
    assert.ok(!cleaned?.includes("the va"));
  });

  test("whitespace inside a name is collapsed, and nothing else is touched", () => {
    assert.equal(displayName("  Emergency   pipe\nleak repair "), "Emergency pipe leak repair");
  });

  test("every urgency the API accepts has words a person would use", () => {
    for (const value of ["whenever", "this_week", "urgent"]) {
      assert.ok(URGENCY_LABELS[value], `no label for ${value}`);
    }
  });
});

describe("the icon for a service", () => {
  test("water and drains", () => {
    assert.equal(getServiceEmoji("Emergency pipe leak repair"), "🚰");
    assert.equal(getServiceEmoji("Blocked drain clearance"), "🚰");
  });

  test("the other trades the platform covers", () => {
    assert.equal(getServiceEmoji("Annual boiler service"), "🔥");
    assert.equal(getServiceEmoji("Consumer unit rewire"), "💡");
    assert.equal(getServiceEmoji("Dog vaccination"), "🐾");
    assert.equal(getServiceEmoji("End of tenancy clean"), "🧹");
    assert.equal(getServiceEmoji("Car servicing"), "🚗");
  });

  test("something we cannot place still gets a sensible icon", () => {
    // A spanner reads as "somebody will come and do something", which is true
    // of every service here even when we cannot tell which.
    assert.equal(getServiceEmoji("Something nobody anticipated"), "🔧");
    assert.equal(getServiceEmoji(""), "🔧");
  });

  test("the old grocery mapping is gone", () => {
    // These used to return a steak, a carton of milk and a loaf, on a platform
    // that books plumbers.
    for (const word of ["chicken", "dairy", "bakery"]) {
      assert.equal(getServiceEmoji(word), "🔧");
    }
  });
});
