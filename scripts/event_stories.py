#!/usr/bin/env python3
"""Which events get 'The story' on their page, and which of them the event storyteller may research today.

The story is the longer read on an event's page (.claude/agents/event-storyteller.md): who is on and what
they have done, when the night or series started and its history, what is special about this one, what it
is like, and other things worth knowing. Every part is quoted, and the event story checker re-checks every
quote before the site shows it.

It runs in the morning run, after the listing writer: at most --max events a day (soonest first, within
the next --days days). An event whose story is still under 6 lines after a try waits a week before the
next one (story_research.next_check), and is dropped once it is over.

A regular night gets a new id for every date, so events of the same series (same venue, same title once
numbers are left out) share their research: an event whose series already has a checked story is given
that file to start from (no new searching needed), and one whose series came up empty in the last week
waits with it.

  python3 scripts/event_stories.py todo --date 2026-10-15        today's events for the storytellers, as JSON
  python3 scripts/event_stories.py unchecked                     stories written since their last check (for the checker)
  python3 scripts/event_stories.py lines <event-id>              one event's story length
  python3 scripts/event_stories.py report                        every upcoming event's story length and state
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

import newsletter as nl

ROOT = Path(__file__).resolve().parent.parent

CHARS_PER_LINE = 70
MIN_LINES = 6
RETRY_DAYS = 7
DEFAULT_MAX = 6
DEFAULT_DAYS = 14
PARTS = ("who", "started", "then", "now", "vibe")


def story_paragraphs(e: dict) -> list[str]:
    st = e.get("story") or {}
    parts = [st.get(k) for k in PARTS] + list(st.get("worth_knowing") or [])
    return [s.strip() for s in parts if isinstance(s, str) and s.strip()]


def story_lines(e: dict) -> int:
    return sum(math.ceil(len(s) / CHARS_PER_LINE) for s in story_paragraphs(e))


def series_key(e: dict) -> str:
    """Same venue and same title once numbers and dates are left out: one regular night or series."""
    v = e.get("venue") or {}
    title = re.sub(r"[0-9]+", "", (e.get("title") or "").lower())
    title = re.sub(r"^the\s+", "", title.replace("&", "and"))
    return f"{v.get('venue_id') or nl_norm(v.get('name'))}|{re.sub(r'[^a-z]+', '', title)}"


def nl_norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def is_checked(e: dict) -> bool:
    """The story has a review newer than its words (only then does the site show it)."""
    st = e.get("story") or {}
    r = st.get("review") or {}
    return bool(st) and bool(r.get("checked_at")) and _ts(r["checked_at"]) >= _ts(st.get("written_at"))


def _ts(s: str | None) -> dt.datetime:
    try:
        t = dt.datetime.fromisoformat((s or "").replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def own_next_check(e: dict) -> dt.date | None:
    """The earliest day this event may be tried again (None: never tried, or the story is long enough)."""
    r = e.get("story_research")
    if not r:
        return None
    if r.get("next_check"):
        return dt.date.fromisoformat(r["next_check"])
    if story_lines(e) < MIN_LINES:  # marked written, but the checker cut it back: still a week after the try
        return dt.date.fromisoformat(r["last_attempt"]) + dt.timedelta(days=RETRY_DAYS)
    return None


def wants_story(e: dict, today: dt.date, horizon: dt.date) -> bool:
    """Still on, soon, shown on the site, and without a story long enough."""
    if e.get("needs_review") or e.get("status") in ("cancelled", "postponed"):
        return False
    if nl.last_date(e) < today or nl.event_date(e) > horizon:
        return False
    return story_lines(e) < MIN_LINES


def todo(today: dt.date, limit: int = DEFAULT_MAX, days: int = DEFAULT_DAYS, root: Path | None = None) -> dict:
    events = nl.load_events(root or ROOT)
    horizon = today + dt.timedelta(days=days)
    by_series: dict[str, list[dict]] = {}
    for e in events.values():
        by_series.setdefault(series_key(e), []).append(e)

    def series_wait(e: dict) -> dt.date | None:
        """The latest retry date among this series' other events that came up short."""
        waits = [own_next_check(o) for o in by_series[series_key(e)] if o["id"] != e["id"] and o.get("story_research")]
        waits = [w for w in waits if w]
        return max(waits) if waits else None

    def sibling(e: dict) -> dict | None:
        done = [o for o in by_series[series_key(e)] if o["id"] != e["id"] and is_checked(o) and story_lines(o) > 0]
        return max(done, key=lambda o: _ts(o["story"]["review"]["checked_at"])) if done else None

    wanted = [e for e in events.values() if wants_story(e, today, horizon)]
    due, waiting = [], []
    for e in wanted:
        sib = sibling(e)
        wait = own_next_check(e)
        if not sib and not e.get("story_research"):
            wait = series_wait(e)
        (waiting if wait and wait > today else due).append((e, sib))

    # Soonest first: a run that is already on counts from today, after the one-off events of the same day
    # (it stays on for a while, so it can wait); then never-tried before retries.
    due.sort(key=lambda x: (max(nl.event_date(x[0]), today), nl.is_run(x[0]), bool(x[0].get("story_research")),
                            nl.event_date(x[0]), x[0]["id"]))
    rows = []
    for e, sib in due[:limit]:
        r = e.get("story_research") or {}
        rows.append({
            "event_id": e["id"],
            "file": f"data/events/{e['starts_at'][:7]}/{e['id']}.json",
            "title": e["title"],
            "date": nl.event_date(e).isoformat(),
            "weekday": nl.event_date(e).strftime("%A"),
            "venue": e["venue"].get("name"),
            "venue_id": e["venue"].get("venue_id"),
            "category": e.get("category"),
            "subcategory": e.get("subcategory"),
            "lineup": e.get("lineup") or [],
            "recurrence": e.get("recurrence"),
            "ticket_url": e.get("ticket_url"),
            "event_pages": sorted({ev["url"] for ev in e.get("evidence", [])}),
            "story_lines": story_lines(e),
            "attempts": r.get("attempts", 0),
            "last_outcome": r.get("outcome"),
            "last_note": r.get("note"),
            "series_story_file": f"data/events/{sib['starts_at'][:7]}/{sib['id']}.json" if sib else None,
        })
    return {"date": today.isoformat(), "min_lines": MIN_LINES, "horizon": horizon.isoformat(),
            "wanted": len(wanted), "due": len(due), "waiting_for_weekly_retry": len(waiting),
            "left_for_later": max(0, len(due) - limit), "research": rows}


def unchecked(today: dt.date | None = None, root: Path | None = None) -> list[str]:
    out = []
    for e in nl.load_events(root or ROOT).values():
        if not e.get("story") or is_checked(e) or e.get("needs_review"):
            continue
        if today and nl.last_date(e) < today:
            continue
        out.append(f"data/events/{e['starts_at'][:7]}/{e['id']}.json")
    return sorted(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("todo")
    t.add_argument("--date", required=True, help="the run date, YYYY-MM-DD (London)")
    t.add_argument("--max", type=int, default=DEFAULT_MAX)
    t.add_argument("--days", type=int, default=DEFAULT_DAYS, help="only events starting within this many days")
    u = sub.add_parser("unchecked")
    u.add_argument("--date", help="leave out events that are already over")
    one = sub.add_parser("lines")
    one.add_argument("event_id")
    rp = sub.add_parser("report")
    rp.add_argument("--date", help="default: today in London")
    a = ap.parse_args(argv)

    if a.cmd == "todo":
        print(json.dumps(todo(dt.date.fromisoformat(a.date), a.max, a.days), indent=2, ensure_ascii=False))
    elif a.cmd == "unchecked":
        for f in unchecked(dt.date.fromisoformat(a.date) if a.date else None):
            print(f)
    elif a.cmd == "lines":
        e = nl.load_events(ROOT).get(a.event_id)
        if not e:
            print(f"no event: {a.event_id}", file=sys.stderr)
            return 1
        n = story_lines(e)
        print(f"{n} lines ({'under' if n < MIN_LINES else 'at least'} {MIN_LINES})")
    else:
        today = dt.date.fromisoformat(a.date) if a.date else dt.datetime.now(nl.LONDON).date()
        events = sorted((e for e in nl.load_events(ROOT).values() if nl.last_date(e) >= today),
                        key=lambda e: (e["starts_at"], e["id"]))
        for e in events:
            r = e.get("story_research") or {}
            state = "checked" if is_checked(e) else ("unchecked" if e.get("story") else "none")
            extra = f"  last try {r['last_attempt']} ({r['outcome']}), next {own_next_check(e)}" if r else ""
            print(f"{story_lines(e):3d}  {state:9s} {e['id']}{extra}")
        print(f"\n{sum(story_lines(e) >= MIN_LINES for e in events)} of {len(events)} upcoming events have a story "
              f"of {MIN_LINES}+ lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
