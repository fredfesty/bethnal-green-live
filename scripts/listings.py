#!/usr/bin/env python3
"""The short description ('listing' blurb) shown with each event on the website.

Usage
  python scripts/listings.py todo                    # events that need a description, as JSON (checked facts only)
  python scripts/listings.py todo --date 2026-10-13  # the same, for a given run date
  python scripts/listings.py todo --all              # every upcoming event, even ones that already have one

The listing writer (.claude/agents/listing-writer.md) works only from what this prints. It holds only
facts the verifier confirmed, plus the venue's profile when that profile has passed its independent
check. Never anything a scout said: the scout's opinion is internal and not a fact.

An event needs a description when it is still on (it hasn't finished before the run date), it isn't under
review, and its `listing` is empty. The verifier empties `listing` whenever a fact it mentions changes,
so a changed event comes back here to be rewritten.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import newsletter as nl

# Keys of the newsletter's event view that don't belong in a listing writer's brief.
NOT_FOR_LISTINGS = ("scout_opinion_internal", "in_earlier_issues", "listing_blurb")


def todo(run_date: dt.date, root: Path | None = None, include_written: bool = False) -> dict:
    events = nl.load_events(root)
    venues = nl.load_venue_profiles(root)
    out = []
    for e in sorted(events.values(), key=lambda e: (e["starts_at"], e["id"])):
        if nl.last_date(e) < run_date or e.get("needs_review"):
            continue
        if e.get("listing") and not include_written:
            continue
        view = {k: v for k, v in nl.event_view(e, venues).items() if k not in NOT_FOR_LISTINGS}
        view["file"] = f"data/events/{e['starts_at'][:7]}/{e['id']}.json"
        view["current_blurb"] = (e.get("listing") or {}).get("blurb")
        out.append(view)
    return {"run_date": run_date.isoformat(), "count": len(out), "events": out}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("todo", help="events that need a description")
    t.add_argument("--date", type=dt.date.fromisoformat, default=None, help="run date (default: today in London)")
    t.add_argument("--all", action="store_true", help="include events that already have a description")
    args = ap.parse_args(argv)
    run_date = args.date or dt.datetime.now(nl.LONDON).date()
    json.dump(todo(run_date, include_written=args.all), sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
