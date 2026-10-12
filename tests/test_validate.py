"""Each house rule in scripts/validate.py should catch the mistake it exists for."""
import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import validate  # noqa: E402

EXAMPLE_CANDIDATE = REPO / "data/candidates/nights-music/_example/2026-10-30-bgwmc-example-night.json"
EXAMPLE_VERIFICATION = REPO / "data/verification/_example/2026-10-30-bgwmc-example-night.json"
EXAMPLE_EVENT = REPO / "docs/examples/event.json"


@pytest.fixture(scope="module")
def validators():
    return validate.load_validators()


def errors(kind, data, validators, path=Path("x.json"), today=None):
    errs = validate.schema_errors(validators[kind], data)
    return errs or validate.CHECKS[kind](path, data, today)


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


# ------------------------------------------------------------- candidates

def test_example_candidate_passes(validators):
    assert errors("candidates", load(EXAMPLE_CANDIDATE), validators) == []


@pytest.mark.parametrize("mutate, expected", [
    (lambda d: d["evidence"].pop(3), "'lineup' is filled in but no evidence item names it"),
    (lambda d: d["venue"].update(venue_id="oval-space"), "do-not-list"),
    (lambda d: d.update(zone="fringe"), "registry says core"),
    (lambda d: d["price"].update(known=False), "known=false but price values are filled in"),
    (lambda d: (d["venue"].update(venue_id="moth-club"), d.update(zone="outer")), "worth_the_trip"),
    (lambda d: d.update(id="2026-11-01-bgwmc-x"), "should start with the event date"),
    (lambda d: [e.update(source_kind="aggregator") for e in d["evidence"]], "needs the date quoted from a primary source"),
    (lambda d: d.update(foo=1), "Additional properties"),
    (lambda d: d["venue"].update(venue_id="nowhere"), "not in the registry"),
    (lambda d: d["price"].update(is_free=True), "marked free but min_gbp"),
    (lambda d: d.update(ends_at="2026-10-29"), "ends before it starts"),
    (lambda d: d.update(starts_at="2026-10-30T21:00:00+01:00"), "should use London's offset that day (+00:00)"),
    (lambda d: d.update(id="2026-10-16-bgwmc-example-night", starts_at="2026-10-16T22:00:00Z", ends_at=None),
     "should use London's offset that day (+01:00)"),
    (lambda d: d.update(status="cancelled", evidence=[d["evidence"][0], d["evidence"][1], d["evidence"][3]]),
     "'status' is filled in"),
])
def test_candidate_rules(validators, mutate, expected):
    d = copy.deepcopy(load(EXAMPLE_CANDIDATE))
    mutate(d)
    errs = errors("candidates", d, validators)
    assert any(expected in e for e in errs), errs


def test_window_only_when_asked(validators):
    import datetime as dt
    d = load(EXAMPLE_CANDIDATE)
    assert errors("candidates", d, validators, today=None) == []
    errs = errors("candidates", d, validators, today=dt.date(2027, 3, 1))
    assert any("outside the scouting window" in e for e in errs)


# ------------------------------------------------------------- verification

def test_example_verification_passes(validators):
    assert errors("verification", load(EXAMPLE_VERIFICATION), validators) == []


@pytest.mark.parametrize("mutate, expected", [
    (lambda d: d.update(decision="hold", reasons=[]), "needs at least one reason"),
    (lambda d: d["field_checks"][2].update(result="contradicted"), "contradicted"),
    (lambda d: d["field_checks"][2].update(result="unverifiable"), "'starts_at' is not confirmed"),
    (lambda d: [c.update(source_kind="aggregator") for c in d["field_checks"]], "non-primary source"),
    (lambda d: d.update(page_status_seen="cancelled"), "must be rejected"),
    (lambda d: d.update(candidate_file="data/candidates/nope.json"), "does not exist"),
])
def test_verification_rules(validators, mutate, expected):
    d = copy.deepcopy(load(EXAMPLE_VERIFICATION))
    mutate(d)
    errs = errors("verification", d, validators)
    assert any(expected in e for e in errs), errs


def test_cancelled_update_to_existing_event_is_allowed(validators):
    d = copy.deepcopy(load(EXAMPLE_VERIFICATION))
    d.update(page_status_seen="cancelled", existing_event="data/events/2026-10/2026-10-30-bgwmc-example-night.json")
    assert errors("verification", d, validators) == []


# ------------------------------------------------------------- events

def test_example_event_passes(validators):
    assert errors("events", load(EXAMPLE_EVENT), validators, path=EXAMPLE_EVENT) == []


@pytest.mark.parametrize("mutate, expected", [
    (lambda d: d["verification"].update(record="data/verification/nope.json"), "does not exist"),
    (lambda d: d["verification"].update(removed_fields=["genres"]), "outcome 'verified' but fields were removed"),
    (lambda d: d["verification"].update(outcome="verified-with-gaps", removed_fields=["genres"]), "still filled in"),
    (lambda d: d["verification"].update(outcome="verified-with-gaps"), "removed_fields is empty"),
    (lambda d: d["evidence"].pop(0), "'title' is filled in"),
])
def test_event_rules(validators, mutate, expected):
    d = copy.deepcopy(load(EXAMPLE_EVENT))
    mutate(d)
    errs = errors("events", d, validators, path=EXAMPLE_EVENT)
    assert any(expected in e for e in errs), errs


def test_event_must_sit_in_its_month_folder(validators, tmp_path, monkeypatch):
    # build a throwaway repo layout so the path rule applies
    monkeypatch.setattr(validate, "ROOT", tmp_path)
    for src in [EXAMPLE_CANDIDATE, EXAMPLE_VERIFICATION]:
        dst = tmp_path / src.relative_to(REPO)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    wrong = tmp_path / "data/events/2026-11/2026-10-30-bgwmc-example-night.json"
    wrong.parent.mkdir(parents=True)
    shutil.copy(EXAMPLE_EVENT, wrong)
    errs = errors("events", load(wrong), validators, path=wrong)
    assert any("should be data/events/2026-10/" in e for e in errs), errs


def test_whole_repo_is_valid():
    assert validate.main(["all"]) == 0
