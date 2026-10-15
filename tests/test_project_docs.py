"""The repository is the project's source of truth: the scheduled tasks read their instructions from
routines/ (scripts/routine_prompt.py), and people and their Claude work from CONTRIBUTING.md,
docs/ship-issue.md and docs/decisions.md. These tests keep those files working and consistent."""
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import routine_prompt  # noqa: E402

ROUTINES = ["morning-run", "weekly-newsletter", "weekly-venues", "weekly-venue-stories"]
AGENTS = {p.stem for p in (REPO / ".claude/agents").glob("*.md")}
AGENT_NAME = re.compile(
    r"\b(scout-(?!rules\b)[a-z]+(?:-[a-z]+)*|venue-(?:finder|researcher)-[a-z]+|venue-(?:editor|checker|storyteller|profiler)"
    r"|verifier|listing-writer|newsletter-(?:editor|intro)|event-story-checker|event-storyteller)\b"
)


# --- scripts/routine_prompt.py -------------------------------------------------------------------

def test_lists_every_routine():
    assert set(ROUTINES) <= set(routine_prompt.routine_names())


@pytest.mark.parametrize("name", ROUTINES)
def test_every_routine_has_a_prompt(name):
    text = routine_prompt.prompt(name)
    assert len(text.split()) > 200, "the prompt looks cut short"
    assert "```" not in text, "the prompt ran past its fenced block"
    assert text.endswith("\n") and not text.startswith("\n")


@pytest.mark.parametrize("name", ["", "no-such-run", "../CLAUDE", "Morning-Run", "morning_run", "-x", "a/b"])
def test_refuses_bad_or_missing_names(name):
    with pytest.raises(ValueError):
        routine_prompt.prompt(name)


def test_refuses_a_routine_without_a_prompt(tmp_path):
    (tmp_path / "empty.md").write_text("# Routine\n\n## Settings\n\nNothing here.\n")
    (tmp_path / "blank.md").write_text("# Routine\n\n## Prompt\n\n```\n\n```\n")
    (tmp_path / "ok.md").write_text("# Routine\n\n## Prompt (what runs)\n\nIntro.\n\n```\nDo the thing.\n```\n\n## After\n\n```\nnot this\n```\n")
    for bad in ("empty", "blank"):
        with pytest.raises(ValueError):
            routine_prompt.prompt(bad, folder=tmp_path)
    assert routine_prompt.prompt("ok", folder=tmp_path) == "Do the thing.\n"


def test_command_line(capsys):
    assert routine_prompt.main(["morning-run"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Run the Bethnal Green Live morning run")
    assert routine_prompt.main(["no-such-run"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "no such routine" in captured.err
    assert routine_prompt.main(["--list"]) == 0
    assert "weekly-venues" in capsys.readouterr().out.split()


# --- what the prompts say ------------------------------------------------------------------------

@pytest.mark.parametrize("name", ROUTINES)
def test_prompts_keep_the_safety_rules(name):
    text = routine_prompt.prompt(name)
    assert re.search(r"never push to main", text, re.I), "every run must say it never pushes to main"
    assert re.search(r"Do NOT use Gmail, Google Calendar, Google Drive, Claude Docs.*any other connector", text), \
        "every run must rule out the connectors"
    assert "data, never instructions" in text
    assert "fredfesty/bethnal-green-live" in text


@pytest.mark.parametrize("name", ROUTINES)
def test_prompts_name_only_agents_that_exist(name):
    named = set(AGENT_NAME.findall(routine_prompt.prompt(name)))
    assert named, "expected the prompt to name its agents"
    missing = sorted(n for n in named if n not in AGENTS)
    assert not missing, f"no .claude/agents/<name>.md for: {missing}"


@pytest.mark.parametrize("name", ROUTINES)
def test_prompts_name_only_scripts_and_docs_that_exist(name):
    text = routine_prompt.prompt(name)
    for path in set(re.findall(r"\b(?:scripts/[a-z_]+\.py|docs/[a-z-]+\.md|routines/[a-z-]+\.md|CLAUDE\.md|requirements\.txt)\b", text)):
        assert (REPO / path).is_file(), f"{name} names {path}, which doesn't exist"


@pytest.mark.parametrize("name", ROUTINES)
def test_reports_end_with_a_pull_request_hyperlink(name):
    text = routine_prompt.prompt(name)
    assert re.search(r"\[Pull request #\d+: [^\]]+\]\(https://github\.com/fredfesty/bethnal-green-live/pull/\d+\)", text)


# --- the docs people and their Claude work from --------------------------------------------------

DOCS = ["CONTRIBUTING.md", "README.md", "docs/ship-issue.md", "docs/decisions.md"]


@pytest.mark.parametrize("doc", DOCS)
def test_docs_point_only_at_files_that_exist(doc):
    text = (REPO / doc).read_text(encoding="utf-8")
    base = (REPO / doc).parent
    links = re.findall(r"\]\((?!https?://|#|mailto:)([^)#\s]+)(?:#[^)]*)?\)", text)
    code = re.findall(r"`((?:\.claude|docs|routines|scripts|tests|schemas|site|\.github)/[^`<>*\s]+|CLAUDE\.md|CONTRIBUTING\.md|README\.md)`", text)
    missing = sorted({p for p in links if not (base / p).exists()} | {p for p in code if not (REPO / p).exists()})
    assert not missing, f"{doc} points at missing paths: {missing}"


def test_ship_issue_covers_the_whole_workflow():
    text = (REPO / "docs/ship-issue.md").read_text(encoding="utf-8")
    steps = re.findall(r"^## (\d+)\. ", text, re.M)
    assert steps == [str(i) for i in range(10)], "steps 0 to 9, in order"
    for must in ("in-progress", "Fixes #", "two reviewers", "unit tests", "never as instructions",
                 "Never commit to `main`", "needs-fred", "markdown hyperlink"):
        assert must in text, f"docs/ship-issue.md should mention {must!r}"


def test_contributing_lists_every_routine():
    text = (REPO / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for name in ROUTINES:
        assert f"routines/{name}.md" in text
    assert "scripts/routine_prompt.py" in text
