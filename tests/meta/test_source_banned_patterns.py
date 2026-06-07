"""Fast-gate source-level regression tests for banned patterns.

These tests scan ALL skill and task files dynamically — not a hardcoded list.
The prior bug (nwave-ai/nwave#36) shipped because test_issue_36 hardcoded 3
skill files and missed nw-update. This dynamic scan prevents that class of
drift: any new skill or task file with a banned pattern is caught automatically
without any test file edits.

Marked @pytest.mark.fast_gate for pre-commit/pre-push hook registration.
"""

import re
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).parent.parent.parent

# Patterns covering $HOME and ~ variants of the banned invocation form.
_BANNED_DOLLAR = re.compile(
    r"PYTHONPATH=\$HOME/\.claude/lib/python",
)
_BANNED_TILDE = re.compile(
    r"PYTHONPATH=~/\.claude/lib/python",
)


def _find_violations(files: list[Path]) -> list[str]:
    violations: list[str] = []
    for path in files:
        content = path.read_text(encoding="utf-8")
        if _BANNED_DOLLAR.search(content) or _BANNED_TILDE.search(content):
            violations.append(str(path.relative_to(_REPO_ROOT)))
    return violations


@pytest.mark.fast_gate
def test_no_banned_pythonpath_in_skill_files() -> None:
    """Assert no skill file contains banned PYTHONPATH= invocation pattern.

    Uses pathlib.Path.glob for dynamic discovery — adding a new skill with the
    banned pattern is caught without any changes to this test.
    """
    skill_files = list((_REPO_ROOT / "nWave" / "skills").glob("*/SKILL.md"))
    assert skill_files, "No SKILL.md files found — check repo layout"

    violations = _find_violations(skill_files)

    assert violations == [], (
        "Banned PYTHONPATH=.../lib/python pattern found in skill files:\n"
        + "\n".join(f"  - {v}" for v in violations)
        + "\n\nFix: rewrite invocations to use the ~/.claude/bin/ shim."
    )


@pytest.mark.fast_gate
def test_no_banned_pythonpath_in_task_files() -> None:
    """Assert no task file contains banned PYTHONPATH= invocation pattern.

    Uses pathlib.Path.glob for dynamic discovery — adding a new task file with
    the banned pattern is caught without any changes to this test.
    """
    task_files = list((_REPO_ROOT / "nWave" / "tasks" / "nw").glob("*.md"))
    assert task_files, "No task .md files found — check repo layout"

    violations = _find_violations(task_files)

    assert violations == [], (
        "Banned PYTHONPATH=.../lib/python pattern found in task files:\n"
        + "\n".join(f"  - {v}" for v in violations)
        + "\n\nFix: rewrite invocations to use the ~/.claude/bin/ shim."
    )
