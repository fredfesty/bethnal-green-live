"""scripts/listings.py: which events the listing writer is asked to describe, and what it is told."""
import copy
import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import listings  # noqa: E402

EX_EVENT = REPO / "docs/examples/event.json"   # Fri 30 Oct 2026, 9pm to 3am


def make_repo(tmp_path, events):
    for e in events:
        p = tmp_path / "data/events" / e["starts_at"][:7] / f"{e['id']}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(e), encoding="utf-8")
    (tmp_path / "data/venues").mkdir(parents=True, exist_ok=True)
    return tmp_path


def event(**changes):
    e = copy.deepcopy(json.loads(EX_EVENT.read_text(encoding="utf-8")))
    e.update(changes)
    return e


def ids(result):
    return [e["id"] for e in result["events"]]


def test_lists_only_upcoming_undescribed_events_not_in_doubt(tmp_path):
    root = make_repo(tmp_path, [
        event(id="needs-one"),
        event(id="has-one", listing={"headline": None, "blurb": "Already written.", "written_at": "2026-10-13T07:00:00+01:00",
                                     "run_id": "x"}),
        event(id="in-doubt", needs_review={"since": "2026-10-13T07:00:00+01:00", "reason": "page gone"}),
        event(id="finished", starts_at="2026-10-01T21:00:00+01:00", ends_at="2026-10-02T03:00:00+01:00"),
    ])
    assert ids(listings.todo(dt.date(2026, 10, 13), root)) == ["needs-one"]
    assert sorted(ids(listings.todo(dt.date(2026, 10, 13), root, include_written=True))) == ["has-one", "needs-one"]


def test_an_event_on_the_run_date_still_counts(tmp_path):
    root = make_repo(tmp_path, [event(id="today")])
    assert ids(listings.todo(dt.date(2026, 10, 31), root)) == ["today"]   # it ends at 3am on the 31st
    assert ids(listings.todo(dt.date(2026, 11, 1), root)) == []


def test_brief_holds_checked_facts_only(tmp_path):
    root = make_repo(tmp_path, [event(id="needs-one", editor_note="The scout loved it")])
    brief = listings.todo(dt.date(2026, 10, 13), root)["events"][0]
    assert "scout_opinion_internal" not in brief and "The scout loved it" not in json.dumps(brief)
    assert brief["weekday"] == "Friday" and brief["time"] == "9pm–3am" and brief["price"] == "£8–£12"
    assert brief["file"] == "data/events/2026-10/needs-one.json"
    assert brief["current_blurb"] is None
