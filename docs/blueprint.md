> **About this file.** This is the original plan for Bethnal Green Live, written on 12 October 2026 and kept for its vision, sources table and open questions. Much has been built since, and some of it differently (six scouts, not four; a weekly venue run; the newsletter made on Wednesdays and sent on Thursdays). Where this and the rest of the repository disagree, the repository wins: see `README.md`, `CLAUDE.md`, `routines/` and `docs/decisions.md`.

# Bethnal Green Live — Blueprint

2026-10-12 · Frederic Festy

## Vision

Bethnal Green Live is a free listings website and weekly newsletter for everything worth doing around Bethnal Green, E2. A team of Claude agents researches it, checks it and drafts it, and a human approves every send.

The model is Cat's Peckham.Live newsletter (Substack, weekly on Thursdays). What we borrow:

- **A fixed weekly shape:** intro, weather, pick of the week, featured events, quick hits, cinema, "On repeat" (recurring nights), "Save the date", local shoutout, sign-off.
- **One block per event:** 🗓 when · 📍 where · 🎟 price and tickets · ♿ access. This doubles as our data model.
- **A personal, warm voice**, and a "double check before heading out" footer.
- **Free for everyone**, with an optional supporter tier later.

What we add on top: a website with every listing searchable by type, date and price; a calendar view; and calendar feeds people can subscribe to.

## The patch

We cover three zones, measured from Bethnal Green tube, and six categories, shared between four scout agents.

| Zone | Area | How we cover it |
| --- | --- | --- |
| Core | E2 postcode, or within about 1 km | Every run, everything that qualifies |
| Fringe | Up to a 20-minute walk (about 1.6 km): Hackney Road, Cambridge Heath, Haggerston, Brick Lane, Mile End, Victoria Park edges | Every run, everything that qualifies |
| Outer | Dalston, Hackney Central, Hackney Wick, west Shoreditch, Clapton | Weekly, standout events only, flagged "worth the trip" (max 5 a week per category) |

| Category | Covers | Scout |
| --- | --- | --- |
| Nights & music | Club nights, gigs, DJ bars, queer parties, karaoke, jazz, open mics | Nights & music scout (designed) |
| Cinema & arts | Films, theatre, comedy, exhibitions, talks | Arts scout |
| Food & drink | Pop-ups, supper clubs, openings, tastings, deals | Food scout |
| Markets & shopping | Columbia Road, Broadway Market, flea and craft markets, sample sales | Community scout |
| Community & family | Workshops, classes, kids' events, local campaigns | Community scout |
| Outdoors & sport | Victoria Park events, runs, boxing at York Hall | Community scout |

The exact boundary is an open decision; see the last sections.

## Running on the Claude Max plan

The agents run as **Claude Code routines** on Fred's Max subscription. That is the supported way to automate Claude Code on a subscription, with one firm boundary: the public website never calls Claude.

**How routines work** ([docs](https://code.claude.com/docs/en/routines.md)):

- A routine is a saved prompt plus our GitHub repo. It runs on Anthropic's cloud on a schedule (hourly at most), so nothing runs on our laptops.
- Each run clones the repo, does its job and pushes a `claude/…` branch or opens a pull request.
- Agent instructions live in the repo (`.claude/agents/`, `.claude/skills/`), so prompts are version-controlled like the data.
- Runs draw on the Max plan's usage limits like interactive sessions do. Limits: 100 scheduled runs an hour per account.
- The default network allowlist can't reach venue websites. Scouts need a custom environment with wider network access.

**The boundary:** the AI works behind the scenes and writes files; visitors only ever see static pages, and the website never calls Claude.

## Architecture

The GitHub repo is the database: one JSON file per event, venue and organiser. Every agent change arrives as a pull request we can read, approve or roll back. Nothing to host, nothing to pay for at the start.

| Part | Choice | Why |
| --- | --- | --- |
| Data | JSON files in the repo (`data/events`, `data/venues`, `data/organisers`) | Readable diffs, full history, one-click undo |
| Website | Astro static site on GitHub Pages, custom domain | Free, fast, no server to run or secure |
| Search and filters | In the browser, over a generated `events.json` | Handles a few thousand events comfortably; no backend |
| Calendar view | Month and week views on the site | Matches "calendar of events" in the brief |
| Calendar feeds | One `.ics` feed per category, plus "everything free" | People subscribe in Google or Apple Calendar; Cat doesn't offer this |
| Newsletter | Buttondown | Its API creates a draft for us to check and send ([docs](https://docs.buttondown.com/drafting-emails-via-the-api)); Substack has no publishing API as far as we know |
| Build and deploy | GitHub Actions on merge to `main` | Site rebuilds within minutes of an approval |
| Agents | Claude Code routines + agent files in `.claude/agents/` | Runs on the Max plan, versioned with the code |

When we need reader accounts or a public submission form, add a small hosted database (Supabase, say). Until then, tips arrive by email or a form that drops files into `data/inbox/tips/`.

## The agent team

Eleven agents and one plain script, in four stages: find, check, write, publish. Finders never write copy, writers never add facts, and a human approves anything that goes out.

| Agent | Job | Runs | Model |
| --- | --- | --- | --- |
| Nights & music scout | Club nights, gigs, DJ bars, queer parties, karaoke, jazz, open mics | Daily 06:07; outer zone Mondays | Sonnet |
| Arts scout | Cinema, theatre, comedy, exhibitions, talks | Daily | Sonnet |
| Food scout | Pop-ups, supper clubs, openings, deals | Daily | Sonnet |
| Community scout | Markets, family, workshops, outdoors, local news | Daily | Sonnet |
| Structured fetcher (plain code, no Claude) | Reads event markup, `.ics` feeds and APIs for registry venues | Before the scouts | None |
| Deduper | Merges the same event found on several sources | After the scouts | Haiku |
| Verifier | Re-opens every source and checks each quoted fact; catches cancellations | After dedupe; again on the day | Sonnet |
| Venue profiler | Address, map position, step-free access, opening hours, vibe | Weekly, and for each new venue | Sonnet |
| Organiser profiler | Who runs it, track record, official links | Weekly, and for each new organiser | Sonnet |
| Listing writer | Turns verified records into site entries in house voice | After verification | Opus |
| Newsletter editor | Picks the week, writes the issue in the weekly shape | Tuesday | Opus |
| QA agent | Checks every date, price and link in drafts against the database | Before any publish | Sonnet |

Scouts run as subagents inside one morning routine, so one routine run covers all four. Each agent's instructions live in `.claude/agents/<name>.md`.

*(Diagram in the original doc: agent pipeline · find, check, write, approve.)*

Nothing reaches readers without passing the checker script, the verifier, the QA agent and a person; venue and organiser profiles feed the database alongside verified events.

## Data model

Six record types, each a JSON file in the repo. Every fact carries the evidence it came from; that rule is what makes an AI-run listing trustworthy.

| Record | Key fields | Written by |
| --- | --- | --- |
| Candidate event | Title, venue, start and end, price (with a "known" flag), ticket link, line-up, genres, status, zone, evidence list, scout confidence | Scouts |
| Event | Everything in a candidate, plus verification result, verified-at time, listing copy, category tags, free and step-free flags | Verifier, then listing writer |
| Venue | Name, address, postcode, map position, zone, type, access notes, website, where it lists events, open or closed | Venue profiler, from the source registry |
| Organiser | Name, links, venues used, past events, notes | Organiser profiler |
| Source registry | Per category: venues to check, platforms and what we may do with each, a watchlist, a do-not-list of closed venues | Humans (agents suggest changes) |
| Issue | Week, intro, picks, sections, links to events, send status | Newsletter editor |

An **evidence item** is a quote copied word for word from a page (max 300 characters), its URL, when it was read, which fields it supports, and whether it is a primary source (venue or ticket page) or an aggregator.

The candidate format is already written: `schemas/candidate-event.schema.json`.

## Trust and accuracy rules

One wrong date or price and readers stop trusting an AI-run listing, so accuracy is enforced by code, not left to the agents' good behaviour.

1. **No evidence, no listing.** Every filled-in fact must be backed by a word-for-word quote with its link. A checker script rejects any record that breaks this before it reaches the verifier.
2. **Never guess.** No time stated means date only; no price stated means "price unknown". Genres and line-ups only as the source names them.
3. **Primary sources decide.** Listings sites (Songkick, ma.to, DesignMyNight) are leads. High confidence needs the venue's page or the ticket page.
4. **Independent verification.** The verifier runs separately from the scout, re-opens each source and searches for the quote. It never sees the scout's reasoning.
5. **Writers can't add facts.** Listing copy and newsletter text may only use verified fields. Opinion is allowed and clearly marked as opinion.
6. **QA before anything goes out.** Every date, price and link in a draft is checked against the database.
7. **Humans approve.** Low-confidence events wait for a person. Every newsletter is sent by a person.
8. **Day-of check.** A light re-check on the day catches cancellations and sold-out nights.
9. **Corrections in public.** A visible "spotted a mistake?" link on every listing; fixes go in within a day.

High-confidence site listings can auto-publish once the verifier has proved reliable over a few weeks. Until then, everything waits for a merge.

## Weekly rhythm

The newsletter lands Thursday at 8am, like Peckham.Live. Agents do the legwork daily; we estimate a person spends 20–30 minutes a day reviewing and about an hour on Wednesday on the issue.

| When | Agents | Person |
| --- | --- | --- |
| Daily, 06:00–07:00 | Structured fetch, four scouts, dedupe, verifier; one pull request of new and changed events | Skim and merge the PR (10–20 minutes) |
| Daily, after merge | Listing writer drafts entries; site rebuilds | Nothing, unless QA flags something |
| Monday | Outer-zone sweep; venue and organiser refresh; archive past events | Apply registry suggestions from run reports |
| Tuesday | Newsletter editor picks the week and drafts the issue in Buttondown | — |
| Wednesday | QA agent checks the draft | Read, edit, write the intro in our own voice |
| Thursday 08:00 | — | Press send |
| Day of each event | Day-of check for cancellations and sold-outs | — |

## Sources, legal and ethics

We read venue sites and ticket pages that allow it, never scrape where terms forbid it, and rewrite rather than copy. The best long-term source is venues and promoters sending listings to us.

| Platform | What we can do | Notes |
| --- | --- | --- |
| Venue websites | Read, primary source | Check robots.txt each run; stop on 403 or 429 |
| Ticket Tailor | Read public box-office pages | API key is per box office, so only with the venue's help ([docs](https://developers.tickettailor.com/docs/intro)) |
| DICE | Read public event and venue pages | Partner API only via a venue or promoter that works with us |
| Skiddle | Location search API with a free key | Non-commercial unless Skiddle agrees in writing; apply first ([API wiki](https://github.com/Skiddle/web-api/wiki/Events-API)) |
| Eventbrite | List events by organiser or venue ID only | Location search shut off in 2020 ([notice](https://github.com/Automattic/eventbrite-api/issues/83)) |
| Songkick, ma.to, DesignMyNight | Leads only, light reads | Confirm on a primary page; review their terms before scaling |
| Resident Advisor | Nothing | Terms ban automated extraction; robots.txt blocks ClaudeBot ([terms](https://ra.co/terms)). Ask promoters directly |
| Instagram | Nothing | No scraping; events arrive as tips |

- **Copyright:** summaries are our own words, 40 words max. No promo text copied. No promoter images unless we have permission; credit any we use.
- **Privacy:** Buttondown holds subscriber emails and handles unsubscribes. A short privacy page on the site covers UK GDPR basics.
- **Transparency:** an "About" page says listings are researched by AI and checked by people, with a corrections link.
- **Paid placements**, if we ever take them, are labelled as such.

## Roadmap

Four phases over about six weeks to a running, mostly automated service. The week counts are our working estimate, not commitments.

*(Diagram in the original doc: roadmap · 4 phases, 4 gates.)*

Issue #1 is made by hand on purpose: we learn what the agents get wrong before letting them run unattended. After week 6, growth work begins: a reader tips form, venue partnerships, and a supporter tier.

## Open decisions

These shape the build; the first three are needed before Phase 1 ends.

- [ ] **Boundary:** E2 only, or the 20-minute walk as drafted? How much of Dalston and Hackney Wick do we cover?
- [ ] **Look-ahead:** 28 days for listings (as drafted), or longer for "Save the date"?
- [ ] **Voice and name:** who writes the weekly intro, and do we sign off as a person, the way Cat does?
- [ ] **Domain:** buy one now (for the site and the newsletter sender address)?
- [ ] **Newsletter platform:** Buttondown (drafts by API) or Substack (what Cat uses, no API)?
- [ ] **Auto-publish:** when, if ever, do high-confidence listings go live without a person merging?
- [ ] **Money:** free with supporters like Peckham.Live, local sponsors, or both? If it becomes a business, move heavy jobs to an API key.

## Status

The repo is public at github.com/fredfesty/bethnal-green-live with the data formats, checking scripts (109 tests), the first two agents (nights & music scout, verifier) and the website. The site is live at fredfesty.github.io/bethnal-green-live, showing "first listings on their way" until real events are verified; it rebuilds every morning. An independent review found and closed several gaps before the first push. The files listed below were the first draft; the repo now supersedes them.

| File | What it is |
| --- | --- |
| `agents/scout-nights-music.md` | The scout's instructions. Moves to `.claude/agents/` when the repo is set up |
| `data/sources/nights-music.json` | 28 venues confirmed open in 2026 (5 core, 7 fringe, 16 outer), platform rules, a watchlist and a do-not-list |
| `schemas/candidate-event.schema.json` | The format scouts hand to the verifier |
| `scripts/validate_candidates.py` | The checker; tested against eight kinds of broken record, all caught |
| `routines/nights-music-scout.md` | Settings and prompt for the daily routine |
| `data/candidates/nights-music/_example/` | One labelled example record |

**Research findings worth knowing** (checked 12 Oct 2026):

- Closed, never list: Oval Space (licence revoked Sept 2022), The Pickle Factory (closed Aug 2024; its old domain is now spam), The Glory (closed Jan 2024; its team now runs The Divine, N16), Visions Video Bar, Peg + Patriot, Space289.
- Studio 9294 in Hackney Wick is now Number 90. The Joiner's Heart opened in Hackney on 28 Aug 2026 as the Joiners Arms' successor.
- Core venues with live programmes: Bethnal Green Working Men's Club, The Star of Bethnal Green, The Sebright Arms, St John on Bethnal Green, Oxford House.
- The Star of Bethnal Green has no proper listing online; a direct relationship would help.

**Next:** run the scout and verifier by hand once in Claude Code, review the first pull request so the first real listings go live, then switch on the morning-run routine. Then set up Buttondown and decide on a domain.

## Sources

- [Claude Code routines](https://code.claude.com/docs/en/routines.md)
- [Claude Code legal and compliance](https://code.claude.com/docs/en/legal-and-compliance.md)
- [Buttondown: drafting emails via the API](https://docs.buttondown.com/drafting-emails-via-the-api)
- [Resident Advisor terms](https://ra.co/terms) and [robots.txt](https://ra.co/robots.txt)
- [Skiddle Events API](https://github.com/Skiddle/web-api/wiki/Events-API)
- [Ticket Tailor API](https://developers.tickettailor.com/docs/intro)
- [DICE API summary](https://apis.io/providers/dice-fm/)
- [Eventbrite search shutdown](https://github.com/Automattic/eventbrite-api/issues/83)
- [Oval Space licence revoked (Time Out)](https://www.timeout.com/london/news/bethnal-green-venue-oval-space-has-lost-its-license-093022)
- [The Pickle Factory closure (DJ Mag)](https://djmag.com/news/pickle-factory-shut-its-first-incarnation-after-nine-years-unveils-final-season-line)
- [The Glory closure (PinkNews)](https://thepinknews.com/2023/12/06/beloved-east-london-queer-venue-the-glory-announces-closure)
- [The Joiner's Heart opening (London The Inside)](https://londontheinside.com/the-joiners-arms-has-a-new-lgbtqia-venue-in-hackney/)
