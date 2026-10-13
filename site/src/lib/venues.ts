// The venue guide: every venue in the registry (data/sources), every venue the weekly venue run added (data/venues),
// and every other venue that appears in our listings, so that every listed event has a venue page to link to.
// A profile is only shown once the independent check has stamped it after its last change (review.checked_at is
// later than profiled_at) and nothing in it is in doubt (needs_review).
import fs from "node:fs";
import path from "node:path";
import { loadEvents, loadPastEvents, priceLabel, type Evidence, type SiteEvent } from "./data";
import { kindLabel } from "./labels";

const REPO = path.resolve(process.cwd(), "..");

export interface VenueProfile {
  id: string; name: string; zone: string; address?: string | null; postcode?: string | null; website?: string | null;
  summary: string | null;
  music: { styles: string[]; notes?: string | null };
  crowd: string | null;
  accessibility: { step_free: boolean | null; accessible_toilet: boolean | null; hearing_loop?: boolean | null; notes?: string | null; access_page?: string | null };
  cost: { free_entry: "always" | "some-nights" | "no" | null; notes?: string | null };
  age_policy?: string | null; capacity?: number | null;
  types?: string[]; aliases?: string[]; status?: "open" | "closed" | "temporarily-closed" | "opening-soon";
  discovered?: { first_seen: string; found_by: string[] } | null;
  evidence: Evidence[];
  profiled_at: string;
  review?: { checked_at: string; removed_fields: string[] } | null;
  needs_review?: { since: string; reason: string } | null;
}

export interface SiteVenue {
  id: string; name: string; zone: string; address: string | null; postcode: string | null;
  kinds: string[];            // reader-facing labels from the registry's types
  kindGroups: string[];       // filter group ids
  profile: VenueProfile | null; // only a checked profile with nothing in doubt
  website: string | null;     // only when a checked profile backs it
  status: string;             // open | closed | temporarily-closed | opening-soon (only from a checked profile)
  source: "registry" | "profile" | "listings"; // where we know it from
  events: SiteEvent[];        // upcoming listings here
  past: SiteEvent[];          // finished listings here, most recent first
  listingPrices: string | null; // e.g. "Free–£15", from our listings
  listingKinds: string[];     // e.g. ["Club night", "Gig"], from our listings
  sources: { url: string; host: string; kind: string; retrieved: string }[];
  searchText: string;
}

// Reader-facing names for the registry's venue types.
export const VENUE_TYPE: Record<string, string> = {
  "gig-venue": "Gig venue", "live-music": "Live music", club: "Club", "dj-bar": "DJ bar", pub: "Pub", bar: "Bar",
  jazz: "Jazz", "queer-venue": "Queer venue", "queer-friendly": "Queer-friendly", cabaret: "Cabaret", drag: "Drag",
  "cabaret-drag": "Cabaret & drag", karaoke: "Karaoke", "open-mic": "Open mic", church: "Church",
  "arts-centre": "Arts centre", theatre: "Theatre", cinema: "Cinema", comedy: "Comedy",
  "record-shop": "Record shop", "in-store": "In-store gigs", "music-venue": "Music venue",
  "hi-fi-listening-bar": "Listening bar", "vinyl-bar": "Vinyl bar", "rooftop-bar": "Rooftop bar", "cocktail-bar": "Cocktail bar",
  "wine-bar": "Wine bar", taproom: "Taproom", restaurant: "Restaurant", cafe: "Café", "cafe-bar": "Café bar", bakery: "Bakery",
  "food-hall": "Food hall", "bottle-shop": "Bottle shop", "cookery-school": "Cookery school", gallery: "Gallery", museum: "Museum",
  "music-hall": "Music hall", bookshop: "Bookshop", market: "Market", "street-market": "Street market",
  "food-market": "Food market", "flower-market": "Flower market", "covered-market": "Covered market", park: "Park",
  "city-farm": "City farm", "nature-reserve": "Nature reserve", library: "Library", "community-centre": "Community centre",
  "community-venue": "Community venue", "sports-venue": "Sports venue", "leisure-centre": "Leisure centre",
  sauna: "Sauna", "wellness-studio": "Wellness studio", "yoga-studio": "Yoga studio", "pilates-studio": "Pilates studio",
  "meditation-centre": "Meditation centre", gym: "Gym", "climbing-wall": "Climbing wall",
};

export const KIND_GROUPS: { id: string; label: string; types: string[] }[] = [
  { id: "clubs", label: "Clubs & DJ bars", types: ["club", "dj-bar"] },
  { id: "gigs", label: "Gig venues", types: ["gig-venue", "music-venue", "live-music", "in-store", "record-shop"] },
  { id: "pubs", label: "Pubs & bars", types: ["pub", "bar"] },
  { id: "queer", label: "Queer venues", types: ["queer-venue", "queer-friendly", "cabaret", "drag", "cabaret-drag"] },
  { id: "arts", label: "Theatres, cinemas & arts centres", types: ["arts-centre", "theatre", "cinema", "comedy", "music-hall"] },
  { id: "galleries", label: "Galleries & museums", types: ["gallery", "museum", "bookshop"] },
  { id: "food", label: "Restaurants, cafés & bars", types: ["restaurant", "cafe", "cafe-bar", "bakery", "food-hall", "wine-bar", "taproom", "cocktail-bar"] },
  { id: "markets", label: "Markets", types: ["market", "street-market", "food-market", "flower-market", "covered-market"] },
  { id: "wellness", label: "Health & wellness", types: ["sauna", "wellness-studio", "yoga-studio", "pilates-studio", "meditation-centre", "gym", "climbing-wall"] },
  { id: "community", label: "Parks, farms & community", types: ["park", "city-farm", "nature-reserve", "library", "community-centre", "community-venue", "church", "sports-venue", "leisure-centre"] },
];

export const ZONE_ORDER = ["core", "fringe", "outer"];
export const ZONE_HEADING: Record<string, { title: string; blurb: string }> = {
  core: { title: "In Bethnal Green", blurb: "E2, or within about a kilometre of the tube." },
  fringe: { title: "A short walk", blurb: "Up to about twenty minutes on foot." },
  outer: { title: "Worth the trip", blurb: "Further out: Shoreditch, Dalston, Hackney Central and Hackney Wick." },
};

export const STATUS_NOTE: Record<string, string> = {
  closed: "This venue has closed.",
  "temporarily-closed": "This venue is temporarily closed.",
  "opening-soon": "This venue hasn't opened yet.",
};

export const FREE_ENTRY: Record<string, string> = {
  always: "Free entry",
  "some-nights": "Free on some nights or at some times",
  no: "Always a charge",
};

function readJson(p: string): any | null {
  try {
    return JSON.parse(fs.readFileSync(p, "utf8").replace(/^﻿/, ""));
  } catch {
    console.warn(`[bgl] skipped unreadable ${p}`);
    return null;
  }
}

function readDir(dir: string): any[] {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isFile() && e.name.endsWith(".json"))
    .map((e) => readJson(path.join(dir, e.name)))
    .filter(Boolean);
}

const sortName = (s: string) => s.toLowerCase().replace(/^the\s+/, "");
const host = (u: string) => new URL(u).hostname.replace(/^www\./, "");

function priceSpan(events: SiteEvent[]): string | null {
  const priced = events.filter((e) => e.price.known && e.status !== "cancelled");
  if (!priced.length) return null;
  const mins = priced.map((e) => (e.price.is_free ? 0 : e.price.min_gbp ?? 0));
  const maxes = priced.map((e) => (e.price.is_free ? 0 : e.price.max_gbp ?? e.price.min_gbp ?? 0));
  const lo = Math.min(...mins), hi = Math.max(...maxes);
  if (hi === 0) return "Free";
  return priceLabel({ known: true, is_free: false, min_gbp: lo, max_gbp: hi === lo ? null : hi });
}

export const normName = (s: string | null | undefined) =>
  (s ?? "").toLowerCase().replace(/&/g, "and").replace(/’/g, "'").replace(/^the\s+/, "").replace(/[^a-z0-9]+/g, "");
const slugify = (s: string) =>
  s.toLowerCase().replace(/&/g, "and").replace(/['’]/g, "").replace(/^the\s+/, "").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60) || "venue";

const visible = (p: VenueProfile | undefined) =>
  !!p && !!p.review && !p.needs_review && new Date(p.review.checked_at).getTime() >= new Date(p.profiled_at).getTime();

const kindsOf = (types: string[]) => types.map((t) => VENUE_TYPE[t]).filter(Boolean);
const groupsOf = (types: string[]) => KIND_GROUPS.filter((g) => types.some((t) => g.types.includes(t))).map((g) => g.id);

let cache: SiteVenue[] | null = null;
let byEvent: Map<string, string> | null = null; // event id -> venue id

export function loadVenues(): SiteVenue[] {
  if (cache) return cache;
  const registry = new Map<string, any>();
  for (const reg of readDir(path.join(REPO, "data", "sources"))) {
    for (const v of reg.venues ?? []) if (!registry.has(v.id)) registry.set(v.id, v);
  }
  const profiles = new Map<string, VenueProfile>();
  for (const p of readDir(path.join(REPO, "data", "venues")) as VenueProfile[]) if (p?.id) profiles.set(p.id, p);

  // The venues we know: the registry, then checked profiles of venues the weekly run added.
  interface Base { id: string; name: string; zone: string; address: string | null; postcode: string | null;
    types: string[]; aliases: string[]; profile: VenueProfile | null; source: SiteVenue["source"] }
  const bases = new Map<string, Base>();
  for (const r of registry.values()) {
    const p = profiles.get(r.id);
    const shown = visible(p) ? p! : null;
    bases.set(r.id, { id: r.id, name: r.name, zone: r.zone, address: shown?.address ?? r.address ?? null,
      postcode: shown?.postcode ?? r.postcode ?? null, types: r.type ?? [], aliases: [...(r.aliases ?? []), ...(p?.aliases ?? [])],
      profile: shown, source: "registry" });
  }
  for (const p of profiles.values()) {
    if (bases.has(p.id) || !visible(p)) continue;
    bases.set(p.id, { id: p.id, name: p.name, zone: p.zone, address: p.address ?? null, postcode: p.postcode ?? null,
      types: p.types ?? [], aliases: p.aliases ?? [], profile: p, source: "profile" });
  }

  // Every listed event gets a venue: by id, then by name, then a listings-only venue made from the event itself.
  const names = new Map<string, string>();
  for (const b of bases.values()) for (const n of [b.name, ...b.aliases]) if (normName(n)) names.set(normName(n), b.id);
  byEvent = new Map();
  const upcoming = loadEvents(), past = loadPastEvents();
  for (const e of [...upcoming, ...past]) {
    let id = e.venue.venue_id && bases.has(e.venue.venue_id) ? e.venue.venue_id : names.get(normName(e.venue.name));
    if (!id) {
      id = e.venue.venue_id ?? slugify(e.venue.name);
      while (bases.has(id) && bases.get(id)!.source !== "listings") id += "-2";
      if (!bases.has(id)) {
        bases.set(id, { id, name: e.venue.name, zone: e.zone, address: e.venue.address ?? null, postcode: e.venue.postcode ?? null,
          types: [], aliases: [], profile: null, source: "listings" });
        names.set(normName(e.venue.name), id);
      }
    }
    byEvent.set(e.id, id);
  }

  cache = [...bases.values()].map((b): SiteVenue => {
    const profile = b.profile;
    const here = upcoming.filter((e) => byEvent!.get(e.id) === b.id);
    const before = past.filter((e) => byEvent!.get(e.id) === b.id);
    const kinds = kindsOf(b.types);
    const seen = new Set<string>();
    const sources = (profile?.evidence ?? [])
      .filter((ev) => (seen.has(ev.url) ? false : (seen.add(ev.url), true)))
      .map((ev) => ({ url: ev.url, host: host(ev.url), kind: ev.source_kind, retrieved: ev.retrieved_at }));
    const listingKinds = [...new Set([...here, ...before].map((e) => kindLabel(e)))];
    return {
      id: b.id,
      name: b.name,
      zone: b.zone,
      address: b.address,
      postcode: b.postcode,
      kinds,
      kindGroups: groupsOf(b.types),
      profile,
      website: profile?.website ?? null,
      status: profile?.status ?? "open",
      source: b.source,
      events: here,
      past: before,
      listingPrices: priceSpan(here),
      listingKinds,
      sources,
      searchText: [b.name, ...b.aliases, ...kinds, ...(profile?.music.styles ?? []), b.address ?? "", b.postcode ?? ""]
        .join(" ").toLowerCase(),
    };
  }).sort((a, b) => ZONE_ORDER.indexOf(a.zone) - ZONE_ORDER.indexOf(b.zone) || sortName(a.name).localeCompare(sortName(b.name)));
  return cache;
}

/** Venues for the Venues page: everything except closed venues. */
export const listedVenues = () => loadVenues().filter((v) => v.status !== "closed");

/** Path of an event's venue page. Every listed event has one. */
export function venuePathFor(e: SiteEvent): string {
  loadVenues();
  const id = byEvent!.get(e.id);
  if (!id) throw new Error(`[bgl] no venue page for event ${e.id} (${e.venue.name})`);
  return `venues/${id}.html`;
}

export const venueMapLink = (v: SiteVenue) =>
  `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent([v.name, v.address, v.postcode].filter(Boolean).join(", "))}`;

/** Access facts as short reader-facing lines, only those a source states. */
export function accessLines(p: VenueProfile): { text: string; good: boolean }[] {
  const a = p.accessibility, out: { text: string; good: boolean }[] = [];
  if (a.step_free === true) out.push({ text: "Step-free entry", good: true });
  if (a.step_free === false) out.push({ text: "Not step-free", good: false });
  if (a.accessible_toilet === true) out.push({ text: "Accessible toilet", good: true });
  if (a.accessible_toilet === false) out.push({ text: "No accessible toilet", good: false });
  if (a.hearing_loop === true) out.push({ text: "Hearing loop", good: true });
  if (a.hearing_loop === false) out.push({ text: "No hearing loop", good: false });
  return out;
}
