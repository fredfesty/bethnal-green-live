// Run with `npm test` (Node's built-in test runner; no extra packages).
import { test } from "node:test";
import assert from "node:assert/strict";
import { sentIssues, groupByMonth, neighbours } from "../src/lib/archive.ts";

const issue = (id: string, issue_number: number) => ({ id, issue_number });
// Deliberately out of order, as files can be read in any order.
const issues = [issue("2026-10-22", 2), issue("2026-11-05", 4), issue("2026-10-15", 1), issue("2026-10-29", 3)];
const ids = (xs: { id: string }[]) => xs.map((x) => x.id);

test("an issue counts as sent from its send date, never before", () => {
  assert.deepEqual(ids(sentIssues(issues, "2026-10-14")), []);
  assert.deepEqual(ids(sentIssues(issues, "2026-10-15")), ["2026-10-15"]);
  assert.deepEqual(ids(sentIssues(issues, "2026-10-28")), ["2026-10-22", "2026-10-15"]);
});

test("sent issues come newest first", () => {
  assert.deepEqual(ids(sentIssues(issues, "2026-12-31")), ["2026-11-05", "2026-10-29", "2026-10-22", "2026-10-15"]);
});

test("sentIssues leaves the list it was given alone", () => {
  const copy = [...issues];
  sentIssues(issues, "2026-12-31");
  assert.deepEqual(issues, copy);
});

test("issues are grouped by the month they went out, keeping their order", () => {
  const groups = groupByMonth(sentIssues(issues, "2026-12-31"));
  assert.deepEqual(groups.map((g) => [g.month, ids(g.issues)]), [
    ["2026-11", ["2026-11-05"]],
    ["2026-10", ["2026-10-29", "2026-10-22", "2026-10-15"]],
  ]);
  assert.deepEqual(groupByMonth([]), []);
});

test("months in different years are kept apart", () => {
  const groups = groupByMonth([issue("2027-01-07", 13), issue("2026-12-31", 12)]);
  assert.deepEqual(groups.map((g) => g.month), ["2027-01", "2026-12"]);
});

test("neighbours link to the sent issues either side", () => {
  const today = "2026-12-31";
  assert.deepEqual(neighbours(issues, "2026-10-22", today), { older: issue("2026-10-15", 1), newer: issue("2026-10-29", 3) });
  assert.deepEqual(neighbours(issues, "2026-10-15", today), { older: null, newer: issue("2026-10-22", 2) });
  assert.deepEqual(neighbours(issues, "2026-11-05", today), { older: issue("2026-10-29", 3), newer: null });
});

test("a sent issue never links on to one that hasn't gone out", () => {
  assert.deepEqual(neighbours(issues, "2026-10-22", "2026-10-28"), { older: issue("2026-10-15", 1), newer: null });
});

test("an unsent preview gets no neighbours", () => {
  assert.deepEqual(neighbours(issues, "2026-10-29", "2026-10-28"), { older: null, newer: null });
  assert.deepEqual(neighbours(issues, "2099-01-01", "2026-12-31"), { older: null, newer: null });
});

test("a lone sent issue, or none at all, has no neighbours", () => {
  assert.deepEqual(neighbours(issues, "2026-10-15", "2026-10-20"), { older: null, newer: null });
  assert.deepEqual(neighbours([], "2026-10-15", "2026-10-20"), { older: null, newer: null });
});

test("groupByMonth expects sorted input: unsorted issues split a month", () => {
  const groups = groupByMonth([issue("2026-10-22", 2), issue("2026-09-24", 0), issue("2026-10-15", 1)]);
  assert.deepEqual(groups.map((g) => g.month), ["2026-10", "2026-09", "2026-10"]);
});
