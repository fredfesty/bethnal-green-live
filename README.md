# Bethnal Green Live

What's on around Bethnal Green, London E2: a listings website and a weekly newsletter, researched by Claude agents and checked by people. Inspired by Peckham.Live.

**Status:** the data formats, the checking scripts, the daily events run (scouts for club & DJ nights, gigs & live music, arts, food & drink, community and health & wellness, and the verifier), the weekly venue run (three finders, three researchers, an editor and a checker), the venue profiler, the website (with its Venues guide) and the weekly newsletter (an AI editor that lays it out and an intro writer for Fred's letter) are in place. The listing writer adds a short description to every published event. Organiser profiles come next. The original plan is in [`docs/blueprint.md`](docs/blueprint.md), and the decisions made since in [`docs/decisions.md`](docs/decisions.md).

**Want to help?** Everything the project runs on is in this repository. Read [`CONTRIBUTING.md`](CONTRIBUTING.md), then ask your Claude to "ship issue 42".

## How it works

```
sources ──► scouts ──► data/candidates ──► verifier ──► data/events ──► website, newsletter, calendar feeds
                            │                  │
                    validate.py checks   check_quote.py re-fetches
                    every fact is        every quoted page; anything
                    quoted               doubtful is held for a person
```

1. **Scouts** (one per category) find events and save each as a *candidate*, with a word-for-word quote and link for every fact.
2. The **verifier** re-opens every cited page, confirms each quote and what it says, and decides: publish, hold for a person, or reject. Every decision is saved in `data/verification/`.
3. Published events land in `data/events/YYYY-MM/`. The website and newsletter read only from there. The **listing writer** then adds a line or two in our own words to each one, built only from its checked facts.
4. Everything arrives as a **pull request**. A person merges it. CI re-checks every file first.
5. Once a week the **newsletter editor** lays out Thursday's issue from those events, and the **intro writer** adds Fred's letter. Fred reads it in the pull request and sends it from Buttondown.

The events agents run every morning as a Claude scheduled task; settings and prompt in [`routines/morning-run.md`](routines/morning-run.md). On Sundays a second run looks for new venues and refreshes the venue guide: [`routines/weekly-venues.md`](routines/weekly-venues.md), explained in [`docs/venue-run.md`](docs/venue-run.md). GitHub then re-checks the work, opens the pull request and, while the `AUTO_MERGE` repository variable is `true`, merges it and republishes the site. Rules every agent follows: [`CLAUDE.md`](CLAUDE.md).

## Layout

| Path | What's there |
| --- | --- |
| `.claude/agents/` | Agent instructions: `scout-nights-clubs.md`, `scout-nights-gigs.md`, `scout-arts.md`, `scout-food-drink.md`, `scout-community.md`, `scout-health-wellness.md`, `verifier.md`, the weekly venue team (`venue-finder-*`, `venue-researcher-*`, `venue-editor`, `venue-checker`), `venue-profiler.md`, `listing-writer.md`, `newsletter-editor.md` and `newsletter-intro.md` |
| `docs/scout-rules.md` | Rules every scout follows |
| `docs/ship-issue.md` | How any change is made, from issue to merge |
| `docs/decisions.md`, `docs/blueprint.md` | Fred's product decisions, and the original plan |
| `schemas/` | Data formats: candidate, verification record, event, venue profile, shared parts |
| `data/sources/` | Per-category venue and platform registry (zones, watchlist, closed venues) |
| `data/candidates/` | Scout output, by category and run date |
| `data/verification/` | The verifier's verdict on every candidate |
| `data/events/` | Verified events, by month — what the public sees |
| `data/venues/` | Venue profiles behind the Venues page, one per venue, every fact quoted |
| `data/venue-leads/`, `data/venue-research/` | The weekly venue run's leads and research findings |
| `data/newsletter/` | Weekly issues (`issues/`), Fred's voice notes (`voice.md`) and his notes for a given issue (`notes/`) |
| `data/runs/` | Each run's report for a person |
| `data/inbox/tips/` | Reader tips waiting to be checked |
| `scripts/` | `validate.py` (format and house rules), `check_quote.py` (quote checker), `page_text.py` (a page's exact text for quoting), `budget.py` (the hard limits on pages and web searches per run), `newsletter.py` (the week's events, rendering, Buttondown drafts) |
| `tests/` | Tests for both scripts |
| `routines/` | Scheduled-run prompts and settings: `morning-run.md`, `weekly-venues.md`, `weekly-venue-stories.md`, `weekly-newsletter.md`. The scheduled tasks read their instructions from here on every run (`scripts/routine_prompt.py`) |
| `docs/examples/` | Example event record and venue profile |
| `site/` | The website: listings with search and filters, calendar, event pages, calendar feeds, newsletter sign-up |

## The newsletter

Every Thursday, the week ahead around E2, in the spirit of Peckham Live: Fred's short letter, a pick of the week, the nights worth crossing the road for, the free and cheap ones, and dates to book now.

- **Laid out by AI.** On Wednesday morning the newsletter editor (Sonnet) picks 10 to 20 verified events, groups them into sections, orders them, chooses each section's layout (a big feature, cards, a list or one line per night) and writes the short notes, subject and preview line.
- **Fred's letter.** The intro writer (Opus) then writes the few lines at the top in Fred's voice, signed Fred, from `data/newsletter/voice.md` and, when he's written some, his notes for that week in `data/newsletter/notes/<issue-date>.md`. It never makes up anything about him.
- **Checked like everything else.** `validate.py newsletter` refuses events that are under review, cancelled, sold out or in the wrong week, words copied from promoters, and any price, time, day or "free" that doesn't match the checked listing.
- **Fred sends it.** The pull request's description is the whole issue. Once merged, it becomes a draft in Buttondown (with `BUTTONDOWN_API_KEY` set) and Fred presses send. Its web page goes up on the Newsletter page on the day.

Settings, prompt and how to review: [`routines/weekly-newsletter.md`](routines/weekly-newsletter.md).

## Working on it locally

```
pip install -r requirements.txt
python -m pytest -q                 # the scripts work
python scripts/validate.py all      # every data file is valid
claude                              # then ask: "use the scout-arts agent for today"
```

## The website

A static site built with Astro from the verified events in `data/events/`. No server, no database and no AI at page-view time.

- **Listings** grouped by day, with search and filters for type, date (today, tomorrow, this weekend, next 7 days, pick dates), price and distance. Filtered views have shareable links.
- **Calendar**: month view, plus subscribable calendar feeds (everything, free things, and one per type of night).
- **Event pages** with tickets, map link, add-to-calendar, and a "How we checked this" note linking the pages each listing was checked against. They also carry schema.org event data for search engines.
- **Venues**: every venue we list, grouped by distance, with filters for kind of place, step-free entry and free nights. Each venue page covers what it's like, the music, who goes, access, cost, what's on there next and the pages it was checked against. A profile shows only after an independent check; anything not found in writing says "not confirmed". Every event links to its venue's page; venues that only appear in listings get a basic page until the weekly run profiles them. Venue pages also list what we've had there before.
- **Newsletter**: sign-up form (set `buttondownUsername` in `site/src/site.config.mjs` once the Buttondown account exists) and an archive of past issues, each with its own page.
- Events with `needs_review` are never shown, and finished events drop off. The site rebuilds every morning.
- All links are relative, so it works on GitHub Pages, a custom domain or from a folder. The font is self-hosted, so no visitor data goes to a font CDN.

```
cd site
npm install
npm run build:demo && npx astro preview    # preview with made-up sample events
npm run build                              # the real site, from data/events
```

Publishing: `.github/workflows/site.yml` builds on every pull request and, once Pages is switched on (Settings > Pages > Source: GitHub Actions) and the repository variable `DEPLOY_SITE` is `true`, publishes from `main`. Set `SITE_URL` as a repository variable if you use a custom domain.

## Rules of the road

- No fact without a quote and a link. Empty is better than wrong.
- No scraping where terms forbid it: never Resident Advisor, never Instagram, always robots.txt.
- Our own words in summaries; no copied promo text or images.
- Agents never push to `main`, merge, or edit `data/sources/`. Merges happen through GitHub's checks (auto-merge) or a person.
