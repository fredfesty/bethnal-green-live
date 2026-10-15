#!/usr/bin/env python3
"""Print a scheduled run's instructions: the fenced block under "## Prompt" in routines/<name>.md.

The scheduled tasks in Fred's Claude account hold only a short launcher. On every run the launcher
clones this repository and runs this script, then follows what it prints, so the copy in routines/
is the one that runs.

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
PROMPT = re.compile(r"^## Prompt\b[^\n]*\n.*?^```[^\n]*\n(.*?)^```[ \t]*$", re.S | re.M)


def routine_names(folder=ROUTINES):
    return sorted(p.stem for p in Path(folder).glob("*.md"))


def prompt(name, folder=ROUTINES):
    """The prompt block of routines/<name>.md, or raise ValueError saying what is wrong."""
    if not NAME.fullmatch(name or ""):
        raise ValueError(f"not a routine name: {name!r} (lowercase letters, digits and hyphens only)")
    path = Path(folder) / f"{name}.md"
    if not path.is_file():
        raise ValueError(f"no such routine: routines/{name}.md")
    match = PROMPT.search(path.read_text(encoding="utf-8"))
    if not match or not match.group(1).strip():
        raise ValueError(f"{path.name} has no '## Prompt' section with a fenced block under it")
    return match.group(1).strip() + "\n"


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
        sys.stdout.write(prompt(args.name))
    except ValueError as err:
        print(f"routine_prompt: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
