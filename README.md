# Bethnal Green Live

What's on around Bethnal Green, London E2: a listings website and a weekly newsletter, researched by Claude agents and checked by people. Inspired by Peckham.Live.

**Status:** the data formats, the checking scripts, the first two agents (nights & music scout, verifier) and the website are in place. The newsletter and the other agents come next. See the blueprint doc in the Bethnal Green Live project for the full plan.

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
3. Published events land in `data/events/YYYY-MM/`. The website and newsletter read only from there.
4. Everything arrives as a **pull request**. A person merges it. CI re-checks every file first.

The agents run as a scheduled Claude Code routine; settings and prompt in [`routines/morning-run.md`](routines/morning-run.md). Rules every agent follows: [`CLAUDE.md`](CLAUDE.md).

## Layout

| Path | What's there |
| --- | --- |
| `.claude/agents/` | Agent instructions: `scout-nights-music.md`, `verifier.md` |
| `schemas/` | Data formats: candidate, verification record, event, shared parts |
| `data/sources/` | Per-category venue and platform registry (zones, watchlist, closed venues) |
| `data/candidates/` | Scout output, by category and run date |
| `data/verification/` | The verifier's verdict on every candidate |
| `data/events/` | Verified events, by month — what the public sees |
| `data/runs/` | Each run's report for a person |
| `data/inbox/tips/` | Reader tips waiting to be checked |
| `scripts/` | `validate.py` (format and house rules), `check_quote.py` (quote checker) |
| `tests/` | Tests for both scripts |
| `routines/` | Scheduled-run prompts and settings |
| `docs/examples/` | Example event record |
| `site/` | The website: listings with search and filters, calendar, event pages, calendar feeds, newsletter sign-up |

## Working on it locally

```
pip install -r requirements.txt
python -m pytest -q                 # the scripts work
python scripts/validate.py all      # every data file is valid
claude                              # then ask: "use the scout-nights-music agent for today"
```

## The website

A static site built with Astro from the verified events in `data/events/`. No server, no database and no AI at page-view time.

- **Listings** grouped by day, with search and filters for type, date (today, tomorrow, this weekend, next 7 days, pick dates), price and distance. Filtered views have shareable links.
- **Calendar**: month view, plus subscribable calendar feeds (everything, free things, and one per type of night).
- **Event pages** with tickets, map link, add-to-calendar, and a "How we checked this" note linking the pages each listing was checked against. They also carry schema.org event data for search engines.
- **Newsletter sign-up**: set `buttondownUsername` in `site/src/site.config.mjs` once the Buttondown account exists.
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
- Agents never push to `main` or edit `data/sources/`; people do.
