"""'The story' on an event page: which events the event storyteller picks each morning, how a regular night's
dates share their research, the weekly retry, and the house rules on the story itself."""
import copy
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import event_stories  # noqa: E402
import validate  # noqa: E402

EX_EVENT = REPO / "docs/examples/event.json"
TODAY = dt.date(2026, 10, 15)
PRESS = "https://www.theguardian.com/music/2024/may/01/example-review"


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def has(errs, text):
    return any(text in e for e in errs)


# ------------------------------------------------------------------ picking events

def event(eid, day, title="Night", venue="bgwmc", **extra):
    return {"id": eid, "title": title, "starts_at": f"{day}T21:00:00+01:00", "venue": {"venue_id": venue, "name": venue},
            "status": "on-sale", "evidence": [{"url": f"https://example.com/{eid}"}], **extra}


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "data/events").mkdir(parents=True)
    return tmp_path


def write(root, e):
    d = root / "data/events" / e["starts_at"][:7]
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{e['id']}.json").write_text(json.dumps(e), encoding="utf-8")


def story(chars=500, written="2026-10-10T08:00:00Z", checked="2026-10-10T09:00:00Z"):
    return {"who": "x" * chars, "written_at": written, "evidence": [],
            "review": {"checked_at": checked, "removed_fields": []} if checked else None}


def ids(result):
    return [r["event_id"] for r in result["research"]]


def test_picks_soonest_upcoming_events_within_the_horizon(repo):
    write(repo, event("2026-10-20-b", "2026-10-20"))
    write(repo, event("2026-10-16-a", "2026-10-16"))
    write(repo, event("2026-10-10-past", "2026-10-10"))
    write(repo, event("2026-12-01-far", "2026-12-01"))
    write(repo, event("2026-10-17-cancelled", "2026-10-17", status="cancelled"))
    write(repo, event("2026-10-18-doubt", "2026-10-18", needs_review={"since": "x", "reason": "y"}))
    write(repo, event("2026-10-19-done", "2026-10-19", title="Other", story=story(),
                      story_research={"last_attempt": "2026-10-10", "outcome": "written", "attempts": 1, "next_check": None}))
    r = event_stories.todo(TODAY, root=repo)
    assert ids(r) == ["2026-10-16-a", "2026-10-20-b"]


def test_cap_and_runs_after_one_offs(repo):
    write(repo, event("2026-09-01-run", "2026-09-01", title="Show", ends_at="2026-11-30T18:00:00+00:00"))
    for d in range(15, 22):
        write(repo, event(f"2026-10-{d}-n", f"2026-10-{d}", title=f"Night {chr(96 + d)}", venue=f"v{d}"))
    r = event_stories.todo(TODAY, limit=3, root=repo)
    assert ids(r) == ["2026-10-15-n", "2026-09-01-run", "2026-10-16-n"]
    assert r["left_for_later"] == 5


def test_a_short_try_waits_a_week(repo):
    tried = {"last_attempt": "2026-10-12", "outcome": "nothing-found", "attempts": 1, "next_check": "2026-10-19"}
    write(repo, event("2026-10-25-a", "2026-10-25", story_research=tried))
    assert ids(event_stories.todo(TODAY, root=repo)) == []
    assert ids(event_stories.todo(dt.date(2026, 10, 19), root=repo)) == ["2026-10-25-a"]


def test_a_series_shares_its_research(repo):
    write(repo, event("2026-10-08-jam-12", "2026-10-08", title="Jazz Jam #12", story=story(),
                      story_research={"last_attempt": "2026-10-07", "outcome": "written", "attempts": 1, "next_check": None}))
    write(repo, event("2026-10-22-jam-14", "2026-10-22", title="Jazz Jam #14"))
    row = event_stories.todo(TODAY, root=repo)["research"][0]
    assert row["series_story_file"] == "data/events/2026-10/2026-10-08-jam-12.json"


def test_a_series_that_came_up_empty_waits_together(repo):
    tried = {"last_attempt": "2026-10-12", "outcome": "nothing-found", "attempts": 1, "next_check": "2026-10-19"}
    write(repo, event("2026-10-13-quiz", "2026-10-13", title="Pub Quiz", story_research=tried))
    write(repo, event("2026-10-20-quiz", "2026-10-20", title="Pub Quiz"))
    r = event_stories.todo(TODAY, root=repo)
    assert ids(r) == [] and r["waiting_for_weekly_retry"] == 1


def test_unchecked_lists_stories_newer_than_their_review(repo):
    write(repo, event("2026-10-20-a", "2026-10-20", story=story(checked=None)))
    write(repo, event("2026-10-21-b", "2026-10-21", story=story(written="2026-10-12T08:00:00Z", checked="2026-10-11T08:00:00Z")))
    write(repo, event("2026-10-22-c", "2026-10-22", story=story()))
    write(repo, event("2026-10-01-old", "2026-10-01", story=story(checked=None)))
    assert event_stories.unchecked(TODAY, root=repo) == ["data/events/2026-10/2026-10-20-a.json",
                                                         "data/events/2026-10/2026-10-21-b.json"]


# ------------------------------------------------------------------ the house rules

@pytest.fixture(scope="module")
def validators():
    return validate.load_validators()


def quote(text, fields=("story.who",), date="2025-05-01", url=PRESS, kind="press"):
    return {"fields": list(fields), "url": url, "quote": text, "retrieved_at": "2026-10-15T07:00:00Z",
            "source_kind": kind, "source_date": date}


GOOD_STORY = {
    "who": "The Guardian called DJ Example's last record a patient, warm set of slow-burning house tracks.",
    "started": "2019, as a monthly night",
    "written_at": "2026-10-15T07:30:00Z",
    "evidence": [
        quote("a patient, warm record of slow-building house that rewards repeated listening"),
        quote("The night began in 2019 as a monthly party", fields=("story.started",), date=None,
              url="https://bgwmc.co.uk/whats-on/example", kind="primary"),
    ],
    "review": None,
}
GOOD_RESEARCH = {"last_attempt": "2026-10-15", "outcome": "partial", "attempts": 1, "next_check": "2026-10-22",
                 "note": "No review of a past edition found."}


def with_story(st=None, research=GOOD_RESEARCH):
    d = load(EX_EVENT)
    d["story"] = copy.deepcopy(st if st is not None else GOOD_STORY)
    d["story_research"] = copy.deepcopy(research)
    return d


def story_errors(data, validators):
    errs = validate.schema_errors(validators["events"], data)
    return errs or validate.check_event_story(data)


def test_good_story_passes(validators):
    assert story_errors(with_story(), validators) == []


def test_a_part_needs_its_own_quote(validators):
    d = with_story()
    d["story"]["vibe"] = "Sweaty and friendly, by all accounts."
    assert has(story_errors(d, validators), "story.vibe: is filled in but no story.evidence item names it")


def test_now_and_vibe_need_recent_sources(validators):
    d = with_story()
    d["story"]["vibe"] = "Reviewers found the room loud and happy."
    d["story"]["evidence"].append(quote("the room was loud and happy until close", fields=("story.vibe",), date="2015-03-01"))
    assert has(story_errors(d, validators), "story.vibe: every source is over 5 years old")


def test_no_copying(validators):
    d = with_story()
    d["story"]["who"] = "Reviewers liked it: a patient, warm record of slow-building house that rewards listening."
    assert has(story_errors(d, validators), "copies the source word for word")


def test_names_may_be_repeated(validators):
    d = with_story()
    d["story"]["evidence"][0]["quote"] = "DJ Example and Example Live Act share the bill for a long night"
    d["story"]["who"] = "DJ Example and Example Live Act have played together before, says the Guardian."
    assert story_errors(d, validators) == []


def test_never_use_sources_are_refused(validators):
    d = with_story()
    d["story"]["evidence"][0]["url"] = "https://ra.co/dj/example"
    assert has(story_errors(d, validators), "never-use source")


def test_retry_is_exactly_a_week(validators):
    assert has(story_errors(with_story(research={**GOOD_RESEARCH, "next_check": "2026-10-16"}), validators),
               "the next check is 2026-10-22")
    assert has(story_errors(with_story(research={**GOOD_RESEARCH, "outcome": "written"}), validators),
               "next_check must be null once the story is written")


def test_story_without_bookkeeping_is_refused(validators):
    assert has(story_errors(with_story(research=None), validators), "story_research is empty")


def test_removed_parts_must_be_empty(validators):
    d = with_story()
    d["story"]["review"] = {"checked_at": "2026-10-15T08:00:00Z", "removed_fields": ["story.who"]}
    assert has(story_errors(d, validators), "'story.who' is listed as removed but still filled in")


def test_story_evidence_is_kept_apart_from_the_verifiers(validators):
    """A story never adds to the event's own evidence, so the verifier's chain stays intact."""
    d = with_story()
    assert d["evidence"] == load(EX_EVENT)["evidence"]
    assert validate.check_event_story(d) == []
