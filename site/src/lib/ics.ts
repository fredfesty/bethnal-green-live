// iCalendar feeds (RFC 5545). Times are written in UTC so every calendar app places them correctly.
import { addDays, hasTime, icsStamp, instant } from "./time";
import type { SiteEvent } from "./data";
import { STATUS } from "./labels";

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

export function vevent(e: SiteEvent, pageUrl: string): string[] {
  const lines = ["BEGIN:VEVENT", `UID:${e.id}@bethnal-green-live`, `DTSTAMP:${icsStamp(new Date(e.updated_at))}`];
  if (hasTime(e.starts_at)) {
    lines.push(`DTSTART:${icsStamp(instant(e.starts_at))}`);
    lines.push(`DTEND:${icsStamp(new Date(e.endsAtIso))}`);
  } else {
    lines.push(`DTSTART;VALUE=DATE:${e.date.replace(/-/g, "")}`);
    lines.push(`DTEND;VALUE=DATE:${addDays(e.date, 1).replace(/-/g, "")}`);
  }
  const status = STATUS[e.status] ? `${STATUS[e.status]}: ` : "";
  lines.push(`SUMMARY:${esc(status + e.title)}`);
  lines.push(`LOCATION:${esc([e.venue.name, e.venue.address, e.venue.postcode].filter(Boolean).join(", "))}`);
  const desc = [e.priceLabel, e.lineup?.length ? `With ${e.lineup.join(", ")}` : "", e.ticket_url ? `Tickets: ${e.ticket_url}` : "", `Details: ${pageUrl}`]
    .filter(Boolean).join("\n");
  lines.push(`DESCRIPTION:${esc(desc)}`);
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
