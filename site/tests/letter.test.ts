// Run with `npm test` (Node's built-in test runner; no extra packages).
import { test } from "node:test";
import assert from "node:assert/strict";
import { letterOf, isReady } from "../src/lib/letter.ts";

const letter = { greeting: "Hello, E2,", paragraphs: ["A quiet week."], sign_off: "Enjoy,", signed: "Fred", postscript: null };

test("an issue with a written letter shows it", () => {
  assert.deepEqual(letterOf({ intro: letter }), letter);
});

test("an issue whose letter Fred left out shows no letter", () => {
  assert.equal(letterOf({ intro: { left_out: true, by: "fred", at: "2026-10-15T09:35:00+01:00" } }), null);
});

test("an issue whose letter isn't written yet shows no letter", () => {
  assert.equal(letterOf({ intro: null }), null);
});

test("an issue is listed once its letter is written or left out, never while still waiting", () => {
  assert.equal(isReady({ intro: letter }), true);
  assert.equal(isReady({ intro: { left_out: true, by: "fred", at: "2026-10-15T09:35:00+01:00" } }), true);
  assert.equal(isReady({ intro: null }), false);
});
