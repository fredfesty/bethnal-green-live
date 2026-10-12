#!/usr/bin/env python3
"""Check Bethnal Green Live data files against the formats and the house rules.

Usage
  python scripts/validate.py candidates data/candidates/nights-music/2026-10-13 --window
  python scripts/validate.py verification data/verification/2026-10-13
  python scripts/validate.py events data/events
  python scripts/validate.py all            # everything under data/ (what CI runs)

Options
  --window        also reject candidates dated outside yesterday .. +60 days (use during runs, not in CI)
  --today DATE    pretend today is DATE (YYYY-MM-DD), for tests

Exit code 0 = all good, 1 = at least one file failed.

What is checked
  every kind     JSON Schema; id starts with the event date; venue is in the category's registry,
                 not on its do-not-list, and in the right zone; price is consistent
  candidates     every filled-in fact is named by an evidence item; outer zone needs worth_the_trip;
                 'high' confidence needs the date quoted from a primary source
  verification   hold/reject give reasons; publish has title, venue and date confirmed and nothing
                 contradicted; a cancelled or vanished new event is never published
  events         every filled-in fact is still backed by evidence; file sits at data/events/YYYY-MM/<id>.json;
                 its verification record exists and says publish; removed fields really are empty
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import jsonschema
    from referencing import Registry, Resource
except ImportError:  # pragma: no cover
    sys.exit("Install the requirements first: pip install -r requirements.txt")

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
SOURCES = ROOT / "data" / "sources"

FACT_FIELDS = [
    "title", "venue.name", "venue.address", "venue.postcode", "starts_at", "ends_at",
    "recurrence", "lineup", "genres", "price", "ticket_url", "age_restriction",
    "accessibility", "status",
]
KEY_FIELDS = ["title", "venue", "starts_at"]


# ---------------------------------------------------------------- helpers

def load_validators() -> dict[str, jsonschema.Draft202012Validator]:
    resources, by_name = [], {}
    for p in SCHEMAS.glob("*.schema.json"):
        schema = json.loads(p.read_text(encoding="utf-8"))
        res = Resource.from_contents(schema)
        resources.append((schema["$id"], res))
        resources.append((p.name, res))  # allow relative refs like "common.schema.json#/..."
        by_name[p.name] = schema
    registry = Registry().with_resources(resources)
    fmt = jsonschema.FormatChecker()
    return {
        kind: jsonschema.Draft202012Validator(by_name[f"{name}.schema.json"], registry=registry, format_checker=fmt)
        for kind, name in [("candidates", "candidate-event"), ("events", "event"), ("verification", "verification")]
    }


_registry_cache: dict[str, dict | None] = {}


def source_registry(category: str | None) -> dict | None:
    if not category:
        return None
    if category not in _registry_cache:
        p = SOURCES / f"{category}.json"
        _registry_cache[category] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    return _registry_cache[category]


def get(obj, dotted: str):
    for part in dotted.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return obj


def is_filled(field: str, value) -> bool:
    if value is None or (isinstance(value, (list, str)) and len(value) == 0):
        return False
    if field == "price":
        return bool(value.get("known"))
    if field == "status":
        return value != "scheduled"  # other statuses need proof
    return True


def covered(field: str, evidence_fields: set[str]) -> bool:
    return field in evidence_fields or field.split(".")[0] in evidence_fields


def schema_errors(validator, data) -> list[str]:
    out = []
    for e in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in e.path) or "(root)"
        out.append(f"format: {loc}: {e.message}")
    return out


def check_evidence_coverage(data: dict) -> list[str]:
    ev_fields = {f for ev in data["evidence"] for f in ev["fields"]}
    return [
        f"evidence: '{field}' is filled in but no evidence item names it"
        for field in FACT_FIELDS
        if is_filled(field, get(data, field)) and not covered(field, ev_fields)
    ]


def check_id_and_date(data: dict, today: dt.date | None) -> list[str]:
    errs = []
    date_part = data["starts_at"][:10]
    if not data["id"].startswith(date_part):
        errs.append(f"id: should start with the event date {date_part}")
    try:
        d = dt.date.fromisoformat(date_part)
    except ValueError:
        return errs + [f"date: {date_part} is not a real date"]
    if today and (d < today - dt.timedelta(days=1) or d > today + dt.timedelta(days=60)):
        errs.append(f"date: {date_part} is outside the scouting window")
    if data.get("ends_at") and data["ends_at"][:10] < date_part:
        errs.append("date: ends before it starts")
    for field in ("starts_at", "ends_at"):
        errs += check_london_offset(field, data.get(field))
    return errs


LONDON = ZoneInfo("Europe/London")


def check_london_offset(field: str, value: str | None) -> list[str]:
    """A time must carry the offset London actually uses that day (+01:00 in summer, +00:00 in winter)."""
    if not value or "T" not in value:
        return []
    try:
        moment = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return [f"date: {field} '{value}' is not a valid time"]
    expected = moment.replace(tzinfo=None).replace(tzinfo=LONDON).utcoffset()
    if moment.utcoffset() != expected:
        hours = int(expected.total_seconds() // 3600)
        return [f"date: {field} should use London's offset that day (+{hours:02d}:00), not {value[19:] or 'Z'}"]
    return []


def check_venue(data: dict) -> list[str]:
    reg = source_registry(data.get("category"))
    if reg is None:
        return []
    errs = []
    venues = {v["id"]: v for v in reg.get("venues", [])}
    closed = {c["id"]: c for c in reg.get("do_not_list", [])}
    vid = data["venue"]["venue_id"]
    if vid is None:
        return errs
    if vid in closed:
        errs.append(f"venue: '{vid}' is on the do-not-list ({closed[vid]['reason']})")
    elif vid not in venues:
        errs.append(f"venue: '{vid}' is not in the registry (use null and flag it in the run report)")
    elif venues[vid]["zone"] != data["zone"]:
        errs.append(f"zone: registry says {venues[vid]['zone']}, record says {data['zone']}")
    if data["zone"] == "outer" and not data.get("worth_the_trip"):
        errs.append("zone: outer-zone events are only kept when worth_the_trip is true")
    return errs


def check_price(p: dict) -> list[str]:
    errs = []
    if p["known"]:
        if p.get("is_free") is None:
            errs.append("price: known=true but is_free is not set")
        if p.get("is_free") is False and p.get("min_gbp") is None:
            errs.append("price: paid event with no min_gbp")
        if p.get("is_free") is True and (p.get("min_gbp") or 0) > 0:
            errs.append("price: marked free but min_gbp is above zero")
        if p.get("min_gbp") is not None and p.get("max_gbp") is not None and p["min_gbp"] > p["max_gbp"]:
            errs.append("price: min_gbp is greater than max_gbp")
    elif any(p.get(k) not in (None, False) for k in ("min_gbp", "max_gbp", "is_free")):
        errs.append("price: known=false but price values are filled in")
    return errs


def venue_has_no_primary(data: dict) -> bool:
    reg = source_registry(data.get("category")) or {}
    vid = get(data, "venue.venue_id")
    return any(v["id"] == vid and v.get("no_primary_listing") for v in reg.get("venues", []))


# ---------------------------------------------------------------- per kind

def check_candidate(path: Path, data: dict, today: dt.date | None) -> list[str]:
    errs = check_evidence_coverage(data) + check_id_and_date(data, today) + check_venue(data) + check_price(data["price"])
    if data["scout_confidence"] == "high" and not any(
        ev["source_kind"] == "primary" and "starts_at" in ev["fields"] for ev in data["evidence"]
    ):
        errs.append("confidence: 'high' needs the date quoted from a primary source")
    return errs


def check_verification(path: Path, data: dict, today: dt.date | None) -> list[str]:
    errs = []
    if data["decision"] in ("hold", "reject") and not data["reasons"]:
        errs.append(f"decision: '{data['decision']}' needs at least one reason")
    cand_path = ROOT / data["candidate_file"]
    if not cand_path.exists():
        errs.append(f"candidate_file: {data['candidate_file']} does not exist")
        cand = {}
    else:
        cand = json.loads(cand_path.read_text(encoding="utf-8"))
        if cand.get("id") != data["id"]:
            errs.append("id: does not match the candidate's id")
    if data["decision"] == "publish":
        checks = data["field_checks"]
        if any(c["result"] == "contradicted" for c in checks):
            errs.append("decision: cannot publish with a contradicted field (fix or empty it, or hold)")
        for key in KEY_FIELDS:
            confirmed = [
                c for c in checks
                if c["result"] == "confirmed" and (c["field"] == key or c["field"].startswith(key + "."))
            ]
            if not confirmed:
                errs.append(f"decision: cannot publish, '{key}' is not confirmed")
            elif not any(c.get("source_kind") == "primary" for c in confirmed) and not venue_has_no_primary(cand):
                errs.append(f"decision: cannot publish, '{key}' is only confirmed by a non-primary source (hold instead)")
        if data["page_status_seen"] in ("cancelled", "postponed", "page-gone") and not data.get("existing_event"):
            errs.append(f"decision: a new event whose page shows '{data['page_status_seen']}' must be rejected")
    return errs


def check_event(path: Path, data: dict, today: dt.date | None) -> list[str]:
    errs = check_evidence_coverage(data) + check_id_and_date(data, None) + check_venue(data) + check_price(data["price"])
    try:
        rel = path.resolve().relative_to(ROOT.resolve())
        expected = Path("data/events") / data["starts_at"][:7] / f"{data['id']}.json"
        if rel.parts[:2] == ("data", "events") and rel != expected:
            errs.append(f"path: should be {expected.as_posix()}")
    except ValueError:
        pass  # file outside the repo: the path rule only applies to data/events
    ver = data["verification"]
    rec_path = ROOT / ver["record"]
    if not rec_path.exists():
        errs.append(f"verification: record {ver['record']} does not exist")
    else:
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        if rec.get("id") != data["id"]:
            errs.append("verification: record is for a different id")
        if rec.get("decision") != "publish":
            errs.append(f"verification: record says '{rec.get('decision')}', not publish")
    removed = ver.get("removed_fields", [])
    if ver["outcome"] == "verified" and removed:
        errs.append("verification: outcome 'verified' but fields were removed (use verified-with-gaps)")
    if ver["outcome"] == "verified-with-gaps" and not removed:
        errs.append("verification: outcome 'verified-with-gaps' but removed_fields is empty")
    for f in removed:
        if is_filled(f, get(data, f)):
            errs.append(f"verification: '{f}' is listed as removed but still filled in")
    return errs


CHECKS = {"candidates": check_candidate, "verification": check_verification, "events": check_event}
DEFAULT_DIRS = {"candidates": "data/candidates", "verification": "data/verification", "events": "data/events"}


def run(kind: str, paths: list[Path], today: dt.date | None, validators) -> tuple[int, int]:
    files: list[Path] = []
    for p in paths:
        files += sorted(p.rglob("*.json")) if p.is_dir() else [p]
    seen: dict[str, Path] = {}
    failed = 0
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"FAIL {f}: not valid JSON ({e})")
            failed += 1
            continue
        errs = schema_errors(validators[kind], data)
        if not errs:
            errs = CHECKS[kind](f, data, today)
        # Events must be unique overall. Candidates and verification records may repeat an id
        # across run dates (an event re-found later), but not within one run folder.
        ident = data.get("id") if isinstance(data, dict) else None
        if ident:
            key = ident if kind == "events" else f"{f.parent}/{ident}"
            if key in seen:
                errs.append(f"duplicate id, also in {seen[key]}")
            else:
                seen[key] = f
        if errs:
            failed += 1
            print(f"FAIL {f}")
            for e in errs:
                print(f"   - {e}")
        else:
            print(f"ok   {f}")
    return len(files), failed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=["candidates", "verification", "events", "all"])
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--window", action="store_true", help="reject candidates outside yesterday..+60 days")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=None)
    args = ap.parse_args(argv)

    validators = load_validators()
    today = (args.today or dt.date.today()) if args.window else None
    kinds = ["candidates", "verification", "events"] if args.kind == "all" else [args.kind]

    total = failed = 0
    for kind in kinds:
        paths = args.paths if (args.paths and args.kind != "all") else [ROOT / DEFAULT_DIRS[kind]]
        print(f"\n== {kind} ==")
        n, f = run(kind, paths, today, validators)
        total += n
        failed += f
    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
