# Bethnal Green Live — rules for every agent

Bethnal Green Live is a free listings website and weekly newsletter for things to do around Bethnal Green, London E2. Claude agents find, check and draft the listings; people approve what goes out. Readers will only trust it if it is never wrong, so **accuracy beats coverage, every time**.

## The non-negotiables

1. **Never invent a fact.** Every date, time, price, venue, line-up, age limit or status in `data/` must be backed by a word-for-word quote from a page, with its URL. If you can't quote it, leave the field empty.
2. **Stay in your lane.** Each agent writes only to its own paths (table below). Nobody but a person edits `data/sources/`; agents suggest changes in their run report.
3. **Never push to `main`, never merge.** Inside a routine, only the routine's main session uses git: it pushes one `claude/<routine>-<date>` branch. Subagents never touch git. Merging is done by GitHub (`.github/workflows/morning-run-pr.yml`, only when the `AUTO_MERGE` variable is on and every check passes) or by a person. Working by hand, use a `claude/<agent>-<date>` branch.
4. **Respect the web.** Obey robots.txt, never fetch ra.co, Instagram or Facebook, never log in anywhere, stop on 403/429. Never copy promo text or images.
5. **Run the checks before finishing**, and never weaken a record just to make a check pass.

## Who writes what

| Agent | Instructions | Writes to |
| --- | --- | --- |
| Nights & music scout (all scouts also follow `docs/scout-rules.md`) | `.claude/agents/scout-nights-music.md` | `data/candidates/nights-music/<date>/`, `data/runs/nights-music/` |
| Verifier | `.claude/agents/verifier.md` | `data/verification/<date>/`, `data/events/`, `data/runs/verifier/` |
| Arts scout | `.claude/agents/scout-arts.md` | `data/candidates/arts/<date>/`, `data/runs/arts/` |
| Food & drink scout | `.claude/agents/scout-food-drink.md` | `data/candidates/food-drink/<date>/`, `data/runs/food-drink/` |
| Community scout | `.claude/agents/scout-community.md` | `data/candidates/community/<date>/`, `data/runs/community/` |
| Health & wellness scout | `.claude/agents/scout-health-wellness.md` | `data/candidates/health-wellness/<date>/`, `data/runs/health-wellness/` |
| Venue finders: web, map, listings (weekly, Haiku) | `.claude/agents/venue-finder-*.md` | `data/venue-leads/<date>/` |
| Venue researchers: reviews, programme, facts (weekly, Haiku) | `.claude/agents/venue-researcher-*.md` | `data/venue-research/<date>/` |
| Venue editor (weekly, Sonnet) | `.claude/agents/venue-editor.md` | `data/venues/`, `data/runs/venue-editor/` |
| Venue checker (weekly, Sonnet) | `.claude/agents/venue-checker.md` | `review`, `needs_review` and `history` in `data/venues/` |
| Venue profiler (one-off profiling by hand) | `.claude/agents/venue-profiler.md` | `data/venues/`, `data/runs/venue-profiler/` |
| Listing writer (Sonnet) | `.claude/agents/listing-writer.md` | the `listing` block of `data/events/` files only, `data/runs/listing-writer/` |
| Newsletter editor (Sonnet) | `.claude/agents/newsletter-editor.md` | `data/newsletter/issues/<issue-date>.json` (all but `intro`), `data/runs/newsletter/` |
| Newsletter intro writer (Opus) | `.claude/agents/newsletter-intro.md` | the `intro` of that issue file only, plus one line in its run report |
| Organiser profiler, QA | not yet written | — |
| (people only) | — | `data/newsletter/voice.md` and `data/newsletter/notes/` — what Fred's letter may say about him |
| (people only) | — | `site/` — the website. Agents never edit it during scheduled runs. |

## Repo map

- `schemas/` — the data formats. `common` (shared parts), `candidate-event` (scout output), `verification` (verifier's verdict), `event` (what the site shows), `venue` (a venue profile for the Venues page), `newsletter-issue` (one weekly issue).
- `data/sources/<category>.json` — the venues and platforms each scout works from, with zones, a watchlist and a do-not-list of closed venues.
- `data/candidates/` → `data/verification/` → `data/events/YYYY-MM/` — the pipeline, one JSON file per event.
- `data/venues/<venue-id>.json` — venue profiles: what it's like, music, crowd, access, cost, each fact quoted. The site shows one only after an independent `review` newer than its `profiled_at`, and while `needs_review` is empty. Venues the weekly run finds live only here (not in `data/sources/`) and carry their own types, zone and location; scouts list events at them too.
- `data/venue-leads/<date>/` and `data/venue-research/<date>/` — the weekly venue run's leads and research findings (`docs/venue-run.md`). `scripts/venue_triage.py` chooses what gets researched; `scripts/zone.py` places a postcode; `scripts/places_search.py` uses Google's Places API when `GOOGLE_MAPS_API_KEY` is set (never open Google Maps pages, never store Google's details).
- `data/newsletter/issues/<issue-date>.json` — one weekly issue (the Thursday it goes out): which verified events, in which sections and layouts, with what words, and Fred's letter. It holds no event facts; they're read from `data/events/` when it's rendered. `scripts/newsletter.py` lists the week's events for the editor and renders an issue as email HTML or Markdown.
- `listing` in an event file — the short description shown with it on the site, written by the listing writer from checked facts only (`scripts/listings.py todo` lists what it may use). The verifier empties it when a fact it mentions changes, and the listing writer re-reads any event that changed after its description was written.
- `data/runs/<agent>/<date>.md` — each run's report for a person.
- `data/inbox/tips/` — reader tips waiting to be checked.
- `scripts/validate.py` — format and house-rule checks. `scripts/check_quote.py` — re-fetches a page and looks for a quote. `scripts/page_text.py` — prints a page's exact text for quoting (scouts read pages with this, never with a summarising reader).
- `routines/` — the prompts and settings for the scheduled runs: `morning-run.md` (daily events), `weekly-venues.md` (Sundays, venues) and `weekly-newsletter.md` (Wednesdays, the newsletter).
- `site/` — the website (Astro). It reads `data/events/`, `data/sources/`, `data/venues/` and `data/newsletter/issues/` at build time; it never calls Claude or any AI service. `site/src/site.config.mjs` holds the settings a person decides (newsletter, corrections contact).
- `_example` folders and `docs/examples/` — illustrative records, not real events.
- A **run** (an exhibition, a theatre run, a special menu over several days) is one record: `starts_at` is the opening day, `ends_at` the closing day, `run_schedule` the opening times as printed.
- An event with `needs_review` set is in doubt: the site must hide it or show it as "details being checked".

## Conventions

- **Time zone:** Europe/London. Write the local time printed on the page, with London's offset at that moment: `+01:00` in summer time, `+00:00` in winter (clocks change at 01:00 UTC on the last Sundays of March and October). Never convert the clock time. A night that starts Friday 10pm is a Friday event.
- **Ids:** `YYYY-MM-DD-<venue-id>-<title-slug>`, lowercase with hyphens. The same event always gets the same id; a new date means a new id.
- **Zones** (from Bethnal Green tube): core = E2 or within about 1 km; fringe = up to a 20-minute walk (1.6 km); outer = further, standout events only, flagged `worth_the_trip`. New venues are only added in core and fringe.
- **Run date** = today's date in London.
- **Spelling:** British English.
- **The newsletter** goes out on Thursdays and covers that Thursday to the next Wednesday. Its words are our own, and any price, time, day or "free" they mention must match the checked event. Fred's letter never claims a first-hand experience unless his notes for that issue gave it. Nothing is emailed without Fred: merged issues become Buttondown *drafts*.

## Commands

```
pip install -r requirements.txt
python scripts/validate.py candidates data/candidates/<category>/<date> --window
python scripts/validate.py verification data/verification/<date>
python scripts/validate.py events data/events
python scripts/validate.py venues data/venues
python scripts/validate.py venue-leads data/venue-leads/<date>
python scripts/validate.py venue-findings data/venue-research/<date>
python scripts/validate.py newsletter data/newsletter/issues/<issue-date>.json --window
python scripts/validate.py all
python scripts/venue_triage.py <date>
python scripts/zone.py "<postcode>"
python scripts/listings.py todo --date <run-date>
python scripts/newsletter.py week <issue-date>
python scripts/newsletter.py render data/newsletter/issues/<issue-date>.json --format md
python scripts/check_quote.py --file <files…>
python scripts/page_text.py <url> [--find "words"]
python -m pytest -q
(cd site && npm test)
```
