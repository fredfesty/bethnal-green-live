#!/usr/bin/env python3
"""Print a scheduled run's instructions: the fenced block in the "## Prompt" section of routines/<name>.md.

The scheduled tasks in Fred's Claude account hold only a short launcher (docs/scheduled-tasks.md).
On every run the launcher clones this repository, runs this script and follows what it prints, so
the copy in routines/ is the one that runs. Because a run does whatever is printed, anything unclear
is an error rather than a guess: no Prompt section, more than one, or no fenced block inside it.

    python3 scripts/routine_prompt.py morning-run
    python3 scripts/routine_prompt.py --list

Exits with status 1 (and prints nothing on stdout) when the routine or its prompt is missing.
"""
import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROUTINES = REPO / "routines"
NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
HEADING = re.compile(r"^## (.*)$", re.M)                      # level-2 headings split a file into sections
PROMPT_HEADING = re.compile(r"Prompt(?:\s*\(.*\))?\s*")       # "## Prompt" or "## Prompt (what the task runs)"
OPEN_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})[^\n`]*$")


def routine_names(folder=ROUTINES):
    """Routine files: every routines/*.md that has a Prompt section."""
    names = []
    for path in sorted(Path(folder).glob("*.md")):
        try:
            _prompt_section(path.read_text(encoding="utf-8-sig"), path.name)
        except ValueError:
            continue
        names.append(path.stem)
    return names


def _prompt_section(text, filename):
    text = text.replace("\r\n", "\n")
    headings = list(HEADING.finditer(text))
    found = [i for i, h in enumerate(headings) if PROMPT_HEADING.fullmatch(h.group(1).strip())]
    if not found:
        raise ValueError(f"{filename} has no '## Prompt' section")
    if len(found) > 1:
        raise ValueError(f"{filename} has {len(found)} '## Prompt' sections; there must be exactly one")
    i = found[0]
    end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
    return text[headings[i].end():end]


def _first_fenced_block(section, filename):
    lines = section.split("\n")
    for start, line in enumerate(lines):
        opening = OPEN_FENCE.match(line)
        if not opening:
            continue
        fence = opening.group(1)
        closing = re.compile(rf"^ {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*$")
        for stop in range(start + 1, len(lines)):
            if closing.match(lines[stop]):
                return "\n".join(lines[start + 1:stop])
        raise ValueError(f"{filename}: the fenced block in its Prompt section is never closed")
    raise ValueError(f"{filename}: its Prompt section has no fenced block")


def prompt(name, folder=ROUTINES):
    """The prompt block of routines/<name>.md, or raise ValueError saying what is wrong."""
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError(f"not a routine name: {name!r} (lowercase letters, digits and hyphens only)")
    path = Path(folder) / f"{name}.md"
    if not path.is_file():
        raise ValueError(f"no such routine: routines/{name}.md")
    section = _prompt_section(path.read_text(encoding="utf-8-sig"), path.name)
    block = _first_fenced_block(section, path.name).strip()
    if not block:
        raise ValueError(f"{path.name}: the fenced block in its Prompt section is empty")
    return block + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", nargs="?", help="routine name, e.g. morning-run")
    parser.add_argument("--list", action="store_true", help="list the routines")
    args = parser.parse_args(argv)
    if args.list:
        print("\n".join(routine_names()))
        return 0
    if not args.name:
        parser.error("give a routine name, or --list")
    try:
        text = prompt(args.name)
    except ValueError as err:
        print(f"routine_prompt: {err}", file=sys.stderr)
        return 1
    # Write UTF-8 bytes whatever the terminal's encoding, so a dash or a pound sign can't crash a run.
    sys.stdout.flush()
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
