#!/usr/bin/env python3
"""Check Bethnal Green Live data files against the formats and the house rules.

Usage
  python scripts/validate.py candidates data/candidates/nights-music/2026-10-13 --window
  python scripts/validate.py verification data/verification/2026-10-13
  python scripts/validate.py events data/events
  python scripts/validate.py venues data/venues
  python scripts/validate.py newsletter data/newsletter/issues
  python scripts/validate.py venue-leads data/venue-leads/2026-10-18
  python scripts/validate.py venue-findings data/venue-research/2026-10-18
  python scripts/validate.py all            # everything under data/ (what CI runs)

Options
  --window        also reject candidates dated outside yesterday .. +DAYS, and check newsletter issues against
                  the events as they stand today (use during runs, not in CI)
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
                verifier's own status quote); no duplicate listings of the same night; the short
                description ('listing') is one or two sentences in our own words, any price, time, day
                or 'free' it mentions matches the checked facts, and it has no advert words, no
                'tonight' and no ticket status
  venues       the venue is in a registry (same name and zone) and not closed; every filled-in field is
                named by an evidence item; the website and access page come from the venue itself; the
                written fields are in our own words, not copied from the quotes; a venue found by the weekly
                run (not in a registry) has its own types, address, postcode and location, sits in the core
                or fringe zone, and doesn't duplicate a venue we know
  venue-leads   every lead has a quote for its name and anything else it states; news about a known venue
                names that venue; nothing from a never-use site
  venue-findings  every proposed value is backed by a quote naming that field; written values are our own words
  newsletter    every event in an issue is published, not in doubt, not cancelled or sold out, and in the
                right week for its section; the editor's words are our own, and any price, time, day or
                'free' they mention matches the checked facts; Fred's letter claims no first-hand
                experience unless his notes for that issue supplied it
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
import newsletter  # noqa: E402
import venuelib  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
SOURCES = ROOT / "data" / "sources"
LONDON = ZoneInfo("Europe/London")

# Fields that state facts. Dotted names are used for evidence coverage.
FACT_FIELDS = [
    "title", "venue.name", "venue.address", "venue.postcode", "starts_at", "ends_at",
    "recurrence", "run_schedule", "lineup", "genres", "price", "ticket_url", "age_restriction",
    "accessibility", "status",
]
TOP_FACTS = ["title", "venue", "starts_at", "ends_at", "recurrence", "run_schedule", "lineup", "genres", "price",
             "ticket_url", "age_restriction", "accessibility", "status"]
MUST_MATCH = ["id", "category", "subcategory", "zone", "worth_the_trip"]
KEY_FIELDS = {"title": ("title",), "venue": ("venue", "venue.name"), "starts_at": ("starts_at",)}
STATUS_FROM_PAGE = {"few-left", "sold-out", "cancelled", "postponed"}
DEFAULTS = {"lineup": [], "genres": [], "worth_the_trip": False}

# Which event types each category may use (a gig filed under food & drink is a mistake).
CATEGORY_SUBCATEGORIES = {
    "nights-music": {"club-night", "gig", "dj-bar", "queer-party", "cabaret-drag", "karaoke", "jazz", "open-mic",
                     "folk-acoustic", "in-store", "festival", "other"},
    "arts": {"theatre", "comedy", "film", "exhibition", "talk", "dance", "performance", "other"},
    "food-drink": {"supper-club", "pop-up", "tasting", "special-menu", "cookery-class", "food-market",
                   "food-festival", "opening", "quiz", "other"},
    "community": {"market", "fair", "workshop", "family", "outdoors", "sport", "talk", "volunteering",
                  "open-studios", "tour", "festival", "other"},
    "health-wellness": {"yoga", "pilates", "fitness", "run", "sauna", "sound-bath", "meditation", "breathwork",
                        "retreat", "workshop", "talk", "festival", "other"},
}
MAX_RUN_DAYS = 200  # an exhibition or run longer than this is almost certainly a mistake


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
        for kind, name in [("candidates", "candidate-event"), ("events", "event"), ("verification", "verification"),
                           ("venues", "venue"), ("venue-leads", "venue-lead"),
                           ("venue-findings", "venue-findings"), ("newsletter", "newsletter-issue")]
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
    last_day = d
    if data.get("ends_at"):
        try:
            last_day = dt.date.fromisoformat(data["ends_at"][:10])
        except ValueError:
            pass
    if (last_day - d).days > MAX_RUN_DAYS:
        errs.append(f"date: runs for more than {MAX_RUN_DAYS} days; check ends_at")
    # A run (exhibition, theatre run) that opened earlier but is still on counts as current.
    if today and (last_day < today - dt.timedelta(days=1) or d > today + dt.timedelta(days=days)):
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


def is_run(data: dict) -> bool:
    """An exhibition, theatre run or multi-day menu: ends two or more days after it starts.
    (An overnight club night ends the next day, which is not a run.)"""
    try:
        return bool(data.get("ends_at")) and (
            dt.date.fromisoformat(data["ends_at"][:10]) - dt.date.fromisoformat(data["starts_at"][:10])).days >= 2
    except ValueError:
        return False


def check_subcategory(data: dict) -> list[str]:
    allowed = CATEGORY_SUBCATEGORIES.get(data.get("category"), set())
    if data.get("subcategory") not in allowed:
        return [f"subcategory: '{data.get('subcategory')}' is not a {data.get('category')} type "
                f"(allowed: {', '.join(sorted(allowed))})"]
    return []


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
        # A venue the weekly venue run added has a profile in data/venues/ instead of a registry entry.
        prof = read_json(ROOT / "data" / "venues" / f"{vid}.json")[0] if (ROOT / "data" / "venues" / f"{vid}.json").exists() else None
        if not isinstance(prof, dict):
            errs.append(f"venue: '{vid}' is not in the registry or data/venues/ (use null and flag it in the run report)")
        elif prof.get("status") == "closed":
            errs.append(f"venue: {prof.get('name', vid)} is marked closed in data/venues/{vid}.json")
        elif prof.get("zone") != data["zone"]:
            errs.append(f"zone: data/venues/{vid}.json says {prof.get('zone')}, record says {data['zone']}")
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
    errs = (check_filename(path, data) + check_sources(data) + check_evidence_coverage(data) + check_subcategory(data)
            + check_id_and_date(data, today, days) + check_venue(data) + check_price(data["price"]))
    if data["scout_confidence"] == "high":
        if not any(ev["source_kind"] == "primary" and "starts_at" in ev["fields"] for ev in data["evidence"]):
            errs.append("confidence: 'high' needs the date quoted from a primary source")
        if is_run(data):
            if not any(ev["source_kind"] == "primary" and "ends_at" in ev["fields"] for ev in data["evidence"]):
                errs.append("confidence: 'high' for a run needs the closing date quoted from a primary source")
        elif "T" not in data["starts_at"]:
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
    if is_run(cand):
        ends = [c for c in checks if c["field"] == "ends_at" and c["result"] == "confirmed" and c["method"] in ("exact", "near")]
        if not ends:
            errs.append("decision: cannot publish a run (an exhibition or a run of dates) without its closing date "
                        "confirmed by the quote checker (hold instead)")
    new = not data.get("existing_event")
    if new and data["page_status_seen"] in ("cancelled", "postponed", "page-gone"):
        errs.append(f"decision: a new event whose page shows '{data['page_status_seen']}' must be rejected")
    if new and cand.get("status") in ("cancelled", "postponed"):
        errs.append(f"decision: a new event the scout found '{cand['status']}' must be rejected")
    return errs


def check_event(path: Path, data: dict, today: dt.date | None, days: int = 31) -> list[str]:
    errs = (check_sources(data) + check_evidence_coverage(data) + check_subcategory(data)
            + check_id_and_date(data, None, days) + check_venue(data) + check_price(data["price"])
            + check_listing(data))
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
            if a.get("ticket_url") and b.get("ticket_url") and a["ticket_url"] != b["ticket_url"]:
                continue  # separate ticket pages: a run of nights, not one night listed twice
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


# ---------------------------------------------------------------- venue profiles

VENUE_FACTS = [
    "types", "status", "aliases", "summary", "crowd", "website", "age_policy", "capacity", "address", "postcode",
    "music.styles", "music.notes",
    "accessibility.step_free", "accessibility.accessible_toilet", "accessibility.hearing_loop",
    "accessibility.notes", "accessibility.access_page",
    "cost.free_entry", "cost.notes",
]
WRITTEN_FIELDS = ["summary", "crowd", "music.notes", "accessibility.notes", "cost.notes"]
COPY_RUN = 7  # this many words in a row lifted from a quote is copying, not our own words


def all_registry_venues() -> tuple[dict[str, dict], list[dict]]:
    venues, closed = {}, []
    for p in sorted(SOURCES.glob("*.json")):
        reg = read_json(p)[0]
        if isinstance(reg, dict):
            for v in reg.get("venues", []):
                venues.setdefault(v["id"], v)
            closed += reg.get("do_not_list", [])
    return venues, closed


def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9£']+", (s or "").lower().replace("’", "'"))


def copied_run(text: str, quote: str, n: int = COPY_RUN) -> str | None:
    """The first run of n words that appears in both, or None."""
    w, q = _words(text), _words(quote)
    grams = {tuple(q[i:i + n]) for i in range(len(q) - n + 1)}
    for i in range(len(w) - n + 1):
        if tuple(w[i:i + n]) in grams:
            return " ".join(w[i:i + n])
    return None


def _other_profiles(exclude: str) -> list[dict]:
    out = []
    for p in sorted((ROOT / "data" / "venues").glob("*.json")):
        d = read_json(p)[0]
        if isinstance(d, dict) and d.get("id") and d["id"] != exclude:
            out.append(d)
    return out


def _filled(v) -> bool:
    return v not in (None, "", []) if not isinstance(v, bool) else True


def check_sources_any(ev: list[dict]) -> list[str]:
    errs = []
    for i, e in enumerate(ev):
        if policy.is_forbidden(e["url"]):
            errs.append(f"evidence[{i}]: {policy.domain_of(e['url'])} is a never-use source")
        elif e["source_kind"] == "primary" and policy.is_discovery_only(e["url"]):
            errs.append(f"evidence[{i}]: {policy.domain_of(e['url'])} is an aggregator; it cannot be 'primary'")
    return errs


def check_venue_profile(path: Path, data: dict, today: dt.date | None = None, days: int = 31) -> list[str]:
    errs = check_filename(path, data)
    venues, closed = all_registry_venues()
    for c in closed:
        if data["id"] == c["id"] or norm_name(data["name"]) == norm_name(c["name"]):
            return errs + [f"venue: {c['name']} is on the do-not-list ({c['reason']})"]
    reg = venues.get(data["id"])
    names = {norm_name(data["name"])} | {norm_name(a) for a in data.get("aliases", [])}
    if reg is not None:
        reg_names = {norm_name(reg["name"])} | {norm_name(a) for a in reg.get("aliases", [])}
        if norm_name(data["name"]) not in reg_names | {norm_name(a) for a in data.get("aliases", [])}:
            errs.append(f"name: registry calls this venue '{reg['name']}'")
        if reg["zone"] != data["zone"]:
            errs.append(f"zone: registry says {reg['zone']}, profile says {data['zone']}")
    else:
        # A venue the weekly run found: it carries everything the registry would.
        for f in ("types", "address", "postcode", "location"):
            if not _filled(data.get(f)):
                errs.append(f"{f}: a venue that is not in data/sources/ needs its own {f}")
        if data["zone"] == "outer":
            errs.append("zone: new venues are only added in the core or fringe zone (outer ones go to a person)")
        loc = data.get("location")
        if loc:
            dist = venuelib.distance_m(loc["lat"], loc["lon"])
            if abs(dist - loc["distance_m"]) > 25:
                errs.append(f"location: distance_m says {loc['distance_m']} but lat/lon are {dist} m from the tube")
            expected = venuelib.zone_for(data.get("postcode"), dist)
            if expected != data["zone"]:
                errs.append(f"zone: {dist} m from Bethnal Green tube is '{expected}', not '{data['zone']}'")
        for k, v in venues.items():
            if names & ({norm_name(v["name"])} | {norm_name(a) for a in v.get("aliases", [])}):
                errs.append(f"name: '{data['name']}' is already in the registry as '{k}'; use that id")
    for other in _other_profiles(data["id"]):
        if names & ({norm_name(other["name"])} | {norm_name(a) for a in other.get("aliases", [])}):
            errs.append(f"name: '{data['name']}' already has a profile, data/venues/{other['id']}.json")

    ev = data["evidence"]
    errs += check_sources_any(ev)
    named = {f for e in ev for f in e["fields"]}
    for field in VENUE_FACTS:
        v = get(data, field)
        if field == "status" and v in (None, "open"):
            continue
        if _filled(v) and not covered(field, named):
            errs.append(f"evidence: '{field}' is filled in but no evidence item names it")

    for field in ("website", "accessibility.access_page"):
        url = get(data, field)
        if url and not any(e["source_kind"] == "primary" and covered(field, set(e["fields"])) for e in ev):
            errs.append(f"{field}: must be backed by a quote from the venue's own page (source_kind 'primary')")
        if url and policy.is_forbidden(url):
            errs.append(f"{field}: points to a never-use source")

    for field in WRITTEN_FIELDS:
        text = get(data, field)
        if not text:
            continue
        for e in ev:
            run_ = copied_run(text, e["quote"])
            if run_:
                errs.append(f"{field}: copies the source word for word (\"{run_}\"); write it in our own words")
                break

    removed = (data.get("review") or {}).get("removed_fields", [])
    for f in removed:
        if _filled(get(data, f)) and not isinstance(get(data, f), bool):
            errs.append(f"review: '{f}' is listed as removed but still filled in")
    return errs


def check_venue_lead(path: Path, data: dict, today: dt.date | None = None, days: int = 31) -> list[str]:
    errs = []
    if path.stem != f"{data['found_by']}-{data['id']}":
        errs.append(f"file: name should be {data['found_by']}-{data['id']}.json")
    errs += check_sources_any(data["evidence"])
    named = {f for e in data["evidence"] for f in e["fields"]}
    for field in ("name", "address", "postcode", "website", "kind_hint"):
        if field == "name" or _filled(data.get(field)):
            if field not in named:
                errs.append(f"evidence: '{field}' {'is filled in but ' if field != 'name' else ''}no evidence item names it")
    if data["signal"] != "new" and "signal" not in named:
        errs.append(f"evidence: signal '{data['signal']}' needs a quote that says so (fields: ['signal'])")
    if data["signal"] != "new" and not data.get("about_venue_id"):
        errs.append(f"about_venue_id: news ('{data['signal']}') must name the known venue it is about")
    if data.get("about_venue_id"):
        ids = {k["id"] for k in venuelib.known_venues()}
        if data["about_venue_id"] not in ids:
            errs.append(f"about_venue_id: '{data['about_venue_id']}' is not a venue we know")
    return errs


def check_venue_findings(path: Path, data: dict, today: dt.date | None = None, days: int = 31) -> list[str]:
    errs = []
    if path.name != f"{data['venue_id']}.{data['aspect']}.json":
        errs.append(f"file: name should be {data['venue_id']}.{data['aspect']}.json")
    for i, f in enumerate(data["findings"]):
        errs += [f"findings[{i}] {e}" for e in check_sources_any(f["evidence"])]
        if not any(covered(f["field"], set(e["fields"])) for e in f["evidence"]):
            errs.append(f"findings[{i}]: no evidence item names '{f['field']}'")
        if f["field"] in WRITTEN_FIELDS and isinstance(f["value"], str):
            for e in f["evidence"]:
                run_ = copied_run(f["value"], e["quote"])
                if run_:
                    errs.append(f"findings[{i}]: '{f['field']}' copies the source word for word (\"{run_}\")")
                    break
    return errs


# ---------------------------------------------------------------- newsletter issues

def without_names(text: str, events: list[dict]) -> str:
    """Event titles, venue names and line-up names may be repeated word for word; take them out first."""
    names = sorted({n for e in events for n in [e["title"], e["venue"]["name"], *(e.get("lineup") or [])] if n},
                   key=len, reverse=True)
    for n in names:
        text = re.sub(re.escape(n), " ", text, flags=re.I)
    return text


LISTING_BLURB_CHARS = (40, 320)  # the short description under each event: one or two sentences
LISTING_HEADLINE_CHARS = 90


def _not_after(a: str | None, b: str | None) -> bool:
    try:
        return dt.datetime.fromisoformat(a) <= dt.datetime.fromisoformat(b)
    except (TypeError, ValueError):
        return True


def check_listing(data: dict) -> list[str]:
    """The event's short description: our own words, consistent with the checked facts, in house style."""
    lst = data.get("listing")
    if not lst:
        return []
    errs = []
    lo, hi = LISTING_BLURB_CHARS
    n = len(lst["blurb"].strip())
    if not lo <= n <= hi:
        errs.append(f"listing.blurb: {n} characters; keep it to one or two sentences ({lo} to {hi} characters)")
    head = lst.get("headline")
    if head and len(head) > LISTING_HEADLINE_CHARS:
        errs.append(f"listing.headline: {len(head)} characters; keep it to {LISTING_HEADLINE_CHARS}")
    quotes = [ev["quote"] for ev in data["evidence"]]
    vid = data["venue"].get("venue_id")
    if vid:
        profile = read_json(ROOT / "data" / "venues" / f"{vid}.json")[0]
        # Only the profile as it stood when the description was written: quotes a later venue run adds
        # must not turn a description that was fine into a failure in someone else's run.
        if isinstance(profile, dict) and _not_after(profile.get("profiled_at"), lst.get("written_at")):
            quotes += [ev["quote"] for ev in profile.get("evidence", [])]
    for field in ("headline", "blurb"):
        text = lst.get(field)
        if not text:
            continue
        plain = without_names(text, [data])  # titles and names may be repeated, and never trip a rule
        for q in quotes:
            run_ = copied_run(plain, q)
            if run_:
                errs.append(f"listing.{field}: copies a source word for word (\"{run_}\"); write it in our own words")
                break
        errs += [f"listing.{field}: {p}" for p in newsletter.fact_problems(plain, [data], one_event=True)]
        errs += [f"listing.{field}: {p}" for p in newsletter.style_problems(plain)]
    return errs


def check_issue(path: Path, data: dict, today: dt.date | None = None, days: int = 31) -> list[str]:
    errs = check_filename(path, data)
    frm, to = (dt.date.fromisoformat(data["covers"][k]) for k in ("from", "to"))
    sent = dt.date.fromisoformat(data["id"])
    if not frm <= to <= frm + dt.timedelta(days=6):
        errs.append("covers: must be one week at most, 'from' no later than 'to'")
    if sent > frm:
        errs.append("covers: the issue must go out on or before the first day it covers")

    # Structure is always checked. Everything that depends on the events (which keep changing after an issue
    # has gone out: tickets sell out, prices move) is checked only with --window, when an issue is being made.
    fresh = today is not None
    events = newsletter.load_events(ROOT)
    venues = newsletter.load_venue_profiles(ROOT)
    used: list[dict] = []
    seen: set[str] = set()
    picks = [i for i, s in enumerate(data["sections"]) if s["kind"] == "pick-of-the-week"]
    if len(picks) > 1:
        errs.append("sections: only one pick of the week")
    if picks and picks[0] != 0:
        errs.append("sections: the pick of the week comes first")

    for si, s in enumerate(data["sections"]):
        where = f"sections[{si}] ({s['kind']})"
        if s["kind"] == "pick-of-the-week" and (len(s["items"]) != 1 or s["layout"] != "hero"):
            errs.append(f"{where}: one event, laid out as 'hero'")
        if s["layout"] == "hero" and len(s["items"]) > 2:
            errs.append(f"{where}: 'hero' is for one or two events")
        for ii, it in enumerate(s["items"]):
            at = f"{where}.items[{ii}]"
            eid = it["event_id"]
            if eid in seen:
                errs.append(f"{at}: {eid} is already in this issue")
            seen.add(eid)
            if s["layout"] == "compact" and it.get("blurb"):
                errs.append(f"{at}: compact entries show no blurb; leave it null")
            if not fresh:
                continue
            e = events.get(eid)
            if e is None:
                errs.append(f"{at}: no published event {eid} in data/events")
                continue
            used.append(e)
            if e.get("needs_review"):
                errs.append(f"{at}: {eid} is under review, so it can't go out")
            if e["status"] in ("cancelled", "postponed", "sold-out"):
                errs.append(f"{at}: {eid} is {e['status']}")
            day = newsletter.event_date(e)
            if s["kind"] == "save-the-date":
                if not to < day <= to + dt.timedelta(days=newsletter.SAVE_THE_DATE_DAYS):
                    errs.append(f"{at}: save-the-date events open after this week and within "
                                f"{newsletter.SAVE_THE_DATE_DAYS} days of it ({day} doesn't)")
            elif not newsletter.on_during(e, frm, to):
                errs.append(f"{at}: {eid} is on {day}, outside this issue's week")
            wanted = newsletter.SECTION_CATEGORY.get(s["kind"])
            if wanted and e["category"] != wanted:
                errs.append(f"{at}: {s['kind']} is for {wanted} events ({eid} is {e['category']})")
            if s["kind"] == "worth-the-trip" and e["zone"] != "outer":
                errs.append(f"{at}: worth-the-trip is for outer-zone events")
            if s["kind"] == "free-and-cheap":
                lo = e["price"].get("min_gbp")
                if not (e["price"].get("known") and (e["price"].get("is_free") or (lo is not None and lo < 10))):
                    errs.append(f"{at}: free-and-cheap needs a checked price that is free or under £10")
            if s["kind"] == "on-repeat" and not e.get("recurrence"):
                errs.append(f"{at}: on-repeat is for regular nights (the event has no recurrence)")
            quotes = [ev["quote"] for ev in e["evidence"]]
            v = venues.get(e["venue"].get("venue_id") or "")
            quotes += [ev["quote"] for ev in (v or {}).get("evidence", [])]
            for field in ("headline", "blurb"):
                text = it.get(field)
                if not text:
                    continue
                for q in quotes:
                    run_ = copied_run(without_names(text, [e]), q)
                    if run_:
                        errs.append(f"{at}.{field}: copies a source word for word (\"{run_}\"); write it in our own words")
                        break
                errs += [f"{at}.{field}: {p}" for p in newsletter.fact_problems(without_names(text, [e]), [e], one_event=True)]

    if not fresh:
        return errs
    all_quotes = [ev["quote"] for e in used for ev in e["evidence"]]
    texts = [("subject", data["subject"]), ("preheader", data["preheader"])]
    texts += [(f"sections[{i}].lede", s.get("lede")) for i, s in enumerate(data["sections"])]
    intro = data.get("intro")
    if intro:
        texts += [(f"intro.paragraphs[{i}]", p) for i, p in enumerate(intro["paragraphs"])]
        texts += [("intro.postscript", intro.get("postscript"))]
        notes = intro.get("used_notes")
        if notes and not (ROOT / notes).is_file():
            errs.append(f"intro.used_notes: {notes} doesn't exist")
        if not notes:
            for i, p in enumerate(intro["paragraphs"] + [intro.get("postscript") or ""]):
                m = newsletter.FIRST_HAND.search(p)
                if m:
                    errs.append(f"intro: claims a first-hand experience (\"{m.group(0)}\"); only Fred's notes for "
                                f"this issue can supply one")
    for where, text in texts:
        if not text:
            continue
        for q in all_quotes:
            run_ = copied_run(without_names(text, used), q)
            if run_:
                errs.append(f"{where}: copies a source word for word (\"{run_}\")")
                break
        errs += [f"{where}: {p}" for p in newsletter.fact_problems(without_names(text, used), used, one_event=False)]
    return errs


CHECKS = {"candidates": check_candidate, "verification": check_verification, "events": check_event,
          "venues": check_venue_profile, "venue-leads": check_venue_lead, "venue-findings": check_venue_findings,
          "newsletter": check_issue}
DEFAULT_DIRS = {"candidates": "data/candidates", "verification": "data/verification", "events": "data/events",
                "venues": "data/venues", "venue-leads": "data/venue-leads", "venue-findings": "data/venue-research",
                "newsletter": "data/newsletter/issues"}
KINDS = list(CHECKS)


def run(kind: str, paths: list[Path], today: dt.date | None, days: int, validators) -> tuple[int, int]:
    files: list[Path] = []
    for p in paths:
        if not p.exists():
            print(f"(nothing to check at {p})")
        elif p.is_dir():
            files += sorted(f for f in p.rglob("*.json") if not f.name.startswith("_"))  # _triage.json etc.
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
        if isinstance(ident, str) and kind in ("candidates", "verification", "events", "venues"):
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
    ap.add_argument("kind", choices=KINDS + ["all"])
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--window", action="store_true", help="reject candidates outside yesterday..+DAYS")
    ap.add_argument("--days", type=int, default=31)
    ap.add_argument("--today", type=dt.date.fromisoformat, default=None)
    args = ap.parse_args(argv)

    validators = load_validators()
    today = (args.today or dt.datetime.now(LONDON).date()) if args.window else None
    kinds = KINDS if args.kind == "all" else [args.kind]

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
