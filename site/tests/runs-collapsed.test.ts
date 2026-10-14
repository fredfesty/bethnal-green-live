import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../src/pages/index.astro", import.meta.url), "utf8");

test("the title is a real heading and the toggle button sits beside it in the same row", () => {
  assert.match(page, /<div class="runs__head">\s*<h2 class="day__head" id="runs-head">[\s\S]*?<\/h2>\s*<button type="button" class="runs__btn"/);
  const btn = page.match(/<button type="button" class="runs__btn"[\s\S]*?<\/button>/)![0];
  assert.doesNotMatch(btn, /<h[1-6]/, "no heading inside the button");
});

test("the button is hidden until script runs, so no-JS readers just see the list", () => {
  const open = page.match(/<button type="button" class="runs__btn"[^>]*>/)![0];
  assert.match(open, /\shidden(\s|>)/);
  assert.match(open, /aria-expanded="false"/);
  assert.match(open, /aria-controls="runs-list"/);
  assert.match(page, /<ul class="day__list" id="runs-list">/);
  assert.doesNotMatch(page.match(/<ul class="day__list" id="runs-list"[^>]*>/)![0], /hidden/, "list is only hidden by script");
});

test("the section shows its title, how many runs it holds, and real Show/Hide text", () => {
  assert.match(page, /Exhibitions & runs[\s\S]*\{runs\.length\}/);
  const btn = page.match(/<button type="button" class="runs__btn"[\s\S]*?<\/button>/)![0];
  const text = btn.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  assert.match(text, /Show exhibitions & runs/);
  assert.match(text, /Hide exhibitions & runs/);
});

test("script starts the section folded, toggles on click, and opens it only when matches first appear", () => {
  assert.match(page, /runsBtn\.hidden = false; setRuns\(false\);/);
  assert.match(page, /runsBtn\.addEventListener\("click", \(\) => setRuns\(runsList\.hidden\)\)/);
  assert.match(page, /if \(runMatch && !hadRunMatch\) setRuns\(true\);/);
  assert.match(page, /hadRunMatch = runMatch;/);
});

test("clearing the filters folds the section away again", () => {
  assert.match(page, /form\.reset\(\); setRuns\(false\);/);
});
