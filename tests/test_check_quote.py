"""scripts/check_quote.py should find real quotes, tolerate formatting, and refuse fakes."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import check_quote  # noqa: E402

PAGE = (REPO / "tests/fixtures/event_page.html").as_uri()
THIN = (REPO / "tests/fixtures/thin_page.html").as_uri()


@pytest.mark.parametrize("quote", [
    "Fri 30 Oct 2026, 9:00 PM – 3:00 AM",                       # en dash vs &ndash;, nbsp
    "Disco and house all night with DJ Example",                # text across <strong>
    "It's strictly 18+.",                                       # straight vs curly apostrophe
    "GENERAL ADMISSION £12 — ONLY A FEW LEFT",                  # case, em dash
    '"startDate": "2026-10-30T21:00:00+00:00"',                 # JSON-LD event data counts
])
def test_exact_matches(quote):
    assert check_quote.check(PAGE, quote)["result"] == "exact"


def test_near_match_on_small_differences():
    res = check_quote.check(PAGE, "Disco and house all night with DJ Example plus a live set by Example Live Act")
    assert res["result"] == "near" and res["score"] >= 0.85


@pytest.mark.parametrize("quote", [
    "Free entry before 11pm",                                   # invented
    "Sat 31 Oct 2026, 9:00 PM",                                 # wrong date
    "SECRET SCRIPT TEXT",                                       # only inside a normal <script>
    "SECRET STYLE TEXT",                                        # only inside <style>
])
def test_fakes_are_missing(quote):
    assert check_quote.check(PAGE, quote)["result"] == "missing"


def test_thin_page_is_flagged():
    assert check_quote.check(THIN, "Some event title")["result"] == "thin-page"


def test_unreachable_page():
    res = check_quote.check((REPO / "tests/fixtures/does_not_exist.html").as_uri(), "anything")
    assert res["result"] == "fetch-failed"


def test_normalise():
    assert check_quote.normalise("It’s  9:00 PM – 3AM") == "it's 9:00 pm - 3am"
