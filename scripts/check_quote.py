#!/usr/bin/env python3
"""Check that evidence quotes really appear on their pages, and say the same thing. Used by the verifier.

The verifier must never take a scout's word for it. This script re-fetches each evidence URL
(respecting robots.txt and our source policy), turns the page into plain text, finds the quote,
and returns the passage it actually matched so the verifier judges the record against the page,
not against the scout's copy.

Usage
  python scripts/check_quote.py --file data/candidates/nights-music/2026-10-13/a.json [b.json ...]
  python scripts/check_quote.py --url https://example.com/event --quote "Fri 16 Oct, 10pm"

Works on any JSON file with an 'evidence' list (candidates and events).

Output: one JSON object per evidence item, on its own line:
  {"file", "index", "url", "final_url", "fields", "result", "score", "http_status",
   "matched_text", "title_nearby", "note"}

Results
  exact          the quote is on the page as whole words (after normalising spaces, quotes, dashes, case)
  near           a passage at least 85% similar is on the page AND every number, day and month in the
                 quote appears in that passage. Judge the record against matched_text, not the quote.
  near-mismatch  a similar passage exists but a number, day or month differs. Treat as NOT confirmed.
  missing        the page loaded but the quote is not there
  too-short      the quote is too short to prove anything (under 8 characters of text)
  thin-page      the page has almost no text (probably built by JavaScript); read it another way
  forbidden      the site is on our never-use list (Resident Advisor, Instagram, closed venues' domains)
  blocked        robots.txt disallows this page for us or for Claude's crawlers; do not fetch it another way
  rate-limited   we already hit our per-site limit, or the site told us to slow down (403/429) this run
  fetch-failed   the page could not be loaded; http_status / note say why

title_nearby (only for quotes backing date, time, price or status without naming the title):
  true if the event's title appears within 400 characters of the match, false if not, null if not
  applicable. On a page listing several events, false means the quote may belong to another event.

Exit code 0 when every quote is exact or near, 1 otherwise.
"""
from __future__ import annotations

import argparse
import codecs
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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import policy  # noqa: E402

USER_AGENT = "BethnalGreenLiveBot/0.1 (+https://github.com/fredfesty/bethnal-green-live)"
ROBOTS_AGENTS = ["BethnalGreenLiveBot", "ClaudeBot", "Claude-User", "anthropic-ai"]
TIMEOUT = 20
MAX_BYTES = 5_000_000
NEAR_THRESHOLD = 0.85
THIN_PAGE_CHARS = 400
MIN_QUOTE_CHARS = 8
TITLE_RADIUS = 400
FACT_FIELDS_NEEDING_TITLE = {"starts_at", "ends_at", "price", "status", "age_restriction", "lineup"}

_TRANSLATE = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-",
    " ": " ", " ": " ", " ": " ",
    "…": "...",
})

DAYS = "mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
MONTHS = ("jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|"
          "august|september|october|november|december")
CRITICAL = re.compile(rf"\d+(?:[.:]\d+)*|\b(?:{DAYS}|{MONTHS}|am|pm|free|sold out|cancelled|postponed)\b")


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(text)).translate(_TRANSLATE).lower()
    text = text.replace("\\/", "/")
    text = re.sub(r"\s+", " ", text)
    return re.sub(r" ([,.;:!?)])", r"\1", text).strip()  # "9pm , Fri" and "9pm, Fri" match


def critical_tokens(text: str) -> list[str]:
    return CRITICAL.findall(text)


# ---------------------------------------------------------------- page text

class _TextExtractor(HTMLParser):
    """Visible text plus JSON-LD event data. Drops scripts, styles, struck-through text and hidden elements."""

    SKIP = {"script", "style", "noscript", "template", "svg", "del", "s", "strike"}
    BLOCK = {"p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6",
             "section", "article", "header", "footer", "dd", "dt", "ul", "ol", "table", "nav", "main"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self._in_jsonld = False
        self._jsonld_buf: list[str] = []
        self._hide_tag: str | None = None
        self._hide_nest = 0

    @staticmethod
    def _hidden(attrs: dict) -> bool:
        style = (attrs.get("style") or "").replace(" ", "").lower()
        return "hidden" in attrs or attrs.get("aria-hidden") == "true" or "display:none" in style or "visibility:hidden" in style

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self._hide_tag:
            if tag == self._hide_tag:
                self._hide_nest += 1
            return
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in_jsonld, self._jsonld_buf = True, []
            return
        if tag in self.SKIP:
            self._skip_depth += 1
        elif self._hidden(a) and tag not in ("br", "img", "input", "meta", "link", "hr"):
            self._hide_tag, self._hide_nest = tag, 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self._hide_tag:
            if tag == self._hide_tag:
                self._hide_nest -= 1
                if self._hide_nest == 0:
                    self._hide_tag = None
            return
        if tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            raw = "".join(self._jsonld_buf)
            self.parts.append(" " + raw + " ")
            try:  # also add the decoded values, so "&pound;8" or "£" in JSON-LD match "£8"
                self.parts.append(" " + " ".join(_json_strings(json.loads(raw))) + " ")
            except ValueError:
                pass
            return
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._hide_tag:
            return
        if self._in_jsonld:
            self._jsonld_buf.append(data)
        elif not self._skip_depth:
            self.parts.append(data)


def _json_strings(obj) -> list[str]:
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _json_strings(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in _json_strings(v)]
    return [str(obj)] if isinstance(obj, (str, int, float)) and not isinstance(obj, bool) else []


def readable_text(raw_html: str) -> str:
    """The page's visible text with its original wording and case, one block per line. Quote from this."""
    p = _TextExtractor()
    p.feed(raw_html)
    text = unicodedata.normalize("NFKC", "".join(p.parts)).replace("\u00a0", " ")
    lines = (re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.split("\n"))
    return "\n".join(l for l in lines if l)


def page_text(raw_html: str) -> str:
    p = _TextExtractor()
    p.feed(raw_html)
    return normalise(" ".join(p.parts))


def decode(body: bytes, header_charset: str | None) -> str:
    charset = header_charset
    if not charset:
        m = re.search(rb"""<meta[^>]+charset=["']?([A-Za-z0-9_\-]+)""", body[:4096], re.I)
        charset = m.group(1).decode("ascii") if m else "utf-8"
    try:
        codecs.lookup(charset)
    except LookupError:
        charset = "utf-8"
    return body.decode(charset, "replace")


# ---------------------------------------------------------------- fetching, politely

_robots: dict[str, urllib.robotparser.RobotFileParser | str] = {}
_per_domain: dict[str, int] = {}
_slowed: set[str] = set()
_pages: dict[str, dict] = {}
MAX_PER_DOMAIN = 20


def robots_verdict(url: str) -> str | None:
    """None if allowed, else a reason. RFC 9309: 4xx = allowed; 5xx or unreachable = disallowed."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return None
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                rp.parse(decode(r.read(500_000), r.headers.get_content_charset()).splitlines())
            _robots[base] = rp
        except urllib.error.HTTPError as e:
            _robots[base] = "allow-all" if 400 <= e.code < 500 and e.code != 429 else f"robots.txt answered HTTP {e.code}"
        except Exception as e:
            _robots[base] = f"robots.txt unreachable ({type(e).__name__})"
    rp = _robots[base]
    if rp == "allow-all":
        return None
    if isinstance(rp, str):
        return rp
    for agent in ROBOTS_AGENTS:
        if not rp.can_fetch(agent, url):
            return f"robots.txt disallows {agent}"
    return None


def fetch(url: str) -> dict:
    """{'status', 'text', 'final_url', 'error', 'result'?}. Cached per process."""
    if url in _pages:
        return _pages[url]
    host = policy.domain_of(url)
    if host in _slowed or _per_domain.get(host, 0) >= MAX_PER_DOMAIN:
        return {"result": "rate-limited", "status": None, "text": None, "final_url": None,
                "error": f"per-site limit reached for {host} this run"}
    _per_domain[host] = _per_domain.get(host, 0) + 1
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-GB,en"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read(MAX_BYTES + 1)
            note = "page truncated at 5 MB" if len(body) > MAX_BYTES else None
            html_doc = decode(body[:MAX_BYTES], r.headers.get_content_charset())
            out = {"status": getattr(r, "status", 200), "final_url": r.geturl(),
                   "text": page_text(html_doc), "readable": readable_text(html_doc), "error": note}
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            _slowed.add(host)
        out = {"status": e.code, "text": None, "final_url": None, "error": f"HTTP {e.code}"}
    except Exception as e:  # timeouts, DNS, TLS, proxy refusals, missing local files
        out = {"status": None, "text": None, "final_url": None, "error": f"{type(e).__name__}: {e}"}
    _pages[url] = out
    return out


# ---------------------------------------------------------------- matching

def find_exact(page: str, q: str) -> tuple[int, int] | None:
    m = re.search(r"(?<![a-z0-9])" + re.escape(q) + r"(?![a-z0-9])", page)
    return (m.start(), m.end()) if m else None


def best_window(page: str, q: str) -> tuple[float, int, int]:
    """Best-matching passage of about the quote's length: (similarity, start, end)."""
    n = len(q)
    if not page:
        return 0.0, 0, 0
    width = n + n // 2
    step = max(1, n // 4)
    best = (0.0, 0, 0)
    for start in range(0, max(1, len(page) - n // 2), step):
        window = page[start:start + width]
        sm = difflib.SequenceMatcher(None, q, window, autojunk=False)
        if sm.real_quick_ratio() < NEAR_THRESHOLD - 0.1 or sm.quick_ratio() < NEAR_THRESHOLD - 0.1:
            continue
        # trim the window to the part that actually lines up with the quote
        blocks = [b for b in sm.get_matching_blocks() if b.size]
        if not blocks:
            continue
        lo = start + blocks[0].b
        hi = start + blocks[-1].b + blocks[-1].size
        while lo > 0 and page[lo - 1].isalnum():  # never cut a word or number in half ("£1" inside "£12")
            lo -= 1
        while hi < len(page) and page[hi].isalnum():
            hi += 1
        score = difflib.SequenceMatcher(None, q, page[lo:hi], autojunk=False).ratio()
        if score > best[0]:
            best = (score, lo, hi)
    return best


def title_variants(title: str) -> list[str]:
    t = normalise(title)
    out = {t, re.sub(r"\s*\(.*?\)\s*", " ", t).strip(), re.split(r"\s[-:|]\s|:\s", t)[0].strip()}
    return [v for v in out if len(v) >= 4]


def title_is_near(page: str, span: tuple[int, int], title: str) -> bool:
    lo, hi = max(0, span[0] - TITLE_RADIUS), span[1] + TITLE_RADIUS
    nearby = page[lo:hi]
    return any(v in nearby for v in title_variants(title))


def check(url: str, quote: str, title: str | None = None, fields: list[str] | None = None) -> dict:
    base = {"final_url": None, "score": None, "http_status": None, "matched_text": None, "title_nearby": None, "note": None}
    if policy.is_forbidden(url):
        return {**base, "result": "forbidden", "note": "never-use site under our source policy"}
    q = normalise(quote)
    if len(re.sub(r"[^a-z0-9]", "", q)) < MIN_QUOTE_CHARS:
        return {**base, "result": "too-short", "note": "quote too short to prove anything"}
    reason = robots_verdict(url)
    if reason:
        return {**base, "result": "blocked", "note": reason + "; do not fetch it another way"}
    page = fetch(url)
    if page.get("result"):
        return {**base, "result": page["result"], "note": page["error"]}
    base.update(http_status=page["status"], final_url=page["final_url"], note=page["error"])
    if page["final_url"] and page["final_url"].rstrip("/") != url.rstrip("/"):
        base["note"] = f"redirected to {page['final_url']}" + (f"; {page['error']}" if page["error"] else "")
    text = page["text"]
    if text is None:
        return {**base, "result": "fetch-failed"}

    needs_title = bool(title) and fields is not None and "title" not in fields and bool(FACT_FIELDS_NEEDING_TITLE & set(fields))
    span = find_exact(text, q)
    if span:
        res = {**base, "result": "exact", "score": 1.0, "matched_text": text[span[0]:span[1]]}
    elif len(text) < THIN_PAGE_CHARS:
        return {**base, "result": "thin-page", "note": f"only {len(text)} characters of text; page is probably built by JavaScript"}
    else:
        score, lo, hi = best_window(text, q)
        span = (lo, hi)
        if score < NEAR_THRESHOLD:
            return {**base, "result": "missing", "score": round(score, 3)}
        passage = text[lo:hi]
        missing = [t for t in critical_tokens(q) if t not in critical_tokens(passage)]
        res = {**base, "score": round(score, 3), "matched_text": passage[:400]}
        if missing:
            res.update(result="near-mismatch", note=f"the page passage differs on: {', '.join(missing)}")
            return res
        res["result"] = "near"
    if needs_title:
        res["title_nearby"] = title_is_near(text, span, title)
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--file", "--candidate", nargs="+", dest="files", help="check every evidence item in these files")
    g.add_argument("--url", help="check one URL (with --quote)")
    ap.add_argument("--quote")
    ap.add_argument("--title", help="with --url: the event title, to report title_nearby")
    ap.add_argument("--max-per-domain", type=int, default=20)
    args = ap.parse_args(argv)
    globals()["MAX_PER_DOMAIN"] = args.max_per_domain

    jobs: list[tuple[str | None, int, dict, str | None]] = []
    if args.url:
        if not args.quote:
            ap.error("--url needs --quote")
        jobs.append((None, 0, {"url": args.url, "quote": args.quote, "fields": ["starts_at"] if args.title else []}, args.title))
    else:
        for f in args.files:
            try:
                data = json.loads(Path(f).read_text(encoding="utf-8-sig"))
                evidence = data["evidence"]
            except (OSError, ValueError, KeyError, TypeError) as e:
                print(json.dumps({"file": f, "result": "unreadable-file", "note": str(e)}))
                jobs.append((f, -1, {}, None))
                continue
            for i, ev in enumerate(evidence):
                jobs.append((f, i, ev, data.get("title")))

    ok = True
    for f, i, ev, title in jobs:
        if i < 0:
            ok = False
            continue
        res = {"file": f, "index": i, "url": ev["url"], "fields": ev.get("fields", []),
               **check(ev["url"], ev["quote"], title, ev.get("fields", []))}
        ok &= res["result"] in ("exact", "near")
        print(json.dumps(res, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
