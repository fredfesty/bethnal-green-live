// iCalendar feeds (RFC 5545). Times are written in UTC so every calendar app places them correctly.
import { addDays, hasTime, icsStamp, instant } from "./time";
import type { SiteEvent } from "./data";
import { STATUS } from "./labels";
import type { CalendarEntry } from "./calendarlinks";

const esc = (s: string) => s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");

// Lines longer than 75 octets are folded with CRLF + space.
function fold(line: string): string {
  const bytes = new TextEncoder().encode(line);
  if (bytes.length <= 75) return line;
  const out: string[] = [];
  let cur = "";
  for (const ch of line) {
    if (new TextEncoder().encode(cur + ch).length > (out.length ? 74 : 75)) {
      out.push(cur);
      cur = ch;
    } else cur += ch;
  }
  out.push(cur);
  return out.join("\r\n ");
}

/** What a calendar shows for an event: the same for the .ics file and the Google, Outlook and Yahoo links. */
export function calendarEntry(e: SiteEvent, pageUrl: string): CalendarEntry {
  const status = STATUS[e.status] ? `${STATUS[e.status]}: ` : "";
  const title = status + e.title;
  const location = [e.venue.name, e.venue.address, e.venue.postcode].filter(Boolean).join(", ");
  const details = [e.priceLabel, e.isRun && e.run_schedule ? `Open: ${e.run_schedule}` : "", e.lineup?.length ? `With ${e.lineup.join(", ")}` : "", e.ticket_url ? `Tickets: ${e.ticket_url}` : "", `Details: ${pageUrl}`]
    .filter(Boolean).join("\n");
  if (e.isRun) {
    // A run (an exhibition, say) is an all-day entry from its opening day to its last day.
    return { title, location, details, allDayFrom: e.date, allDayUntilExclusive: addDays(e.until, 1) };
  }
  if (hasTime(e.starts_at)) return { title, location, details, start: instant(e.starts_at), end: new Date(e.endsAtIso) };
  return { title, location, details, allDayFrom: e.date, allDayUntilExclusive: addDays(e.date, 1) };
}

export function vevent(e: SiteEvent, pageUrl: string): string[] {
  const c = calendarEntry(e, pageUrl);
  const lines = ["BEGIN:VEVENT", `UID:${e.id}@bethnal-green-live`, `DTSTAMP:${icsStamp(new Date(e.updated_at))}`];
  if (c.allDayFrom && c.allDayUntilExclusive) {
    lines.push(`DTSTART;VALUE=DATE:${c.allDayFrom.replace(/-/g, "")}`);
    lines.push(`DTEND;VALUE=DATE:${c.allDayUntilExclusive.replace(/-/g, "")}`);
  } else {
    lines.push(`DTSTART:${icsStamp(c.start!)}`);
    lines.push(`DTEND:${icsStamp(c.end!)}`);
  }
  lines.push(`SUMMARY:${esc(c.title)}`);
  lines.push(`LOCATION:${esc(c.location)}`);
  lines.push(`DESCRIPTION:${esc(c.details)}`);
  lines.push(`URL:${pageUrl}`);
  if (e.status === "cancelled") lines.push("STATUS:CANCELLED");
  lines.push("END:VEVENT");
  return lines;
}

export function calendar(name: string, events: SiteEvent[], pageUrl: (e: SiteEvent) => string): string {
  const lines = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Bethnal Green Live//Listings//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
    `X-WR-CALNAME:${esc(name)}`, "X-WR-TIMEZONE:Europe/London", "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H",
    ...events.flatMap((e) => vevent(e, pageUrl(e))),
    "END:VCALENDAR",
  ];
  return lines.map(fold).join("\r\n") + "\r\n";
}
