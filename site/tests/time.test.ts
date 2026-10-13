// Run with `npm test`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { weekLabel } from "../src/lib/time.ts";

test("a week inside one month names the month once", () => {
  assert.equal(weekLabel("2026-10-15", "2026-10-21"), "15–21 October");
});

test("a week across a month end names both months", () => {
  assert.equal(weekLabel("2026-10-29", "2026-11-04"), "29 October – 4 November");
});

test("a week across a year end names both months", () => {
  assert.equal(weekLabel("2026-12-31", "2027-01-06"), "31 December – 6 January");
});

test("the same month in different years is not treated as one month", () => {
  assert.equal(weekLabel("2026-01-29", "2027-01-04"), "29 January – 4 January");
});
