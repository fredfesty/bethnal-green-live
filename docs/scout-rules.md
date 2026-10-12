# Rules for every scout

Every scout (nights & music, arts, food & drink, community) follows this file **as well as** its own agent file. Your agent file says what's yours and where to look; this file says how to work. If the two disagree, the stricter one wins. `CLAUDE.md` at the repo root applies too.

Your only job is to **find** events and **record what the sources say, with proof**. You do not decide what gets published, you do not write listings copy, and you never fill a gap with a guess. Don't touch git: the routine that called you handles branches and pull requests. A separate verifier re-checks everything you hand over, so an empty field is always better than a wrong one.

In the paths below, `<category>` is your category (`nights-music`, `arts`, `food-drink` or `community`) and `<run-date>` is today's date in London.

## Where and when

- Read `data/sources/<category>.json` first. It defines the zones, the venues, the platforms and what you may do with each. Each listing has a `role` (`primary`, `discovery` or `unusable`) and often a `readable` result and `notes`: follow the notes, and never read an `unusable` listing.
- **core** and **fringe** venues: check every run. **outer** venues: as your agent file says, standout events only, each with `worth_the_trip: true` and a one-line reason in `why_its_good`.
- Venues on `do_not_list` are closed (or renamed: use the new venue). Never record an event at a closed venue. If a source claims one is open again, put it in the run report with the link and do nothing else. Domains under `blocked_domains` are never fetched, whatever else links to them.
- **Time window:** today up to **28 days ahead**. A **run** (an exhibition, a theatre run, a special menu over several days) counts if any part of it falls in the window, even if it opened weeks ago.
- **Times:** Europe/London, written as the **local time printed on the page** plus the offset London uses at that moment: `+01:00` in summer time, `+00:00` from 02:00 on Sunday 25 October 2026 until 01:00 on Sunday 28 March 2027. Never convert the clock time. If a venue's data carries the wrong offset, keep the printed time and fix only the offset. A Friday 10pm–4am night is a Friday event, and its `ends_at` is on Saturday.
- **Years:** many pages print "Wed 14 Oct" with no year. Take the year from the event's own page if it prints one. If it doesn't, the year is the one that puts the date inside the window, **and** the weekday must match that date (14 Oct 2026 is a Wednesday). If the weekday doesn't match, don't record the date; mention it in `notes_for_verifier`.

## Recurring events and runs

- **Recurring** (a weekly quiz, a monthly market, a Sunday flower market): record the **next occurrence only**, with `recurrence` filled in from the page's own words ("Every Sunday", "First Saturday of the month"). Next week a new candidate with the next date is written.
- **Runs** (one event on many days: a gallery show from 9 October to 12 December, a play running for three weeks, a special menu all week): **one** candidate for the whole run.
  - `starts_at` = opening date, `ends_at` = closing date. Use dates only (`2026-10-09`) unless the page gives a time on those exact days.
  - `run_schedule` = the opening days and times in the page's own words, e.g. "Tue–Sun 11am–6pm". It needs evidence like any other fact. Leave it empty if the page doesn't say.
  - The id uses the **opening date**, even if that's in the past. The same run always keeps the same id.
  - If you can't quote the closing date, leave `ends_at` empty and say so in `notes_for_verifier`.
- A run longer than about 6 months is a permanent display, not an event: don't record it.

## Order of work

1. **Load context.** Read the source registry, `schemas/candidate-event.schema.json` (and `schemas/common.schema.json` for the shared parts), and list what already exists in `data/events/` and `data/candidates/<category>/` for the window, so you can skip events already known and unchanged.
2. **Primary sources, venue by venue.** For each venue in the zones your agent file covers, read its `primary` listings with `scripts/page_text.py`. Prefer structured data when a page has it: schema.org `Event` JSON-LD, an `.ics` link or a JSON feed (page_text.py prints JSON-LD after the page text).
3. **Discovery sweep**, as your agent file describes. Every lead must then be **confirmed on a primary page** (the event's own ticket page or the venue's site) before it can be `high` confidence.
4. **Reader tips.** Files in `data/inbox/tips/` whose first lines include `category: <category>` and a `url:`. Open that URL and treat it like any other source: a venue or ticket page is `primary`, a listings site is `aggregator`. Use `source_kind: reader-tip` only for a page the reader made themselves (a flyer page, a post). A tip with no URL can't be recorded; mention it in the run report.
5. **Write candidates**, then **self-check** (below), then **write the run report**.

## Reading pages

- **Read every page you take evidence from with** `python scripts/page_text.py <url>` (add `--find "<words>"` to jump to the right part of a long page). It prints the page's exact visible text plus any embedded event data, and it obeys robots.txt and our never-use list, including on redirects. **Copy quotes only from its output**, so they match word for word.
- WebFetch and WebSearch are for discovery only: finding which pages to read. Their output is reworded, so never quote it.
- If `page_text.py` answers `REFUSED`, leave that page alone. If it answers `FAILED` or prints almost nothing (a page built by JavaScript), look for the same event on the ticket seller's page (DICE, Ticket Tailor, Skiddle, Eventbrite) instead. If there is none, skip the event and mention it in the run report.

## Rules for sources

- **Never fetch ra.co** (Resident Advisor) or any scraper or site that republishes it. Its terms forbid it. If an event only appears on RA, mention the event name and venue in the run report so a person can ask the promoter; do not record it.
- **Never fetch Instagram or Facebook**, or anything behind a login, cookie wall or paywall. Never log in anywhere.
- Check each platform's `policy` in the registry before using it: `do-not-use` and `do-not-scrape` are never fetched; `discovery-only` sources can never be the sole evidence for a `high` candidate.
- Be polite: one page at a time, no more than about 20 fetches per website per run, and stop on a 403, 429 or a robots.txt refusal. Note it in the report and move on.
- Budget: stop after about **150 page fetches** in a run, even if you're not finished, and say in the report what was skipped. Spend the budget on core venues first, then fringe, then outer.

## Rules for facts (the important bit)

- **Quote, don't paraphrase.** Each evidence item holds **one contiguous snippet** (10 to 300 characters) copied word for word from the page, the URL, when you read it, and which fields it supports. Never stitch separate bits of a page into one quote; use one evidence item per snippet. The verifier's script searches the page for that exact text, as whole words.
- **Quote the venue too.** On aggregator pages include the venue name in a quote, or the verifier cannot confirm the venue.
- **Tie quotes to the event.** Prefer the event's own page (one event per URL) over a venue's list of events. On a page listing several events, a quote backing a date, time or price must include the event's title or sit right next to it.
- **Every fact you fill in needs evidence naming it:** title, venue, address, date and time, end date or time, recurrence, run schedule, line-up, genres, price, ticket link, age limit, access info, and any status other than `scheduled`.
- **Never infer.** No time stated → date only. No price stated → `price.known: false`. "Tickets from £8" → `min_gbp: 8`, `max_gbp: null`, notes "from £8". "Free before 11pm, £5 after" or "From free" → `is_free: false`, `min_gbp: 0`, notes quoting the tiers. `is_free: true` only when the page says it's free for everyone. "Pay what you can" or "suggested donation £5" → `is_free: false`, `min_gbp: 0`, notes quoting it. Don't take access information from general knowledge of a venue; that's the venue profiler's job.
- **Line-up and genres only as the source names them.**
- **Status.** Look for "sold out", "cancelled", "postponed", "last few", "fully booked" and record them with evidence. A sold-out event is still worth recording; the editor decides.
- **Copyright.** `summary` is at most 40 words, neutral, in your own words. Never copy promo text into it. Never download or link images.
- **Opinions stay in `why_its_good`.** Tell the editor why an event stands out, using only facts already in evidence.

## Ids and duplicates

- Id format: `YYYY-MM-DD-<venue-id>-<title-slug>`, e.g. `2026-10-16-bgwmc-sexquisite`. Use the venue id from **your** registry. For a venue not in your registry, use a slug of the venue name, set `venue.venue_id: null`, and suggest the venue in the run report.
- The same event found on two sources is **one** candidate with evidence from both. Match on date + venue + similar title.
- If the event already exists in `data/events/` and nothing has changed, skip it. If something changed (time, price, status, line-up, closing date), write a fresh candidate with the same id and say what changed in `notes_for_verifier`.
- If the **date** changed, the id changes too: write a candidate with the new id and put "date moved from <old date>, was <old id>" in `notes_for_verifier`.
- An event that belongs to another scout's category is theirs, even when it's at one of your venues. Skip it.

## Confidence

- `high`: date, time (or, for a run, the opening and closing dates) and venue quoted from a primary source.
- `medium`: primary source but time or price missing; or the venue is marked `no_primary_listing`.
- `low`: aggregator or reader tip only.

## Output

One JSON file per candidate at `data/candidates/<category>/<run-date>/<id>.json`, matching `schemas/candidate-event.schema.json`. The file name must be the id. Set `scout.name` to `<category>` and `scout.run_id` to `<run-date>-a` (`-b` for a second run the same day). A worked example is in `data/candidates/nights-music/_example/`. `summary` is internal only; it is never published as written.

## Self-check before you finish

1. `python scripts/validate.py candidates data/candidates/<category>/<run-date> --window`. Fix every failure. If you can't fix one honestly (no evidence for a field), empty that field rather than inventing support.
2. `python scripts/check_quote.py --file data/candidates/<category>/<run-date>/*.json`. A `missing` or `near-mismatch` quote means you paraphrased, stitched or misread: copy the exact text again. `title_nearby: false` means the quote is on a list page away from the title: quote a passage that includes the title, or use the event's own page. `blocked` or `forbidden`: drop that evidence item and the facts that relied on it. `thin-page` or `fetch-failed` can be left for the verifier, but mention it in `notes_for_verifier`.
3. Do not finish with failing files. If you found nothing, write no candidates, just the report.

## Run report

Write `data/runs/<category>/<run-date>.md` with:

- **Counts:** candidates written, by zone and confidence; events skipped as unchanged; fetches used.
- **Changes spotted:** cancellations, sold-outs, time, price or closing-date changes on known events.
- **Registry suggestions** (for a person to apply): new venues found, with address and the link where they list events; dead or moved listing URLs; a watchlist venue that showed signs of life; any do-not-list venue that seems to be back.
- **Blocked or skipped:** sources that refused access, RA-only events worth asking the promoter about, venues not reached because of the budget.
- **Editor's heads-up:** up to 5 events you think are the strongest in the window, by id, one line each.

Keep it short and factual. A person reads it over coffee.
