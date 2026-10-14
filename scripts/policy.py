"""Source policy shared by validate.py and check_quote.py.

Which websites we may never use, and which are only listings aggregators, comes from the
'platforms' section of every data/sources/<category>.json, plus a hard-coded backstop that
no registry edit can remove.

A person can approve one venue's page on an aggregator as that venue's primary listing (for example
Backyard Comedy Club, whose real booking system is DesignMyNight): in the venue's registry entry, that
listing has "role": "primary" and an "approved" note saying who approved it and when. Evidence from a
page under that listing's URL then counts as primary, for that venue only.
"""
from __future__ import annotations

import json
import urllib.parse
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources"

# Never fetched, never accepted as evidence, whatever the registries say.
ALWAYS_FORBIDDEN = {"ra.co", "residentadvisor.net", "instagram.com", "facebook.com", "fb.com", "fb.me"}


def domain_of(url: str) -> str:
    host = (urllib.parse.urlsplit(url).hostname or "").lower().rstrip(".")  # "ra.co." is ra.co
    return host[4:] if host.startswith("www.") else host


def _matches(host: str, domains: set[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


@lru_cache(maxsize=1)
def _domains() -> tuple[frozenset, frozenset]:
    forbidden, discovery = set(ALWAYS_FORBIDDEN), set()
    for p in SOURCES.glob("*.json"):
        reg = json.loads(p.read_text(encoding="utf-8-sig"))
        for pl in reg.get("platforms", []):
            doms = set(pl.get("domains", []))
            if pl.get("policy") in ("do-not-use", "do-not-scrape"):
                forbidden |= doms
            elif pl.get("policy") == "discovery-only":
                discovery |= doms
        for closed in reg.get("do_not_list", []):
            forbidden |= set(closed.get("domains", []))
        for blocked in reg.get("blocked_domains", []):  # e.g. an open venue whose website was hacked
            forbidden.add(blocked["domain"])
    return frozenset(forbidden), frozenset(discovery)


def is_forbidden(url: str) -> bool:
    return _matches(domain_of(url), set(_domains()[0]))


def is_discovery_only(url: str) -> bool:
    return _matches(domain_of(url), set(_domains()[1]))


def _same_page_or_below(url: str, prefix: str) -> bool:
    def segments(u: str) -> list[str] | None:
        parts = urllib.parse.urlsplit(u)
        if parts.scheme != "https" or parts.port not in (None, 443) or parts.username or parts.password:
            return None
        segs = [s for s in urllib.parse.unquote(parts.path).split("/") if s]
        if any(s in (".", "..") or "/" in s or "\\" in s for s in segs):
            return None
        return [domain_of(u)] + segs
    u, p = segments(url), segments(prefix)
    return u is not None and p is not None and u[:len(p)] == p


@lru_cache(maxsize=1)
def _approved_primary() -> tuple[tuple[str, str], ...]:
    """(venue id, listing URL) for every aggregator listing a person approved as a venue's primary one."""
    out = []
    for p in SOURCES.glob("*.json"):
        reg = json.loads(p.read_text(encoding="utf-8-sig"))
        for v in reg.get("venues", []):
            for listing in v.get("listings", []):
                ok = listing.get("approved") or {}
                if listing.get("role") == "primary" and ok.get("by") and ok.get("on") and listing.get("url") \
                        and is_discovery_only(listing["url"]):
                    out.append((v["id"], listing["url"]))
    return tuple(out)


def is_approved_primary(url: str, venue_id: str | None) -> bool:
    """True if a person approved this aggregator page as the primary listing of this venue."""
    return bool(venue_id) and any(vid == venue_id and _same_page_or_below(url, listing)
                                  for vid, listing in _approved_primary())
