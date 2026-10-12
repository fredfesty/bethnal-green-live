// Relative links, so the built site works at any address (GitHub Pages sub-path, a custom domain, a folder).
// With build.format "file", a page at /events/x.html is one folder deep.

export function prefixFor(pathname: string, base = import.meta.env.BASE_URL || "/"): string {
  let p = pathname.startsWith(base) ? pathname.slice(base.length) : pathname.replace(/^\//, "");
  const depth = p.split("/").length - 1;
  return depth > 0 ? "../".repeat(depth) : "./";
}

/** rel(Astro.url.pathname, "events/x.html") */
export const rel = (pathname: string, target: string) => prefixFor(pathname) + target.replace(/^\//, "");
