import type { APIRoute } from "astro";
import { loadEvents } from "../../lib/data";
import { calendar } from "../../lib/ics";
import { FEEDS } from "../../lib/feeds";

export function getStaticPaths() {
  return FEEDS.map((f) => ({ params: { feed: f.id } }));
}

export const GET: APIRoute = ({ params, site }) => {
  const f = FEEDS.find((x) => x.id === params.feed)!;
  const events = loadEvents().filter((e) => f.match(e));
  const body = calendar(`Bethnal Green Live: ${f.label}`, events, (e) => new URL(`events/${e.id}.html`, site).href);
  return new Response(body, { headers: { "Content-Type": "text/calendar; charset=utf-8" } });
};
