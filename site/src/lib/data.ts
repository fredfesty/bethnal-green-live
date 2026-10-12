// Loads verified events from ../data/events (the repo's published events) for the build.
// With BGL_DEMO=1 it uses made-up sample events instead, for previews before real listings exist.
import fs from "node:fs";
import path from "node:path";
import { addDays, hasTime, instant, londonDate, todayInLondon, type When } from "./time";
import { kindLabel, typeGroup } from "./labels";
import { demoEvents } from "./demo";
import config from "../site.config.mjs";

export const DEMO = process.env.BGL_DEMO === "1";
const REPO = path.resolve(process.cwd(), "..");

export interface Price { known: boolean; is_free?: boolean | null; min_gbp?: number | null; max_gbp?: number | null; notes?: string | null }
export interface Evidence { fields: string[]; url: string; quote: string; retrieved_at: string; source_kind: string }
export interface RawEvent {
  id: string; category: string; subcategory: string; title: string;
  venue: { venue_id: string | null; name: string; address?: string | null; postcode?: string | null };
  starts_at: When; ends_at?: When | null; recurrence?: string | null; run_schedule?: string | null; zone: string; worth_the_trip?: boolean;
  lineup?: string[]; genres?: string[]; price: Price; ticket_url: string | null; age_restriction?: string | null;
  accessibility?: string | null; status: string; evidence: Evidence[];
  verification: { verified_at: string; outcome: string; removed_fields?: string[] };
  listing?: { headline?: string | null; blurb: string } | null;
  needs_review?: { since: string; reason: string } | null;
  updated_at: string;
}
export interface SiteEvent extends RawEvent {
  date: string;          // London date, YYYY-MM-DD (the opening day, for a run)
  until: string;         // last London date it's on (same as date, except for runs)
  isRun: boolean;        // an exhibition, theatre run or multi-day menu, shown under "On now"
  endsAtIso: string;     // when it stops being "upcoming"
  group: string;         // filter group id
  priceLabel: string;
  priceFilter: string;   // "free" | lowest price as a number | "unknown"
  searchText: string;
  sources: { url: string; host: string; kind: string }[];
}

export function priceLabel(p: Price): string {
  if (!p.known) return "Price not listed";
  if (p.is_free) return "Free";
  const min = p.min_gbp ?? null, max = p.max_gbp ?? null;
  const gbp = (n: number) => `£${Number.isInteger(n) ? n : n.toFixed(2)}`;
  if (min === 0 && max) return `Free–${gbp(max)}`;
  if (min !== null && max !== null && max !== min) return `${gbp(min)}–${gbp(max)}`;
  if (min !== null && max === null) return `From ${gbp(min)}`;
  return min !== null ? gbp(min) : "See tickets";
}

function readJsonFiles(dir: string): any[] {
  if (!fs.existsSync(dir)) return [];
  const out: any[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!entry.name.startsWith("_")) out.push(...readJsonFiles(p));
    } else if (entry.name.endsWith(".json")) {
      try {
        out.push(JSON.parse(fs.readFileSync(p, "utf8").replace(/^﻿/, "")));
      } catch {
        console.warn(`[bgl] skipped unreadable ${p}`);
      }
    }
  }
  return out;
}

function venueRegistry(): Map<string, any> {
  const map = new Map<string, any>();
  for (const reg of readJsonFiles(path.join(REPO, "data", "sources"))) {
    for (const v of reg.venues ?? []) map.set(v.id, v);
  }
  return map;
}

const daysBetween = (a: string, b: string) => Math.round((Date.parse(`${b}T12:00:00Z`) - Date.parse(`${a}T12:00:00Z`)) / 864e5);

function enrich(e: RawEvent, venues: Map<string, any>): SiteEvent {
  const v = e.venue.venue_id ? venues.get(e.venue.venue_id) : undefined;
  const venue = { ...e.venue, address: e.venue.address ?? v?.address ?? null, postcode: e.venue.postcode ?? v?.postcode ?? null };
  const start = instant(e.starts_at);
  const date = londonDate(e.starts_at);
  const lastDay = e.ends_at ? londonDate(e.ends_at) : date;
  // Runs end two or more days after they open; an overnight club night ends the next day and isn't a run.
  const isRun = daysBetween(date, lastDay) >= 2;
  const end = e.ends_at && hasTime(e.ends_at) ? instant(e.ends_at)
    : e.ends_at ? new Date(`${addDays(lastDay, 1)}T00:00:00Z`) // a date-only end lasts all that day
    : hasTime(e.starts_at) ? new Date(start.getTime() + 4 * 3600e3)
    : new Date(`${date}T23:00:00Z`);
  const seen = new Set<string>();
  const sources = e.evidence
    .filter((ev) => (seen.has(ev.url) ? false : (seen.add(ev.url), true)))
    .map((ev) => ({ url: ev.url, host: new URL(ev.url).hostname.replace(/^www\./, ""), kind: ev.source_kind }));
  return {
    ...e,
    venue,
    date,
    until: isRun ? lastDay : date,
    isRun,
    endsAtIso: end.toISOString(),
    group: typeGroup(e),
    priceLabel: priceLabel(e.price),
    priceFilter: !e.price.known ? "unknown" : e.price.is_free ? "free" : String(e.price.min_gbp ?? "unknown"),
    searchText: [e.title, venue.name, kindLabel(e), ...(e.lineup ?? []), ...(e.genres ?? [])].join(" ").toLowerCase(),
    sources,
  };
}

let cache: SiteEvent[] | null = null;

/** Upcoming, publishable events, soonest first. Events under review are never shown. */
export function loadEvents(): SiteEvent[] {
  if (cache) return cache;
  const venues = venueRegistry();
  const raw: RawEvent[] = DEMO ? demoEvents(todayInLondon()) : readJsonFiles(path.join(REPO, "data", "events"));
  const now = Date.now();
  const last = addDays(todayInLondon(), config.daysAhead);
  cache = raw
    .filter((e) => e && e.id && !e.needs_review)
    .map((e) => enrich(e, venues))
    .filter((e) => new Date(e.endsAtIso).getTime() > now && e.date <= last)
    .sort((a, b) => instant(a.starts_at).getTime() - instant(b.starts_at).getTime() || a.title.localeCompare(b.title));
  return cache;
}

export function byDate(events: SiteEvent[]): [string, SiteEvent[]][] {
  const m = new Map<string, SiteEvent[]>();
  for (const e of events) m.set(e.date, [...(m.get(e.date) ?? []), e]);
  return [...m.entries()];
}

export interface RegularMarket { id: string; name: string; zone: string; schedule: string; source: string }

/** Markets that trade every week. Their hours are quoted from each market's own page, recorded in the
 *  community source registry by a person; they're shown apart from dated events. */
export function regularMarkets(): RegularMarket[] {
  const reg = readJsonFiles(path.join(REPO, "data", "sources")).find((r) => r.category === "community");
  return (reg?.venues ?? [])
    .filter((v: any) => v.regular_schedule && v.zone !== "outer" && v.status === "open"
      && (v.type ?? []).some((t: string) => t === "market" || t === "street-market"))
    .map((v: any) => ({ id: v.id, name: v.name, zone: v.zone, schedule: v.regular_schedule,
      source: (v.listings ?? []).find((l: any) => l.role === "primary")?.url ?? v.website }))
    .sort((a: RegularMarket, b: RegularMarket) => (a.zone === b.zone ? a.name.localeCompare(b.name) : a.zone === "core" ? -1 : 1));
}

export const mapLink = (e: SiteEvent) =>
  `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent([e.venue.name, e.venue.address, e.venue.postcode].filter(Boolean).join(", "))}`;

let allCache: Map<string, SiteEvent> | null = null;

/** Every published event by id, past ones included (for newsletter archives). Events under review are left out. */
export function loadAllEventsById(): Map<string, SiteEvent> {
  if (allCache) return allCache;
  const venues = venueRegistry();
  const raw: RawEvent[] = DEMO ? demoEvents(todayInLondon()) : readJsonFiles(path.join(REPO, "data", "events"));
  allCache = new Map(raw.filter((e) => e && e.id && !e.needs_review).map((e) => [e.id, enrich(e, venues)]));
  return allCache;
}
