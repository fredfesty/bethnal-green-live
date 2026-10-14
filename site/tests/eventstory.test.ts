// Run with `npm test`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { shownStory } from "../src/lib/eventstory.ts";

const base = { who: "Says the Guardian.", written_at: "2026-10-15T07:00:00Z", evidence: [] };

test("an unchecked story is never shown", () => {
  assert.equal(shownStory({ ...base, review: null }), null);
  assert.equal(shownStory(null), null);
});

test("a review older than the words doesn't count", () => {
  assert.equal(shownStory({ ...base, review: { checked_at: "2026-10-14T07:00:00Z", removed_fields: [] } }), null);
});

test("a checked story is shown, unless the checker cut everything", () => {
  const review = { checked_at: "2026-10-15T08:00:00+01:00", removed_fields: [] };
  assert.ok(shownStory({ ...base, review: { checked_at: "2026-10-15T08:00:00Z", removed_fields: [] } }));
  assert.equal(shownStory({ ...base, who: null, review: { ...review, checked_at: "2026-10-15T09:00:00Z" } }), null);
});
