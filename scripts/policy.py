"""Source policy shared by validate.py and check_quote.py.

Which websites we may never use, and which are only listings aggregators, comes from the
'platforms' section of every data/sources/<category>.json, plus a hard-coded backstop that
no registry edit can remove.
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
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
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
