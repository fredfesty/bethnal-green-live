# Bethnal Green Live — rules for every agent

Bethnal Green Live is a free listings website and weekly newsletter for things to do around Bethnal Green, London E2. Claude agents find, check and draft the listings; people approve what goes out. Readers will only trust it if it is never wrong, so **accuracy beats coverage, every time**.

## The non-negotiables

1. **Never invent a fact.** Every date, time, price, venue, line-up, age limit or status in `data/` must be backed by a word-for-word quote from a page, with its URL. If you can't quote it, leave the field empty.
2. **Stay in your lane.** Each agent writes only to its own paths (table below). Nobody but a person edits `data/sources/`; agents suggest changes in their run report.
3. **Never push to `main`, never merge.** Inside a routine, only the routine's main session uses git: it makes one `claude/<routine>-<date>` branch and one pull request. Subagents never touch git. Working by hand, use a `claude/<agent>-<date>` branch.
4. **Respect the web.** Obey robots.txt, never fetch ra.co or Instagram, never log in anywhere, stop on 403/429. Never copy promo text or images.
5. **Run the checks before finishing**, and never weaken a record just to make a check pass.

## Who writes what

| Agent | Instructions | Writes to |
| --- | --- | --- |
| Nights & music scout | `.claude/agents/scout-nights-music.md` | `data/candidates/nights-music/<date>/`, `data/runs/nights-music/` |
| Verifier | `.claude/agents/verifier.md` | `data/verification/<date>/`, `data/events/`, `data/runs/verifier/` |
| Arts, food & drink, community scouts | not yet written | their own `data/candidates/<category>/` |
| Venue and organiser profilers, listing writer, newsletter editor, QA | not yet written | — |
| (people only) | — | `site/` — the website. Agents never edit it during scheduled runs. |

## Repo map

- `schemas/` — the data formats. `common` (shared parts), `candidate-event` (scout output), `verification` (verifier's verdict), `event` (what the site shows).
- `data/sources/<category>.json` — the venues and platforms each scout works from, with zones, a watchlist and a do-not-list of closed venues.
- `data/candidates/` → `data/verification/` → `data/events/YYYY-MM/` — the pipeline, one JSON file per event.
- `data/runs/<agent>/<date>.md` — each run's report for a person.
- `data/inbox/tips/` — reader tips waiting to be checked.
- `scripts/validate.py` — format and house-rule checks. `scripts/check_quote.py` — re-fetches a page and looks for a quote.
- `routines/` — the prompts and settings for the scheduled runs.
- `site/` — the website (Astro). It reads `data/events/` and `data/sources/` at build time; it never calls Claude or any AI service. `site/src/site.config.mjs` holds the settings a person decides (newsletter, corrections contact).
- `_example` folders and `docs/examples/` — illustrative records, not real events.
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
python scripts/validate.py candidates data/candidates/nights-music/<date> --window
python scripts/validate.py verification data/verification/<date>
python scripts/validate.py events data/events
python scripts/validate.py all
python scripts/check_quote.py --file <files…>
python -m pytest -q
```
