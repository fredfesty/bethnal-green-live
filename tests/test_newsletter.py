"""The newsletter checks catch what they exist for, and the renderer shows only checked facts."""
import copy
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import newsletter  # noqa: E402
import validate  # noqa: E402

EX_ISSUE = REPO / "docs/examples/newsletter-issue.json"
EX_EVENT = REPO / "docs/examples/event.json"
TODAY = dt.date(2026, 10, 28)


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validators():
    return validate.load_validators()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(validate, "ROOT", tmp_path)
    monkeypatch.setattr(newsletter, "ROOT", tmp_path)
    ev = tmp_path / "data/events/2026-10/2026-10-30-bgwmc-example-night.json"
    ev.parent.mkdir(parents=True)
    shutil.copy(EX_EVENT, ev)
    (tmp_path / "data/venues").mkdir(parents=True)
    (tmp_path / "data/newsletter/issues").mkdir(parents=True)
    return tmp_path


def errors(data, validators, today=TODAY):
    errs = validate.schema_errors(validators["newsletter"], data)
    return errs or validate.check_issue(Path(f"{data['id']}.json"), data, today)


def has(errs, text):
    return any(text in e for e in errs)


def blurb(d, text):
    d["sections"][0]["items"][0]["blurb"] = text


def test_example_issue_passes(repo, validators):
    assert errors(load(EX_ISSUE), validators) == []


@pytest.mark.parametrize("mutate, expected", [
    (lambda d: blurb(d, "Doors at 10pm, so no rush."), "isn't a checked start or end time"),
    (lambda d: blurb(d, "Tickets are £5 if you're quick."), "which no checked price says"),
    (lambda d: blurb(d, "A good Sunday night out at the club."), "it's on a Friday"),
    (lambda d: blurb(d, "Free entry, so just turn up and dance."), "checked price isn't free"),
    (lambda d: blurb(d, "Early bird £8, general admission £12, only a few left."), "copies a source word for word"),
    (lambda d: d["sections"][0]["items"][0].update(event_id="2026-10-31-bgwmc-nothing"), "no published event"),
    (lambda d: d.update(covers={"from": "2026-11-05", "to": "2026-11-11"}, id="2026-11-05"), "outside this issue's week"),
    (lambda d: d["sections"][0].update(kind="worth-the-trip", layout="cards"), "outer-zone events"),
    (lambda d: d["sections"][0].update(kind="on-repeat", layout="compact"), "regular nights"),
    (lambda d: d["sections"][0].update(layout="compact"), "one event, laid out as 'hero'"),
    (lambda d: d["sections"].append(copy.deepcopy(d["sections"][0])), "already in this issue"),
    (lambda d: d["intro"]["paragraphs"].append("I went last week and loved every minute of it."), "first-hand experience"),
    (lambda d: d["intro"]["paragraphs"].append("Tickets are only £3 on the door, which is a steal."), "no checked price"),
    (lambda d: d["intro"].update(used_notes="data/newsletter/notes/2026-10-29.md"), "doesn't exist"),
    (lambda d: d.update(id="2026-10-30"), "on or before the first day"),
    (lambda d: d["intro"].update(signed="The team"), "format: intro"),
])
def test_issue_rules(repo, validators, mutate, expected):
    d = load(EX_ISSUE)
    mutate(d)
    errs = errors(d, validators)
    assert has(errs, expected), errs


def test_free_and_cheap_means_under_a_tenner(repo, validators):
    d = load(EX_ISSUE)
    d["sections"][0].update(kind="free-and-cheap", layout="list")
    assert not has(errors(d, validators), "free or under £10")  # from £8
    ev = repo / "data/events/2026-10/2026-10-30-bgwmc-example-night.json"
    e = load(ev)
    e["price"].update(min_gbp=12, max_gbp=15, notes=None)
    ev.write_text(json.dumps(e), encoding="utf-8")
    blurb(d, None)
    assert has(errors(d, validators), "free or under £10")


def test_names_may_be_repeated(repo, validators):
    d = load(EX_ISSUE)
    blurb(d, "EXAMPLE NIGHT at Bethnal Green Working Men's Club, with DJ Example.")
    assert errors(d, validators) == []


def test_notes_allow_first_hand(repo, validators):
    notes = repo / "data/newsletter/notes/2026-10-29.md"
    notes.parent.mkdir(parents=True)
    notes.write_text("- I went to the jazz night last week and loved it\n", encoding="utf-8")
    d = load(EX_ISSUE)
    d["intro"]["paragraphs"].append("I went to the jazz night last week and it was lovely.")
    d["intro"]["used_notes"] = "data/newsletter/notes/2026-10-29.md"
    assert errors(d, validators) == []


def test_sold_out_or_under_review_is_refused_only_when_fresh(repo, validators):
    ev = repo / "data/events/2026-10/2026-10-30-bgwmc-example-night.json"
    e = load(ev)
    e["status"] = "sold-out"
    ev.write_text(json.dumps(e), encoding="utf-8")
    d = load(EX_ISSUE)
    assert has(errors(d, validators), "is sold-out")
    # An issue that has gone out isn't failed later because tickets sold out (CI runs without --window).
    assert errors(d, validators, today=None) == []


def test_render_uses_checked_facts(repo):
    d = load(EX_ISSUE)
    events = newsletter.load_events(repo)
    html = newsletter.render_html(d, events, "https://example.org/")
    md = newsletter.render_markdown(d, events, "https://example.org/")
    for out in (html, md):
        assert "Fri 30 Oct · 9pm–3am · Bethnal Green Working Men&#x27;s Club · £8–£12".replace("&#x27;", "'" if out is md else "&#x27;") in out
        assert "Fred" in out
        assert "https://example.org/events/2026-10-30-bgwmc-example-night.html" in out
    assert "Last few tickets" in html
    assert newsletter.esc(d["preheader"]) in html


def test_render_skips_missing_events(repo):
    d = load(EX_ISSUE)
    d["sections"].append({"kind": "quick-hits", "heading": "More", "layout": "compact",
                          "items": [{"event_id": "2026-11-01-nowhere-gone"}]})
    md = newsletter.render_markdown(d, newsletter.load_events(repo))
    assert "## More" not in md


def test_week_lists_only_usable_events(repo):
    w = newsletter.week(dt.date(2026, 10, 29), repo)
    assert [e["id"] for e in w["this_week"]] == ["2026-10-30-bgwmc-example-night"]
    assert w["issue_number"] == 1
    assert w["covers"]["label"] == "29 October – 4 November"
    ev = repo / "data/events/2026-10/2026-10-30-bgwmc-example-night.json"
    e = load(ev)
    e["needs_review"] = {"since": "2026-10-27T10:00:00Z", "reason": "page gone"}
    ev.write_text(json.dumps(e), encoding="utf-8")
    w = newsletter.week(dt.date(2026, 10, 29), repo)
    assert w["this_week"] == [] and w["left_out"][0]["why"] == "under review"


@pytest.mark.parametrize("starts, expected", [
    ("2026-10-30T21:00:00+00:00", "9pm"), ("2026-10-16T19:30:00+01:00", "7:30pm"),
    ("2026-10-17T00:00:00+01:00", "midnight"), ("2026-10-17T12:00:00+01:00", "noon"),
])
def test_clock(starts, expected):
    assert newsletter.clock(starts) == expected


def test_runs_count_for_every_week_they_are_on(repo, validators):
    ev = repo / "data/events/2026-10/2026-10-30-bgwmc-example-night.json"
    e = load(ev)
    e.update(category="arts", subcategory="exhibition", ends_at="2026-11-20", starts_at="2026-10-30",
             run_schedule="Tue–Sun 11am–6pm")
    ev.write_text(json.dumps(e), encoding="utf-8")
    d = load(EX_ISSUE)
    d.update(id="2026-11-05", covers={"from": "2026-11-05", "to": "2026-11-11"})
    d["intro"]["paragraphs"] = ["A quiet week, but a good one for a slow afternoon at an exhibition."]
    d["sections"][0]["items"][0]["blurb"] = "Open until 6pm most days, so it works for a Saturday afternoon too."
    assert errors(d, validators, today=dt.date(2026, 11, 4)) == []
    assert "Until Fri 20 Nov (Tue–Sun 11am–6pm)" in newsletter.render_markdown(d, newsletter.load_events(repo))
    d["sections"][0].update(kind="food-and-drink")
    assert has(errors(d, validators, today=dt.date(2026, 11, 4)), "food-and-drink is for food-drink events")


def test_health_and_wellness_section_takes_only_wellness_events(repo, validators):
    d = load(EX_ISSUE)
    d["sections"][0].update(kind="health-and-wellness", layout="list")
    blurb(d, None)
    assert has(errors(d, validators), "health-and-wellness is for health-wellness events")
    ev = repo / "data/events/2026-10/2026-10-30-bgwmc-example-night.json"
    e = load(ev)
    e.update(category="health-wellness", subcategory="sound-bath", genres=[], lineup=[])
    ev.write_text(json.dumps(e), encoding="utf-8")
    assert not has(errors(d, validators), "is for health-wellness events")
    assert newsletter.kind_label(e) == "Sound bath"


def test_test_recipients_keeps_only_addresses():
    assert newsletter.test_recipients(" a@x.com, b@y.co.uk ;nope, ") == ["a@x.com", "b@y.co.uk"]
    assert newsletter.test_recipients(None) == []


def test_buttondown_test_copy_goes_only_to_the_test_list(repo, monkeypatch, capsys):
    issue_path = repo / "data/newsletter/issues/2026-10-29.json"
    issue_path.write_text(EX_ISSUE.read_text(encoding="utf-8"), encoding="utf-8")
    calls = []

    class Resp:
        def __init__(self, body):
            self.body = body

        def read(self):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        calls.append((req.full_url, json.loads(req.data.decode())))
        return Resp(b'{"id": "em_123"}' if req.full_url.endswith("/emails") else b"{}")

    monkeypatch.setattr(newsletter.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("BUTTONDOWN_API_KEY", "k")
    assert newsletter.main(["buttondown-draft", str(issue_path), "--test-to", "fred@example.com"]) == 0
    assert calls[0][1]["status"] == "draft"
    assert calls[1] == ("https://api.buttondown.com/v1/emails/em_123/send-draft", {"recipients": ["fred@example.com"]})
    assert len(calls) == 2

    calls.clear()
    monkeypatch.delenv("NEWSLETTER_TEST_TO", raising=False)
    assert newsletter.main(["buttondown-draft", str(issue_path)]) == 0
    assert len(calls) == 1  # no test list: draft only, nothing emailed
