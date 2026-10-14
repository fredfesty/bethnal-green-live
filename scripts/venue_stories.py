#!/usr/bin/env python3
"""Which venue descriptions are too short, and which of those the venue storyteller may research today.

A venue page's description is everything we write about the place: the summary, the music, crowd, access
and cost notes, and 'The story'. It is measured in lines as the page shows them (about 70 characters a line
at the page's text width, every paragraph starting a new line). A venue under 15 lines is flagged.

A flagged venue is researched in the weekly venue run's stories session on Sundays
(routines/weekly-venue-stories.md), one storyteller agent per venue, at most --max a week. If a venue is still short after a try (nothing found,
or not enough), it waits a week after that try before the next one: story_research.next_check.

  python3 scripts/venue_stories.py report                      every profile's line count, flagged ones marked
  python3 scripts/venue_stories.py todo --date 2026-10-15      today's venues for the storytellers, as JSON
  python3 scripts/venue_stories.py lines <venue-id>            one venue's line count
  python3 scripts/venue_stories.py unchecked                   profiles changed since their last check (for the checker)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CHARS_PER_LINE = 70
MIN_LINES = 15
RETRY_DAYS = 7
DEFAULT_MAX = 12
ZONE_ORDER = {"core": 0, "fringe": 1, "outer": 2}


def venues_dir() -> Path:
    return ROOT / "data" / "venues"


def paragraphs(p: dict) -> list[str]:
    """Every piece of written description, in the order the venue page shows it."""
    music, acc, cost, story = p.get("music") or {}, p.get("accessibility") or {}, p.get("cost") or {}, p.get("story") or {}
    parts = [p.get("summary"), music.get("notes"), p.get("crowd"), acc.get("notes"), cost.get("notes"),
             story.get("opened"), story.get("then"), story.get("now"), story.get("vibe"),
             *(story.get("worth_knowing") or [])]
    return [s.strip() for s in parts if isinstance(s, str) and s.strip()]


def description_lines(p: dict) -> int:
    return sum(math.ceil(len(s) / CHARS_PER_LINE) for s in paragraphs(p))


def is_flagged(p: dict) -> bool:
    """Short, and shown (or showable) on the site: closed venues and profiles in doubt are left alone."""
    if p.get("status") == "closed" or p.get("needs_review"):
        return False
    return description_lines(p) < MIN_LINES


def next_check(p: dict) -> dt.date | None:
    """The earliest day the storyteller may look at this venue again (None: never tried, so any day)."""
    r = p.get("story_research")
    if not r:
        return None
    if r.get("next_check"):
        return dt.date.fromisoformat(r["next_check"])
    # Marked written, but the checker later cut it back under 15 lines: still a week after the last try.
    return dt.date.fromisoformat(r["last_attempt"]) + dt.timedelta(days=RETRY_DAYS)


def is_due(p: dict, today: dt.date) -> bool:
    n = next_check(p)
    return n is None or n <= today


def load_profiles() -> list[dict]:
    out = []
    for f in sorted(venues_dir().glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("id"):
            out.append(d)
    return out


def todo(today: dt.date, limit: int = DEFAULT_MAX) -> dict:
    flagged = [p for p in load_profiles() if is_flagged(p)]
    due = [p for p in flagged if is_due(p, today)]
    waiting = [p for p in flagged if not is_due(p, today)]

    def key(p):
        r = p.get("story_research")
        tried = r is not None
        return (tried, (r or {}).get("last_attempt", ""), ZONE_ORDER.get(p.get("zone"), 9), description_lines(p), p["id"])

    due.sort(key=key)
    rows = []
    for p in due[:limit]:
        r = p.get("story_research") or {}
        rows.append({"venue_id": p["id"], "name": p["name"], "zone": p.get("zone"), "lines": description_lines(p),
                     "attempts": r.get("attempts", 0), "last_outcome": r.get("outcome"),
                     "last_note": r.get("note"), "website": p.get("website")})
    return {"date": today.isoformat(), "min_lines": MIN_LINES, "flagged": len(flagged), "due": len(due),
            "waiting_for_weekly_retry": len(waiting), "left_for_later_weeks": max(0, len(due) - limit),
            "research": rows}


def needs_check(p: dict) -> bool:
    r = p.get("review")
    return not r or r.get("checked_at", "") < p.get("profiled_at", "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("todo")
    t.add_argument("--date", required=True, help="the run date, YYYY-MM-DD (London)")
    t.add_argument("--max", type=int, default=DEFAULT_MAX)
    sub.add_parser("report")
    sub.add_parser("unchecked")
    one = sub.add_parser("lines")
    one.add_argument("venue_id")
    a = ap.parse_args(argv)

    if a.cmd == "todo":
        print(json.dumps(todo(dt.date.fromisoformat(a.date), a.max), indent=2, ensure_ascii=False))
    elif a.cmd == "report":
        profiles = sorted(load_profiles(), key=lambda p: (description_lines(p), p["id"]))
        for p in profiles:
            mark = "SHORT" if is_flagged(p) else "     "
            r = p.get("story_research") or {}
            extra = f"  last try {r['last_attempt']} ({r['outcome']}), next {next_check(p)}" if r else ""
            print(f"{mark} {description_lines(p):3d}  {p['id']}{extra}")
        print(f"\n{sum(is_flagged(p) for p in profiles)} of {len(profiles)} under {MIN_LINES} lines")
    elif a.cmd == "unchecked":
        for p in load_profiles():
            if needs_check(p) and not p.get("needs_review"):
                print(f"data/venues/{p['id']}.json")
    else:
        f = venues_dir() / f"{a.venue_id}.json"
        if not f.exists():
            print(f"no profile: {f}", file=sys.stderr)
            return 1
        p = json.loads(f.read_text(encoding="utf-8"))
        print(f"{description_lines(p)} lines ({'under' if description_lines(p) < MIN_LINES else 'at least'} {MIN_LINES})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
