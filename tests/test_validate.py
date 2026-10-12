"""Each house rule in scripts/validate.py should catch the mistake it exists for."""
import copy
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import validate  # noqa: E402

EX_CAND = REPO / "data/candidates/nights-music/_example/2026-10-30-bgwmc-example-night.json"
EX_VER = REPO / "data/verification/_example/2026-10-30-bgwmc-example-night.json"
EX_EVENT = REPO / "docs/examples/event.json"
AGGREGATOR = "https://www.timeout.com/london/things-to-do/123-example"


@pytest.fixture(scope="module")
def validators():
    return validate.load_validators()


def errors(kind, data, validators, path=None, today=None):
    path = path or Path(f"{data.get('id', 'x')}.json")
    errs = validate.schema_errors(validators[kind], data)
    return errs or validate.CHECKS[kind](path, data, today)


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def has(errs, text):
    return any(text in e for e in errs)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway copy of the example chain, so tests can change candidate, record and event together."""
    monkeypatch.setattr(validate, "ROOT", tmp_path)
    for src in (EX_CAND, EX_VER):
        dst = tmp_path / src.relative_to(REPO)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    ev = tmp_path / "data/events/2026-10/2026-10-30-bgwmc-example-night.json"
    ev.parent.mkdir(parents=True)
    shutil.copy(EX_EVENT, ev)

    class R:
        cand = tmp_path / EX_CAND.relative_to(REPO)
        ver = tmp_path / EX_VER.relative_to(REPO)
        event = ev

        @staticmethod
        def edit(path, fn):
            d = load(path)
            fn(d)
            path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            return d
    return R


# ============================================================= candidates

def test_example_candidate_passes(validators):
    assert errors("candidates", load(EX_CAND), validators) == []


@pytest.mark.parametrize("mutate, expected", [
    (lambda d: d["evidence"].pop(3), "'lineup' is filled in but no evidence item names it"),
    (lambda d: d["venue"].update(venue_id="oval-space"), "do-not-list"),
    (lambda d: d["venue"].update(venue_id=None, name="The Oval Space"), "do-not-list"),
    (lambda d: d.update(zone="fringe"), "registry says core"),
    (lambda d: d["price"].update(known=False), "known=false but other price values"),
    (lambda d: (d["venue"].update(venue_id="moth-club"), d.update(zone="outer")), "worth_the_trip"),
    (lambda d: (d["venue"].update(venue_id=None), d.update(zone="outer")), "worth_the_trip"),
    (lambda d: d.update(id="2026-11-01-bgwmc-x"), "should start with the event date"),
    (lambda d: [e.update(source_kind="aggregator") for e in d["evidence"]], "needs the date quoted from a primary source"),
    (lambda d: d.update(starts_at="2026-10-30", ends_at=None), "needs a start time"),
    (lambda d: d.update(foo=1), "Additional properties"),
    (lambda d: d["venue"].update(venue_id="nowhere"), "not in the registry"),
    (lambda d: d["price"].update(is_free=True), "marked free but min_gbp"),
    (lambda d: d.update(ends_at="2026-10-29"), "ends before it starts"),
    (lambda d: d.update(ends_at="2026-10-30T04:00:00+00:00"), "ends_at is not after starts_at"),
    (lambda d: d.update(starts_at="2026-10-30T21:00:00+01:00"), "Keep the local time printed on the page (21:00)"),
    (lambda d: d.update(status="cancelled", evidence=[d["evidence"][0], d["evidence"][1], d["evidence"][3]]), "'status' is filled in"),
    (lambda d: d["evidence"][0].update(url="https://ra.co/events/123"), "never-use source"),
    (lambda d: d["evidence"][0].update(url="https://www.instagram.com/p/abc"), "never-use source"),
    (lambda d: d["evidence"][0].update(url="https://thepicklefactory.co.uk/x"), "never-use source"),
    (lambda d: d["evidence"][0].update(url=AGGREGATOR), "cannot be 'primary'"),
    (lambda d: d.update(ticket_url="javascript:alert(1)"), "format: ticket_url"),
    (lambda d: d.update(ticket_url="see venue site"), "format: ticket_url"),
    (lambda d: d.update(found_at="2026-13-45T99:99:00Z"), "format: found_at"),
    (lambda d: d["evidence"][0].update(quote="   "), "format: evidence.0.quote"),
    (lambda d: d["evidence"][0].update(quote="Fri"), "format: evidence.0.quote"),
    (lambda d: d.update(subcategory="exhibition"), "is not a nights-music type"),
    (lambda d: d.update(run_schedule="Tue–Sun 11am–6pm"), "'run_schedule' is filled in"),
    (lambda d: d.update(ends_at="2027-08-01"), "runs for more than"),
    (lambda d: (d["venue"].update(venue_id="star-of-bethnal-green", name="The Star of Bethnal Green",
                                  address="359 Bethnal Green Rd, London", postcode="E2 6LG")), "'medium' at most"),
])
def test_candidate_rules(validators, mutate, expected):
    d = copy.deepcopy(load(EX_CAND))
    mutate(d)
    errs = errors("candidates", d, validators, path=EX_CAND)
    assert has(errs, expected), errs


def test_candidate_file_name_must_match_id(validators):
    errs = errors("candidates", load(EX_CAND), validators, path=Path("other.json"))
    assert has(errs, "name should be 2026-10-30-bgwmc-example-night.json")


def test_a_run_that_opened_earlier_is_still_current(validators):
    d = copy.deepcopy(load(EX_CAND))
    d.update(id="2026-09-01-bgwmc-example-night", starts_at="2026-09-01", ends_at="2026-11-30")
    d["evidence"][1]["quote"] = "Exhibition runs 1 September to 30 November 2026"
    assert not has(validate.check_candidate(EX_CAND.with_name(d["id"] + ".json"), d, dt.date(2026, 10, 13)), "outside the scouting window")
    d.update(ends_at="2026-10-01")
    assert has(validate.check_candidate(EX_CAND.with_name(d["id"] + ".json"), d, dt.date(2026, 10, 13)), "outside the scouting window")


def test_window_only_when_asked(validators):
    d = load(EX_CAND)
    assert validate.check_candidate(EX_CAND, d, None) == []
    assert has(validate.check_candidate(EX_CAND, d, dt.date(2027, 3, 1)), "outside the scouting window")


@pytest.mark.parametrize("value, ok", [
    ("2026-10-16T22:00:00+01:00", True),    # summer time
    ("2026-10-16T22:00:00Z", False),        # wrong offset in summer
    ("2026-10-30T21:00:00+00:00", True),    # winter time
    ("2026-10-30T21:00:00+01:00", False),
    ("2026-10-25T01:30:00+01:00", True),    # the repeated hour, first time round
    ("2026-10-25T01:30:00+00:00", True),    # ... and second time round
    ("2026-03-29T01:30:00+00:00", False),   # the skipped hour does not exist
    ("2026-03-29T03:00:00+01:00", True),
    ("2026-10-16", True),                   # date only
])
def test_london_offsets(value, ok):
    assert (validate.check_london_time("starts_at", value) == []) is ok


# ============================================================= verification

def test_example_verification_passes(validators):
    assert errors("verification", load(EX_VER), validators, path=EX_VER) == []


def checks_for(d, field):
    return [c for c in d["field_checks"] if c["field"] == field]


@pytest.mark.parametrize("mutate, expected", [
    (lambda d: d.update(decision="hold", reasons=[]), "needs at least one reason"),
    (lambda d: checks_for(d, "price")[0].update(result="contradicted"), "contradicted"),
    (lambda d: checks_for(d, "starts_at")[0].update(result="unverifiable"), "'starts_at' is not confirmed"),
    (lambda d: checks_for(d, "starts_at")[0].update(method="read"), "only confirmed by reading the page"),
    (lambda d: checks_for(d, "title")[0].update(method="none"), "confirmed but has no URL or method"),
    (lambda d: checks_for(d, "title")[0].update(url=None), "confirmed but has no URL or method"),
    (lambda d: checks_for(d, "title")[0].update(url="https://example.com/elsewhere"), "not cited by the candidate"),
    (lambda d: d.update(field_checks=[c for c in d["field_checks"] if c["field"] != "lineup"]), "no check for 'lineup'"),
    (lambda d: checks_for(d, "venue")[0].update(field="venue.postcode"), "'venue' is not confirmed"),
    (lambda d: d.update(page_status_seen="cancelled"), "must be rejected"),
    (lambda d: d.update(existing_event="data/events/2026-10/nope.json"), "does not exist"),
    (lambda d: d.update(candidate_file="data/candidates/nope.json"), "does not exist"),
    (lambda d: d.update(decided_by="human", reasons=[]), "a person's decision needs a reason"),
])
def test_verification_rules(validators, mutate, expected):
    d = copy.deepcopy(load(EX_VER))
    mutate(d)
    errs = errors("verification", d, validators, path=EX_VER)
    assert has(errs, expected), errs


def test_source_kind_comes_from_the_candidate_not_the_verifier(validators, repo):
    # the verifier labels everything primary, but the scout's evidence was all aggregator
    repo.edit(repo.cand, lambda d: [e.update(source_kind="aggregator") for e in d["evidence"]])
    errs = validate.check_verification(repo.ver, load(repo.ver), None)
    assert has(errs, "not confirmed from a primary source")


def test_no_primary_listing_venue_may_publish_on_aggregator_but_not_on_a_tip(validators, repo):
    def to_star(d):
        d["venue"].update(venue_id="star-of-bethnal-green", name="The Star of Bethnal Green")
        for e in d["evidence"]:
            e["source_kind"] = "aggregator"
    repo.edit(repo.cand, to_star)
    assert validate.check_verification(repo.ver, load(repo.ver), None) == []
    repo.edit(repo.cand, lambda d: [e.update(source_kind="reader-tip") for e in d["evidence"]])
    assert has(validate.check_verification(repo.ver, load(repo.ver), None), "not confirmed from a primary source")


def test_new_event_the_scout_saw_cancelled_is_rejected(validators, repo):
    repo.edit(repo.cand, lambda d: d.update(status="cancelled"))
    assert has(validate.check_verification(repo.ver, load(repo.ver), None), "the scout found 'cancelled'")


def test_cancelled_update_to_existing_event_is_allowed(validators, repo):
    d = repo.edit(repo.ver, lambda d: d.update(page_status_seen="cancelled",
                                               existing_event="data/events/2026-10/2026-10-30-bgwmc-example-night.json"))
    assert validate.check_verification(repo.ver, d, None) == []


def test_human_override_publishes_a_hold(validators, repo):
    d = repo.edit(repo.ver, lambda d: (d.update(decided_by="human", reasons=["Phoned the venue on 13 Oct: confirmed."]),
                                       checks_for(d, "starts_at")[0].update(method="read")))
    assert validate.check_verification(repo.ver, d, None) == []
    errs = validate.check_event(repo.event, load(repo.event), None)
    assert has(errs, "add a history entry with by: 'human'")


# ============================================================= events

def test_example_event_passes(validators):
    assert errors("events", load(EX_EVENT), validators, path=EX_EVENT) == []


@pytest.mark.parametrize("mutate, expected", [
    (lambda d: d["verification"].update(record="data/verification/nope.json"), "does not exist"),
    (lambda d: d["verification"].update(removed_fields=["genres"]), "outcome 'verified' but fields were removed"),
    (lambda d: d["verification"].update(outcome="verified-with-gaps", removed_fields=["genres"]), "still filled in"),
    (lambda d: d["verification"].update(outcome="verified-with-gaps"), "removed_fields is empty"),
    (lambda d: d["evidence"].pop(0), "'title' is filled in"),
    (lambda d: d["price"].update(min_gbp=5), "price: differs from the verified candidate"),
    (lambda d: d.update(starts_at="2026-10-30T22:00:00+00:00"), "starts_at: differs"),
    (lambda d: d.update(title="A different night"), "title: differs"),
    (lambda d: d.update(status="scheduled"), "matches neither the candidate nor what the verifier saw"),
    (lambda d: (d.update(accessibility="Step-free access"),
                d["evidence"].append({"fields": ["accessibility"], "url": d["ticket_url"], "quote": "Step-free access throughout",
                                      "retrieved_at": "2026-10-13T06:11:40+01:00", "source_kind": "primary"})),
     "not in the candidate"),
    (lambda d: d.update(zone="fringe"), "zone: differs"),
])
def test_event_rules(validators, mutate, expected):
    d = copy.deepcopy(load(EX_EVENT))
    mutate(d)
    errs = errors("events", d, validators, path=EX_EVENT)
    assert has(errs, expected), errs


def test_unverifiable_field_must_be_removed(validators, repo):
    repo.edit(repo.ver, lambda d: checks_for(d, "price")[0].update(result="unverifiable", method="none"))
    errs = validate.check_event(repo.event, load(repo.event), None)
    assert has(errs, "price: could not be confirmed, so it must be emptied")


def test_correct_removal_passes(validators, repo):
    repo.edit(repo.ver, lambda d: checks_for(d, "genres")[0].update(result="unverifiable", method="none"))
    d = repo.edit(repo.event, lambda d: (d.update(genres=[]),
                                         d["verification"].update(outcome="verified-with-gaps", removed_fields=["genres"])))
    assert validate.check_event(repo.event, d, None) == []


def test_verifier_may_add_its_own_status_quote(validators, repo):
    repo.edit(repo.ver, lambda d: d.update(page_status_seen="sold-out"))
    d = repo.edit(repo.event, lambda d: (d.update(status="sold-out"), d["evidence"].append(
        {"fields": ["status"], "url": d["ticket_url"], "quote": "This event is sold out",
         "retrieved_at": "2026-10-14T07:00:00+01:00", "source_kind": "primary"})))
    assert validate.check_event(repo.event, d, None) == []


def test_event_must_sit_in_its_month_folder(validators, repo):
    wrong = repo.event.parent.parent / "2026-11" / repo.event.name
    wrong.parent.mkdir()
    shutil.move(repo.event, wrong)
    assert has(validate.check_event(wrong, load(wrong), None), "should be data/events/2026-10/")


def test_run_of_nights_with_their_own_ticket_pages_is_not_a_duplicate(validators, repo):
    twin = load(repo.event)
    twin.update(id="2026-10-31-bgwmc-example-night", starts_at="2026-10-31T21:00:00+00:00", ends_at="2026-11-01T03:00:00+00:00",
                ticket_url="https://www.tickettailor.com/events/workingmens-club/0000001")
    assert validate.check_duplicate_events([(repo.event, load(repo.event)), (Path("twin.json"), twin)]) == {}


def test_same_night_listed_twice_is_caught(validators, repo):
    twin = load(repo.event)
    twin.update(id="2026-10-31-bgwmc-example-night-2", title="EXAMPLE NIGHT (illustrative)",
                starts_at="2026-10-31T21:00:00+00:00", ends_at="2026-11-01T03:00:00+00:00")
    dups = validate.check_duplicate_events([(repo.event, load(repo.event)), (Path("twin.json"), twin)])
    assert dups and has(next(iter(dups.values())), "looks like the same night")


# ============================================================= robustness

def test_bad_files_fail_without_crashing(validators, tmp_path, capsys):
    (tmp_path / "utf16.json").write_text('{"id": "x"}', encoding="utf-16")
    (tmp_path / "bom.json").write_bytes(b"\xef\xbb\xbf" + EX_CAND.read_bytes())
    (tmp_path / "broken.json").write_text("{nope", encoding="utf-8")
    n, failed = validate.run("candidates", [tmp_path, tmp_path / "missing-dir"], None, 31, validators)
    out = capsys.readouterr().out
    assert n == 3 and failed == 3  # BOM file is read fine but its name doesn't match its id
    assert "UTF-16" in out and "not valid JSON" in out and "nothing to check" in out


def test_whole_repo_is_valid():
    assert validate.main(["all"]) == 0


def test_a_run_needs_its_closing_date_for_high_confidence(validators):
    d = copy.deepcopy(load(EX_CAND))
    d.update(starts_at="2026-10-30", ends_at="2026-12-12")
    d["evidence"][1]["fields"] = [f for f in d["evidence"][1]["fields"] if f != "ends_at"]
    errs = validate.check_candidate(EX_CAND, d, None)
    assert has(errs, "closing date quoted from a primary source"), errs
    assert not has(errs, "needs a start time")
    assert validate.is_run(d) and not validate.is_run(load(EX_CAND))
