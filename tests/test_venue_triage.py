"""scripts/venue_triage.py: which venues the weekly run's researchers are asked to look at.

The weekly run shares one WebSearch limit across all its agents, so triage caps how many venues go to
research. These tests build a small repository in a temporary folder and run triage against it.
"""
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import venue_triage  # noqa: E402
import venuelib  # noqa: E402

RUN_DATE = "2026-10-18"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """An empty repository layout, with the scripts pointed at it."""
    for sub in ("data/sources", "data/venues", f"data/venue-leads/{RUN_DATE}"):
        (tmp_path / sub).mkdir(parents=True)
    monkeypatch.setattr(venuelib, "ROOT", tmp_path)
    monkeypatch.setattr(venuelib, "SOURCES", tmp_path / "data/sources")
    monkeypatch.setattr(venuelib, "VENUES", tmp_path / "data/venues")
    monkeypatch.setattr(venue_triage, "ROOT", tmp_path)
    return tmp_path


def write_registry(root, venues):
    reg = {"category": "test", "venues": [{"id": i, "name": i.replace("-", " ").title(), "zone": z,
                                           "postcode": "E2 6NB"} for i, z in venues]}
    (root / "data/sources/test.json").write_text(json.dumps(reg), encoding="utf-8")


def write_profile(root, venue_id, profiled_at="2026-09-01", zone="core"):
    p = {"id": venue_id, "name": venue_id.title(), "zone": zone, "profiled_at": profiled_at, "status": "open"}
    (root / f"data/venues/{venue_id}.json").write_text(json.dumps(p), encoding="utf-8")


def write_lead(root, name, **extra):
    lead = {"name": name, "found_by": "web", "signal": "new", **extra}
    path = root / f"data/venue-leads/{RUN_DATE}/web-{venuelib.slug(name)}.json"
    path.write_text(json.dumps(lead), encoding="utf-8")


def triage(root, *args):
    assert venue_triage.main([RUN_DATE, "--no-lookup", *args]) == 0
    return json.loads((root / f"data/venue-leads/{RUN_DATE}/_triage.json").read_text(encoding="utf-8"))


def ids(rows, reason=None):
    return [r["venue_id"] for r in rows if reason is None or r["reason"] == reason]


def test_unprofiled_venues_are_capped_at_five_by_default(repo):
    write_registry(repo, [(f"venue-{n:02d}", "core") for n in range(72)])
    out = triage(repo)
    assert len(ids(out["research"], "unprofiled")) == 5
    held = [r for r in out["report_only"] if "unprofiled" in r["reason"]]
    assert len(held) == 67
    assert held[0]["reason"] == "over this week's limit of 5 unprofiled venues; next week"


def test_max_unprofiled_can_be_changed(repo):
    write_registry(repo, [(f"venue-{n:02d}", "core") for n in range(12)])
    out = triage(repo, "--max-unprofiled", "8")
    assert len(ids(out["research"], "unprofiled")) == 8
    assert len([r for r in out["report_only"] if "unprofiled" in r["reason"]]) == 4
    assert "limit of 8 unprofiled" in out["report_only"][0]["reason"]


def test_zero_sends_every_unprofiled_venue_to_report_only(repo):
    write_registry(repo, [("a-venue", "core"), ("b-venue", "fringe")])
    out = triage(repo, "--max-unprofiled", "0")
    assert ids(out["research"]) == []
    assert sorted(ids(out["report_only"])) == ["a-venue", "b-venue"]


def test_core_first_then_fringe_then_outer(repo):
    # Registry order is deliberately the reverse of the order they should be chosen in.
    write_registry(repo, [("outer-1", "outer"), ("outer-2", "outer"), ("fringe-1", "fringe"), ("fringe-2", "fringe"),
                          ("core-1", "core"), ("core-2", "core")])
    out = triage(repo, "--max-unprofiled", "3")
    assert ids(out["research"], "unprofiled") == ["core-1", "core-2", "fringe-1"]
    assert ids(out["report_only"]) == ["fringe-2", "outer-1", "outer-2"]


def test_a_venue_with_no_zone_comes_after_fringe_and_before_outer(repo):
    write_registry(repo, [("outer-1", "outer"), ("no-zone", None), ("fringe-1", "fringe"), ("core-1", "core")])
    out = triage(repo, "--max-unprofiled", "4")
    assert ids(out["research"], "unprofiled") == ["core-1", "fringe-1", "no-zone", "outer-1"]


def test_venues_that_are_profiled_do_not_count_against_the_cap(repo):
    write_registry(repo, [(f"venue-{n}", "core") for n in range(8)])
    for n in range(3):
        write_profile(repo, f"venue-{n}")
    out = triage(repo, "--max-unprofiled", "5", "--refresh", "0")
    assert ids(out["research"], "unprofiled") == [f"venue-{n}" for n in range(3, 8)]
    assert out["report_only"] == []


def test_the_cap_leaves_new_venues_signals_and_refreshes_alone(repo):
    write_registry(repo, [(f"venue-{n:02d}", "core") for n in range(20)] + [("old-news", "core")])
    write_profile(repo, "old-news")
    write_profile(repo, "stale-profile", profiled_at="2026-01-01")
    write_lead(repo, "Brand New Bar", postcode="E2 7AA", website="https://brandnewbar.example")
    write_lead(repo, "Old News", about_venue_id="old-news", signal="closing")
    out = triage(repo, "--max-unprofiled", "2", "--refresh", "1")
    reasons = {}
    for r in out["research"]:
        reasons.setdefault(r["reason"], []).append(r["venue_id"])
    assert reasons["new"] == ["brand-new-bar"]
    assert reasons["signal"] == ["old-news"]
    assert len(reasons["unprofiled"]) == 2
    assert reasons["refresh"] == ["stale-profile"]


def test_a_venue_with_news_is_researched_even_when_it_has_no_profile(repo):
    write_registry(repo, [(f"venue-{n}", "core") for n in range(6)])
    write_lead(repo, "Venue 5", about_venue_id="venue-5", signal="closed")
    out = triage(repo, "--max-unprofiled", "2")
    assert ids(out["research"], "signal") == ["venue-5"]
    # The venue with news was taken as a signal, so it doesn't use up one of the unprofiled places.
    assert ids(out["research"], "unprofiled") == ["venue-0", "venue-1"]


def test_the_default_keeps_a_typical_week_near_the_planned_size(repo):
    """routines/weekly-venues.md plans for about 16 venues: up to 10 new, 6 refreshed, plus a handful."""
    write_registry(repo, [(f"venue-{n:02d}", "core") for n in range(72)])
    for n in range(6):
        write_profile(repo, f"profiled-{n}", profiled_at=f"2026-0{n + 1}-01")
    out = triage(repo)
    assert len(out["research"]) == 5 + 6
    assert dt.date.fromisoformat(out["run_date"]) == dt.date(2026, 10, 18)
