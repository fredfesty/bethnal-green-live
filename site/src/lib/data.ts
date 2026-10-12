// Loads verified events from ../data/events (the repo's published events) for the build.
// With BGL_DEMO=1 it uses made-up sample events instead, for previews before real listings exist.
import fs from "node:fs";
import path from "node:path";
import { addDays, hasTime, instant, londonDate, todayInLondon, type When } from "./time";
import { typeGroup } from "./labels";
import { demoEvents } from "./demo";
import config from "../site.config.mjs";

export const DEMO = process.env.BGL_DEMO === "1";
const REPO = path.resolve(process.cwd(), "..");

export interface Price { known: boolean; is_free?: boolean | null; min_gbp?: number | null; max_gbp?: number | null; notes?: string | null }
export interface Evidence { fields: string[]; url: string; quote: string; retrieved_at: string; source_kind: string }
export interface RawEvent {
  id: string; category: string; subcategory: string; title: string;
  venue: { venue_id: string | null; name: string; address?: string | null; postcode?: string | null };
  starts_at: When; ends_at?: When | null; recurrence?: string | null; zone: string; worth_the_trip?: boolean;
  lineup?: string[]; genres?: string[]; price: Price; ticket_url: string | null; age_restriction?: string | null;
  accessibility?: string | null; status: string; evidence: Evidence[];
  verification: { verified_at: string; outcome: string; removed_fields?: string[] };
  listing?: { headline?: string | null; blurb: string } | null;
  needs_review?: { since: string; reason: string } | null;
  updated_at: string;
}
export interface SiteEvent extends RawEvent {
  date: string;          // London date, YYYY-MM-DD
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

function enrich(e: RawEvent, venues: Map<string, any>): SiteEvent {
  const v = e.venue.venue_id ? venues.get(e.venue.venue_id) : undefined;
  const venue = { ...e.venue, address: e.venue.address ?? v?.address ?? null, postcode: e.venue.postcode ?? v?.postcode ?? null };
  const start = instant(e.starts_at);
  const end = e.ends_at && hasTime(e.ends_at) ? instant(e.ends_at)
    : hasTime(e.starts_at) ? new Date(start.getTime() + 4 * 3600e3)
    : new Date(`${londonDate(e.starts_at)}T23:00:00Z`);
  const seen = new Set<string>();
  const sources = e.evidence
    .filter((ev) => (seen.has(ev.url) ? false : (seen.add(ev.url), true)))
    .map((ev) => ({ url: ev.url, host: new URL(ev.url).hostname.replace(/^www\./, ""), kind: ev.source_kind }));
  return {
    ...e,
    venue,
    date: londonDate(e.starts_at),
    endsAtIso: end.toISOString(),
    group: typeGroup(e),
    priceLabel: priceLabel(e.price),
    priceFilter: !e.price.known ? "unknown" : e.price.is_free ? "free" : String(e.price.min_gbp ?? "unknown"),
    searchText: [e.title, venue.name, ...(e.lineup ?? []), ...(e.genres ?? [])].join(" ").toLowerCase(),
    sources,
  };
}

let cache: SiteEvent[] | null = null;
let allCache: SiteEvent[] | null = null;

/** Every publishable event we have ever listed, past and future. Events under review are never included. */
export function loadAllEvents(): SiteEvent[] {
  if (allCache) return allCache;
  const venues = venueRegistry();
  const raw: RawEvent[] = DEMO ? demoEvents(todayInLondon()) : readJsonFiles(path.join(REPO, "data", "events"));
  allCache = raw.filter((e) => e && e.id && !e.needs_review).map((e) => enrich(e, venues));
  return allCache;
}

/** Events that have finished, most recent first. */
export function loadPastEvents(): SiteEvent[] {
  const now = Date.now();
  return loadAllEvents()
    .filter((e) => new Date(e.endsAtIso).getTime() <= now)
    .sort((a, b) => instant(b.starts_at).getTime() - instant(a.starts_at).getTime());
}

/** Upcoming, publishable events, soonest first. Events under review are never shown. */
export function loadEvents(): SiteEvent[] {
  if (cache) return cache;
  const now = Date.now();
  const last = addDays(todayInLondon(), config.daysAhead);
  cache = loadAllEvents()
    .filter((e) => new Date(e.endsAtIso).getTime() > now && e.date <= last)
    .sort((a, b) => instant(a.starts_at).getTime() - instant(b.starts_at).getTime() || a.title.localeCompare(b.title));
  return cache;
}

export function byDate(events: SiteEvent[]): [string, SiteEvent[]][] {
  const m = new Map<string, SiteEvent[]>();
  for (const e of events) m.set(e.date, [...(m.get(e.date) ?? []), e]);
  return [...m.entries()];
}

export const mapLink = (e: SiteEvent) =>
  `https://www.openstreetmap.org/search?query=${encodeURIComponent([e.venue.name, e.venue.address, e.venue.postcode].filter(Boolean).join(", "))}`;
