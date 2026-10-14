import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../src/pages/index.astro", import.meta.url), "utf8");

test("the exhibitions & runs section is a details element that starts closed", () => {
  const tag = page.match(/<details class="runs"[^>]*>/);
  assert.ok(tag, "runs section should be a <details class=\"runs\">");
  assert.doesNotMatch(tag[0], /\sopen(\s|=|>)/, "runs section must not start open");
});

test("the closed section still shows its title and how many runs it holds", () => {
  assert.match(page, /<h2 class="day__head" id="runs-head">[\s\S]*Exhibitions & runs[\s\S]*\{runs\.length\}/);
});

test("the title is a real heading outside the summary button", () => {
  const summary = page.match(/<summary class="runs__summary">[\s\S]*?<\/summary>/);
  assert.ok(summary, "runs section needs a summary");
  assert.doesNotMatch(summary[0], /<h[1-6]/, "no heading inside the summary");
  assert.match(page, /<h2 class="day__head" id="runs-head">[\s\S]*?<\/h2>\s*<details class="runs"/);
});

test("a search or filter opens the section only when matches first appear", () => {
  assert.match(page, /const runMatch = filtering && /);
  assert.match(page, /if \(runMatch && !hadRunMatch\) runsBox\.open = true;/);
  assert.match(page, /hadRunMatch = runMatch;/);
});

test("clearing the filters folds the section away again", () => {
  assert.match(page, /form\.reset\(\); if \(runsBox\) runsBox\.open = false;/);
});

test("the toggle button has real, readable text for both states", () => {
  const summary = page.match(/<summary class="runs__summary">[\s\S]*?<\/summary>/)![0];
  const text = summary.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  assert.match(text, /Show exhibitions & runs/);
  assert.match(text, /Hide exhibitions & runs/);
});
