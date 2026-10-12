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
| Venue profiler | `.claude/agents/venue-profiler.md` | `data/venues/`, `data/runs/venue-profiler/` |
| Arts scout | `.claude/agents/scout-arts.md` | `data/candidates/arts/<date>/`, `data/runs/arts/` |
| Food & drink scout | `.claude/agents/scout-food-drink.md` | `data/candidates/food-drink/<date>/`, `data/runs/food-drink/` |
| Community scout | `.claude/agents/scout-community.md` | `data/candidates/community/<date>/`, `data/runs/community/` |
| Organiser profiler, listing writer, newsletter editor, QA | not yet written | — |
| (people only) | — | `site/` — the website. Agents never edit it during scheduled runs. |

## Repo map

- `schemas/` — the data formats. `common` (shared parts), `candidate-event` (scout output), `verification` (verifier's verdict), `event` (what the site shows), `venue` (a venue profile for the Venues page).
- `data/sources/<category>.json` — the venues and platforms each scout works from, with zones, a watchlist and a do-not-list of closed venues.
- `data/candidates/` → `data/verification/` → `data/events/YYYY-MM/` — the pipeline, one JSON file per event.
- `data/venues/<venue-id>.json` — venue profiles: what it's like, music, crowd, access, cost, each fact quoted. The site shows one only after its independent `review` and while `needs_review` is empty.
- `data/runs/<agent>/<date>.md` — each run's report for a person.
- `data/inbox/tips/` — reader tips waiting to be checked.
- `scripts/validate.py` — format and house-rule checks. `scripts/check_quote.py` — re-fetches a page and looks for a quote. `scripts/page_text.py` — prints a page's exact text for quoting (scouts read pages with this, never with a summarising reader).
- `routines/` — the prompts and settings for the scheduled runs.
- `site/` — the website (Astro). It reads `data/events/`, `data/sources/` and `data/venues/` at build time; it never calls Claude or any AI service. `site/src/site.config.mjs` holds the settings a person decides (newsletter, corrections contact).
- `_example` folders and `docs/examples/` — illustrative records, not real events.
- A **run** (an exhibition, a theatre run, a special menu over several days) is one record: `starts_at` is the opening day, `ends_at` the closing day, `run_schedule` the opening times as printed.
- An event with `needs_review` set is in doubt: the site must hide it or show it as "details being checked".

## Conventions

- **Time zone:** Europe/London. Write the local time printed on the page, with London's offset at that moment: `+01:00` in summer time, `+00:00` in winter (clocks change at 01:00 UTC on the last Sundays of March and October). Never convert the clock time. A night that starts Friday 10pm is a Friday event.
- **Ids:** `YYYY-MM-DD-<venue-id>-<title-slug>`, lowercase with hyphens. The same event always gets the same id; a new date means a new id.
- **Zones** (from Bethnal Green tube): core = E2 or within about 1 km; fringe = up to a 20-minute walk; outer = further, standout events only, flagged `worth_the_trip`.
- **Run date** = today's date in London.
- **Spelling:** British English.

## Commands

```
pip install -r requirements.txt
python scripts/validate.py candidates data/candidates/<category>/<date> --window
python scripts/validate.py verification data/verification/<date>
python scripts/validate.py events data/events
python scripts/validate.py venues data/venues
python scripts/validate.py all
python scripts/check_quote.py --file <files…>
python scripts/page_text.py <url> [--find "words"]
python -m pytest -q
```
