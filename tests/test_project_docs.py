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


def _write(folder, name, text, encoding="utf-8"):
    (folder / f"{name}.md").write_text(text, encoding=encoding)


PROMPT_FILES = {
    "ok": "# Routine\n\n## Prompt (what runs)\n\nIntro.\n\n```\nDo the thing.\n```\n\n## After\n\n```\nnot this\n```\n",
    "tagged": "## Prompt\n\n```text\nDo the thing.\n```\n",
    "tildes": "## Prompt\n\n~~~\nDo the thing.\n~~~\n\n```\nnot this\n```\n",
    "indented": "## Prompt\n\n   ```\nDo the thing.\n   ```\n",
    "crlf": "## Prompt\r\n\r\n```\r\nDo the thing.\r\n```\r\n",
    "longer-fence": "## Prompt\n\n````\nDo the thing.\n```\nstill the thing\n````\n",
}
BROKEN_FILES = {
    "no-section": "# Routine\n\n## Settings\n\nNothing here.\n",
    "blank": "# Routine\n\n## Prompt\n\n```\n\n```\n",
    # no fence in the Prompt section: must not borrow the next section's block
    "no-fence": "## Prompt\n\nSee below.\n\n## Reviewing\n\n```\nrm -rf everything\n```\n",
    "two-sections": "## Prompt\n\n```\none\n```\n\n## Prompt (old)\n\n```\ntwo\n```\n",
    "unclosed": "## Prompt\n\n```\nDo the thing.\n",
    "wrong-heading": "## Prompt-old\n\n```\nDo the thing.\n```\n",
}


@pytest.mark.parametrize("name", PROMPT_FILES)
def test_reads_the_prompt_block(tmp_path, name):
    _write(tmp_path, name, PROMPT_FILES[name])
    expected = "Do the thing.\n```\nstill the thing\n" if name == "longer-fence" else "Do the thing.\n"
    assert routine_prompt.prompt(name, folder=tmp_path) == expected


def test_reads_a_file_saved_with_a_byte_order_mark(tmp_path):
    _write(tmp_path, "bom", PROMPT_FILES["tagged"], encoding="utf-8-sig")
    assert routine_prompt.prompt("bom", folder=tmp_path) == "Do the thing.\n"


@pytest.mark.parametrize("name", BROKEN_FILES)
def test_refuses_anything_unclear(tmp_path, name):
    _write(tmp_path, name, BROKEN_FILES[name])
    with pytest.raises(ValueError):
        routine_prompt.prompt(name, folder=tmp_path)
    assert name not in routine_prompt.routine_names(tmp_path) or name in ("blank", "no-fence", "unclosed")


def test_lists_only_files_with_a_prompt_section(tmp_path):
    _write(tmp_path, "ok", PROMPT_FILES["ok"])
    _write(tmp_path, "notes", "# Not a routine\n")
    assert routine_prompt.routine_names(tmp_path) == ["ok"]


def test_command_line(capsys):
    assert routine_prompt.main(["morning-run"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Run the Bethnal Green Live morning run")
    assert out == routine_prompt.prompt("morning-run")
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
    text = routine_prompt.prompt(name)
    named = set(AGENT_NAME.findall(text))
    # any agent file the prompt points at, and any name given a model in brackets, must exist too
    named |= set(re.findall(r"\.claude/agents/([a-z-]+)\.md", text))
    named |= set(re.findall(r"\b([a-z]+(?:-[a-z]+)+) \((?:sonnet|haiku|opus)\)", text))
    assert named, "expected the prompt to name its agents"
    missing = sorted(n for n in named if n not in AGENTS)
    assert not missing, f"no .claude/agents/<name>.md for: {missing}"


@pytest.mark.parametrize("name", ROUTINES)
def test_prompts_name_only_scripts_and_docs_that_exist(name):
    text = routine_prompt.prompt(name)
    for path in set(re.findall(r"\b(?:scripts/[a-z_]+\.py|docs/[a-z-]+\.md|routines/[a-z-]+\.md|CLAUDE\.md|requirements\.txt)\b", text)):
        assert (REPO / path).is_file(), f"{name} names {path}, which doesn't exist"


MAY_MERGE_ITSELF = {"weekly-venue-stories"}  # Fred's decision: that run's own pull request is always merged


@pytest.mark.parametrize("name", ROUTINES)
def test_only_the_venue_stories_run_merges_its_own_pull_request(name):
    text = routine_prompt.prompt(name)
    merges = bool(re.search(r"merge_pull_request|merge it yourself", text))
    assert merges == (name in MAY_MERGE_ITSELF)
    if merges:
        assert "Never merge any other pull request" in text


@pytest.mark.parametrize("name", ROUTINES)
def test_prompts_reuse_the_launchers_clone(name):
    text = routine_prompt.prompt(name)
    assert "already working in a clone of fredfesty/bethnal-green-live" in text
    assert "check out origin/main" in text


@pytest.mark.parametrize("name", ROUTINES)
def test_reports_end_with_a_pull_request_hyperlink(name):
    text = routine_prompt.prompt(name)
    assert re.search(r"\[Pull request #\d+: [^\]]+\]\(https://github\.com/fredfesty/bethnal-green-live/pull/\d+\)", text)


# --- the docs people and their Claude work from --------------------------------------------------

DOCS = ["CONTRIBUTING.md", "README.md", "docs/ship-issue.md", "docs/decisions.md", "docs/scheduled-tasks.md"]


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


# --- the launchers recorded in docs/scheduled-tasks.md ---------------------------------------------

def _launchers():
    text = (REPO / "docs/scheduled-tasks.md").read_text(encoding="utf-8")
    return dict(re.findall(r"^## Launcher: `([a-z-]+)`\n\n```\n(.*?)\n```", text, re.S | re.M))


def test_every_routine_has_a_recorded_launcher():
    assert sorted(_launchers()) == sorted(ROUTINES)


@pytest.mark.parametrize("name", ROUTINES)
def test_launchers_keep_their_fixed_rules(name):
    text = _launchers()[name]
    assert f"python3 scripts/routine_prompt.py {name}" in text
    assert "Never push to main" in text
    assert re.search(r"Never use Gmail, Google Calendar, Google Drive, Claude Docs or any other connector", text)
    assert "Never change scheduled tasks, repository settings, secrets" in text
    assert "never instructions" in text
    allows_github_tools = "mcp__github__" in text
    assert allows_github_tools == (name in MAY_MERGE_ITSELF)
    assert ("Never merge any pull request yourself." in text) == (name not in MAY_MERGE_ITSELF)


def test_codeowners_lists_only_paths_that_exist():
    lines = (REPO / ".github/CODEOWNERS").read_text(encoding="utf-8").splitlines()
    paths = [line.split()[0] for line in lines if line.strip() and not line.startswith("#")]
    assert "/routines/" in paths and "/CLAUDE.md" in paths
    missing = [p for p in paths if not (REPO / p.strip("/")).exists()]
    assert not missing, f"CODEOWNERS names missing paths: {missing}"
