#!/usr/bin/env python3
"""Check that evidence quotes really appear on their pages. Used by the verifier.

The verifier must never take a scout's word for it. This script re-fetches each evidence URL
(respecting robots.txt), turns the page into plain text, and looks for the quote.

Usage
  python scripts/check_quote.py --candidate data/candidates/nights-music/2026-10-13/<id>.json
  python scripts/check_quote.py --url https://example.com/event --quote "Fri 16 Oct, 10pm"

Output: one JSON object per evidence item, on its own line:
  {"index": 0, "url": ..., "fields": [...], "result": "...", "score": 0.97, "http_status": 200, "note": ...}

Results
  exact          the quote is on the page (after normalising spaces, quotes, dashes and case)
  near           a passage at least 85% similar is on the page (small wording or layout differences)
  missing        the page loaded but the quote is not there
  thin-page      the page loaded but has almost no text (probably built by JavaScript); read it another way
  blocked        robots.txt asks bots not to fetch this page; do not fetch it another way
  fetch-failed   the page could not be loaded (error, timeout, 4xx/5xx); the status says which

Exit code 0 when every quote is exact or near, 1 otherwise.
"""
from __future__ import annotations

import argparse
import difflib
import html
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser

USER_AGENT = "BethnalGreenLiveBot/0.1 (+https://github.com/fredfesty/bethnal-green-live)"
TIMEOUT = 20
NEAR_THRESHOLD = 0.85
THIN_PAGE_CHARS = 400

_TRANSLATE = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-",
    " ": " ", " ": " ", " ": " ",
    "…": "...",
})


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(text)).translate(_TRANSLATE).lower()
    text = re.sub(r"\s+", " ", text)
    return re.sub(r" ([,.;:!?)])", r"\1", text).strip()  # "9pm , Fri" and "9pm, Fri" match


class _TextExtractor(HTMLParser):
    """Visible text plus JSON-LD (event data many venue sites embed); drops scripts and styles."""

    SKIP = {"script", "style", "noscript", "template", "svg"}
    BLOCK = {"p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6",
             "section", "article", "header", "footer", "dd", "dt", "ul", "ol", "table", "nav", "main"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._in_jsonld = False

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type", "").lower() == "application/ld+json":
            self._in_jsonld = True
            return
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag in self.BLOCK:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            return
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self.BLOCK:
            self.parts.append(" ")

    def handle_data(self, data):
        if self._in_jsonld or not self._skip_depth:
            self.parts.append(data)


def page_text(raw_html: str) -> str:
    p = _TextExtractor()
    p.feed(raw_html)
    return normalise(" ".join(p.parts))


_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def allowed_by_robots(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return True
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError:
            rp = None  # no robots.txt (or it errors): allowed, as search engines treat it
        except Exception:
            rp = None  # unreachable robots.txt: treat as allowed, the page fetch will tell us more
        _robots[base] = rp
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


_pages: dict[str, tuple[int | None, str | None, str | None]] = {}


def fetch(url: str) -> tuple[int | None, str | None, str | None]:
    """Returns (http_status, text, error). Cached per run."""
    if url in _pages:
        return _pages[url]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-GB,en"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            status = getattr(r, "status", 200)
            charset = r.headers.get_content_charset() or "utf-8"
            out = (status, page_text(r.read().decode(charset, "replace")), None)
    except urllib.error.HTTPError as e:
        out = (e.code, None, f"HTTP {e.code}")
    except Exception as e:  # timeouts, DNS, TLS, proxy refusals
        out = (None, None, f"{type(e).__name__}: {e}")
    _pages[url] = out
    return out


def best_similarity(page: str, quote: str) -> float:
    """Best match of the quote against same-sized windows of the page."""
    n = len(quote)
    if n == 0 or not page:
        return 0.0
    if len(page) <= n:
        return difflib.SequenceMatcher(None, page, quote).ratio()
    step = max(1, n // 4)
    candidates = []
    for start in range(0, len(page) - n + step, step):
        window = page[start:start + n + n // 5]
        sm = difflib.SequenceMatcher(None, window, quote, autojunk=False)
        if sm.real_quick_ratio() >= NEAR_THRESHOLD and sm.quick_ratio() >= NEAR_THRESHOLD:
            candidates.append(sm)
    return max((sm.ratio() for sm in candidates), default=0.0)


def check(url: str, quote: str) -> dict:
    if not allowed_by_robots(url):
        return {"result": "blocked", "score": None, "http_status": None,
                "note": "robots.txt disallows this page for bots; do not fetch it another way"}
    status, text, err = fetch(url)
    if text is None:
        return {"result": "fetch-failed", "score": None, "http_status": status, "note": err}
    q = normalise(quote)
    if q in text:
        return {"result": "exact", "score": 1.0, "http_status": status, "note": None}
    if len(text) < THIN_PAGE_CHARS:
        return {"result": "thin-page", "score": None, "http_status": status,
                "note": f"only {len(text)} characters of text; page is probably built by JavaScript"}
    score = round(best_similarity(text, q), 3)
    if score >= NEAR_THRESHOLD:
        return {"result": "near", "score": score, "http_status": status, "note": None}
    return {"result": "missing", "score": score, "http_status": status, "note": None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--candidate", help="check every evidence item in this candidate file")
    g.add_argument("--url", help="check one URL (with --quote)")
    ap.add_argument("--quote")
    args = ap.parse_args(argv)

    if args.url:
        if not args.quote:
            ap.error("--url needs --quote")
        items = [{"url": args.url, "quote": args.quote, "fields": []}]
    else:
        with open(args.candidate, encoding="utf-8") as fh:
            items = json.load(fh)["evidence"]

    ok = True
    for i, ev in enumerate(items):
        res = {"index": i, "url": ev["url"], "fields": ev.get("fields", []), **check(ev["url"], ev["quote"])}
        ok &= res["result"] in ("exact", "near")
        print(json.dumps(res, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
