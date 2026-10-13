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

**Budget.** Stop at about 60 page fetches per agent and say in your final message what you didn't get to.

**Finish.** Run the format check on your files (the command is in your instructions) and fix what fails by removing, never by weakening a quote. End with a short message: what you wrote, what you couldn't reach.
