// Made-up events for previewing the site before real listings exist. Every venue and act here is invented.
// Only used when BGL_DEMO=1; the live site reads verified events from data/events.
import { addDays } from "./time";
import type { RawEvent } from "./data";

const VENUES = {
  lantern: { venue_id: null, name: "The Lantern Rooms", address: "12 Example Row, London", postcode: "E2 0ZZ", zone: "core" },
  arch: { venue_id: null, name: "Arch 41", address: "41 Viaduct Yard, London", postcode: "E2 0ZY", zone: "core" },
  finch: { venue_id: null, name: "The Finch & Barrow", address: "88 Sample Road, London", postcode: "E2 0ZX", zone: "core" },
  agnes: { venue_id: null, name: "St Agnes Hall", address: "3 Demonstration Square, London", postcode: "E2 0ZW", zone: "core" },
  canal: { venue_id: null, name: "Canalside Studios", address: "Unit 5, Towpath Works, London", postcode: "E2 0ZV", zone: "fringe" },
  north: { venue_id: null, name: "Northbank Warehouse", address: "1 Placeholder Wharf, London", postcode: "E9 0ZZ", zone: "outer" },
} as const;

type V = keyof typeof VENUES;

function offset(date: string): string {
  // London is on +01:00 from the last Sunday in March to the last Sunday in October.
  const d = new Date(`${date}T12:00:00Z`);
  const lastSunday = (month: number) => {
    const t = new Date(Date.UTC(d.getUTCFullYear(), month + 1, 0));
    t.setUTCDate(t.getUTCDate() - t.getUTCDay());
    return t.toISOString().slice(0, 10);
  };
  return date >= lastSunday(2) && date < lastSunday(9) ? "+01:00" : "+00:00";
}

function at(date: string, hhmm: string) {
  return `${date}T${hhmm}:00${offset(date)}`;
}

const free = { known: true, is_free: true, min_gbp: 0, max_gbp: null, notes: null };
const gbp = (min: number, max: number | null = null, notes: string | null = null) => ({ known: true, is_free: false, min_gbp: min, max_gbp: max, notes });
const unknown = { known: false, is_free: null, min_gbp: null, max_gbp: null, notes: null };

export function demoEvents(today: string): RawEvent[] {
  const rows: [number, string, string | null, V, string, string, string, any, string[], string[], string?, string?][] = [
    // dayOffset, start, end, venue, title, category, subcategory, price, lineup, genres, status, recurrence
    [0, "19:30", "23:00", "finch", "Jazz jam at the Finch", "nights-music", "jazz", free, ["The House Trio"], ["jazz"], "scheduled", "every week"],
    [0, "20:00", "23:30", "lantern", "Songs from the back room", "nights-music", "open-mic", free, [], ["acoustic"], "scheduled"],
    [1, "19:00", "22:00", "agnes", "Candlelit strings", "nights-music", "gig", gbp(14, 18), ["Quartet Imaginaire"], ["classical"], "few-left"],
    [2, "22:00", "03:00", "arch", "Low Light", "nights-music", "club-night", gbp(8, 12, "£8 early bird, £12 general admission"), ["DJ Placeholder", "Sample Selector"], ["house", "disco"]],
    [3, "21:00", "02:00", "lantern", "Glitter Bin", "nights-music", "queer-party", gbp(5), ["Miss Example", "DJ Fictional"], ["pop", "disco"]],
    [3, "18:00", "21:00", "canal", "Making Waves: printmaking open studio", "arts", "other", free, [], []],
    [4, "12:00", "17:00", "canal", "Arches food market", "food-drink", "other", free, [], []],
    [4, "22:00", "04:00", "north", "Northbank all-nighter", "nights-music", "club-night", gbp(15, 25), ["Imaginary Crew"], ["techno"]],
    [4, "20:00", "23:00", "finch", "Karaoke at the Finch", "nights-music", "karaoke", free, [], [], "scheduled", "every week"],
    [5, "16:00", "19:00", "agnes", "Folk session upstairs", "nights-music", "folk-acoustic", gbp(6), ["The Hypotheticals"], ["folk"]],
    [7, "20:00", null, "arch", "First-time band night", "nights-music", "gig", gbp(4), ["Band A", "Band B", "Band C"], ["indie"]],
    [9, "", null, "lantern", "Halloween costume party", "nights-music", "club-night", unknown, [], [], "scheduled"],
    [10, "19:30", "22:30", "agnes", "Short films on the green", "arts", "other", gbp(7), [], []],
    [11, "21:00", "02:00", "arch", "Bass Theory", "nights-music", "club-night", gbp(10), ["Sub Example", "Line Out"], ["drum and bass"], "sold-out"],
    [12, "13:00", "16:00", "canal", "Repair café", "community", "other", free, [], []],
    [13, "20:00", "23:00", "finch", "Cabaret Sauvage-ish", "nights-music", "cabaret-drag", gbp(12), ["Madame Demo"], [], "cancelled"],
    [16, "19:00", "22:00", "lantern", "Record fair after dark", "nights-music", "in-store", free, [], ["soul", "funk"]],
    [18, "22:00", "03:00", "lantern", "Glitter Bin: second helpings", "nights-music", "queer-party", gbp(5, 8), ["Miss Example"], ["pop"]],
  ];
  return rows.map(([d, start, end, v, title, category, subcategory, price, lineup, genres, status = "scheduled", recurrence = null], i) => {
    const date = addDays(today, d);
    const venue = VENUES[v];
    const endDate = end && end < start ? addDays(date, 1) : date;
    const slug = title.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
    const url = `https://tickets.example.com/demo/${slug}`;
    return {
      id: `${date}-demo-${slug}`,
      category, subcategory, title,
      venue: { venue_id: venue.venue_id, name: venue.name, address: venue.address, postcode: venue.postcode },
      starts_at: start ? at(date, start) : date,
      ends_at: start && end ? at(endDate, end) : null,
      recurrence,
      zone: venue.zone, worth_the_trip: venue.zone === "outer",
      lineup, genres, price,
      ticket_url: url,
      age_restriction: subcategory === "club-night" ? "18+" : null,
      accessibility: i % 3 === 0 ? "Step-free access to the main room" : null,
      status,
      evidence: [{ fields: ["title", "starts_at", "venue", "price"], url, quote: "(sample event)", retrieved_at: `${today}T07:00:00+01:00`, source_kind: "primary" }],
      verification: { verified_at: `${today}T07:20:00+01:00`, outcome: "verified", removed_fields: [] },
      listing: null,
      needs_review: null,
      updated_at: `${today}T07:20:00+01:00`,
    } as RawEvent;
  });
}
