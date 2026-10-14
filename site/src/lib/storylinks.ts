// Credit links in "The story" on a venue page. When the story names the site a fact came from ("says Time Out",
// "a 2005 Londonist report"), the name becomes a link to the exact page the storyteller read, taken from the
// profile's evidence, so readers can click through and read it there. "The venue's own website" or "the café's own
// page" links to the venue's own page the same way. Nothing is linked unless its URL is in that story's evidence.

export interface StoryEvidence { fields: string[]; url: string; source_kind: string }
export interface Segment { text: string; href?: string }

// Domain endings dropped to find a site's name in its address (timeout.com → timeout, standard.co.uk → standard).
const SUFFIXES = new Set(["com", "co", "uk", "org", "net", "io", "info", "gov", "ac", "eu", "london", "news", "art", "de", "fr", "it", "ie"]);
// Names a site goes by that its address doesn't spell out (normalised: lowercase letters and digits, & as "and").
const ALIASES: Record<string, string[]> = {
  secretldn: ["secretlondon"],
  standard: ["eveningstandard", "londoneveningstandard"],
  theguardian: ["guardian"],
  ft: ["financialtimes"],
  bbc: ["bbcnews", "bbclondon"],
};

const norm = (s: string) => s.toLowerCase().replace(/&/g, "and").replace(/[^\p{L}\p{N}]/gu, "");

export function siteKey(url: string): string {
  let host: string;
  try { host = new URL(url).hostname.toLowerCase(); } catch { return ""; }
  const labels = host.split(".");
  while (labels.length > 1 && SUFFIXES.has(labels[labels.length - 1])) labels.pop();
  return norm(labels[labels.length - 1] ?? "");
}

function namesFor(key: string): Set<string> {
  const names = new Set([key, ...(ALIASES[key] ?? [])]);
  for (const n of [...names]) names.add(n.startsWith("the") ? n.slice(3) : `the${n}`);
  names.delete("");
  return names;
}

const usesPart = (ev: StoryEvidence, part: string) => ev.fields.some((f) => f === "story" || f === `story.${part}`);

export function linkSources(text: string, part: string, evidence: StoryEvidence[]): Segment[] {
  if (!text) return [{ text }];
  const story = evidence.filter((ev) => ev.fields.some((f) => f === "story" || f.startsWith("story.")));
  // This part's own evidence first, then the rest of the story's, so the link goes to the page behind this sentence.
  const ordered = [...story.filter((ev) => usesPart(ev, part)), ...story.filter((ev) => !usesPart(ev, part))];

  const sites = new Map<string, string>(); // site key → first URL
  let ownUrl: string | undefined;
  for (const ev of ordered) {
    if (ev.source_kind === "primary") { ownUrl ??= ev.url; continue; }
    const key = siteKey(ev.url);
    if (key && !sites.has(key)) sites.set(key, ev.url);
  }

  type Hit = { start: number; end: number; href: string };
  const hits: Hit[] = [];

  // Site names: runs of 1 to 5 words, starting with a capital, that spell the site's name.
  // A possessive stays outside the link: "Secret London's words" links "Secret London".
  const words = [...text.matchAll(/[\p{L}\p{N}&]+(?:['’]\p{L}+)?/gu)].map((m) => {
    const w = m[0].replace(/['’]s$/u, "");
    return { start: m.index!, end: m.index! + w.length, w };
  });
  const linked = new Set<string>();
  for (let i = 0; i < words.length; i++) {
    if (!/^\p{Lu}/u.test(words[i].w)) continue;
    for (let n = Math.min(5, words.length - i); n >= 1; n--) {
      const span = words.slice(i, i + n);
      const name = norm(span.map((x) => x.w).join(""));
      const found = [...sites].find(([key]) => !linked.has(key) && namesFor(key).has(name));
      if (found) {
        hits.push({ start: span[0].start, end: span[n - 1].end, href: found[1] });
        linked.add(found[0]);
        i += n - 1;
        break;
      }
    }
  }

  // The venue's own site: "own website", "own site", "own page(s)".
  if (ownUrl) {
    const m = /\bown (?:web ?site|site|pages?)\b/i.exec(text);
    if (m) hits.push({ start: m.index, end: m.index + m[0].length, href: ownUrl });
  }

  hits.sort((a, b) => a.start - b.start);
  const out: Segment[] = [];
  let at = 0;
  for (const h of hits) {
    if (h.start < at) continue;
    if (h.start > at) out.push({ text: text.slice(at, h.start) });
    out.push({ text: text.slice(h.start, h.end), href: h.href });
    at = h.end;
  }
  if (at < text.length) out.push({ text: text.slice(at) });
  return out;
}
