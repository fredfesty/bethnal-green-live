"""The longer venue description ('The story'): which venues are flagged as short, when the storyteller may
try them again (a week after a try, never daily), and the house rules on the story itself."""
import copy
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import validate  # noqa: E402
import venue_stories  # noqa: E402

EX_VENUE = REPO / "docs/examples/venue.json"
TODAY = dt.date(2026, 10, 15)


def profile(vid, chars=70, zone="core", **extra):
    return {"id": vid, "name": vid.title(), "zone": zone, "summary": "x" * chars, "music": {"styles": []},
            "crowd": None, "accessibility": {}, "cost": {}, **extra}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "data/venues").mkdir(parents=True)
    monkeypatch.setattr(venue_stories, "ROOT", tmp_path)
    return tmp_path


def write(root, p):
    (root / f"data/venues/{p['id']}.json").write_text(json.dumps(p), encoding="utf-8")


def test_lines_count_each_paragraph_at_page_width():
    p = profile("a", chars=71, crowd="y" * 10, story={"then": "z" * 140, "worth_knowing": ["w" * 20, "v" * 20],
                                                     "written_at": "2026-10-15T08:00:00Z"})
    assert venue_stories.description_lines(p) == 2 + 1 + 2 + 1 + 1


def test_short_venues_are_flagged_but_closed_or_doubtful_ones_are_not():
    assert venue_stories.is_flagged(profile("a", chars=70 * 14))
    assert not venue_stories.is_flagged(profile("a", chars=70 * 15))
    assert not venue_stories.is_flagged(profile("a", status="closed"))
    assert not venue_stories.is_flagged(profile("a", needs_review={"since": "x", "reason": "in doubt"}))


def test_nothing_found_waits_a_week(repo):
    tried = {"last_attempt": "2026-10-10", "outcome": "nothing-found", "attempts": 1, "next_check": "2026-10-17"}
    write(repo, profile("tried", story_research=tried))
    write(repo, profile("never"))
    t = venue_stories.todo(TODAY)
    assert [r["venue_id"] for r in t["research"]] == ["never"]
    assert t["waiting_for_weekly_retry"] == 1
    t = venue_stories.todo(dt.date(2026, 10, 17))
    assert [r["venue_id"] for r in t["research"]] == ["never", "tried"]
    assert t["research"][1]["attempts"] == 1


def test_never_tried_first_then_core_before_fringe_and_the_daily_cap(repo):
    write(repo, profile("fringe-one", zone="fringe"))
    for i in range(12):
        write(repo, profile(f"core-{i:02d}"))
    t = venue_stories.todo(TODAY, limit=10)
    ids = [r["venue_id"] for r in t["research"]]
    assert len(ids) == 10 and "fringe-one" not in ids
    assert t["left_for_later_days"] == 3


def test_written_but_cut_back_still_waits_a_week(repo):
    r = {"last_attempt": "2026-10-12", "outcome": "written", "attempts": 1, "next_check": None}
    write(repo, profile("cut", story_research=r))
    assert venue_stories.todo(TODAY)["research"] == []
    assert venue_stories.todo(dt.date(2026, 10, 19))["research"][0]["venue_id"] == "cut"


# ---------------------------------------------------------------- house rules on the story

@pytest.fixture(scope="module")
def validators():
    return validate.load_validators()


def errors(d, validators):
    errs = validate.schema_errors(validators["venues"], d)
    return errs or validate.CHECKS["venues"](Path(f"{d['id']}.json"), d, None)


def with_story(**story):
    d = copy.deepcopy(json.loads(EX_VENUE.read_text(encoding="utf-8")))
    d["story"] = {"written_at": "2026-10-15T08:00:00Z", **story}
    d["evidence"].append({"fields": ["story.opened"], "url": "https://example.org/about",
                          "quote": "The venue first opened its doors in 1998 on Hackney Road",
                          "retrieved_at": "2026-10-15T07:50:00Z", "source_kind": "primary", "source_date": "2024-01-01"})
    d["story_research"] = {"last_attempt": "2026-10-15", "outcome": "partial", "attempts": 1, "next_check": "2026-10-22"}
    return d


def test_a_backed_story_passes(validators):
    assert errors(with_story(opened="1998"), validators) == []


@pytest.mark.parametrize("mutate,expected", [
    (lambda d: d["story"].update(vibe="Dark and loud."), "'story.vibe' is filled in but no evidence item names it"),
    (lambda d: d["story"].update(opened="It first opened its doors in 1998 on Hackney Road"), "copies the source"),
    (lambda d: d["story_research"].update(next_check="2026-10-16"), "weekly retries only"),
    (lambda d: d["story_research"].update(outcome="written"), "next_check must be null"),
    (lambda d: d.update(story={"written_at": "2026-10-15T08:00:00Z"}), "has no content"),
    (lambda d: d["story"].update(worth_knowing=["too short"]), "format:"),
])
def test_story_rules(validators, mutate, expected):
    d = with_story(opened="1998")
    mutate(d)
    errs = errors(d, validators)
    assert any(expected in e for e in errs), errs
