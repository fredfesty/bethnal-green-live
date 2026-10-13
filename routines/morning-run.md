# Routine: morning run (five scouts + verifier + listing writer)

Every morning one scheduled run finds new events (five scouts on Haiku: nights & music, arts, food & drink, community, health & wellness), checks them (the verifier, on Sonnet), writes a short description for each published event (the listing writer, on Sonnet), runs every check and pushes a branch. GitHub then takes over (`.github/workflows/morning-run-pr.yml`): it re-runs the checks, opens the pull request and, while **auto-merge** is on, merges it and republishes the site.

```
06:07  scheduled run ──► 5 scouts (side by side) ──► verifier ──► listing writer ──► checks ──► push claude/morning-run-<date>
                                                                                   │
       GitHub workflow ◄────────────────────────────────────────┘
         re-run checks ──► open pull request ──► merge (if AUTO_MERGE=true) ──► site republishes
```

## Settings

| Setting | Value |
| --- | --- |
| Schedule | Daily at 06:07 Europe/London, as a Claude scheduled task (claude.ai, scheduled tasks) |
| Models | The main session coordinates; the five scouts run on Haiku, the verifier and the listing writer on Sonnet (set in each agent file) |
| Network | The run needs to reach venue and ticket websites; the environment this was set up in can |
| Auto-merge | Repository variable `AUTO_MERGE` = `true`. Set it to `false` to review every pull request yourself |
| GitHub setting | Settings > Actions > General > "Allow GitHub Actions to create and approve pull requests" must be ticked |
| API credentials (optional) | `SKIDDLE_API_KEY`, once Skiddle approves the application |

## Prompt (what the scheduled task runs)

```
Run the Bethnal Green Live morning run. The run date is today's date in Europe/London
(check with: TZ=Europe/London date +%F). Work unattended; nobody is watching.

Setup
1. Attach the repository fredfesty/bethnal-green-live with push access (the add_repo tool), then
   clone it as that tool says, and work inside the clone. Run:
   pip install --break-system-packages -q -r requirements.txt
   git config user.name "Fred Festy"
   git config user.email "37367535+fredfesty@users.noreply.github.com"
2. Create a branch named claude/morning-run-<run-date> from main. If that branch already exists on
   GitHub, use claude/morning-run-<run-date>-2 (then -3, and so on).

Work
3. Start these five scout subagents at the same time, each with the run date and the day of the week,
   and let each follow its instructions in full (they also read docs/scout-rules.md):
   scout-nights-music, scout-arts, scout-food-drink, scout-community, scout-health-wellness
   (.claude/agents/).
   Each writes only to its own data/candidates/<category>/ and data/runs/<category>/ folders.
   If one fails, carry on with the others and say so in the report.
4. When all the scouts have finished, use the verifier subagent (.claude/agents/verifier.md), with the
   run date, on the new candidates of every category and for its re-checks of upcoming events. Do not
   pass it the scouts' run reports or any of your own views on the candidates; it must work only from
   the files.
4b. When the verifier has finished, use the listing-writer subagent (.claude/agents/listing-writer.md)
   with the run date. It writes the short description of every event that still lacks one, using only
   python3 scripts/listings.py todo --date <run-date>. Don't pass it the scouts' reports or your own views.
   If it fails, carry on: events without a description still publish, and the next run picks them up.

Checks
5. Run: python3 scripts/validate.py all  and  python3 -m pytest -q. Both must pass. If they do not,
   you may only do these things. Never edit a fact in any file, and never edit checks or tests:
   - for a new event that fails: change its verification decision from publish to hold, add the
     failure as a reason, and delete the event file;
   - for an update to an existing event that fails: do the same, and restore the event file from
     main (git checkout origin/main -- <path>);
   - delete a candidate file that fails its format check and note it in the verifier's run report;
   - for an event whose short description fails: set its "listing" back to null (the facts stay as they
     are) and note it in the listing writer's run report.
   If they still fail, stop: do not push, and explain what failed in your final message.

Publish
6. Commit everything under data/candidates/, data/verification/, data/events/ and data/runs/ with the
   message "Morning run <run-date>" and push the branch. Do not push to main and do not merge:
   GitHub opens the pull request and, while auto-merge is on, merges it after its own checks.
   Do not edit anything outside data/candidates/, data/verification/, data/events/ and data/runs/.
7. Wait for the pull request: every 30 seconds for up to 10 minutes, fetch
   https://api.github.com/repos/fredfesty/bethnal-green-live/pulls?state=all&head=fredfesty:<branch>
   and read the first result's number, html_url and merged_at.

Report
8. Finish with a short report for Fred, in plain English: events found and published per category,
   held (one line each with the reason) and rejected; anything flagged on already-published events; venues that couldn't be
   reached; how many descriptions the listing writer wrote; and whether the pull request was merged. End your final message with the pull
   request's URL as a markdown hyperlink, for example
   [Pull request #12: Morning run — 2026-10-20](https://github.com/fredfesty/bethnal-green-live/pull/12).
   If no pull request appeared, say so and give the branch link instead.
```

## Reviewing (when auto-merge is off, or after the fact)

1. Read the verifier's report at the top of the pull request. Anything under **Held** needs a person: check the link it gives. To publish it anyway (say, after phoning the venue), edit its verification record: set `"decision": "publish"`, `"decided_by": "human"` and put what you checked in `reasons`; then create the event file (copy `docs/examples/event.json` as a template) with a `history` line `by: "human"`. Otherwise leave it out.
2. Skim the new files in `data/events/`, including each one's short description (`listing.blurb`). To fix one, edit the words, or set `listing` to null to have it rewritten in the next run.
3. Check the **flagged** events: anything with `needs_review` is hidden on the site until a person clears it (set it to null and add a `history` line).
4. Merge if it isn't merged already. The website rebuilds from `main` within a minute or two.
5. Apply any **Registry suggestions** from the scouts' reports in a separate small change.
