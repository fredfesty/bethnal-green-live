# The weekly venue run

Every Sunday morning a team of agents looks for venues around Bethnal Green we don't list yet, re-researches some we do, and updates the Venues pages. Finders and researchers are on Haiku; the editor and the checker are on Sonnet.

```
                 ┌─ venue-finder-web ───────┐
  finders        ├─ venue-finder-map ───────┼─► data/venue-leads/<date>/
  (Haiku)        └─ venue-finder-listings ──┘            │
                                                         ▼
  triage (script)        scripts/venue_triage.py ─► _triage.json: which venues to research
                                                         │
                 ┌─ venue-researcher-reviews ─┐          ▼
  researchers    ├─ venue-researcher-programme┼─► data/venue-research/<date>/<venue>.<aspect>.json
  (Haiku)        └─ venue-researcher-facts ───┘          │
                                                         ▼
  editor (Sonnet)   venue-editor: compares findings with what's published ─► data/venues/<id>.json
                                                         │
  checker (Sonnet)  venue-checker: re-fetches every quote, cuts what isn't supported, stamps review
                                                         │
  checks, branch, pull request, auto-merge ─► the site republishes
```

The routine that runs it: `routines/weekly-venues.md`.

## Rules every finder and researcher follows

These come on top of `CLAUDE.md`.

**Reading pages.** Read every page you take a quote from with `python3 scripts/page_text.py <url>` (add `--find "words"` for long pages). Copy quotes only from its output, so they are word for word. WebSearch and WebFetch are for *finding* pages; their output is reworded, so never quote it. If `page_text.py` says REFUSED, leave the page alone; never fetch it another way. FAILED or a near-empty page (built by JavaScript): try another page.

**Never.** Never fetch ra.co, Instagram, Facebook, TikTok, X, or any domain on the never-use list in `data/sources/`. Never open Google Maps pages (their terms forbid it; the map finder uses Google's official API through a script instead). Never log in. Stop on a 403 or 429 from a site. About 20 fetches per site per run at most.

**Quotes.** One evidence item is one contiguous snippet, 10 to 300 characters, copied exactly, with its URL, the time you read it (`date -u +%Y-%m-%dT%H:%M:%SZ`) and `source_kind`:
- `primary`: the venue's own website, or its own page on a ticketing site;
- `press`: an article or review by a named publication;
- `directory`: an access guide, pub directory, council register or hire listing;
- `aggregator`: a listings site that copies others (Songkick, ma.to, DesignMyNight). Never `primary`.

**Facts.** Record only what a page says. Never infer: a basement bar is not "not step-free" until a page says so; a techno night is not a "techno venue". Leave out what you can't quote; the editor would rather have nothing than a guess. Written values (summaries, notes) are in **our own words**: seven or more words in a row copied from a quote are refused by the checks.

**Fresh sources.** Give `source_date` when the page shows when it was written. A source over five years old, or one describing a previous owner or format, can't back crowd, music or access. **News** (closing, closed, renamed, reopening, opening soon) only counts from a page dated in the last six months; older news goes in your final message, not in a lead. Check the venue's own site or ticket page too: events on sale after the news date usually mean it's still open.

**Your lane.** Write only the files your instructions name. Don't touch git, `data/sources/`, `data/venues/`, `data/events/` or `site/`.

**Known pages before searching.** WebSearch is the scarcest tool in the run, so look up what you already know first, and use WebSearch only for what a known page can't tell you (press reviews, and news of a closing or a new name). For a venue we already list, start from, in this order:
1. its website and listing pages in `data/sources/`, or in its profile in `data/venues/<id>.json` (`website`, `accessibility.access_page`, evidence URLs);
2. its sitemap: `<website>/sitemap.xml`, or `/sitemap_index.xml` and `/page-sitemap.xml` (WordPress sites usually have these), read with `scripts/page_text.py`, to find the access, FAQ, what's-on, about and hire pages;
3. pages those pages link to, and the pages already linked in the registry.
For a venue that isn't listed yet, the lead's own website and evidence URLs come first. A page you reach this way is as good a source as one a search finds.

**Budget.** Stop at about 60 page fetches per agent and say in your final message what you didn't get to. WebSearch has its own, much smaller limit, because it is shared: the whole run gets about 200 calls, and once they are used up every agent still to start has none. So each agent has a cap on its WebSearch calls in total, written in its instructions, and stops searching when it reaches it:

| Agent | WebSearch calls at most |
| --- | --- |
| venue-finder-web, venue-finder-map, venue-finder-listings | 25 each |
| venue-researcher-reviews | 15 each |
| venue-researcher-programme, venue-researcher-facts | 8 each |

A full week (the triage script's limits, about 21 venues in four batches of up to six) comes to 75 + 4 × 31 = 199. If you reach your cap, say in your final message what you didn't search for; that is better than leaving the later agents with nothing. If you change a cap, or the number of venues triage sends to research, keep this total under 200.

**Finish.** Run the format check on your files (the command is in your instructions) and fix what fails by removing, never by weakening a quote. End with a short message: what you wrote, what you couldn't reach.
