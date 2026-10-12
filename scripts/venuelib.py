"""Shared helpers for the weekly venue run: who we already know, names, distance and zones.

Used by zone.py, places_search.py, venue_triage.py and validate.py.
"""
from __future__ import annotations

import json
import math
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources"
VENUES = ROOT / "data" / "venues"

# Bethnal Green Underground station.
BG_TUBE = (51.52700, -0.05490)
CORE_M = 1000      # CLAUDE.md: core = E2 or within about 1 km
FRINGE_M = 1600    # fringe = up to a 20-minute walk


def norm_name(s: str | None) -> str:
    s = (s or "").lower().replace("&", "and").replace("’", "'")
    s = re.sub(r"^the\s+", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def slug(s: str) -> str:
    s = (s or "").lower().replace("&", "and").replace("’", "").replace("'", "")
    s = re.sub(r"^the\s+", "", s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60]


def domain(url: str | None) -> str:
    host = (urllib.parse.urlsplit(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def distance_m(lat: float, lon: float, origin: tuple[float, float] = BG_TUBE) -> int:
    r = 6371000.0
    p1, p2 = math.radians(origin[0]), math.radians(lat)
    dp, dl = p2 - p1, math.radians(lon - origin[1])
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(round(2 * r * math.asin(math.sqrt(a))))


def zone_for(postcode: str | None, dist: int | None) -> str | None:
    if postcode and postcode.upper().replace(" ", "")[:-3] == "E2":
        return "core"
    if dist is None:
        return None
    return "core" if dist <= CORE_M else "fringe" if dist <= FRINGE_M else "outer"


def _read(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def known_venues() -> list[dict]:
    """Every venue we know of, as {id, name, names, websites, postcode, zone, where}.
    where: registry | profile | watchlist | closed."""
    out: dict[str, dict] = {}

    def add(v: dict, where: str, website=None):
        rec = out.setdefault(v["id"], {"id": v["id"], "name": v.get("name", v["id"]), "names": set(), "websites": set(),
                                       "postcode": v.get("postcode"), "zone": v.get("zone"), "where": where})
        rec["names"] |= {norm_name(v.get("name"))} | {norm_name(a) for a in v.get("aliases", []) or []}
        for w in (website, v.get("website")):
            if w:
                rec["websites"].add(domain(w))
        rec["postcode"] = rec["postcode"] or v.get("postcode")
        if where == "closed":
            rec["where"] = "closed"

    for p in sorted(SOURCES.glob("*.json")):
        reg = _read(p) or {}
        for v in reg.get("venues", []):
            add(v, "registry")
        for v in reg.get("watchlist", []):
            add(v, "watchlist")
        for v in reg.get("do_not_list", []):
            add(v, "closed")
    for p in sorted(VENUES.glob("*.json")):
        v = _read(p)
        if isinstance(v, dict) and v.get("id"):
            add(v, "profile" if v["id"] not in out else out[v["id"]]["where"])
            if v.get("status") == "closed":
                out[v["id"]]["where"] = "closed"
    for rec in out.values():
        rec["names"].discard("")
    return list(out.values())


# Websites many venues share; a match on these says nothing.
SHARED_DOMAINS = {"dice.fm", "tickettailor.com", "skiddle.com", "songkick.com", "designmynight.com", "ma.to",
                  "facebook.com", "instagram.com", "linktr.ee", "eventbrite.co.uk", "eventbrite.com",
                  "seetickets.com", "fatsoma.com", "wix.com", "squarespace.com"}


def match_known(name: str | None, website: str | None = None, postcode: str | None = None,
                known: list[dict] | None = None) -> dict | None:
    """The known venue this looks like, or None. Name match, or same own website."""
    known = known if known is not None else known_venues()
    n, d = norm_name(name), domain(website)
    for k in known:
        if n and n in k["names"]:
            return k
    if d and d not in SHARED_DOMAINS:
        for k in known:
            if d in k["websites"]:
                return k
    # "Sebright Arms" vs "The Sebright Arms Bethnal Green": one name inside the other, same postcode.
    if n and postcode:
        pc = postcode.replace(" ", "").upper()
        for k in known:
            if k["postcode"] and k["postcode"].replace(" ", "").upper() == pc and any(
                    len(x) >= 5 and (x in n or n in x) for x in k["names"]):
                return k
    return None
