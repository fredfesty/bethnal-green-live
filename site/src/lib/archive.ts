// The newsletter archive: which issues readers can look back at, how they're grouped, and what comes before and after.
// Pure functions with no imports, so they can be tested without building the site (see site/tests/archive.test.ts).
// Only issues whose send date has come are ever listed or linked; an unsent issue is a preview and stays out of sight.

/** The parts of an issue the archive needs. */
export interface ArchiveIssue { id: string; issue_number: number }

/** Issues that have gone out by `today` (YYYY-MM-DD, London), newest first. */
export function sentIssues<T extends ArchiveIssue>(issues: T[], today: string): T[] {
  return issues.filter((i) => i.id <= today).sort((a, b) => b.id.localeCompare(a.id));
}

export interface MonthGroup<T> { month: string; issues: T[] } // month as YYYY-MM

/**
 * Groups issues by the month they went out, keeping the order they come in.
 * Pass them sorted (as sentIssues returns them): a month only forms one group when its issues sit together.
 */
export function groupByMonth<T extends ArchiveIssue>(issues: T[]): MonthGroup<T>[] {
  const groups: MonthGroup<T>[] = [];
  for (const i of issues) {
    const month = i.id.slice(0, 7);
    const last = groups[groups.length - 1];
    if (last && last.month === month) last.issues.push(i);
    else groups.push({ month, issues: [i] });
  }
  return groups;
}

/**
 * The sent issues either side of `id`: `older` went out before it, `newer` after it.
 * An unsent issue (a preview) gets no neighbours, so a preview never links on to the archive's issues and back.
 */
export function neighbours<T extends ArchiveIssue>(issues: T[], id: string, today: string): { older: T | null; newer: T | null } {
  const sent = sentIssues(issues, today); // newest first
  const at = sent.findIndex((i) => i.id === id);
  if (at === -1) return { older: null, newer: null };
  return { newer: sent[at - 1] ?? null, older: sent[at + 1] ?? null };
}
