"""scripts/check_quote.py should find real quotes, tolerate formatting, refuse fakes and wrong numbers,
and behave politely on the web."""
import http.server
import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import check_quote  # noqa: E402

FIX = REPO / "tests/fixtures"
PAGE = (FIX / "event_page.html").as_uri()
MULTI = (FIX / "multi_event.html").as_uri()
THIN = (FIX / "thin_page.html").as_uri()


@pytest.fixture(autouse=True)
def fresh_state():
    for cache in (check_quote._robots, check_quote._per_domain, check_quote._pages):
        cache.clear()
    check_quote._slowed.clear()


# ------------------------------------------------------------- matching

@pytest.mark.parametrize("quote", [
    "Fri 30 Oct 2026, 9:00 PM – 3:00 AM",                       # en dash vs &ndash;, nbsp
    "Disco and house all night with DJ Example",                # text across <strong>
    "It's strictly 18+.",                                       # straight vs curly apostrophe
    "GENERAL ADMISSION £12 — ONLY A FEW LEFT",                  # case, em dash
    '"startDate": "2026-10-30T21:00:00+00:00"',                 # JSON-LD event data counts
])
def test_exact_matches(quote):
    res = check_quote.check(PAGE, quote)
    assert res["result"] == "exact" and res["matched_text"]


def test_near_match_on_small_wording_differences():
    res = check_quote.check(PAGE, "Disco and house all night with DJ Example plus a live set by Example Live Act")
    assert res["result"] == "near" and res["score"] >= 0.85 and "live set from" in res["matched_text"]


@pytest.mark.parametrize("quote, result", [
    ("General admission £1", "near-mismatch"),                                 # £1 is not £12
    ("Early bird £9 General admission £12 — only a few left", "near-mismatch"),  # wrong price
    ("Sat 30 Oct 2026, 9:00 PM – 3:00 AM", "near-mismatch"),                    # wrong weekday
    ("Fri 30 Oct 2026, 10:00 PM – 3:00 AM", "near-mismatch"),                   # wrong time
    ("Free entry before 11pm tonight", "missing"),                              # invented
    ("SECRET SCRIPT TEXT", "missing"),                                          # only in a normal <script>
    ("SECRET STYLE TEXT", "missing"),                                           # only in <style>
])
def test_wrong_or_invented_quotes_are_not_confirmed(quote, result):
    assert check_quote.check(PAGE, quote)["result"] == result


@pytest.mark.parametrize("quote", ["   ", "abc", "£8 9pm"])
def test_too_short(quote):
    assert check_quote.check(PAGE, quote)["result"] == "too-short"


@pytest.mark.parametrize("quote", ["Was £20 earlier", "free entry for everyone all night", "secret guest"])
def test_struck_through_and_hidden_text_does_not_count(quote):
    assert check_quote.check(MULTI, quote)["result"] == "missing"


def test_title_nearby_on_a_multi_event_page():
    right = check_quote.check(MULTI, "Fri 30 Oct 2026, 9:00 PM – 3:00 AM", title="Night A: Disco Inferno", fields=["starts_at"])
    wrong = check_quote.check(MULTI, "Sat 31 Oct 2026, 10:00 PM – 2:00 AM", title="Night A: Disco Inferno", fields=["starts_at"])
    assert right["result"] == wrong["result"] == "exact"
    assert right["title_nearby"] is True and wrong["title_nearby"] is False
    # quotes that name the title themselves don't need the check
    assert check_quote.check(MULTI, "Night A: Disco Inferno", title="Night A: Disco Inferno", fields=["title"])["title_nearby"] is None


def test_thin_page_is_flagged():
    assert check_quote.check(THIN, "Some event title here")["result"] == "thin-page"


def test_unreachable_page():
    assert check_quote.check((FIX / "does_not_exist.html").as_uri(), "anything at all")["result"] == "fetch-failed"


@pytest.mark.parametrize("url", ["https://ra.co/events/123456", "https://www.instagram.com/p/abc/", "https://thepicklefactory.co.uk/"])
def test_forbidden_sites_are_never_fetched(url, monkeypatch):
    monkeypatch.setattr(check_quote, "fetch", lambda u: pytest.fail("must not fetch"))
    assert check_quote.check(url, "Some event title here")["result"] == "forbidden"


def test_normalise():
    assert check_quote.normalise("It’s  9:00 PM – 3AM") == "it's 9:00 pm - 3am"


def test_cp1252_page_without_header_charset():
    body = '<html><head><meta charset="windows-1252"></head><body><p>Tickets £8 on the door tonight</p></body></html>'
    text = check_quote.page_text(check_quote.decode(body.encode("cp1252"), None))
    assert "tickets £8 on the door tonight" in text


# ------------------------------------------------------------- politeness, over real HTTP

class _Site(http.server.BaseHTTPRequestHandler):
    robots: tuple[int, str] = (404, "")
    pages = {
        "/event": (200, "<p>" + "Night A: Disco Inferno. Fri 30 Oct 2026, 9:00 PM. " * 20 + "</p>"),
        "/slow": (429, "slow down"),
    }

    def do_GET(self):
        if self.path == "/robots.txt":
            code, body = self.robots
        elif self.path == "/old":
            self.send_response(301)
            self.send_header("Location", "/event")
            self.end_headers()
            return
        else:
            code, body = self.pages.get(self.path, (404, "not found"))
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *a):
        pass


def serve(robots):
    handler = type("H", (_Site,), {"robots": robots})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


QUOTE = "Fri 30 Oct 2026, 9:00 PM"


def test_robots_disallowing_claudebot_blocks_us_too():
    srv, base = serve((200, "User-agent: ClaudeBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"))
    try:
        assert check_quote.check(base + "/event", QUOTE)["result"] == "blocked"
    finally:
        srv.shutdown()


def test_robots_server_error_means_do_not_fetch():
    srv, base = serve((503, "down"))
    try:
        assert check_quote.check(base + "/event", QUOTE)["result"] == "blocked"
    finally:
        srv.shutdown()


def test_missing_robots_means_allowed_and_redirects_are_reported():
    srv, base = serve((404, ""))
    try:
        assert check_quote.check(base + "/event", QUOTE)["result"] == "exact"
        res = check_quote.check(base + "/old", QUOTE)
        assert res["final_url"].endswith("/event") and "redirected" in res["note"]
    finally:
        srv.shutdown()


def test_429_stops_further_fetches_to_that_site():
    srv, base = serve((404, ""))
    try:
        assert check_quote.check(base + "/slow", QUOTE)["result"] == "fetch-failed"
        assert check_quote.check(base + "/event", QUOTE)["result"] == "rate-limited"
    finally:
        srv.shutdown()


def test_per_site_limit(monkeypatch):
    monkeypatch.setattr(check_quote, "MAX_PER_DOMAIN", 1)
    srv, base = serve((404, ""))
    try:
        assert check_quote.check(base + "/event", QUOTE)["result"] == "exact"
        assert check_quote.check(base + "/old", QUOTE)["result"] == "rate-limited"
    finally:
        srv.shutdown()
