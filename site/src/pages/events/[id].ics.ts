import type { APIRoute } from "astro";
import { loadEvents, type SiteEvent } from "../../lib/data";
import { calendar } from "../../lib/ics";

export function getStaticPaths() {
  return loadEvents().map((e) => ({ params: { id: e.id }, props: { e } }));
}

export const GET: APIRoute = ({ props, site }) => {
  const e = (props as { e: SiteEvent }).e;
  const body = calendar(e.title, [e], (x) => new URL(`events/${x.id}.html`, site).href);
  return new Response(body, { headers: { "Content-Type": "text/calendar; charset=utf-8" } });
};
