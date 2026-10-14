// Run with `npm test`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { linkSources, siteKey } from "../src/lib/storylinks.ts";

const TO = "https://www.timeout.com/london/restaurants/e-pellicci";
const LN = "https://londonist.com/2005/03/caff_gets_liste";
const OWN = "https://epellicci.co.uk/pages/our-story";
const ev = [
  { fields: ["story.vibe"], url: TO, source_kind: "press" },
  { fields: ["story.vibe"], url: OWN, source_kind: "primary" },
  { fields: ["story.worth_knowing"], url: LN, source_kind: "press" },
];

test("a site's name in its address", () => {
  assert.equal(siteKey(TO), "timeout");
  assert.equal(siteKey("https://www.standard.co.uk/x"), "standard");
  assert.equal(siteKey("https://gb.britishlistedbuildings.co.uk/1"), "britishlistedbuildings");
});

test("a named press source and the venue's own page become links", () => {
  const segs = linkSources("Time Out describes it as fitted out with Formica. The café's own page stresses its panelling.", "vibe", ev);
  assert.deepEqual(segs.filter((s) => s.href), [
    { text: "Time Out", href: TO },
    { text: "own page", href: OWN },
  ]);
  assert.equal(segs.map((s) => s.text).join(""), "Time Out describes it as fitted out with Formica. The café's own page stresses its panelling.");
});

test("a source cited in another part of the story is still linked", () => {
  const segs = linkSources("The Krays were regulars, according to a 2005 Londonist report.", "worth_knowing", ev);
  assert.deepEqual(segs.filter((s) => s.href), [{ text: "Londonist", href: LN }]);
});

test("names not in the evidence and lowercase words stay plain", () => {
  assert.deepEqual(linkSources("The Guardian loved the timeout.", "vibe", ev), [{ text: "The Guardian loved the timeout." }]);
});

test("names with & and aliases match", () => {
  const e = [
    { fields: ["story"], url: "https://www.countryandtownhouse.co.uk/a", source_kind: "press" },
    { fields: ["story"], url: "https://secretldn.com/b", source_kind: "press" },
  ];
  const segs = linkSources("Country & Town House and Secret London both liked it.", "now", e);
  assert.deepEqual(segs.filter((s) => s.href).map((s) => s.text), ["Country & Town House", "Secret London"]);
});

test("a possessive stays outside the link", () => {
  const e = [{ fields: ["story.then"], url: "https://secretldn.com/vpm", source_kind: "press" }];
  assert.deepEqual(linkSources("It became, in Secret London's words, vital.", "then", e), [
    { text: "It became, in " }, { text: "Secret London", href: "https://secretldn.com/vpm" }, { text: "'s words, vital." },
  ]);
});
