# Routine: weekly venue run

Every Sunday morning one scheduled run looks for venues around Bethnal Green that we don't list yet, re-researches some we do, and updates the Venues pages. It finishes before the morning run, so the scouts can look for events at any venue it adds the same day. How the team fits together: [`docs/venue-run.md`](../docs/venue-run.md).

```
04:58 Sunday  scheduled run
  finders (Haiku, in parallel)       web · map · listings          → data/venue-leads/<date>/
  triage (script)                    venue_triage.py               → which venues to research
  researchers (Haiku, in parallel)   reviews · programme · facts   → data/venue-research/<date>/
  editor (Sonnet)                    compares with what's published → data/venues/
  checker (Sonnet)                   re-fetches every quote, stamps the review
  checks ──► push claude/weekly-venues-<date>
GitHub (.github/workflows/weekly-venues-pr.yml): re-run checks ──► pull request ──► merge (AUTO_MERGE) ──► site republishes
```

## Settings

| Setting | Value |
| --- | --- |
| Schedule | Sundays at 04:58 Europe/London, as a Claude scheduled task |
| Models | Finders and researchers on Haiku, editor and checker on Sonnet (set in each agent file); the main session only coordinates |
| Auto-merge | Same repository variable as the morning run: `AUTO_MERGE` = `true` merges automatically after GitHub's checks |
| Google Maps (optional) | `GOOGLE_MAPS_API_KEY` in the scheduled task's environment, a Google Cloud key with "Places API (New)" enabled. Without it the map finder uses pub directories and council licensing registers. About 55 searches a week. |
| Limits | Up to 10 new venues researched a week, plus the 6 oldest profiles refreshed and any venue with news (closing, renamed) |

## Prompt (what the scheduled task runs)

```
Run the Bethnal Green Live weekly venue run. The run date is today's date in Europe/London
(check with: TZ=Europe/London date +%F). Work unattended; nobody is watching.

Setup
1. Attach the repository fredfesty/bethnal-green-live with push access (the add_repo tool), then
   clone it as that tool says, and work inside the clone. Run:
   pip install --break-system-packages -q -r requirements.txt
   git config user.name "Fred Festy"
   git config user.email "37367535+fredfesty@users.noreply.github.com"
2. Create a branch named claude/weekly-venues-<run-date> from main. If that branch already exists on
   GitHub, use claude/weekly-venues-<run-date>-2 (then -3, and so on).

Find
3. In one message, start these three subagents together, each with the run date, and let each
   follow its instructions in full: venue-finder-web, venue-finder-map, venue-finder-listings.
   (If GOOGLE_MAPS_API_KEY is set in this environment, tell venue-finder-map so.)
4. When all three have finished: python3 scripts/venue_triage.py <run-date>
   Read data/venue-leads/<run-date>/_triage.json.

Research
5. Split the "research" list into batches of at most 6 venues, in the order given. For every batch,
   start the three researchers together: venue-researcher-reviews, venue-researcher-programme and
   venue-researcher-facts. Give each the run date and the batch's entries copied exactly from
   _triage.json (venue_id, name, reason, zone, postcode, website, leads). Start all batches at once.
   If the research list is empty, skip to step 7.

Edit and check
6. When every researcher has finished, use the venue-editor subagent with the run date.
7. List the profiles that changed: git status --porcelain data/venues
   If any did, use the venue-checker subagent with the run date and that list of files only. Do not
   pass it the editor's report or any of your own views. Save its final message, as it is, to
   data/runs/venue-checker/<run-date>.md

Checks
8. Run: python3 scripts/validate.py all  and  python3 -m pytest -q  and  (cd site && npm ci && npm run build).
   All three must pass. If they do not, you may only do these things. Never edit a fact in any
   file, and never edit checks, tests or the site:
   - a lead or findings file that fails: delete it and note it in the editor's run report;
   - a changed profile that fails: restore it from main (git checkout origin/main -- <path>), or
     delete it if it is new, and note it in the editor's run report.
   If they still fail, stop: do not push, and explain what failed in your final message.

Publish
9. Commit everything under data/venue-leads/, data/venue-research/, data/venues/ and data/runs/
   with the message "Weekly venues <run-date>" and push the branch. Do not push to main and do not
   merge: GitHub opens the pull request and, while auto-merge is on, merges it after its own
   checks. Do not edit anything outside those folders.
10. Wait for the pull request: every 30 seconds for up to 10 minutes, fetch
    https://api.github.com/repos/fredfesty/bethnal-green-live/pulls?state=all&head=fredfesty:<branch>
    and read the first result's number, html_url and merged_at.

Report
11. Finish with a short report for Fred: leads found by each finder; new venues added (name and
    zone); venues updated (one line each); anything held for a person and why; venues closed or
    renamed; anything that couldn't be reached; and whether the pull request was merged. End your
    final message with the pull request's URL as a markdown hyperlink, for example
    [Pull request #14: Weekly venues — 2026-10-18](https://github.com/fredfesty/bethnal-green-live/pull/14).
    If no pull request appeared, say so and give the branch link instead.
```

## Reviewing (when auto-merge is off, or after the fact)

1. Read the editor's report at the top of the pull request: **New venues added**, **Updated**, **Held for a person**.
2. A held venue (`needs_review` set) shows only its address and listings. To clear it, check what the reason says (phone or visit the venue), edit the profile, set `needs_review` to null and add a `history` line with `by: "human"`.
3. To remove a venue the run added by mistake, delete its file in `data/venues/` (events listed there keep working: the site gives them a basic venue page).
4. Apply the **Suggestions for a person** (registry corrections, listing pages for the scouts) in a separate small change to `data/sources/`.
