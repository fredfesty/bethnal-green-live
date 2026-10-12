// Reader-facing names for categories and types, and the filter groups shown on the listings page.

export const CATEGORY: Record<string, string> = {
  "nights-music": "Nights & music",
  arts: "Cinema & arts",
  "food-drink": "Food & drink",
  community: "Community",
};

export const SUBCATEGORY: Record<string, string> = {
  "club-night": "Club night",
  gig: "Gig",
  "dj-bar": "DJ bar",
  "queer-party": "Queer party",
  "cabaret-drag": "Cabaret & drag",
  karaoke: "Karaoke",
  jazz: "Jazz",
  "open-mic": "Open mic",
  "folk-acoustic": "Folk & acoustic",
  "in-store": "In-store gig",
  festival: "Festival",
  other: "Music",
};

/** Filter groups, in the order shown. A group matches on subcategory (music) or on category (everything else). */
export const TYPE_GROUPS: { id: string; label: string; match: (e: { category: string; subcategory: string }) => boolean }[] = [
  { id: "clubs", label: "Clubs & DJs", match: (e) => ["club-night", "dj-bar"].includes(e.subcategory) },
  { id: "gigs", label: "Gigs & live music", match: (e) => ["gig", "in-store", "festival", "other"].includes(e.subcategory) && e.category === "nights-music" },
  { id: "queer", label: "Queer & cabaret", match: (e) => ["queer-party", "cabaret-drag"].includes(e.subcategory) },
  { id: "jazz", label: "Jazz & folk", match: (e) => ["jazz", "folk-acoustic"].includes(e.subcategory) },
  { id: "singalong", label: "Karaoke & open mic", match: (e) => ["karaoke", "open-mic"].includes(e.subcategory) },
  { id: "arts", label: "Cinema & arts", match: (e) => e.category === "arts" },
  { id: "food", label: "Food & drink", match: (e) => e.category === "food-drink" },
  { id: "community", label: "Community", match: (e) => e.category === "community" },
];

export const typeGroup = (e: { category: string; subcategory: string }) => TYPE_GROUPS.find((g) => g.match(e))?.id ?? "other";

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
