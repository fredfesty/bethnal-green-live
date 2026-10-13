// Everything is shown in London time, whatever the reader's or the build machine's time zone.
const TZ = "Europe/London";

export type When = string; // "2026-10-16T22:00:00+01:00" or "2026-10-16"

export const hasTime = (w: When) => w.includes("T");

export function instant(w: When): Date {
  // A bare date counts as midday London time, so it lands on the right day everywhere.
  return hasTime(w) ? new Date(w) : new Date(`${w}T12:00:00Z`);
}

const parts = (d: Date, opts: Intl.DateTimeFormatOptions) =>
  Object.fromEntries(new Intl.DateTimeFormat("en-GB", { timeZone: TZ, ...opts }).formatToParts(d).map((p) => [p.type, p.value]));

/** London calendar date as YYYY-MM-DD. */
export function londonDate(w: When | Date): string {
  if (typeof w === "string" && !hasTime(w)) return w;
  const p = parts(typeof w === "string" ? instant(w) : w, { year: "numeric", month: "2-digit", day: "2-digit" });
  return `${p.year}-${p.month}-${p.day}`;
}

/** "9pm", "9:30pm", "midnight", "noon" */
export function clock(w: When): string {
  const p = parts(instant(w), { hour: "numeric", minute: "2-digit", hour12: true });
  const h = Number(p.hour), m = p.minute, am = (p.dayPeriod || "").toLowerCase().startsWith("a");
  if (h === 12 && m === "00") return am ? "midnight" : "noon";
  return `${h}${m === "00" ? "" : `:${m}`}${am ? "am" : "pm"}`;
}

export function timeRange(start: When, end?: When | null): string {
  if (!hasTime(start)) return "Time to be confirmed";
  return end && hasTime(end) ? `${clock(start)}–${clock(end)}` : clock(start);
}

const dateFmt = (d: string, opts: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", ...opts }).format(new Date(`${d}T12:00:00Z`));

/** For a YYYY-MM-DD London date. */
export const weekday = (d: string) => dateFmt(d, { weekday: "long" });
export const weekdayShort = (d: string) => dateFmt(d, { weekday: "short" });
export const dayMonth = (d: string) => dateFmt(d, { day: "numeric", month: "long" });
export const dayMonthShort = (d: string) => dateFmt(d, { day: "numeric", month: "short" });
export const monthYear = (d: string) => dateFmt(d, { month: "long", year: "numeric" });
export const longDate = (d: string) => dateFmt(d, { weekday: "long", day: "numeric", month: "long", year: "numeric" });

/** The week an issue covers: "15–21 October", or "29 October – 4 November" across a month end. */
export function weekLabel(from: string, to: string): string {
  return from.slice(0, 7) === to.slice(0, 7) ? `${Number(from.slice(8))}–${dayMonth(to)}` : `${dayMonth(from)} – ${dayMonth(to)}`;
}

export function addDays(d: string, n: number): string {
  const t = new Date(`${d}T12:00:00Z`);
  t.setUTCDate(t.getUTCDate() + n);
  return t.toISOString().slice(0, 10);
}

export const todayInLondon = () => londonDate(new Date());

/** ICS timestamp in UTC: 20261030T210000Z */
export const icsStamp = (d: Date) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
