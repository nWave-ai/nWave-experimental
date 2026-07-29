"""Tests for the worktree-removal guard's command parsing (scripts/hooks/worktree_removal_guard.py).

Pure, in-process tests of `_find_removal_target` / `_reason_is_valid` -- the
tokenized detection must find a `git worktree remove <path>` buried after a
`&&`, must NOT false-positive on the phrase inside a quoted commit message,
and must ignore every OTHER `git worktree` subcommand (`add`, `list`,
`lock`, `prune`, ...).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_HOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "hooks"
    / "worktree_removal_guard.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("worktree_removal_guard", _HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


_MODULE = _load()
_FIND_TARGET = _MODULE._find_removal_target
_REASON_VALID = _MODULE._reason_is_valid


@pytest.mark.parametrize(
    ("command", "expected_target"),
    [
        ("git worktree remove /tmp/wt-lane", "/tmp/wt-lane"),
        ("git worktree remove --force /tmp/wt-lane", "/tmp/wt-lane"),
        ("git worktree remove -f /tmp/wt-lane", "/tmp/wt-lane"),
        ("cd /repo && git worktree remove ../wt-lane", "../wt-lane"),
        ("git worktree remove /tmp/wt-lane && echo done", "/tmp/wt-lane"),
        ("git status ; git worktree remove /tmp/wt-lane", "/tmp/wt-lane"),
    ],
)
def test_finds_removal_target(command: str, expected_target: str) -> None:
    assert _FIND_TARGET(command) == expected_target


@pytest.mark.parametrize(
    "command",
    [
        "git worktree list",
        "git worktree add /tmp/wt-lane -b lane",
        "git worktree lock /tmp/wt-lane",
        "git worktree unlock /tmp/wt-lane",
        "git worktree prune",
        # mentioned inside a commit message -- NOT a real invocation
        'git commit -m "document git worktree remove behaviour"',
        "echo 'git worktree remove /tmp/wt-lane'",
        "git status",
        "rm -rf /tmp/wt-lane",
        # a bare `git worktree remove` with no path argument -- nothing to check
        "git worktree remove",
        "git worktree remove --force",
    ],
)
def test_does_not_false_match(command: str) -> None:
    assert _FIND_TARGET(command) is None


def test_unparseable_command_does_not_match() -> None:
    assert _FIND_TARGET('git worktree remove "unterminated') is None


@pytest.mark.parametrize(
    "reason",
    [
        "",
        "1",
        "true",
        "yes",
        "ok",
        "  short  ",
    ],
)
def test_bare_flag_reasons_are_invalid(reason: str) -> None:
    assert not _REASON_VALID(reason)


@pytest.mark.parametrize(
    "reason",
    [
        "confirmed with the lane owner this is dead",
        "Ale confirmed via Slack this worktree is stale",
    ],
)
def test_prose_reasons_are_valid(reason: str) -> None:
    assert _REASON_VALID(reason)
