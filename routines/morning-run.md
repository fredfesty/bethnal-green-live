# Routine: morning run (scout + verifier)

One scheduled routine runs the nights & music scout, then the verifier, and opens one pull request for a person to review. The two agents run as separate subagents, so the verifier never sees the scout's reasoning.

Create it at claude.ai/code/routines (or with `/schedule` in Claude Code):

| Setting | Value |
| --- | --- |
| Repository | `fredfesty/bethnal-green-live` |
| Schedule | Daily at 06:07 Europe/London (a few minutes past the hour starts more reliably) |
| Model | Sonnet for the main session; the scout runs on Haiku and the verifier on Sonnet (set in each agent file) |
| Environment | A custom environment. Network access **Full**, or **Custom** with the venue and ticketing domains from `data/sources/nights-music.json` plus the default package list. The default "Trusted" list cannot reach venue websites. |
| Setup script | `pip install -r requirements.txt` |
| API credentials (optional) | `SKIDDLE_API_KEY`, once Skiddle approves the application |
| Connectors | Remove all. This routine only needs the web and the repo. |

## Prompt

```
Run the Bethnal Green Live morning run. The run date is today's date in Europe/London.

1. Create a branch named claude/morning-run-<run-date> from main.
2. Use the scout-nights-music subagent (.claude/agents/scout-nights-music.md) and let it
   follow its instructions in full. Monday runs include the outer zone; other days do not.
3. When the scout has finished, use the verifier subagent (.claude/agents/verifier.md) on
   the new candidates. Do not pass it the scout's run report or any of your own views on
   the candidates; it must work only from the files.
4. Run: python scripts/validate.py all  and  python -m pytest -q. Both must pass. If they do
   not, you may only do these things, never edit a fact in any file and never edit checks or tests:
   - for a new event that fails: change its verification decision from publish to hold, add the
     failure as a reason, and delete the event file;
   - for an update to an existing event that fails: do the same, and restore the event file from
     main (git checkout main -- <path>);
   - delete a candidate file that fails its format check and note it in the PR body.
5. Commit everything under data/candidates/, data/verification/, data/events/ and data/runs/,
   push the branch, and open a pull request titled "Morning run — <run-date>". The body is the
   verifier's run report followed by the scout's run report.
6. Do not merge. Do not edit anything outside data/candidates/, data/verification/,
   data/events/ and data/runs/.
7. End your final message with the pull request's URL as a markdown hyperlink, for example
   [Pull request #12: Morning run — 2026-10-20](https://github.com/fredfesty/bethnal-green-live/pull/12).
```

## Reviewing the pull request

1. Read the verifier's report at the top. Anything under **Held** needs you: check the link it gives. To publish it anyway (say, after phoning the venue), edit its verification record: set `"decision": "publish"`, `"decided_by": "human"` and put what you checked in `reasons`; then create the event file (copy `docs/examples/event.json` as a template) with a `history` line `by: "human"`. Otherwise leave it out.
2. Skim the new files in `data/events/`. The CI check at the bottom of the PR must be green.
3. Check the **flagged** events: anything with `needs_review` is hidden or flagged on the site until a person clears it (set it to null and add a `history` line).
4. Merge. The website rebuilds from `main` (once it exists).
5. Apply any **Registry suggestions** from the scout's report in a separate small commit.
