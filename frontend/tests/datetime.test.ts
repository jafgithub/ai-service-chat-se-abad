import { test, describe } from "node:test";
import assert from "node:assert/strict";

import {
  parseWallClock,
  formatTime,
  formatDay,
  formatDayShort,
  formatWhen,
  dayKey,
  groupSlotsByDay,
  formatDuration,
  toApiDateTime,
} from "../src/lib/datetime.ts";

/**
 * Times are the part of this application most likely to be quietly wrong.
 *
 * Everything the API sends is naive, and the whole module exists to read those
 * strings literally rather than as instants. The test that matters most is the
 * one asserting that: run the suite with TZ set to anything you like and the
 * answers must not move.
 */

describe("reading the API's naive datetimes", () => {
  test("pulls the parts out of a naive ISO string", () => {
    assert.deepEqual(parseWallClock("2026-08-12T14:30:00"), {
      year: 2026, month: 8, day: 12, hour: 14, minute: 30,
    });
  });

  test("accepts a space instead of a T, which some drivers produce", () => {
    assert.deepEqual(parseWallClock("2026-08-12 09:05:00")?.hour, 9);
  });

  test("returns null rather than a wrong answer for anything else", () => {
    for (const bad of ["", "not a date", "12/08/2026", null, undefined]) {
      assert.equal(parseWallClock(bad as string), null);
    }
  });

  test("the wall clock is never shifted by a timezone", () => {
    // The reason this module exists. `new Date("2026-08-12T14:00:00")` reads
    // that as local time, so in Karachi it is 14:00 and in Los Angeles it is
    // still 14:00 but a different instant; convert either to UTC and the
    // displayed hour moves. Ours must not, whatever TZ the process runs under.
    const iso = "2026-08-12T14:00:00";
    assert.equal(formatTime(iso), "2:00 PM");
    assert.equal(formatDay(iso), "Wednesday 12 August");
    assert.equal(dayKey(iso), "2026-08-12");
  });
});

describe("how a time is written", () => {
  test("midnight and noon are 12, not 0", () => {
    assert.equal(formatTime("2026-08-12T00:00:00"), "12:00 AM");
    assert.equal(formatTime("2026-08-12T12:00:00"), "12:00 PM");
  });

  test("minutes keep their leading zero", () => {
    assert.equal(formatTime("2026-08-12T09:05:00"), "9:05 AM");
  });

  test("the long form matches the shape the API's own labels use", () => {
    // The server sends "Wednesday 12 August, 2:00 PM" for the same slot. If
    // these two ever disagree the customer sees one time on the picker and
    // another on the confirmation.
    assert.equal(formatWhen("2026-08-12T14:00:00"), "Wednesday 12 August, 2:00 PM");
  });

  test("the short form fits a tab", () => {
    assert.equal(formatDayShort("2026-08-12T14:00:00"), "Wed 12 Aug");
  });

  test("nothing in, nothing out", () => {
    assert.equal(formatTime(null), "");
    assert.equal(formatDay(undefined), "");
    assert.equal(formatWhen(""), "");
  });
});

describe("grouping slots into days", () => {
  const slots = [
    { starts_at: "2026-08-12T09:00:00" },
    { starts_at: "2026-08-12T10:30:00" },
    { starts_at: "2026-08-13T09:00:00" },
  ];

  test("one entry per day, in the order the API gave them", () => {
    const days = groupSlotsByDay(slots);
    assert.equal(days.length, 2);
    assert.deepEqual(days.map((d) => d.key), ["2026-08-12", "2026-08-13"]);
    assert.equal(days[0].slots.length, 2);
    assert.equal(days[0].label, "Wednesday 12 August");
  });

  test("does not re-sort, because the API already ranked them", () => {
    // Deliberately out of order. Re-sorting here would quietly become a second
    // opinion about what is soonest, and the provider card's "next free" is
    // computed by the backend from this same list.
    const days = groupSlotsByDay([
      { starts_at: "2026-08-13T09:00:00" },
      { starts_at: "2026-08-12T09:00:00" },
    ]);
    assert.deepEqual(days.map((d) => d.key), ["2026-08-13", "2026-08-12"]);
  });

  test("skips anything unparseable instead of making a day out of it", () => {
    const days = groupSlotsByDay([{ starts_at: "rubbish" }, { starts_at: "2026-08-12T09:00:00" }]);
    assert.equal(days.length, 1);
  });

  test("nothing free is an empty list, not a day with no times", () => {
    assert.deepEqual(groupSlotsByDay([]), []);
  });
});

describe("how long a visit takes", () => {
  test("under an hour stays in minutes", () => {
    assert.equal(formatDuration(45), "45 min");
  });

  test("a whole number of hours does not print zero minutes", () => {
    assert.equal(formatDuration(60), "1 hr");
    assert.equal(formatDuration(120), "2 hr");
  });

  test("ninety minutes reads as an hour and a half", () => {
    assert.equal(formatDuration(90), "1 hr 30 min");
  });

  test("nothing knowable prints nothing, rather than 0 min", () => {
    assert.equal(formatDuration(null), "");
    assert.equal(formatDuration(0), "");
    assert.equal(formatDuration(undefined), "");
  });
});

describe("sending a time back", () => {
  test("a date and time input become the naive form the API expects", () => {
    assert.equal(toApiDateTime("2026-08-12", "09:00"), "2026-08-12T09:00:00");
  });

  test("seconds are not doubled up when the input already has them", () => {
    assert.equal(toApiDateTime("2026-08-12", "09:00:30"), "2026-08-12T09:00:30");
  });
});
