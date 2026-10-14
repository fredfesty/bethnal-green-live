// "Add to my calendar" links for the web calendars readers use most: Google, Outlook.com, Microsoft 365 and Yahoo.
// Apple Calendar and everything else use the event's .ics file, built by ics.ts from the same entry.
// Pure functions with no imports, so they can be tested without building the site (see site/tests/calendarlinks.test.ts).

/** One calendar entry, worked out once by ics.ts so the links and the .ics file always say the same thing. */
export interface CalendarEntry {
  title: string;
  location: string;
  details: string;
  /** A timed event: exact start and end instants. */
  start?: Date;
  end?: Date;
  /** An all-day entry (a run, or a date-only event): first day and the day after the last, as YYYY-MM-DD. */
  allDayFrom?: string;
  allDayUntilExclusive?: string;
}

export interface CalendarLink { id: string; label: string; href: string }

const isAllDay = (c: CalendarEntry) => !!(c.allDayFrom && c.allDayUntilExclusive);
const compact = (d: string) => d.replace(/-/g, "");
/** 20261016T210000Z */
const utcStamp = (d: Date) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
/** 2026-10-16T21:00:00Z */
const utcIso = (d: Date) => d.toISOString().replace(/\.\d{3}/, "");
const lastDay = (exclusive: string) => {
  const d = new Date(`${exclusive}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
};
// Spaces as %20, not "+": Outlook on the web reads the query itself and would show the plus signs.
const query = (params: Record<string, string>) => new URLSearchParams(params).toString().replace(/\+/g, "%20");

export function googleLink(c: CalendarEntry): string {
  const dates = isAllDay(c)
    ? `${compact(c.allDayFrom!)}/${compact(c.allDayUntilExclusive!)}`
    : `${utcStamp(c.start!)}/${utcStamp(c.end!)}`;
  return `https://calendar.google.com/calendar/render?${query({ action: "TEMPLATE", text: c.title, dates, details: c.details, location: c.location })}`;
}

function outlookLink(host: string, c: CalendarEntry): string {
  const when: Record<string, string> = isAllDay(c)
    ? { startdt: c.allDayFrom!, enddt: c.allDayUntilExclusive!, allday: "true" }
    : { startdt: utcIso(c.start!), enddt: utcIso(c.end!), allday: "false" };
  return `https://${host}/calendar/0/action/compose?${query({ path: "/calendar/action/compose", rru: "addevent", subject: c.title, ...when, body: c.details, location: c.location })}`;
}

export const outlookComLink = (c: CalendarEntry) => outlookLink("outlook.live.com", c);
export const microsoft365Link = (c: CalendarEntry) => outlookLink("outlook.office.com", c);

export function yahooLink(c: CalendarEntry): string {
  let when: Record<string, string>;
  if (!isAllDay(c)) when = { st: utcStamp(c.start!), et: utcStamp(c.end!) };
  else if (lastDay(c.allDayUntilExclusive!) === c.allDayFrom) when = { st: compact(c.allDayFrom!), dur: "allday" };
  // Yahoo can't take an all-day entry over several days, so a run goes in from the start of its first day to the
  // end of its last, in the reader's own time (no Z).
  else when = { st: `${compact(c.allDayFrom!)}T000000`, et: `${compact(lastDay(c.allDayUntilExclusive!))}T235900` };
  return `https://calendar.yahoo.com/?${query({ v: "60", title: c.title, ...when, desc: c.details, in_loc: c.location })}`;
}

/** The web calendars, in the order they're offered. The .ics download is added by the page. */
export function calendarLinks(c: CalendarEntry): CalendarLink[] {
  return [
    { id: "google", label: "Google Calendar", href: googleLink(c) },
    { id: "outlook", label: "Outlook.com", href: outlookComLink(c) },
    { id: "microsoft365", label: "Outlook (work or school)", href: microsoft365Link(c) },
    { id: "yahoo", label: "Yahoo Calendar", href: yahooLink(c) },
  ];
}
