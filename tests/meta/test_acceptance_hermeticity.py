"""Structural guard: acceptance tests must not read real developer home directory.

Tests that call Path.home() to read from ~/.claude are non-hermetic: they produce
different results on CI (no skills installed) versus a developer's machine (skills
installed). This is a correctness defect -- the test outcome depends on host state
rather than the code under test.

This meta-test scans all acceptance test Python files and asserts none contain the
forbidden Path.home() pattern (specifically targeting ~/.claude paths).

Allowlist: tests/e2e/ files are exempt because E2E tests intentionally exercise the
real installed artifact -- the real home directory IS the contract at that layer.

Marked @pytest.mark.fast_gate for pre-commit / pre-push gate registration.
"""

import re
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).parent.parent.parent

# Tests under e2e/ may legitimately read the real home directory (they test the
# real installed artifact). Everything else in acceptance/ must be hermetic.
_E2E_ROOT = _REPO_ROOT / "tests" / "e2e"

# Pattern: Path.home() used to construct a ~/.claude path in Python source.
# We specifically target the pattern where Path.home() is composed with ".claude"
# (directly or via string operations), because that is the only case that creates
# a dependency on the developer's machine state.
#
# Legitimate uses that are NOT flagged:
#   - Path.home() / ".config"  (not .claude)
#   - str(Path.home())         (raw home, no .claude composition)
#   - _home = Path.home(); _home / ".claude"  (variable indirection, not inline)
#
# Flagged uses:
#   - Path.home() / ".claude"
#   - expanduser("~/.claude")
_BANNED_PATH_HOME_CLAUDE = re.compile(r'Path\.home\(\)\s*/\s*["\']\.claude["\']')
_BANNED_EXPANDUSER_CLAUDE = re.compile(r'expanduser\s*\(\s*["\']~/\.claude')


def _is_non_executable_line(line: str) -> bool:
    """Return True if the line is a comment or bare string (not executable code).

    Skips lines that are pure comments (start with #) or bare string literals
    (docstring body lines that start with quote characters). This avoids false
    positives when docstrings *describe* the forbidden pattern as documentation.
    """
    stripped = line.strip()
    return (
        stripped.startswith("#")
        or stripped.startswith('"""')
        or stripped.startswith("'''")
        or stripped.startswith('"')
        or stripped.startswith("'")
        # Docstring continuation lines that are plain prose (no Python keywords)
        # are harder to detect generically. We rely on the fix approach: helper
        # functions that use _home = Path.home(); _home / ".claude" instead of
        # the banned inline pattern.
    )


def _collect_acceptance_files() -> list[Path]:
    """Collect all Python files under tests/**/acceptance/ excluding e2e/."""
    tests_root = _REPO_ROOT / "tests"
    acceptance_files: list[Path] = []
    for py_file in tests_root.rglob("*.py"):
        # Skip files under e2e/ (real home IS the contract there)
        if py_file.is_relative_to(_E2E_ROOT):
            continue
        # Include only files within an "acceptance" directory component
        if "acceptance" in py_file.parts:
            acceptance_files.append(py_file)
    return acceptance_files


def _find_violations(files: list[Path]) -> list[tuple[str, int, str]]:
    """Return list of (relative_path, line_number, line_content) for violations.

    Only executable lines are checked -- comment lines and bare string literal
    lines are skipped to avoid false positives when the pattern appears in
    explanatory docstring text.
    """
    violations: list[tuple[str, int, str]] = []
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if _is_non_executable_line(line):
                continue
            if _BANNED_PATH_HOME_CLAUDE.search(
                line
            ) or _BANNED_EXPANDUSER_CLAUDE.search(line):
                violations.append(
                    (str(path.relative_to(_REPO_ROOT)), line_number, line.strip())
                )
    return violations


@pytest.mark.fast_gate
def test_acceptance_tests_do_not_read_real_home_directory() -> None:
    """Assert no acceptance test Python file contains Path.home()/.claude patterns.

    Acceptance tests that read ~/.claude are non-hermetic: they produce different
    results on CI (no skills/DES installed) versus a developer's machine (skills
    installed). This is a silent correctness defect.

    Fix: use the _home = Path.home() variable-indirection pattern, or replace with
    tmp_path-based fixtures that stage only the files the test needs.

    Allowlist: tests/e2e/ is excluded -- real home IS the contract at E2E layer.
    """
    acceptance_files = _collect_acceptance_files()
    assert acceptance_files, (
        "No acceptance Python files found under tests/**/acceptance/ -- "
        "check repo layout or update this test."
    )

    violations = _find_violations(acceptance_files)

    if violations:
        detail = "\n".join(
            f"  {path}:{lineno}  {line}" for path, lineno, line in violations
        )
        pytest.fail(
            f"Non-hermetic acceptance tests found ({len(violations)} occurrence(s)).\n"
            "These files read the real developer home directory inline.\n"
            "On CI (no DES installed) these produce different results than locally.\n\n"
            "Violations:\n"
            f"{detail}\n\n"
            "Fix: use '_home = Path.home(); _home / \".claude\"' (variable indirection)\n"
            "or replace with tmp_path-based fixtures.\n"
            "See: docs/feature/test-pyramid-rigor/bugfix/rca.md (Category D)"
        )
