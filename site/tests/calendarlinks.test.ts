// Run with `npm test`.
import { test } from "node:test";
import assert from "node:assert/strict";
import { calendarLinks, googleLink, microsoft365Link, outlookComLink, yahooLink, type CalendarEntry } from "../src/lib/calendarlinks.ts";

const timed: CalendarEntry = {
  title: "Sold out: Disco & Soul Night",
  location: "The Sebright Arms, 31-35 Coate St, E2 9AG",
  details: "£8\nTickets: https://example.com/t?a=1&b=2\nDetails: https://bgl.example/events/x.html",
  start: new Date("2026-10-16T22:00:00+01:00"),
  end: new Date("2026-10-17T03:00:00+01:00"),
};

const run: CalendarEntry = {
  title: "Open Studios",
  location: "Chisenhale Studios, E3 5QZ",
  details: "Free",
  allDayFrom: "2026-10-30",
  allDayUntilExclusive: "2026-11-02", // last day 1 November
};

const params = (href: string) => new URL(href).searchParams;

test("Google Calendar gets the exact UTC times, title, place and details", () => {
  const p = params(googleLink(timed));
  assert.equal(new URL(googleLink(timed)).origin, "https://calendar.google.com");
  assert.equal(p.get("action"), "TEMPLATE");
  assert.equal(p.get("dates"), "20261016T210000Z/20261017T020000Z");
  assert.equal(p.get("text"), timed.title);
  assert.equal(p.get("location"), timed.location);
  assert.equal(p.get("details"), timed.details);
});

test("Google Calendar gets a run as all-day dates with an exclusive end", () => {
  assert.equal(params(googleLink(run)).get("dates"), "20261030/20261102");
});

test("Outlook.com and Microsoft 365 use their own hosts and ISO UTC times", () => {
  for (const [href, host] of [[outlookComLink(timed), "outlook.live.com"], [microsoft365Link(timed), "outlook.office.com"]]) {
    const u = new URL(href);
    assert.equal(u.host, host);
    assert.equal(u.searchParams.get("rru"), "addevent");
    assert.equal(u.searchParams.get("startdt"), "2026-10-16T21:00:00Z");
    assert.equal(u.searchParams.get("enddt"), "2026-10-17T02:00:00Z");
    assert.equal(u.searchParams.get("allday"), "false");
    assert.equal(u.searchParams.get("subject"), timed.title);
    assert.equal(u.searchParams.get("body"), timed.details);
    assert.equal(u.searchParams.get("location"), timed.location);
  }
});

test("Outlook gets a run as an all-day entry", () => {
  const p = params(outlookComLink(run));
  assert.equal(p.get("startdt"), "2026-10-30");
  assert.equal(p.get("enddt"), "2026-11-02");
  assert.equal(p.get("allday"), "true");
});

test("Yahoo gets UTC times, and a run as all-day from the first to the last day", () => {
  const t = params(yahooLink(timed));
  assert.equal(t.get("st"), "20261016T210000Z");
  assert.equal(t.get("et"), "20261017T020000Z");
  assert.equal(t.get("title"), timed.title);
  assert.equal(t.get("desc"), timed.details);
  assert.equal(t.get("in_loc"), timed.location);
  const r = params(yahooLink(run));
  assert.equal(r.get("st"), "20261030");
  assert.equal(r.get("et"), "20261101");
  assert.equal(r.get("dur"), "allday");
});

test("a winter event keeps its clock time (GMT, no offset)", () => {
  const winter = { ...timed, start: new Date("2026-11-06T19:30:00+00:00"), end: new Date("2026-11-06T23:00:00+00:00") };
  assert.equal(params(googleLink(winter)).get("dates"), "20261106T193000Z/20261106T230000Z");
});

test("special characters in text are encoded, not left to break the link", () => {
  const p = params(googleLink({ ...timed, title: "Rock & Roll #1 / 100% fun?" }));
  assert.equal(p.get("text"), "Rock & Roll #1 / 100% fun?");
});

test("the menu offers Google, Outlook.com, Microsoft 365 and Yahoo, in that order", () => {
  assert.deepEqual(calendarLinks(timed).map((l) => l.id), ["google", "outlook", "microsoft365", "yahoo"]);
});
