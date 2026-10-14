#!/usr/bin/env python3
"""Hard limits on how much each agent asks of other people's websites in one run.

Fred's rule: at most 20 pages per website per run, and at most 5 web searches, so nobody we list from
is upset by us. These are hard limits, not guides. scripts/page_text.py and scripts/check_quote.py
enforce the page limits whenever they are called with `--as <agent>`; web searches are counted by this
script, which every scout calls BEFORE each web search and obeys.

Limits (per run date, per agent):
  - 20 pages per website (the registrable domain: www.dice.fm, dice.fm. and shop.dice.fm are one site);
  - 150 pages in all;
  - 5 web searches.
  The two nights & music scouts (nights-clubs and nights-gigs) share ONE allowance of 20 pages per
  website between them: neither may take more than 12 of a site's 20, except dice.fm, which is split
  14 for nights-clubs and 6 for nights-gigs.
  A site that answered 403 or 429 is not read again by anyone using --as for the rest of the run.

A page that a scout has already read in this run is served from the run's page cache, so reading it
again (for example in the scout's own quote self-check) costs nothing and does not touch the site.
The verifier uses `--as verifier`: its pages are counted the same way, but it never reads or writes the
cache, so it always checks the live page.

Only the names below are accepted, so a typo can't start a fresh allowance.

Usage
  python scripts/budget.py search --as nights-clubs "Hackney Wick club night October 2026"
      OK search 2 of 5 for nights-clubs        (exit 0: you may make this one web search)
      REFUSED 5 of 5 web searches used ...     (exit 2: make no more web searches this run)
  python scripts/budget.py page --as verifier <url>
      count a page read some other way (a WebFetch, an API call) BEFORE making it; obey REFUSED
  python scripts/budget.py usage [--as <agent>] [--date YYYY-MM-DD]
      pages per website and searches used so far, for run reports

The ledger lives in .budget/<run-date>/ (not committed).
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import fcntl
    msvcrt = None
except ImportError:  # Windows
    fcntl = None
    import msvcrt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import policy  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BUDGET_DIR = ROOT / ".budget"
LONDON = ZoneInfo("Europe/London")

PAGES_PER_SITE = 20
PAGES_PER_RUN = 150
SEARCHES_PER_RUN = 5

SCOUTS = {"nights-clubs", "nights-gigs", "arts", "food-drink", "community", "health-wellness"}
NO_CACHE = {"verifier"}  # counted like the scouts, but always reads the live page
AGENTS = SCOUTS | NO_CACHE

# Agents that share one allowance per website.
SHARED_ALLOWANCE = {"nights-clubs": "nights", "nights-gigs": "nights"}
SHARED_MAX_EACH = 12  # within a shared allowance, no agent takes more than this of one site...
# ... except where a site both agents need is split differently.
SPLIT = {("nights", "dice.fm"): {"nights-clubs": 14, "nights-gigs": 6}}

# Second-level labels under which the registrable domain has three labels (venue.co.uk, council.gov.uk).
SECOND_LEVEL = {"co", "org", "ac", "gov", "ltd", "plc", "me", "net", "nhs", "sch", "com"}
# One platform on several domains.
ALIASES = {"eventbrite.co.uk": "eventbrite.com", "fb.com": "facebook.com", "fb.me": "facebook.com",
           "residentadvisor.net": "ra.co"}


def run_date() -> str:
    return dt.datetime.now(LONDON).date().isoformat()


def check_agent(agent: str) -> None:
    if agent not in AGENTS:
        raise ValueError(f"'{agent}' is not a known name; use one of: {', '.join(sorted(AGENTS))}")


def site_of(url: str) -> str:
    """The website a URL belongs to, for the limits: its registrable domain."""
    host = policy.domain_of(url)
    labels = [l for l in host.split(".") if l]
    if host.replace(".", "").isdigit() or ":" in host:  # an IP address is its own site
        return host
    if len(labels) <= 2:
        site = ".".join(labels)
    elif len(labels[-1]) == 2 and labels[-2] in SECOND_LEVEL:
        site = ".".join(labels[-3:])
    else:
        site = ".".join(labels[-2:])
    return ALIASES.get(site, site)


def _dir(date: str) -> Path:
    d = BUDGET_DIR / date
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextlib.contextmanager
def _locked(date: str):
    """Agents run side by side, so every read-then-append of the ledger happens under one lock."""
    with open(_dir(date) / ".lock", "a+") as lock:
        if fcntl:
            fcntl.flock(lock, fcntl.LOCK_EX)
        else:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)  # retries for ~10 s, then raises
        try:
            yield
        finally:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_UN)
            else:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def _ledger(date: str) -> list[dict]:
    p = _dir(date) / "ledger.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        with contextlib.suppress(ValueError):
            out.append(json.loads(line))
    return out


def _append(date: str, row: dict) -> None:
    with open(_dir(date) / "ledger.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def page_refusal(rows: list[dict], agent: str, url: str) -> str | None:
    """Why this agent may not read one more page of this site, or None if it may."""
    site = site_of(url)
    if any(r["kind"] == "slowed" and r["site"] == site for r in rows):
        return f"budget: {site} answered 403 or 429 earlier in this run; leave it alone until tomorrow"
    pages = [r for r in rows if r["kind"] == "page"]
    mine = [r for r in pages if r["agent"] == agent]
    if len(mine) >= PAGES_PER_RUN:
        return f"budget: {agent} has read {len(mine)} pages this run, the limit is {PAGES_PER_RUN}"
    group = SHARED_ALLOWANCE.get(agent)
    sharers = {a for a, g in SHARED_ALLOWANCE.items() if g == group} if group else {agent}
    if group:
        cap = SPLIT.get((group, site), {}).get(agent, SHARED_MAX_EACH)
        used = sum(1 for r in mine if r["site"] == site)
        if used >= cap:
            return (f"budget: {agent} has used its {cap} pages on {site} this run "
                    f"(the two nights scouts share {PAGES_PER_SITE} per website)")
    used = sum(1 for r in pages if r["agent"] in sharers and r["site"] == site)
    if used >= PAGES_PER_SITE:
        who = agent if len(sharers) == 1 else " and ".join(sorted(sharers))
        return f"budget: {who} have read {used} pages on {site} this run, the limit is {PAGES_PER_SITE}"
    return None


def charge_page(agent: str, url: str, date: str | None = None) -> str | None:
    """Record one page read. Returns a refusal reason instead (and records nothing) if over a limit."""
    check_agent(agent)
    date = date or run_date()
    with _locked(date):
        reason = page_refusal(_ledger(date), agent, url)
        if reason:
            return reason
        _append(date, {"kind": "page", "agent": agent, "site": site_of(url), "url": url,
                       "at": dt.datetime.now(LONDON).isoformat(timespec="seconds")})
    return None


def mark_slowed(agent: str, url: str, status: int, date: str | None = None) -> None:
    """A site told us to go away (403/429): nobody under --as reads it again this run."""
    date = date or run_date()
    with _locked(date):
        _append(date, {"kind": "slowed", "agent": agent, "site": site_of(url), "status": status,
                       "at": dt.datetime.now(LONDON).isoformat(timespec="seconds")})


def charge_search(agent: str, query: str, date: str | None = None) -> tuple[bool, int]:
    """(allowed, searches used including this one if allowed)."""
    check_agent(agent)
    date = date or run_date()
    with _locked(date):
        used = sum(1 for r in _ledger(date) if r["kind"] == "search" and r["agent"] == agent)
        if used >= SEARCHES_PER_RUN:
            return False, used
        _append(date, {"kind": "search", "agent": agent, "query": query[:200],
                       "at": dt.datetime.now(LONDON).isoformat(timespec="seconds")})
        return True, used + 1


def usage(date: str | None = None, agent: str | None = None) -> dict:
    date = date or run_date()
    rows = [r for r in _ledger(date) if agent is None or r["agent"] == agent]
    out: dict = {}
    for r in rows:
        a = out.setdefault(r["agent"], {"pages": 0, "sites": Counter(), "searches": 0})
        if r["kind"] == "page":
            a["pages"] += 1
            a["sites"][r["site"]] += 1
        elif r["kind"] == "search":
            a["searches"] += 1
    return out


# ---------------------------------------------------------------- page cache (one run)

def _cache_path(date: str, kind: str, key: str) -> Path:
    d = _dir(date) / kind
    d.mkdir(exist_ok=True)
    return d / (hashlib.sha256(key.encode()).hexdigest()[:32] + ".json")


def cache_get(kind: str, key: str, date: str | None = None):
    p = _cache_path(date or run_date(), kind, key)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None


def cache_put(kind: str, key: str, value, date: str | None = None) -> None:
    """Best effort: a page that can't be cached is simply read again (and counted) next time."""
    try:
        p = _cache_path(date or run_date(), kind, key)
        fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False)
        os.replace(tmp, p)
    except OSError:
        with contextlib.suppress(OSError, UnboundLocalError):
            os.remove(tmp)


# ---------------------------------------------------------------- command line

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="ask for one web search; obey the answer")
    s.add_argument("--as", dest="agent", required=True)
    s.add_argument("query")
    pg = sub.add_parser("page", help="count one page read some other way (WebFetch, an API) before making it")
    pg.add_argument("--as", dest="agent", required=True)
    pg.add_argument("url")
    u = sub.add_parser("usage", help="what has been used this run")
    u.add_argument("--as", dest="agent", default=None)
    u.add_argument("--date", default=None)
    args = ap.parse_args(argv)

    if args.cmd == "page":
        try:
            reason = charge_page(args.agent, args.url)
        except ValueError as e:
            print(f"REFUSED {e}")
            return 2
        if reason:
            print(f"REFUSED {reason}")
            return 2
        print(f"OK page counted for {args.agent} on {site_of(args.url)}")
        return 0
    if args.cmd == "search":
        try:
            ok, used = charge_search(args.agent, args.query)
        except ValueError as e:
            print(f"REFUSED {e}")
            return 2
        if ok:
            print(f"OK search {used} of {SEARCHES_PER_RUN} for {args.agent}")
            return 0
        print(f"REFUSED {used} of {SEARCHES_PER_RUN} web searches used by {args.agent} this run. "
              "Make no more web searches; say in the run report what you could not look for.")
        return 2

    date = args.date or run_date()
    found = usage(date, args.agent)
    if not found:
        print(f"Nothing used on {date}" + (f" by {args.agent}" if args.agent else ""))
        return 0
    for agent, a in sorted(found.items()):
        top = ", ".join(f"{s} {n}" for s, n in a["sites"].most_common())
        print(f"{agent}: {a['pages']} pages ({top or 'none'}); {a['searches']} of {SEARCHES_PER_RUN} web searches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
