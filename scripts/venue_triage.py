#!/usr/bin/env python3
"""Sort the week's venue leads and choose which venues the researchers look at.

Reads every lead in data/venue-leads/<run-date>/, merges leads about the same place, matches them
against the venues we know (registry, watchlist, closed list, profiles), looks up where new ones
are (scripts/zone.py), and writes data/venue-leads/<run-date>/_triage.json:

  research     venues for the three researchers this week:
                 new       a lead for a venue we don't know, in the core or fringe zone (or zone not known yet)
                 signal    news about a known venue: closing, closed, renamed, reopened, opening soon
                 unprofiled  a registry venue with no profile yet
                 refresh   the known venues whose profiles are oldest
  report_only  new venues further out (outer zone), and leads for venues on the closed list or watchlist:
               for a person to look at, not researched
  known        leads that are venues we already know, with nothing new to say

Usage
  python scripts/venue_triage.py 2026-10-18 [--max-new 10] [--refresh 6] [--no-lookup]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import venuelib  # noqa: E402
import zone as zonelib  # noqa: E402

ROOT = venuelib.ROOT


def load_leads(folder: Path) -> list[tuple[str, dict]]:
    out = []
    for p in sorted(folder.glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8-sig"))
        except ValueError:
            print(f"skipped unreadable lead {p}", file=sys.stderr)
            continue
        if isinstance(d, dict) and d.get("name"):
            out.append((p.relative_to(ROOT).as_posix(), d))
    return out


def first(values):
    return next((v for v in values if v), None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_date", type=dt.date.fromisoformat)
    ap.add_argument("--max-new", type=int, default=10)
    ap.add_argument("--refresh", type=int, default=6)
    ap.add_argument("--no-lookup", action="store_true", help="don't look postcodes up (tests)")
    args = ap.parse_args(argv)

    folder = ROOT / "data" / "venue-leads" / args.run_date.isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    known = venuelib.known_venues()
    by_id = {k["id"]: k for k in known}

    # 1. Group leads: by the known venue they are about, else by name.
    groups: dict[str, dict] = {}
    for path, lead in load_leads(folder):
        k = by_id.get(lead.get("about_venue_id") or "") or venuelib.match_known(
            lead["name"], lead.get("website"), lead.get("postcode"), known)
        key = f"known:{k['id']}" if k else f"new:{venuelib.norm_name(lead['name'])}"
        g = groups.setdefault(key, {"known": k, "leads": []})
        g["leads"].append((path, lead))

    research, report_only, known_out = [], [], []
    new_rows = []
    for key, g in groups.items():
        leads = [l for _, l in g["leads"]]
        paths = [p for p, _ in g["leads"]]
        found_by = sorted({l["found_by"] for l in leads})
        signals = sorted({l["signal"] for l in leads} - {"new"})
        k = g["known"]
        if k:
            row = {"venue_id": k["id"], "name": k["name"], "where": k["where"], "found_by": found_by,
                   "signals": signals, "leads": paths}
            if k["where"] in ("closed", "watchlist"):
                report_only.append({**row, "reason": f"lead for a venue on the {'closed list' if k['where'] == 'closed' else 'watchlist'}"})
            elif signals:
                research.append({**row, "reason": "signal", "zone": k["zone"], "postcode": k["postcode"]})
            else:
                known_out.append(row)
            continue
        name = first(l["name"] for l in leads)
        postcode = first(l.get("postcode") for l in leads)
        loc = None
        if postcode and not args.no_lookup:
            loc = zonelib.lookup(postcode)
            if "error" in loc:
                loc = None
        zone = loc["zone"] if loc else venuelib.zone_for(postcode, None)
        vid = venuelib.slug(name)
        while vid in by_id:  # a different place that slugs the same as one we know
            vid += "-2"
        new_rows.append({"venue_id": vid, "name": name, "found_by": found_by, "signals": signals,
                         "postcode": postcode, "zone": zone, "distance_m": loc["distance_m"] if loc else None,
                         "website": first(l.get("website") for l in leads), "leads": paths})

    # 2. New venues: core first, then fringe, then unknown zone; more finders agreeing ranks higher.
    order = {"core": 0, "fringe": 1, None: 2}
    new_rows.sort(key=lambda r: (order.get(r["zone"], 3), -len(r["found_by"]), r["distance_m"] or 99999))
    taken = 0
    for r in new_rows:
        if r["zone"] == "outer":
            report_only.append({**r, "reason": "new venue in the outer zone (we only add core and fringe venues)"})
        elif taken < args.max_new:
            research.append({**r, "reason": "new"})
            taken += 1
        else:
            report_only.append({**r, "reason": f"over this week's limit of {args.max_new} new venues; next week"})

    # 3. Registry venues with no profile, then the oldest profiles.
    chosen = {r["venue_id"] for r in research}
    profiles = {}
    for p in (ROOT / "data" / "venues").glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8-sig"))
            profiles[d["id"]] = d
        except (ValueError, KeyError):
            pass
    for k in known:
        if k["where"] == "registry" and k["id"] not in profiles and k["id"] not in chosen:
            research.append({"venue_id": k["id"], "name": k["name"], "reason": "unprofiled", "zone": k["zone"],
                             "postcode": k["postcode"], "leads": []})
            chosen.add(k["id"])
    oldest = sorted((p for p in profiles.values() if p["id"] not in chosen and p.get("status") != "closed"),
                    key=lambda p: p.get("profiled_at", ""))
    for p in oldest[: args.refresh]:
        research.append({"venue_id": p["id"], "name": p["name"], "reason": "refresh", "zone": p["zone"],
                         "postcode": p.get("postcode"), "profiled_at": p.get("profiled_at"), "leads": []})

    out = {"run_date": args.run_date.isoformat(), "research": research, "report_only": report_only, "known": known_out}
    (folder / "_triage.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = {}
    for r in research:
        counts[r["reason"]] = counts.get(r["reason"], 0) + 1
    print(f"OK research {len(research)} {counts}; report only {len(report_only)}; already known {len(known_out)}")
    print(f"wrote {(folder / '_triage.json').relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
