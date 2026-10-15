# Bethnal Green Live — rules for every agent

Bethnal Green Live is a free listings website and weekly newsletter for things to do around Bethnal Green, London E2. Claude agents find, check and draft the listings; people approve what goes out. Readers will only trust it if it is never wrong, so **accuracy beats coverage, every time**.

## Working on the project

Anyone with write access works on it with their own Claude, the same way (`CONTRIBUTING.md`):

- **Any change by hand** ("ship issue 42", or a change someone asks for) follows `docs/ship-issue.md` from start to finish: issue, branch, change, tests, pull request, independent review, fixes, merge. The `ship-issue` skill in `.claude/skills/` points there.
- **Product decisions** Fred has made are in `docs/decisions.md`. Follow them; to change one, ask Fred in an issue.
- **The scheduled runs** read their instructions from `routines/` on `main` (`docs/scheduled-tasks.md`), so a merged change to a routine changes the next run.

## The non-negotiables

1. **Never invent a fact.** Every date, time, price, venue, line-up, age limit or status in `data/` must be backed by a word-for-word quote from a page, with its URL. If you can't quote it, leave the field empty.
2. **Stay in your lane.** Each agent writes only to its own paths (table below). Nobody but a person edits `data/sources/` (or Claude working by hand at a person's request); agents suggest changes in their run report.
3. **Never push to `main`; merge only as these rules say.** Inside a routine, only the routine's main session uses git: it pushes one branch (`claude/<routine>-<date>`; the newsletter's is `claude/newsletter-<issue-date>`). Subagents never touch git. A run's pull request is merged by GitHub (its workflow, only while the `AUTO_MERGE` variable is on, or `NEWSLETTER_AUTO_MERGE` for the newsletter, and every check passes); the one exception is the venue stories run, which also merges its own pull request once every check has passed, because Fred wants it always merged. Working by hand, follow `docs/ship-issue.md`: a `claude/issue-<n>-<slug>` branch (running one agent by hand, `claude/<agent>-<date>`; never a scheduled run's branch name), and Claude merges the pull request itself once every check on it has passed, except newsletter issues, which Fred reads first, anything labelled `needs-fred`, and changes to `.github/`, Fred's letter, his site settings or his decisions, which wait for him.
4. **Respect the web.** Obey robots.txt, never fetch ra.co, Instagram or Facebook, never log in anywhere, stop on 403/429. Never copy promo text or images. In the morning run, hard limits per agent: 20 pages per website and 5 web searches (`scripts/budget.py` enforces them for the scouts, the verifier and the event storytellers, who share 20 pages per website as a team; the venue storytellers on Sundays work the same way, with 8 searches each). Other runs follow their own routine's limits.
5. **Run the checks before finishing**, and never weaken a record just to make a check pass.

## Who writes what

| Agent | Instructions | Writes to |
| --- | --- | --- |
| Club & DJ nights scout (all scouts also follow `docs/scout-rules.md`) | `.claude/agents/scout-nights-clubs.md` | `data/candidates/nights-music/<date>/` (shared, never overwriting), `data/runs/nights-clubs/` |
| Gigs & live music scout | `.claude/agents/scout-nights-gigs.md` | `data/candidates/nights-music/<date>/` (shared, never overwriting), `data/runs/nights-gigs/` |
| Verifier | `.claude/agents/verifier.md` | `data/verification/<date>/`, `data/events/`, `data/runs/verifier/` |
| Arts scout | `.claude/agents/scout-arts.md` | `data/candidates/arts/<date>/`, `data/runs/arts/` |
| Food & drink scout | `.claude/agents/scout-food-drink.md` | `data/candidates/food-drink/<date>/`, `data/runs/food-drink/` |
| Community scout | `.claude/agents/scout-community.md` | `data/candidates/community/<date>/`, `data/runs/community/` |
| Health & wellness scout | `.claude/agents/scout-health-wellness.md` | `data/candidates/health-wellness/<date>/`, `data/runs/health-wellness/` |
| Venue finders: web, map, listings (weekly, Haiku) | `.claude/agents/venue-finder-*.md` | `data/venue-leads/<date>/` |
| Venue researchers: reviews, programme, facts (weekly, Haiku) | `.claude/agents/venue-researcher-*.md` | `data/venue-research/<date>/` |
| Venue editor (weekly, Sonnet) | `.claude/agents/venue-editor.md` | `data/venues/`, `data/runs/venue-editor/` |
| Venue checker (weekly, Sonnet) | `.claude/agents/venue-checker.md` | `review`, `needs_review` and `history` in `data/venues/` |
| Venue storyteller (weekly, Sundays' stories session, Sonnet, one per short venue) | `.claude/agents/venue-storyteller.md` | `story`, `story_research`, its own `story.*` evidence, `profiled_at` and `history` in one `data/venues/<id>.json`; the main session writes `data/runs/venue-stories/` |
| Venue profiler (one-off profiling by hand) | `.claude/agents/venue-profiler.md` | `data/venues/`, `data/runs/venue-profiler/` |
| Listing writer (Sonnet) | `.claude/agents/listing-writer.md` | the `listing` block of `data/events/` files only, `data/runs/listing-writer/` |
| Event storyteller (daily, morning run, Sonnet, one per event, up to 10 a day) | `.claude/agents/event-storyteller.md` | `story`, `story_research` and one `history` line in one `data/events/` file; the main session writes `data/runs/event-stories/` |
| Event story checker (daily, morning run, Sonnet) | `.claude/agents/event-story-checker.md` | cuts in `story`, its `review`, and `history` in `data/events/` files |
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
- `story` in a venue profile — the longer read under "The story" on its page (opened, then, now, vibe, worth knowing), each part quoted. `scripts/venue_stories.py` flags venues whose description is under 15 lines and picks up to 12 a week for the storytellers (the weekly venue run's second Sunday session); one that is still short after a try waits a week (`story_research.next_check`).
- `listing` in an event file — the short description shown with it on the site, written by the listing writer from checked facts only (`scripts/listings.py todo` lists what it may use). The verifier empties it when a fact it mentions changes, and the listing writer re-reads any event that changed after its description was written.
- `story` in an event file — the longer read under "The story" on its page (who's on, where the night or series comes from, this time, what it's like, worth knowing), each part quoted in `story.evidence` (kept apart from the verifier's `evidence`). `scripts/event_stories.py` picks up to 10 of the soonest events a day for the event storytellers; dates of one regular night share their research, and one that comes up short waits a week (`story_research.next_check`). The site shows a story only once the event story checker's `story.review` is newer than it. The verifier resets it when the title or line-up changes.
- `data/runs/<agent>/<date>.md` — each run's report for a person.
- `data/inbox/tips/` — reader tips waiting to be checked.
- `docs/` — how things work: `ship-issue.md` (making any change), `decisions.md` (Fred's product decisions), `scheduled-tasks.md` (the scheduled tasks' launchers), `scout-rules.md`, `venue-run.md`, and `blueprint.md` (the original plan).
- `scripts/validate.py` — format and house-rule checks. `scripts/check_quote.py` — re-fetches a page and looks for a quote. `scripts/page_text.py` — prints a page's exact text for quoting (scouts read pages with this, never with a summarising reader).
- `routines/` — the prompts and settings for the scheduled runs (each scheduled task prints its run's prompt with `scripts/routine_prompt.py` and follows it; the tasks' launchers are in `docs/scheduled-tasks.md`): `morning-run.md` (daily events and event stories), `weekly-venues.md` (Sundays, venues), `weekly-venue-stories.md` (Sundays, venue stories) and `weekly-newsletter.md` (Wednesdays, the newsletter).
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
python scripts/event_stories.py todo --date <run-date> --max 10
python scripts/event_stories.py unchecked --date <run-date>
python scripts/check_quote.py --story --file <event files…>
python scripts/venue_stories.py report
python scripts/venue_stories.py todo --date <run-date> --max 12
python scripts/newsletter.py week <issue-date>
python scripts/newsletter.py render data/newsletter/issues/<issue-date>.json --format md
python scripts/check_quote.py --file <files…>
python scripts/page_text.py [--as <scout>] <url> [--find "words"]
python scripts/budget.py search --as <scout> "<query>"
python scripts/budget.py usage [--as <scout>] [--date <run-date>]
python scripts/routine_prompt.py <routine>        # what a scheduled run will do
python -m pytest -q
(cd site && npm test)
```
