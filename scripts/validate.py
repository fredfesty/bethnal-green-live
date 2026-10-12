#!/usr/bin/env python3
"""Check Bethnal Green Live data files against the formats and the house rules.

Usage
  python scripts/validate.py candidates data/candidates/nights-music/2026-10-13 --window
  python scripts/validate.py verification data/verification/2026-10-13
  python scripts/validate.py events data/events
  python scripts/validate.py all            # everything under data/ (what CI runs)

Options
  --window        also reject candidates dated outside yesterday .. +DAYS (use during runs, not in CI)
  --days N        size of that window (default 31: the scouts look 28 days ahead, plus slack)
  --today DATE    pretend today is DATE (YYYY-MM-DD), for tests. Default: today in London.

Exit code 0 = all good (or nothing to check), 1 = at least one file failed.

The point of these checks: no fact reaches the public unless a word-for-word quote backs it and the
verifier confirmed that quote. So beyond the formats, they tie the three stages together:
  candidates    every filled-in fact is named by an evidence item; no forbidden sources; aggregators are
                never labelled primary; closed venues are refused; 'high' confidence means a primary source
  verification  one check per fact; 'confirmed' means a cited URL was actually checked; publish needs
                title, venue and date confirmed by script (not just read) from a primary source; nothing
                contradicted; new events that are cancelled are rejected
  events        every fact equals the candidate's, or was emptied because it could not be confirmed;
                every fact left has a confirmed check; evidence comes from the candidate (plus the
                verifier's own status quote); no duplicate listings of the same night
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import jsonschema
    from referencing import Registry, Resource
except ImportError:  # pragma: no cover
    sys.exit("Install the requirements first: pip install -r requirements.txt")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import policy  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
SOURCES = ROOT / "data" / "sources"
LONDON = ZoneInfo("Europe/London")

# Fields that state facts. Dotted names are used for evidence coverage.
FACT_FIELDS = [
    "title", "venue.name", "venue.address", "venue.postcode", "starts_at", "ends_at",
    "recurrence", "lineup", "genres", "price", "ticket_url", "age_restriction",
    "accessibility", "status",
]
TOP_FACTS = ["title", "venue", "starts_at", "ends_at", "recurrence", "lineup", "genres", "price",
             "ticket_url", "age_restriction", "accessibility", "status"]
MUST_MATCH = ["id", "category", "subcategory", "zone", "worth_the_trip"]
KEY_FIELDS = {"title": ("title",), "venue": ("venue", "venue.name"), "starts_at": ("starts_at",)}
STATUS_FROM_PAGE = {"few-left", "sold-out", "cancelled", "postponed"}
DEFAULTS = {"lineup": [], "genres": [], "worth_the_trip": False}


# ---------------------------------------------------------------- loading

def read_json(path: Path) -> tuple[object | None, str | None]:
    """Never crashes: returns (data, None) or (None, reason)."""
    try:
        raw = path.read_bytes()
    except OSError as e:
        return None, f"cannot read ({e.strerror or e})"
    for enc in ("utf-8-sig", "utf-16"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return None, "not UTF-8 text (save the file as UTF-8)"
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return None, "saved as UTF-16; save it as UTF-8 (in PowerShell use Out-File -Encoding utf8)"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"not valid JSON ({e})"


def load_validators() -> dict[str, jsonschema.Draft202012Validator]:
    resources, by_name = [], {}
    for p in SCHEMAS.glob("*.schema.json"):
        schema = json.loads(p.read_text(encoding="utf-8"))
        res = Resource.from_contents(schema)
        resources += [(schema["$id"], res), (p.name, res)]
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
        _registry_cache[category] = read_json(p)[0] if p.exists() else None
    return _registry_cache[category]


# ---------------------------------------------------------------- small helpers

def get(obj, dotted: str):
    for part in dotted.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return obj


def value(record: dict, field: str):
    v = record.get(field)
    return DEFAULTS.get(field) if v is None and field in DEFAULTS else v


def is_filled(field: str, v) -> bool:
    if v is None or (isinstance(v, (list, str)) and len(v) == 0):
        return False
    if field == "price":
        return bool(v.get("known"))
    if field == "status":
        return v != "scheduled"  # 'scheduled' is the default assumption; anything else needs proof
    if field == "venue":
        return True
    return True


def covered(field: str, evidence_fields: set[str]) -> bool:
    return field in evidence_fields or field.split(".")[0] in evidence_fields


def check_is_for(check_field: str, top: str) -> bool:
    return check_field == top or check_field.startswith(top + ".")


def schema_errors(validator, data) -> list[str]:
    out = []
    for e in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in e.path) or "(root)"
        out.append(f"format: {loc}: {e.message}")
    return out


def norm_name(s: str | None) -> str:
    s = (s or "").lower().replace("&", "and")
    s = re.sub(r"^the\s+", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def evidence_kind(cand: dict, url: str | None, top: str) -> set[str]:
    return {ev["source_kind"] for ev in cand.get("evidence", [])
            if ev["url"] == url and any(check_is_for(f, top) or f == top for f in ev["fields"])}


# ---------------------------------------------------------------- shared rules

def check_evidence_coverage(data: dict) -> list[str]:
    ev_fields = {f for ev in data["evidence"] for f in ev["fields"]}
    return [
        f"evidence: '{field}' is filled in but no evidence item names it"
        for field in FACT_FIELDS
        if is_filled(field, get(data, field)) and not covered(field, ev_fields)
    ]


def check_sources(data: dict) -> list[str]:
    errs = []
    for i, ev in enumerate(data["evidence"]):
        if policy.is_forbidden(ev["url"]):
            errs.append(f"evidence[{i}]: {policy.domain_of(ev['url'])} is a never-use source")
        elif ev["source_kind"] == "primary" and policy.is_discovery_only(ev["url"]):
            errs.append(f"evidence[{i}]: {policy.domain_of(ev['url'])} is an aggregator; it cannot be 'primary'")
    if data.get("ticket_url") and policy.is_forbidden(data["ticket_url"]):
        errs.append("ticket_url: points to a never-use source")
    return errs


def parse_when(v: str) -> dt.datetime | dt.date:
    return dt.datetime.fromisoformat(v.replace("Z", "+00:00")) if "T" in v else dt.date.fromisoformat(v)


def check_london_time(field: str, v: str | None) -> list[str]:
    """The offset must be one London really uses at that local time (both are fine in the repeated hour
    on the last Sunday of October; times in the skipped hour in March don't exist)."""
    if not v or "T" not in v:
        return []
    try:
        moment = parse_when(v)
    except ValueError:
        return [f"date: {field} '{v}' is not a valid time"]
    if moment.astimezone(LONDON).replace(tzinfo=None) != moment.replace(tzinfo=None):
        local = moment.strftime("%H:%M")
        right = moment.replace(tzinfo=None).replace(tzinfo=LONDON).strftime("%z")
        right = f"{right[:3]}:{right[3:]}"
        return [f"date: {field} has the wrong offset for London on that day. Keep the local time printed on the "
                f"page ({local}) and change only the offset, to {right}"]
    return []


def check_id_and_date(data: dict, today: dt.date | None, days: int) -> list[str]:
    errs = []
    date_part = data["starts_at"][:10]
    if not data["id"].startswith(date_part):
        errs.append(f"id: should start with the event date {date_part}")
    try:
        start = parse_when(data["starts_at"])
        d = dt.date.fromisoformat(date_part)
    except ValueError:
        return errs + [f"date: starts_at '{data['starts_at']}' is not a real date or time"]
    if today and (d < today - dt.timedelta(days=1) or d > today + dt.timedelta(days=days)):
        errs.append(f"date: {date_part} is outside the scouting window")
    if data.get("ends_at"):
        try:
            end = parse_when(data["ends_at"])
            if isinstance(start, dt.datetime) and isinstance(end, dt.datetime):
                if end <= start:
                    errs.append("date: ends_at is not after starts_at (an overnight end belongs to the next day)")
            elif str(end)[:10] < date_part:
                errs.append("date: ends before it starts")
        except ValueError:
            errs.append(f"date: ends_at '{data['ends_at']}' is not a real date or time")
    for field in ("starts_at", "ends_at"):
        errs += check_london_time(field, data.get(field))
    return errs


def check_venue(data: dict) -> list[str]:
    errs = []
    if data["zone"] == "outer" and not data.get("worth_the_trip"):
        errs.append("zone: outer-zone events are only kept when worth_the_trip is true")
    reg = source_registry(data.get("category"))
    if reg is None:
        return errs
    venues = {v["id"]: v for v in reg.get("venues", [])}
    vid, vname = data["venue"]["venue_id"], norm_name(data["venue"]["name"])
    for closed in reg.get("do_not_list", []):
        if vid == closed["id"] or (vname and vname == norm_name(closed["name"])):
            errs.append(f"venue: {closed['name']} is on the do-not-list ({closed['reason']})")
            return errs
    if vid is None:
        return errs
    if vid not in venues:
        errs.append(f"venue: '{vid}' is not in the registry (use null and flag it in the run report)")
    elif venues[vid]["zone"] != data["zone"]:
        errs.append(f"zone: registry says {venues[vid]['zone']}, record says {data['zone']}")
    return errs


def check_price(p: dict) -> list[str]:
    errs = []
    if p["known"]:
        if p.get("is_free") is None:
            errs.append("price: known=true but is_free is not set")
        if p.get("is_free") is False and p.get("min_gbp") is None:
            errs.append("price: paid event with no min_gbp (use 0 if free before a certain time)")
        if p.get("is_free") is True and (p.get("min_gbp") or 0) > 0:
            errs.append("price: marked free but min_gbp is above zero")
        if p.get("min_gbp") is not None and p.get("max_gbp") is not None and p["min_gbp"] > p["max_gbp"]:
            errs.append("price: min_gbp is greater than max_gbp")
    elif any(p.get(k) not in (None,) for k in ("min_gbp", "max_gbp", "is_free", "notes")):
        errs.append("price: known=false but other price values are filled in (set them all to null)")
    return errs


def check_filename(path: Path, data: dict) -> list[str]:
    return [] if path.stem == data["id"] else [f"file: name should be {data['id']}.json"]


def venue_has_no_primary(data: dict) -> bool:
    reg = source_registry(data.get("category")) or {}
    vid = get(data, "venue.venue_id")
    return any(v["id"] == vid and v.get("no_primary_listing") for v in reg.get("venues", []))


def load_ref(rel: str | None, label: str) -> tuple[dict | None, list[str]]:
    if not rel:
        return None, [f"{label}: missing"]
    p = ROOT / rel
    if not p.exists():
        return None, [f"{label}: {rel} does not exist"]
    data, err = read_json(p)
    if err or not isinstance(data, dict):
        return None, [f"{label}: {rel} is unreadable ({err or 'not an object'})"]
    return data, []


# ---------------------------------------------------------------- per kind

def check_candidate(path: Path, data: dict, today: dt.date | None, days: int = 31) -> list[str]:
    errs = (check_filename(path, data) + check_sources(data) + check_evidence_coverage(data)
            + check_id_and_date(data, today, days) + check_venue(data) + check_price(data["price"]))
    if data["scout_confidence"] == "high":
        if not any(ev["source_kind"] == "primary" and "starts_at" in ev["fields"] for ev in data["evidence"]):
            errs.append("confidence: 'high' needs the date quoted from a primary source")
        if "T" not in data["starts_at"]:
            errs.append("confidence: 'high' needs a start time, not just a date")
        if venue_has_no_primary(data):
            errs.append("confidence: venues marked no_primary_listing are 'medium' at most")
    return errs


def check_verification(path: Path, data: dict, today: dt.date | None, days: int = 31) -> list[str]:
    errs = check_filename(path, data)
    decision, by = data["decision"], data.get("decided_by", "verifier")
    if decision in ("hold", "reject") and not data["reasons"]:
        errs.append(f"decision: '{decision}' needs at least one reason")
    if by == "human" and not data["reasons"]:
        errs.append("decided_by: a person's decision needs a reason (what they checked)")
    cand, e = load_ref(data["candidate_file"], "candidate_file")
    errs += e
    if data.get("existing_event") and not (ROOT / data["existing_event"]).exists():
        errs.append(f"existing_event: {data['existing_event']} does not exist")
    if cand is None:
        return errs
    if cand.get("id") != data["id"]:
        errs.append("id: does not match the candidate's id")

    cited = {ev["url"] for ev in cand.get("evidence", [])} | ({cand["ticket_url"]} if cand.get("ticket_url") else set())
    for i, c in enumerate(data["field_checks"]):
        if c["result"] == "confirmed" and (c["method"] == "none" or not c.get("url")):
            errs.append(f"field_checks[{i}]: '{c['field']}' is confirmed but has no URL or method")
        if c.get("url") and c["url"] not in cited:
            errs.append(f"field_checks[{i}]: {c['url']} is not cited by the candidate; check only cited pages")

    if decision != "publish" or by == "human":
        return errs

    checks = data["field_checks"]
    for top in TOP_FACTS:
        if is_filled(top, cand.get(top)) and not any(check_is_for(c["field"], top) for c in checks):
            errs.append(f"field_checks: no check for '{top}', which the candidate filled in")
    if any(c["result"] == "contradicted" for c in checks):
        errs.append("decision: cannot publish with a contradicted field (hold instead)")
    for key, names in KEY_FIELDS.items():
        ok = [c for c in checks if c["field"] in names and c["result"] == "confirmed"]
        if not ok:
            errs.append(f"decision: cannot publish, '{key}' is not confirmed")
            continue
        scripted = [c for c in ok if c["method"] in ("exact", "near")]
        if not scripted:
            errs.append(f"decision: cannot publish, '{key}' was only confirmed by reading the page, not by the "
                        f"quote checker (hold instead)")
            continue
        kinds = set().union(*(evidence_kind(cand, c["url"], key) for c in scripted))
        if "primary" not in kinds and not ("aggregator" in kinds and venue_has_no_primary(cand)):
            errs.append(f"decision: cannot publish, '{key}' is not confirmed from a primary source (hold instead)")
    new = not data.get("existing_event")
    if new and data["page_status_seen"] in ("cancelled", "postponed", "page-gone"):
        errs.append(f"decision: a new event whose page shows '{data['page_status_seen']}' must be rejected")
    if new and cand.get("status") in ("cancelled", "postponed"):
        errs.append(f"decision: a new event the scout found '{cand['status']}' must be rejected")
    return errs


def check_event(path: Path, data: dict, today: dt.date | None, days: int = 31) -> list[str]:
    errs = (check_sources(data) + check_evidence_coverage(data)
            + check_id_and_date(data, None, days) + check_venue(data) + check_price(data["price"]))
    try:  # the folder-and-name rule for events covers the file name
        rel = path.resolve().relative_to(ROOT.resolve())
        expected = Path("data/events") / data["starts_at"][:7] / f"{data['id']}.json"
        if rel.parts[:2] == ("data", "events") and rel != expected:
            errs.append(f"path: should be {expected.as_posix()}")
    except ValueError:
        pass  # outside the repo: the path rule only applies to data/events

    ver = data["verification"]
    removed = ver.get("removed_fields", [])
    if ver["outcome"] == "verified" and removed:
        errs.append("verification: outcome 'verified' but fields were removed (use verified-with-gaps)")
    if ver["outcome"] == "verified-with-gaps" and not removed:
        errs.append("verification: outcome 'verified-with-gaps' but removed_fields is empty")
    for f in removed:
        if is_filled(f, data.get(f)):
            errs.append(f"verification: '{f}' is listed as removed but still filled in")

    rec, e = load_ref(ver["record"], "verification")
    errs += e
    if rec is None:
        return errs
    if rec.get("id") != data["id"]:
        errs.append("verification: record is for a different id")
    if rec.get("decision") != "publish":
        return errs + [f"verification: record says '{rec.get('decision')}', not publish"]
    if rec.get("decided_by") == "human":
        if not any(h.get("by") == "human" for h in data.get("history", [])):
            errs.append("history: a person published this; add a history entry with by: 'human'")
        return errs

    cand, e = load_ref(rec.get("candidate_file"), "verification.candidate_file")
    errs += e
    if cand is None:
        return errs
    checks = rec.get("field_checks", [])
    confirmed = {c["field"].split(".")[0] for c in checks if c["result"] == "confirmed"}
    doubtful = {c["field"].split(".")[0] for c in checks if c["result"] != "confirmed"} - confirmed

    for f in MUST_MATCH:
        if value(data, f) != value(cand, f):
            errs.append(f"{f}: differs from the candidate ({value(cand, f)!r})")
    for f in TOP_FACTS:
        ev_v, cand_v = value(data, f), value(cand, f)
        if f in removed:
            if not is_filled(f, cand_v):
                errs.append(f"verification: '{f}' is listed as removed but the candidate never filled it")
            continue
        if f == "status":
            allowed = {cand_v} | ({rec.get("page_status_seen")} & STATUS_FROM_PAGE)
            if ev_v not in allowed:
                errs.append(f"status: '{ev_v}' matches neither the candidate nor what the verifier saw on the page")
        elif ev_v != cand_v:
            errs.append(f"{f}: differs from the verified candidate; facts may only be copied or removed")
        if is_filled(f, ev_v) and f not in confirmed:
            errs.append(f"{f}: is filled in but the verification record has no confirmed check for it")
        if is_filled(f, cand_v) and f in doubtful and f != "status":
            errs.append(f"{f}: could not be confirmed, so it must be emptied and listed in removed_fields")

    cand_ev = [json.dumps(ev, sort_keys=True) for ev in cand.get("evidence", [])]
    cited = {ev["url"] for ev in cand.get("evidence", [])} | ({cand["ticket_url"]} if cand.get("ticket_url") else set())
    for i, ev in enumerate(data["evidence"]):
        if json.dumps(ev, sort_keys=True) in cand_ev:
            continue
        if ev["fields"] == ["status"] and ev["url"] in cited and ev["source_kind"] == "primary":
            continue  # the verifier's own status quote from the event's primary page
        errs.append(f"evidence[{i}]: not in the candidate (only the verifier's own status quote may be added)")
    return errs


def check_duplicate_events(events: list[tuple[Path, dict]]) -> dict[Path, list[str]]:
    """Same venue, similar title, within 7 days, under different ids: probably one night listed twice."""
    out: dict[Path, list[str]] = {}
    for i, (pa, a) in enumerate(events):
        for pb, b in events[i + 1:]:
            if not a["venue"]["venue_id"] or a["venue"]["venue_id"] != b["venue"]["venue_id"]:
                continue
            if {a["status"], b["status"]} & {"cancelled", "postponed"}:
                continue
            try:
                gap = abs((dt.date.fromisoformat(a["starts_at"][:10]) - dt.date.fromisoformat(b["starts_at"][:10])).days)
            except ValueError:
                continue
            sim = difflib.SequenceMatcher(None, a["title"].lower(), b["title"].lower()).ratio()
            if gap <= 7 and sim >= 0.8 and not (a.get("recurrence") and b.get("recurrence")):
                out.setdefault(pb, []).append(
                    f"duplicate: looks like the same night as {pa.name} ({gap} days apart). If the date changed, "
                    f"mark the old one postponed or remove it")
    return out


CHECKS = {"candidates": check_candidate, "verification": check_verification, "events": check_event}
DEFAULT_DIRS = {"candidates": "data/candidates", "verification": "data/verification", "events": "data/events"}


def run(kind: str, paths: list[Path], today: dt.date | None, days: int, validators) -> tuple[int, int]:
    files: list[Path] = []
    for p in paths:
        if not p.exists():
            print(f"(nothing to check at {p})")
        elif p.is_dir():
            files += sorted(p.rglob("*.json"))
        else:
            files.append(p)
    seen: dict[str, Path] = {}
    results: dict[Path, list[str]] = {}
    good_events: list[tuple[Path, dict]] = []
    for f in files:
        data, err = read_json(f)
        if err or not isinstance(data, dict):
            results[f] = [err or "not a JSON object"]
            continue
        errs = schema_errors(validators[kind], data)
        if not errs:
            try:
                errs = CHECKS[kind](f, data, today, days)
            except Exception as e:  # a bug or a very odd file must not hide the other results
                errs = [f"checker crashed on this file: {type(e).__name__}: {e}"]
            if kind == "events":
                good_events.append((f, data))
        ident = data.get("id")
        if isinstance(ident, str):
            key = ident if kind == "events" else f"{f.parent}/{ident}"
            if key in seen:
                errs.append(f"duplicate id, also in {seen[key]}")
            else:
                seen[key] = f
        results[f] = errs
    for f, extra in check_duplicate_events(good_events).items():
        results[f] += extra
    failed = 0
    for f, errs in results.items():
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
    ap.add_argument("--window", action="store_true", help="reject candidates outside yesterday..+DAYS")
    ap.add_argument("--days", type=int, default=31)
    ap.add_argument("--today", type=dt.date.fromisoformat, default=None)
    args = ap.parse_args(argv)

    validators = load_validators()
    today = (args.today or dt.datetime.now(LONDON).date()) if args.window else None
    kinds = ["candidates", "verification", "events"] if args.kind == "all" else [args.kind]

    total = failed = 0
    for kind in kinds:
        paths = args.paths if (args.paths and args.kind != "all") else [ROOT / DEFAULT_DIRS[kind]]
        print(f"\n== {kind} ==")
        n, f = run(kind, paths, today, args.days, validators)
        total += n
        failed += f
    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
