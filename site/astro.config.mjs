// Bethnal Green Live website.
// Every internal link is relative and pages are written as plain .html files, so the same build works
// on GitHub Pages (under /bethnal-green-live/), on a custom domain, or opened from a folder.
import { defineConfig } from "astro/config";

export default defineConfig({
  // Used for canonical links, JSON-LD and calendar feed URLs. Set BGL_SITE_URL when the domain is decided.
  site: process.env.BGL_SITE_URL || "https://fredfesty.github.io/bethnal-green-live/",
  build: {
    format: "file",
    inlineStylesheets: "always",
  },
  trailingSlash: "ignore",
  devToolbar: { enabled: false },
});
