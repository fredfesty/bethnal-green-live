"""scripts/budget.py must hold every scout to Fred's hard limits: 20 pages per website, 5 web searches,
150 pages in all, with the two nights scouts sharing one allowance per website."""
import http.server
import json
import sys
import threading
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
    monkeypatch.setattr(budget, "run_date", lambda: DATE)  # so the command-line tools use the same ledger
    real_exists = budget.member_exists
    monkeypatch.setattr(budget, "member_exists", lambda kind, ident: not ident.startswith("no-such"))
    monkeypatch.setattr(budget, "_real_member_exists", real_exists, raising=False)
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
    assert "its 12 pages on ma.to" in read("nights-clubs", "https://ma.to/venue/13")  # can't starve the other
    for i in range(8):
        assert read("nights-gigs", f"https://ma.to/venue/g{i}") is None
    assert "nights-clubs and nights-gigs" in read("nights-gigs", "https://ma.to/venue/more")


def test_one_website_however_its_address_is_written():
    for i, host in enumerate(["dice.fm", "www.dice.fm", "dice.fm.", "shop.dice.fm"] * 5):
        assert read("arts", f"https://{host}/p/{i}") is None
    assert read("arts", "https://WWW.DICE.FM/one-more") is not None
    assert budget.site_of("https://events.towerhamlets.gov.uk/x") == "towerhamlets.gov.uk"
    assert budget.site_of("https://www.eventbrite.co.uk/e/1") == budget.site_of("https://eventbrite.com/e/2")


def test_only_known_names_get_an_allowance():
    for name in ("nights-club", "nights-music", "Arts", "verifier2"):
        with pytest.raises(ValueError):
            read(name, "https://example.org/")


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


def test_a_site_that_said_go_away_is_left_alone_all_run():
    budget.mark_slowed("arts", "https://www.richmix.org.uk/events", 403, DATE)
    assert "403 or 429" in read("community", "https://richmix.org.uk/whats-on")


def test_page_command_counts_other_reads(capsys):
    assert budget.main(["page", "--as", "verifier", "https://dice.fm/event/1"]) == 0
    assert budget.usage(DATE, "verifier")["verifier"]["pages"] == 1
    assert budget.main(["page", "--as", "nobody", "https://dice.fm/event/1"]) == 2


# ------------------------------------------------------------- searches

def test_five_web_searches_then_refused(capsys):
    for i in range(1, 6):
        assert budget.main(["search", "--as", "food-drink", f"supper club {i}"]) == 0
        assert f"OK search {i} of 5" in capsys.readouterr().out
    assert budget.main(["search", "--as", "food-drink", "one more"]) == 2
    assert "REFUSED 5 of 5" in capsys.readouterr().out
    assert budget.main(["search", "--as", "arts", "a different scout"]) == 0


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


@pytest.mark.parametrize("who", [None, "verifier"])
def test_verifier_never_uses_the_scouts_cache(who):
    page = (FIX / "event_page.html").as_uri()
    budget.cache_put("pages", page, {"status": 200, "final_url": page, "text": "planted text", "readable": "planted",
                                      "error": None}, DATE)
    check_quote.use_budget(who)
    assert check_quote.check(page, "planted text")["result"] == "missing"
    assert check_quote.check(page, "Disco and house all night with DJ Example")["result"] == "exact"
    if who:  # counted, though not cached
        assert budget.usage(DATE, who)[who]["pages"] == 1
        assert budget.cache_get("pages", page, DATE)["text"] == "planted text"


def test_failed_reads_are_not_cached():
    check_quote.use_budget("arts", DATE)
    missing = (FIX / "no_such_page.html").as_uri()
    assert check_quote.fetch(missing)["text"] is None
    assert budget.cache_get("pages", missing, DATE) is None


def test_a_redirect_to_another_website_is_counted_too():
    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/robots.txt":
                self.send_response(404)
                self.end_headers()
                return
            if self.path == "/landing":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<p>landed</p>")
                return
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/landing")
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Redirect)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        check_quote.use_budget("arts", DATE)
        check_quote.fetch(f"http://localhost:{srv.server_port}/start")
    finally:
        srv.shutdown()
        srv.server_close()
    assert budget.usage(DATE, "arts")["arts"]["sites"] == {"localhost": 1, "127.0.0.1": 1}


def test_page_text_says_refused_when_over_budget(capsys):
    for i in range(20):
        read("community", f"https://venue.example/{i}")
    assert page_text.main(["--as", "community", "https://venue.example/more"]) == 2
    assert capsys.readouterr().out.startswith("REFUSED budget:")


def test_verifier_pays_once_per_page_and_scouts_cannot_starve_it():
    for _ in range(3):  # the same page checked at three steps
        assert read("verifier", "https://dice.fm/event/1") is None
    assert budget.usage(DATE, "verifier")["verifier"]["pages"] == 1
    for i in range(19):
        assert read("verifier", f"https://dice.fm/event/n{i}") is None
    assert read("verifier", "https://dice.fm/event/one-too-many") is not None
    assert read("verifier", "https://dice.fm/event/1") is None  # an already counted page stays readable


def test_a_real_403_is_remembered_for_the_run(monkeypatch):
    import urllib.error

    def refuse(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(check_quote._opener, "open", refuse)
    check_quote.use_budget("arts", DATE)
    assert check_quote.fetch((FIX / "event_page.html").as_uri())["status"] == 403
    assert any(r["kind"] == "slowed" for r in budget._ledger(DATE))


def test_a_ledger_that_cannot_be_locked_refuses(monkeypatch):
    def broken(date):
        raise OSError("locked by another reader")
    monkeypatch.setattr(budget, "_locked", broken)
    assert "ledger is unavailable" in read("arts", "https://example.org/")


# ------------------------------------------------------------- storytellers, counted as teams

def test_storytellers_are_named_per_event_or_venue():
    assert read("event-storyteller/2026-10-16-sebright-arms-cowz", "https://example.org/a") is None
    assert read("venue-storyteller/oxford-house", "https://example.org/b") is None
    for bad in ("event-storyteller", "event-storyteller/", "event-storyteller/Bad Id", "story-teller/x"):
        with pytest.raises(ValueError):
            read(bad, "https://example.org/")


def test_storytellers_share_twenty_pages_per_website_as_a_team():
    for n in range(10):  # ten storytellers, two Time Out pages each
        for i in range(2):
            assert read(f"event-storyteller/event-{n}", f"https://www.timeout.com/{n}/{i}") is None
    assert "the event-storytellers have read 20" in read("event-storyteller/event-10", "https://www.timeout.com/x")
    # the Sunday venue storytellers are a different team
    assert read("venue-storyteller/oxford-house", "https://www.timeout.com/x") is None


def test_one_storyteller_cannot_take_the_whole_team_allowance():
    for i in range(12):
        assert read("event-storyteller/a", f"https://dice.fm/event/{i}") is None
    assert "its 12 pages on dice.fm" in read("event-storyteller/a", "https://dice.fm/event/12")
    assert read("event-storyteller/b", "https://dice.fm/event/b") is None


@pytest.mark.parametrize("who, pages, searches", [("event-storyteller/e1", 25, 5), ("venue-storyteller/v1", 30, 8)])
def test_each_storyteller_has_its_own_caps(who, pages, searches, capsys):
    for i in range(pages):
        assert read(who, f"https://site{i % 3}.example/{i}") is None
    assert f"limit is {pages}" in read(who, "https://fresh.example/")
    for i in range(searches):
        assert budget.main(["search", "--as", who, f"query {i}"]) == 0
    assert budget.main(["search", "--as", who, "one more"]) == 2
    assert f"REFUSED {searches} of {searches}" in capsys.readouterr().out


def test_storytellers_reuse_each_others_pages(monkeypatch):
    calls = []
    real = check_quote._opener.open
    monkeypatch.setattr(check_quote._opener, "open", lambda req, timeout=None: (calls.append(1), real(req, timeout=timeout))[1])
    page = (FIX / "event_page.html").as_uri()
    check_quote.use_budget("event-storyteller/a", DATE)
    check_quote.fetch(page)
    check_quote._pages.clear()
    check_quote.use_budget("event-storyteller/b", DATE)
    assert check_quote.fetch(page)["text"]
    assert len(calls) == 1


def test_storyteller_names_must_be_real_and_exact():
    real = budget._real_member_exists
    event = next((REPO / "data/events").glob("*/*.json")).stem
    venue = next((REPO / "data/venues").glob("*.json")).stem
    assert real("event-storyteller", event) and real("venue-storyteller", venue)
    assert not real("event-storyteller", event + "-typo") and not real("venue-storyteller", "no-such-venue")
    for bad in ("event-storyteller/no-such-event", "event-storyteller/abc\n", "Event-Storyteller/abc",
                "event-storyteller/ABC"):
        with pytest.raises(ValueError):
            read(bad, "https://example.org/")


def test_a_storyteller_team_has_a_search_cap_in_all():
    for n in range(10):
        for i in range(5):
            assert budget.charge_search(f"event-storyteller/e{n}", f"q{i}", DATE)[0]
    assert budget.charge_search("event-storyteller/e10", "one more", DATE)[0] is False
    assert budget.charge_search("venue-storyteller/v1", "other team", DATE)[0]


def test_allowances_start_again_each_run_date():
    for i in range(20):
        read("event-storyteller/e1" if i < 12 else "event-storyteller/e2", f"https://www.timeout.com/{i}")
    assert read("event-storyteller/e3", "https://www.timeout.com/x") is not None
    assert budget.charge_page("event-storyteller/e3", "https://www.timeout.com/x", "2026-10-15") is None


def test_only_story_quotes_are_rechecked(tmp_path, capsys):
    page = (FIX / "event_page.html").as_uri()
    profile = tmp_path / "v.json"
    profile.write_text(json.dumps({"evidence": [
        {"url": page, "quote": "Disco and house all night with DJ Example", "fields": ["story.vibe"]},
        {"url": "https://old.example/never-fetched", "quote": "an older profile quote", "fields": ["address"]}]}))
    assert check_quote.main(["--only-story", "--file", str(profile)]) == 0
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines()]
    assert [l["index"] for l in lines] == [0] and lines[0]["result"] == "exact"
