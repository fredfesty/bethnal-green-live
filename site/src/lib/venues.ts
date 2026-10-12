// The venue guide: every venue in the registry (data/sources), with its checked profile (data/venues) when it has one,
// plus what our own verified listings say about it (what's on there next, and what those nights cost).
// A profile is only shown once the independent check has stamped it (review) and nothing in it is in doubt (needs_review).
import fs from "node:fs";
import path from "node:path";
import { loadEvents, priceLabel, type Evidence, type SiteEvent } from "./data";
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
  events: SiteEvent[];        // upcoming listings here
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
  "record-shop": "Record shop", "in-store": "In-store gigs",
  "hi-fi-listening-bar": "Listening bar", "vinyl-bar": "Vinyl bar", "rooftop-bar": "Rooftop bar", "cocktail-bar": "Cocktail bar",
  "wine-bar": "Wine bar", taproom: "Taproom", restaurant: "Restaurant", cafe: "Café", "cafe-bar": "Café bar", bakery: "Bakery",
  "food-hall": "Food hall", "bottle-shop": "Bottle shop", "cookery-school": "Cookery school", gallery: "Gallery", museum: "Museum",
  "music-hall": "Music hall", bookshop: "Bookshop", market: "Market", "street-market": "Street market",
  "food-market": "Food market", "flower-market": "Flower market", "covered-market": "Covered market", park: "Park",
  "city-farm": "City farm", "nature-reserve": "Nature reserve", library: "Library", "community-centre": "Community centre",
  "sports-venue": "Sports venue", "leisure-centre": "Leisure centre",
};

export const KIND_GROUPS: { id: string; label: string; types: string[] }[] = [
  { id: "clubs", label: "Clubs & DJ bars", types: ["club", "dj-bar"] },
  { id: "gigs", label: "Gig venues", types: ["gig-venue", "live-music", "in-store", "record-shop"] },
  { id: "pubs", label: "Pubs & bars", types: ["pub", "bar"] },
  { id: "queer", label: "Queer venues", types: ["queer-venue", "queer-friendly", "cabaret", "drag", "cabaret-drag"] },
  { id: "arts", label: "Theatres, cinemas & arts centres", types: ["arts-centre", "theatre", "cinema", "comedy", "music-hall"] },
  { id: "galleries", label: "Galleries & museums", types: ["gallery", "museum", "bookshop"] },
  { id: "food", label: "Restaurants, cafés & bars", types: ["restaurant", "cafe", "cafe-bar", "bakery", "food-hall", "wine-bar", "taproom", "cocktail-bar"] },
  { id: "markets", label: "Markets", types: ["market", "street-market", "food-market", "flower-market", "covered-market"] },
  { id: "community", label: "Parks, farms & community", types: ["park", "city-farm", "nature-reserve", "library", "community-centre", "church", "sports-venue", "leisure-centre"] },
];

export const ZONE_ORDER = ["core", "fringe", "outer"];
export const ZONE_HEADING: Record<string, { title: string; blurb: string }> = {
  core: { title: "In Bethnal Green", blurb: "E2, or within about a kilometre of the tube." },
  fringe: { title: "A short walk", blurb: "Up to about twenty minutes on foot." },
  outer: { title: "Worth the trip", blurb: "Further out: Shoreditch, Dalston, Hackney Central and Hackney Wick." },
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

let cache: SiteVenue[] | null = null;

export function loadVenues(): SiteVenue[] {
  if (cache) return cache;
  const registry = new Map<string, any>();
  for (const reg of readDir(path.join(REPO, "data", "sources"))) {
    for (const v of reg.venues ?? []) if (!registry.has(v.id)) registry.set(v.id, v);
  }
  const profiles = new Map<string, VenueProfile>();
  for (const p of readDir(path.join(REPO, "data", "venues")) as VenueProfile[]) {
    if (p?.id && p.review && !p.needs_review) profiles.set(p.id, p);
  }
  const events = loadEvents();

  cache = [...registry.values()].map((r): SiteVenue => {
    const profile = profiles.get(r.id) ?? null;
    const here = events.filter((e) => e.venue.venue_id === r.id);
    const kinds = (r.type ?? []).map((t: string) => VENUE_TYPE[t]).filter(Boolean);
    const seen = new Set<string>();
    const sources = (profile?.evidence ?? [])
      .filter((ev) => (seen.has(ev.url) ? false : (seen.add(ev.url), true)))
      .map((ev) => ({ url: ev.url, host: host(ev.url), kind: ev.source_kind, retrieved: ev.retrieved_at }));
    const listingKinds = [...new Set(here.map((e) => kindLabel(e)))];
    return {
      id: r.id,
      name: r.name,
      zone: r.zone,
      address: profile?.address ?? r.address ?? null,
      postcode: profile?.postcode ?? r.postcode ?? null,
      kinds,
      kindGroups: KIND_GROUPS.filter((g) => (r.type ?? []).some((t: string) => g.types.includes(t))).map((g) => g.id),
      profile,
      website: profile?.website ?? null,
      events: here,
      listingPrices: priceSpan(here),
      listingKinds,
      sources,
      searchText: [r.name, ...(r.aliases ?? []), ...kinds, ...(profile?.music.styles ?? []), r.address ?? "", r.postcode ?? ""]
        .join(" ").toLowerCase(),
    };
  }).sort((a, b) => ZONE_ORDER.indexOf(a.zone) - ZONE_ORDER.indexOf(b.zone) || sortName(a.name).localeCompare(sortName(b.name)));
  return cache;
}

let ids: Set<string> | null = null;
/** Path of a venue's page, or null when the venue has none (not in the registry). */
export function venuePath(venueId: string | null | undefined): string | null {
  if (!venueId) return null;
  ids ??= new Set(loadVenues().map((v) => v.id));
  return ids.has(venueId) ? `venues/${venueId}.html` : null;
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
