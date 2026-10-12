// Calendar feeds people can subscribe to: everything, free things, each broad category and each kind of event.
import { CATEGORY, TYPE_GROUPS } from "./labels";
import type { SiteEvent } from "./data";

const CATEGORY_FEEDS = [
  { id: "nights", category: "nights-music" },
  { id: "arts", category: "arts" },
];

export const FEEDS: { id: string; label: string; match: (e: SiteEvent) => boolean }[] = [
  { id: "all", label: "Everything", match: () => true },
  { id: "free", label: "Free things", match: (e) => e.price.is_free === true },
  ...CATEGORY_FEEDS.map((c) => ({ id: c.id, label: `All ${CATEGORY[c.category].toLowerCase()}`, match: (e: SiteEvent) => e.category === c.category })),
  ...TYPE_GROUPS.map((g) => ({ id: g.id, label: g.label, match: (e: SiteEvent) => e.group === g.id })),
];
