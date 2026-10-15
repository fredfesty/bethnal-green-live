// Newsletter issues (data/newsletter/issues/<send-date>.json), as laid out by the newsletter editor agent.
// An issue holds no event facts of its own; every date, time and price shown comes from the verified event.
// An issue is listed once its send date has come; before that its page is built only as an unlisted preview.
import fs from "node:fs";
import path from "node:path";
import { DEMO, loadAllEventsById, type SiteEvent } from "./data";
import { todayInLondon } from "./time";
import type { Intro } from "./letter";
export { letterOf, type Letter } from "./letter";

const REPO = path.resolve(process.cwd(), "..");

export interface IssueItem { event_id: string; headline?: string | null; blurb?: string | null }
export interface IssueSection {
  kind: string; heading: string; emoji?: string | null; layout: "hero" | "cards" | "list" | "compact";
  lede?: string | null; items: IssueItem[];
}
export interface Issue {
  id: string; issue_number: number; covers: { from: string; to: string }; subject: string; preheader: string;
  intro: Intro;
  sections: IssueSection[];
}
export interface ResolvedSection extends IssueSection { entries: { item: IssueItem; e: SiteEvent }[] }

export function loadIssues(): Issue[] {
  if (DEMO) return [];
  const dir = path.join(REPO, "data", "newsletter", "issues");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((f) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f))
    .map((f) => {
      try { return JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")) as Issue; }
      catch { console.warn(`[bgl] skipped unreadable issue ${f}`); return null; }
    })
    .filter((i): i is Issue => !!i && !!i.id && !!i.intro)
    .sort((a, b) => b.id.localeCompare(a.id));
}

export const isOut = (i: Issue) => i.id <= todayInLondon();

export function resolveSections(i: Issue): ResolvedSection[] {
  const events = loadAllEventsById();
  return i.sections
    .map((s) => ({ ...s, entries: s.items.flatMap((item) => (events.has(item.event_id) ? [{ item, e: events.get(item.event_id)! }] : [])) }))
    .filter((s) => s.entries.length > 0);
}
