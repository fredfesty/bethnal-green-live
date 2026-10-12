// Calendar feeds people can subscribe to: everything, free things, and each kind of night.
import { TYPE_GROUPS } from "./labels";
import type { SiteEvent } from "./data";

export const FEEDS: { id: string; label: string; match: (e: SiteEvent) => boolean }[] = [
  { id: "all", label: "Everything", match: () => true },
  { id: "free", label: "Free things", match: (e) => e.price.is_free === true },
  ...TYPE_GROUPS.map((g) => ({ id: g.id, label: g.label, match: (e: SiteEvent) => e.group === g.id })),
];
