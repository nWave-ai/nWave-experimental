"""Detect a subject workspace's own declared whole-suite test command.

K4 Run 12 debrief: `verification-scope.commands` only ever named the new
oracle's own narrow test (`hc.api.tests.test_maintenance_windows`), never
the subject's whole-suite command its own root `CLAUDE.md` already states
(`Run the subject's own tests: k4-fixture-venv/bin/python manage.py test
hc.api --noinput`). Regressions outside the narrow oracle (an N+1 query, two
stale pinned assertions, a crash on unsaved `Check` instances) were invisible
to BASELINE/GREEN and only surfaced through 3 reviewer rounds.

There is no dedicated schema field for this (`nWave/schemas/
thin-delivery-contract.schema.json`'s `verificationScope` only has
`commands`, `additionalProperties: false`) -- detection reads the workspace's
own root `CLAUDE.md`, declaratively, the same document DISTILL/ATD already
read for project facts. Python-only, no shell, no `git`.

Matching is deliberately narrow to avoid a false trigger on unrelated prose
that merely contains a keyword (e.g. this repo's own CLAUDE.md says "Never
run the whole suite" as a swarm-safety rule, with no command attached): a
line must carry a whole-suite keyword AND a `label: `command`` shape AND the
command text itself must mention "test". No match at all means nothing to
check -- silence is not treated as evidence of a missing command (`Missing
facts return to their owner; DISTILL never guesses them`).
"""

from __future__ import annotations

import re
import shlex
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


_WHOLE_SUITE_KEYWORDS = (
    "own tests",
    "full suite",
    "whole suite",
    "all tests",
    "test suite",
    "entire suite",
)
_LABELED_COMMAND = re.compile(r":\s*`([^`]+)`")


def declared_whole_suite_command(repo_root: Path) -> list[str] | None:
    """The shell-split tokens of the subject's own declared whole-suite
    command, or `None` when its root `CLAUDE.md` is absent or states no such
    command in the narrow labeled shape this resolver recognizes."""
    claude_md = repo_root / "CLAUDE.md"
    if not claude_md.is_file():
        return None
    try:
        text = claude_md.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    for line in text.splitlines():
        lowered = line.lower()
        if not any(keyword in lowered for keyword in _WHOLE_SUITE_KEYWORDS):
            continue
        match = _LABELED_COMMAND.search(line)
        if match is None:
            continue
        command_text = match.group(1)
        if "test" not in command_text.lower():
            continue
        try:
            tokens = shlex.split(command_text)
        except ValueError:
            continue
        if tokens:
            return tokens
    return None


def _last_non_flag_token(tokens: list[str]) -> str | None:
    for token in reversed(tokens):
        if not token.startswith("-"):
            return token
    return None


def _command_argv(command: dict) -> list[str]:
    executable = command.get("executable", {})
    head = str(executable.get("name") or executable.get("path") or "")
    return [head, *command.get("arguments", [])]


def contract_covers_whole_suite(repo_root: Path, contract: dict) -> bool:
    """True when the workspace declares no whole-suite command, or when one
    of `verification-scope.commands` already carries its exact scope token
    (a narrower descendant, e.g. the oracle's own test, does not count)."""
    declared = declared_whole_suite_command(repo_root)
    if declared is None:
        return True
    declared_scope = _last_non_flag_token(declared)
    if declared_scope is None:
        return True
    for command in contract.get("verification-scope", {}).get("commands", []):
        if _last_non_flag_token(_command_argv(command)) == declared_scope:
            return True
    return False
