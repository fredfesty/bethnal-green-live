#!/usr/bin/env python3
"""Print a web page's visible text exactly as written, for quoting in evidence.

Scouts use this instead of a summarising web reader, so their quotes are word for word and
pass scripts/check_quote.py. It follows the same rules: never-use sites are refused, robots.txt
is obeyed (for us and for Claude's crawlers), and a site that answers 403/429 is left alone.

Usage
  python scripts/page_text.py https://www.oxfordhouse.org.uk/events/
  python scripts/page_text.py --as arts <url>              # scouts: always say who you are (scripts/budget.py)
  python scripts/page_text.py <url> --find "friday jazz"     # only lines containing these words, with context
  python scripts/page_text.py <url> --max-chars 20000

The first line says what happened: "OK <final url>", or "REFUSED <reason>" / "FAILED <reason>".
With --as, every page counts against that scout's hard limits for the run (20 pages per website, 150 in
all); over a limit the answer is "REFUSED budget: ..." and that site must be left alone for the rest of
the run. A page already read this run comes from the run's cache and costs nothing.
JSON-LD event data embedded in the page is included as text, so dates and prices from it can be quoted too.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_quote as cq  # noqa: E402
import policy  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--find", help="show only lines containing all these words (case-insensitive), with 2 lines of context")
    ap.add_argument("--max-chars", type=int, default=30000)
    ap.add_argument("--as", dest="agent", default=None, help="your scout name, e.g. nights-clubs (counts the page against your budget)")
    ap.add_argument("--run-date", default=None, help="with --as: the run date (default: today in London)")
    args = ap.parse_args(argv)
    try:
        cq.use_budget(args.agent, args.run_date)
    except ValueError as e:
        print(f"REFUSED {e}")
        return 2

    if policy.is_forbidden(args.url):
        print("REFUSED never-use site under our source policy")
        return 2
    reason = cq.budget_refusal(args.url)  # before anything touches the site, robots.txt included
    if reason:
        print(f"REFUSED {reason}")
        return 2
    reason = cq.robots_verdict(args.url)
    if reason:
        print(f"REFUSED {reason}")
        return 2
    page = cq.fetch(args.url)
    if page.get("result") == "rate-limited":
        print(f"REFUSED {page.get('error')}")
        return 2
    if page.get("result") == "blocked":
        print(f"REFUSED {page.get('error')}")
        return 2
    if page.get("result") or page.get("readable") is None:
        print(f"FAILED {page.get('error') or page.get('result')} (status {page.get('status')})")
        return 1
    print(f"OK {page['final_url']}")
    text = page["readable"]
    if args.find:
        words = args.find.lower().split()
        lines = text.split("\n")
        keep = set()
        for i, line in enumerate(lines):
            if all(w in line.lower() for w in words):
                keep.update(range(max(0, i - 2), min(len(lines), i + 3)))
        text = "\n".join(lines[i] if i - 1 in keep or i == min(keep) else f"...\n{lines[i]}" for i in sorted(keep)) if keep else "(no matching lines)"
    print(text[: args.max_chars])
    if len(text) > args.max_chars:
        print(f"\n[truncated at {args.max_chars} of {len(text)} characters; use --find or --max-chars]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
