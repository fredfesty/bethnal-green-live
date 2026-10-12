// Reader-facing names for categories and types, and the filter groups shown on the listings page.

export const CATEGORY: Record<string, string> = {
  "nights-music": "Nights & music",
  arts: "Cinema & arts",
  "food-drink": "Food & drink",
  community: "Community",
};

export const SUBCATEGORY: Record<string, string> = {
  // nights & music
  "club-night": "Club night",
  gig: "Gig",
  "dj-bar": "DJ night",
  "queer-party": "Queer party",
  "cabaret-drag": "Cabaret & drag",
  karaoke: "Karaoke",
  jazz: "Jazz",
  "open-mic": "Open mic",
  "folk-acoustic": "Folk & acoustic",
  "in-store": "In-store gig",
  // arts
  theatre: "Theatre",
  comedy: "Comedy",
  film: "Film",
  exhibition: "Exhibition",
  dance: "Dance",
  performance: "Performance",
  // food & drink
  "supper-club": "Supper club",
  "pop-up": "Pop-up",
  tasting: "Tasting",
  "special-menu": "Special menu",
  "cookery-class": "Cookery class",
  "food-market": "Food market",
  "food-festival": "Food festival",
  opening: "Opening",
  quiz: "Quiz",
  // community
  market: "Market",
  fair: "Fair",
  workshop: "Workshop",
  family: "Family",
  outdoors: "Outdoors",
  sport: "Sport",
  volunteering: "Volunteering",
  "open-studios": "Open studios",
  tour: "Walk or tour",
  // shared
  talk: "Talk",
  festival: "Festival",
};

/** What kind of event this is, in a word or two ("Club night", "Exhibition", "Supper club"). */
export const kindLabel = (e: { category: string; subcategory: string }) =>
  (e.subcategory !== "other" && SUBCATEGORY[e.subcategory]) || (e.category === "nights-music" ? "Music" : CATEGORY[e.category]) || "Event";

type Kind = { category: string; subcategory: string };
const is = (category: string, ...subs: string[]) => (e: Kind) => e.category === category && (subs.length === 0 || subs.includes(e.subcategory));

/** Filter groups, in the order shown. Each event falls in the first group that matches. */
export const TYPE_GROUPS: { id: string; label: string; match: (e: Kind) => boolean }[] = [
  { id: "clubs", label: "Clubs & DJs", match: is("nights-music", "club-night", "dj-bar") },
  { id: "gigs", label: "Gigs & live music", match: is("nights-music", "gig", "in-store", "festival", "other") },
  { id: "queer", label: "Queer & cabaret", match: (e) => ["queer-party", "cabaret-drag"].includes(e.subcategory) },
  { id: "jazz", label: "Jazz & folk", match: is("nights-music", "jazz", "folk-acoustic") },
  { id: "singalong", label: "Karaoke & open mic", match: is("nights-music", "karaoke", "open-mic") },
  { id: "stage", label: "Theatre & comedy", match: is("arts", "theatre", "comedy", "dance", "performance") },
  { id: "film", label: "Film", match: is("arts", "film") },
  { id: "exhibitions", label: "Exhibitions", match: (e) => is("arts", "exhibition")(e) || is("community", "open-studios")(e) },
  { id: "talks", label: "Talks & readings", match: (e) => is("arts", "talk", "other")(e) || is("community", "talk")(e) },
  { id: "food", label: "Food & drink", match: is("food-drink") },
  { id: "markets", label: "Markets & fairs", match: is("community", "market", "fair") },
  { id: "family", label: "Family", match: is("community", "family") },
  { id: "outdoors", label: "Outdoors & sport", match: is("community", "outdoors", "sport", "tour") },
  { id: "community", label: "Workshops & community", match: is("community") },
];

export const typeGroup = (e: Kind) => TYPE_GROUPS.find((g) => g.match(e))?.id ?? "other";

export const ZONE: Record<string, string> = {
  core: "Bethnal Green",
  fringe: "A short walk",
  outer: "Worth the trip",
};

export const STATUS: Record<string, string> = {
  "sold-out": "Sold out",
  cancelled: "Cancelled",
  postponed: "Postponed",
  "few-left": "Last few tickets",
};
