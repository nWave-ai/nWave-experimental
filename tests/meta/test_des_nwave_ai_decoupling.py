"""CI import-boundary guard: src/des/ must not contain top-level nwave_ai imports.

Root cause: RC-C — substrate_probe.py introduced a coupling violation by having
top-level 'from nwave_ai...' imports. This caused all S3/S4 container tests to
fail because the import chain broke standalone DES deployment.

This meta-test scans all src/des/**/*.py files for top-level nwave_ai import
patterns and asserts zero violations. It prevents future recurrence at the
cheapest possible layer (pre-commit, not container test).

A top-level import is any import that appears at module scope (not inside a
function, method, or conditional block). The regex targets lines that begin
with 'from nwave_ai' or 'import nwave_ai' after optional whitespace — but
NOT lines indented with 4+ spaces (which are inside a function body).

Marked @pytest.mark.fast_gate for pre-commit layer registration.

Test Budget: 1 behavior x 2 = 2 max. Using 1 test.
"""

from __future__ import annotations

import re
from pathlib import Path


_REPO_ROOT = Path(__file__).parent.parent.parent
_DES_SRC = _REPO_ROOT / "src" / "des"

# Match top-level nwave_ai imports: lines starting with 'from nwave_ai' or
# 'import nwave_ai' (no leading whitespace — module-scope only).
_TOP_LEVEL_NWAVE_AI_IMPORT = re.compile(
    r"^(?:from nwave_ai|import nwave_ai)",
    re.MULTILINE,
)

import pytest  # noqa: E402


@pytest.mark.fast_gate
def test_des_has_no_top_level_nwave_ai_imports() -> None:
    """Assert no src/des/ file contains top-level 'from nwave_ai' or 'import nwave_ai'.

    Scans dynamically so any future violation is caught without test edits.
    Top-level = module-scope (no leading whitespace). Guarded / lazy imports
    inside function bodies are allowed (the fix pattern for RC-A).

    If this test fails: move the nwave_ai import inside the function that uses
    it, guarded by try/except ImportError to preserve fail-open contract.
    """
    python_files = list(_DES_SRC.rglob("*.py"))
    assert python_files, f"No Python files found under {_DES_SRC} — check repo layout"

    violations: list[str] = []
    for path in python_files:
        content = path.read_text(encoding="utf-8")
        if _TOP_LEVEL_NWAVE_AI_IMPORT.search(content):
            violations.append(str(path.relative_to(_REPO_ROOT)))

    assert violations == [], (
        f"Top-level nwave_ai imports found in src/des/ files ({len(violations)} violation(s)):\n"
        + "\n".join(f"  - {v}" for v in violations)
        + "\n\nFix: move nwave_ai imports inside the function body with try/except ImportError.\n"
        "See substrate_probe.py for the canonical fix pattern."
    )
