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
  assert.match(page, /<summary class="runs__summary">[\s\S]*Exhibitions & runs[\s\S]*\{runs\.length\}/);
});

test("a search or filter opens the section when it has matches", () => {
  assert.match(page, /filtering[\s\S]*runsBox\.open = true/);
});
