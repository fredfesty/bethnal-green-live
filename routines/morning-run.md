# Routine: morning run (scout + verifier)

One scheduled routine runs the nights & music scout, then the verifier, and opens one pull request for a person to review. The two agents run as separate subagents, so the verifier never sees the scout's reasoning.

Create it at claude.ai/code/routines (or with `/schedule` in Claude Code):

| Setting | Value |
| --- | --- |
| Repository | `fredfesty/bethnal-green-live` |
| Schedule | Daily at 06:07 Europe/London (a few minutes past the hour starts more reliably) |
| Model | Sonnet |
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
4. Run: python scripts/validate.py all  and  python -m pytest -q. Both must pass. If they
   do not, fix the data files (never the checks or tests) or change publish decisions to hold.
5. Commit everything under data/candidates/, data/verification/, data/events/ and data/runs/,
   push the branch, and open a pull request titled "Morning run — <run-date>". The body is the
   verifier's run report followed by the scout's run report.
6. Do not merge. Do not edit anything outside data/candidates/, data/verification/,
   data/events/ and data/runs/.
```

## Reviewing the pull request

1. Read the verifier's report at the top. Anything under **Held** needs you: check the link it gives and either fix the event by hand (add `history` with `by: "human"`) or leave it out.
2. Skim the new files in `data/events/`. The CI check at the bottom of the PR must be green.
3. Merge. The website rebuilds from `main` (once it exists).
4. Apply any **Registry suggestions** from the scout's report in a separate small commit.
