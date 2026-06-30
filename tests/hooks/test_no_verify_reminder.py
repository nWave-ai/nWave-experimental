"""Tests for the lean --no-verify reminder guard (scripts/hooks/no_verify_reminder.py).

The guard BLOCKS a git verify-bypass with an imperative reminder. The critical
contract is the ABSENCE of false-positives: a commit MESSAGE that merely mentions
a bypass flag, `git push -n` (dry-run), and `git log -n` (count) must NOT be
blocked — only a REAL standalone bypass flag fires. A naive raw-string regex would
false-block legitimate commits (this session itself wrote commit messages mentioning
`--no-verify`); the tokenized detector must not.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_HOOK_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "hooks" / "no_verify_reminder.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("no_verify_reminder", _HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


_GUARD = _load()._command_carries_git_bypass


@pytest.mark.parametrize(
    "command",
    [
        "git commit --no-verify",
        "git commit --no-verify -m 'msg'",
        "git commit -n",
        "git commit -n -m 'msg'",
        "git commit --no-gpg-sign",
        "git push --no-verify",
        "git add . && git commit -n",
        "git add . && git commit --no-verify -m 'x'",
        "GIT_EDITOR=true git commit -n",
        "git -c user.name=x commit --no-verify",
    ],
)
def test_blocks_real_bypass(command: str) -> None:
    assert _GUARD(command), f"a real git verify-bypass must be blocked: {command!r}"


@pytest.mark.parametrize(
    "command",
    [
        # bypass flag string mentioned INSIDE a commit message — NOT a real flag
        'git commit -m "document the --no-verify guard"',
        'git commit -m "fix -n flag handling in the parser"',
        "git commit -m 'explain --no-gpg-sign behaviour'",
        # push -n is --dry-run, log -n is a count — never guarded
        "git push -n",
        "git push -n origin main",
        "git log -n 5",
        "git log --oneline -n 10",
        # the flag echoed/quoted, not executed
        'echo "git commit --no-verify"',
        "grep -n no-verify scripts/hooks/no_verify_reminder.py",
        # ordinary git, no bypass
        "git commit -m 'normal commit'",
        "git status",
        "git push origin main",
        # not a git command at all
        "python -m pytest -n 2",
        "ls -n",
    ],
)
def test_does_not_false_block(command: str) -> None:
    assert not _GUARD(command), (
        f"must NOT block a non-bypass command (false-positive): {command!r}"
    )


def test_unparseable_command_does_not_block() -> None:
    """An unbalanced-quote command is unparseable -> fail-open (no false-block)."""
    assert not _GUARD('git commit -m "unterminated')
