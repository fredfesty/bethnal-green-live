# Bethnal Green Live

What's on around Bethnal Green, London E2: a listings website and a weekly newsletter, researched by Claude agents and checked by people. Inspired by Peckham.Live.

**Status:** the data formats, the checking scripts and the first two agents (nights & music scout, verifier) are in place. The website, newsletter and other agents come next. See the blueprint doc in the Bethnal Green Live project for the full plan.

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

## Working on it locally

```
pip install -r requirements.txt
python -m pytest -q                 # the scripts work
python scripts/validate.py all      # every data file is valid
claude                              # then ask: "use the scout-nights-music agent for today"
```

## Rules of the road

- No fact without a quote and a link. Empty is better than wrong.
- No scraping where terms forbid it: never Resident Advisor, never Instagram, always robots.txt.
- Our own words in summaries; no copied promo text or images.
- Agents never push to `main` or edit `data/sources/`; people do.
