"""scripts/budget.py must hold every scout to Fred's hard limits: 20 pages per website, 5 web searches,
150 pages in all, with the two nights scouts sharing one allowance per website."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import budget  # noqa: E402
import check_quote  # noqa: E402
import page_text  # noqa: E402

DATE = "2026-10-14"
FIX = REPO / "tests/fixtures"


@pytest.fixture(autouse=True)
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(budget, "BUDGET_DIR", tmp_path / ".budget")
    for cache in (check_quote._robots, check_quote._per_domain, check_quote._pages):
        cache.clear()
    check_quote._slowed.clear()
    yield
    check_quote.use_budget(None)


def read(agent, url):
    return budget.charge_page(agent, url, DATE)


# ------------------------------------------------------------- pages

def test_twenty_pages_per_website_then_refused():
    for i in range(20):
        assert read("arts", f"https://www.example.org/page/{i}") is None
    reason = read("arts", "https://example.org/page/20")  # www. or not, it's the same website
    assert reason and "limit is 20" in reason
    assert read("arts", "https://another.example.com/") is None  # other sites are unaffected


def test_each_scout_has_its_own_allowance():
    for i in range(20):
        assert read("arts", f"https://venue.example/{i}") is None
    assert read("community", "https://venue.example/x") is None


def test_the_two_nights_scouts_share_one_allowance_per_website():
    for i in range(12):
        assert read("nights-clubs", f"https://ma.to/venue/{i}") is None
    for i in range(8):
        assert read("nights-gigs", f"https://ma.to/venue/g{i}") is None
    assert "nights-clubs and nights-gigs" in read("nights-gigs", "https://ma.to/venue/more")
    assert read("nights-clubs", "https://ma.to/venue/more") is not None


def test_dice_is_split_fourteen_and_six():
    for i in range(14):
        assert read("nights-clubs", f"https://dice.fm/event/{i}") is None
    assert "14 pages on dice.fm" in read("nights-clubs", "https://dice.fm/event/14")
    for i in range(6):
        assert read("nights-gigs", f"https://dice.fm/event/g{i}") is None
    assert "6 pages on dice.fm" in read("nights-gigs", "https://dice.fm/event/g6")


def test_a_refused_page_is_not_counted():
    for i in range(20):
        read("arts", f"https://venue.example/{i}")
    for _ in range(3):
        read("arts", "https://venue.example/again")
    assert budget.usage(DATE, "arts")["arts"]["pages"] == 20


def test_one_hundred_and_fifty_pages_in_all():
    for i in range(150):
        assert read("community", f"https://site{i // 20}.example/{i}") is None
    assert "limit is 150" in read("community", "https://fresh.example/")


def test_agent_names_are_checked():
    with pytest.raises(ValueError):
        read("Nights Clubs!", "https://example.org/")


# ------------------------------------------------------------- searches

def test_five_web_searches_then_refused(capsys):
    for i in range(1, 6):
        assert budget.main(["search", "--as", "food-drink", "--date", DATE, f"supper club {i}"]) == 0
        assert f"OK search {i} of 5" in capsys.readouterr().out
    assert budget.main(["search", "--as", "food-drink", "--date", DATE, "one more"]) == 2
    assert "REFUSED 5 of 5" in capsys.readouterr().out
    assert budget.main(["search", "--as", "arts", "--date", DATE, "a different scout"]) == 0


def test_usage_reports_what_was_used(capsys):
    read("nights-gigs", "https://dice.fm/venue/a")
    read("nights-gigs", "https://www.troxy.co.uk/whats-on")
    budget.charge_search("nights-gigs", "Dalston jazz", DATE)
    assert budget.main(["usage", "--date", DATE]) == 0
    out = capsys.readouterr().out
    assert "nights-gigs: 2 pages" in out and "dice.fm 1" in out and "1 of 5 web searches" in out


# ------------------------------------------------------------- the readers enforce it

def test_check_quote_charges_new_pages_and_reuses_cached_ones(monkeypatch):
    calls = []
    real = check_quote._opener.open

    def counting_open(req, timeout=None):
        calls.append(req.full_url)
        return real(req, timeout=timeout)

    monkeypatch.setattr(check_quote._opener, "open", counting_open)
    page = (FIX / "event_page.html").as_uri()
    check_quote.use_budget("arts", DATE)
    assert check_quote.check(page, "Disco and house all night with DJ Example")["result"] == "exact"
    check_quote._pages.clear()  # a new process (the scout's self-check) ...
    assert check_quote.check(page, "Disco and house all night with DJ Example")["result"] == "exact"
    assert len(calls) == 1  # ... reads the run's cache, not the site
    assert budget.usage(DATE, "arts")["arts"]["pages"] == 1


def test_check_quote_refuses_over_budget():
    for i in range(20):
        read("arts", f"https://venue.example/{i}")
    check_quote.use_budget("arts", DATE)
    res = check_quote.fetch("https://venue.example/one-too-many")
    assert res["result"] == "rate-limited" and "budget" in res["error"]


def test_verifier_never_uses_the_scouts_cache(monkeypatch):
    page = (FIX / "event_page.html").as_uri()
    budget.cache_put("pages", page, {"status": 200, "final_url": page, "text": "planted text", "readable": "planted",
                                      "error": None}, DATE)
    check_quote.use_budget(None)
    assert check_quote.check(page, "planted text")["result"] != "exact"


def test_page_text_says_refused_when_over_budget(capsys):
    for i in range(20):
        read("community", f"https://venue.example/{i}")
    assert page_text.main(["--as", "community", "--run-date", DATE, "https://venue.example/more"]) == 2
    assert capsys.readouterr().out.startswith("REFUSED budget:")
