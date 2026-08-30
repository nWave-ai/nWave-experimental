#!/usr/bin/env python3
"""Pre-commit gate: a staged `.md` file may not introduce a NEW `des <verb>`
citation for a verb absent from the live `_REGISTRY` (F-INSTALL-REMOVAL-
TRANSPARENCY follow-up -- documentation-staleness ratchet).

A zero-tolerance version of this gate cannot be armed today: the tree
already carries a measured baseline of ghost-verb citations
(`nWave/data/ghost-verb-citation-baseline.json`, ~100 distinct verbs across
~260 files -- see `scripts/shared/ghost_verb_census.py`'s module docstring
for the exact extraction rule and its known precision limits). Arming a
gate that starts red on ~500 existing (file, verb) pairs gets disarmed
within a day, which is the same outcome as never arming it -- Ale's own
standing instruction against a gate that "nasce rosso".

The ratchet instead fails ONLY on a citation not already in the baseline:
existing debt is untouched, and a NEW ghost citation in a staged file
blocks. The baseline can only shrink (documentation cleanup, run
`scripts/generate_ghost_verb_baseline.py` after) or grow via a deliberate,
reviewed re-run of that same script -- never automatically as a side
effect of this gate.

Scope: only staged `.md` files are scanned (GDP-1/GDP-5) -- never the
whole tree on every commit.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from des.cli.registry_diff import registry_names_from_source
from des.runtime.spawn import spawn
from scripts.shared.ghost_verb_census import (
    extract_des_verb_citations,
    ghost_verbs,
)


_MAIN_TRACKED_PATH = "src/des/cli/__main__.py"
_BASELINE_TRACKED_PATH = "nWave/data/ghost-verb-citation-baseline.json"


def new_ghost_citations(
    current: dict[str, frozenset[str]], baseline: dict[str, frozenset[str]]
) -> dict[str, frozenset[str]]:
    """Pure predicate: per staged file, ghost verbs cited NOW that were not
    already in the baseline for that same file. Files/verbs with nothing
    new are omitted from the result."""
    result: dict[str, frozenset[str]] = {}
    for path, verbs in current.items():
        new = verbs - baseline.get(path, frozenset())
        if new:
            result[path] = new
    return result


def _staged_markdown_files() -> list[str]:
    try:
        result = spawn(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return []
    files = result.stdout.strip().splitlines() if result.stdout.strip() else []
    return [f for f in files if f.endswith(".md")]


def _load_baseline(repo_root: Path) -> dict[str, frozenset[str]]:
    baseline_path = repo_root / _BASELINE_TRACKED_PATH
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {path: frozenset(verbs) for path, verbs in data.get("files", {}).items()}


def main() -> int:
    staged = _staged_markdown_files()
    if not staged:
        return 0  # GDP-1/GDP-5: no staged .md file, nothing to scan

    repo_root = Path.cwd()
    live = registry_names_from_source(repo_root / _MAIN_TRACKED_PATH)
    if live is None:
        # Degrade LOUD (GDP-6): a corrupt/unreadable registry means this
        # gate cannot tell a ghost citation from a real one, so it must not
        # silently pass a commit it cannot actually verify.
        print(
            f"WHAT: could not parse {_MAIN_TRACKED_PATH} to get the live "
            "`des` subcommand set.\n"
            "WHY: this gate cannot tell a ghost citation from a real one "
            "without the live set.\n"
            "HOW: fix the syntax error in that file (the Python Quality "
            "gate will also reject it) before this gate can run.",
            file=sys.stderr,
        )
        return 1

    baseline = _load_baseline(repo_root)

    current: dict[str, frozenset[str]] = {}
    for relative_path in staged:
        path = repo_root / relative_path
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        cited = extract_des_verb_citations(text)
        if not cited:
            continue
        ghosts = ghost_verbs(cited, live=live)
        if ghosts:
            current[relative_path] = ghosts

    new = new_ghost_citations(current, baseline)
    if not new:
        return 0

    lines = []
    for path, verbs in sorted(new.items()):
        lines.append(f"  {path}: {', '.join(sorted(verbs))}")
    print(
        "WHAT: staged .md file(s) cite a `des <verb>` not in the live "
        "`_REGISTRY` and not already in the known-debt baseline:\n"
        + "\n".join(lines)
        + "\n"
        "WHY: this is documentation instructing a reader to run a "
        "subcommand that no longer exists -- the same transparency gap "
        "F-INSTALL-REMOVAL-TRANSPARENCY was filed for, in a doc instead "
        "of the CLI.\n"
        "HOW: cite a real subcommand (see `des --help`), or if the verb "
        "genuinely still exists check for a typo; if this citation is "
        "intentional and reviewed (e.g. documenting historical behaviour "
        "in prose), wrap it so it does not read as an instruction, or "
        "extend `nWave/data/ghost-verb-citation-baseline.json` via a "
        "deliberate `uv run python scripts/generate_ghost_verb_baseline.py` "
        "re-run -- never edit that JSON file by hand.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
