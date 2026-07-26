"""Regression: the TypeScript smoke must not dirty its own tracked lockfile.

Defect: ``typescript-smoke-rewrites-the-tracked-lockfile-it-tests-against``.

``scripts/polyglot/smoke_typescript_pilot.py`` used to run ``npm install`` with
``cwd`` pointing at the git-tracked ``tests/polyglot-pilot/typescript/`` directory,
so npm rewrote the *tracked* ``package-lock.json`` in place. Anyone who ran the
smoke (directly or via the pytest wrapper) got a permanent
``M .../package-lock.json`` in ``git status`` — noise on a tracked file they never
touched. The fix sandboxes the install+test in a temp copy; the tracked lockfile is
never written.

This test observes the real property by running the real smoke script and asserting
the tracked lockfile is byte-identical afterwards. It is written so that it can NEVER
leave the tree dirty itself — even when it FAILS (pre-fix) — by capturing the lockfile
bytes up front and restoring them in a ``finally``. Without that guard the regression
test would itself be an instance of the defect it guards against.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT = REPO_ROOT / "scripts" / "polyglot" / "smoke_typescript_pilot.py"
PILOT_DIR = REPO_ROOT / "tests" / "polyglot-pilot" / "typescript"
TRACKED_LOCKFILE = PILOT_DIR / "package-lock.json"


@pytest.mark.polyglot_smoke
@pytest.mark.slow
def test_smoke_does_not_dirty_tracked_lockfile() -> None:
    """Running the smoke leaves the tracked package-lock.json byte-identical.

    Negative example: the smoke must still genuinely run (npm install + vitest
    GREEN), not become a no-op to stay clean.
    """
    if shutil.which("npx") is None or shutil.which("npm") is None:
        pytest.skip("Node toolchain (npm/npx) not on PATH — polyglot smoke deferred")

    assert SMOKE_SCRIPT.is_file(), f"missing smoke script: {SMOKE_SCRIPT}"
    assert TRACKED_LOCKFILE.is_file(), f"missing tracked lockfile: {TRACKED_LOCKFILE}"

    before = TRACKED_LOCKFILE.read_bytes()
    try:
        result = subprocess.run(
            [sys.executable, str(SMOKE_SCRIPT)],
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )

        # Negative example — the smoke must actually have run, not skipped/no-op'd.
        assert result.returncode == 0, (
            "smoke did not exit 0\n"
            f"exit={result.returncode}\n--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )
        assert "GREEN end-to-end" in result.stdout, (
            "smoke did not run vitest to GREEN — it must not become a no-op to stay "
            f"clean\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )

        # Core property — the tracked lockfile must be untouched by the smoke run.
        after = TRACKED_LOCKFILE.read_bytes()
        assert after == before, (
            "smoke rewrote the tracked package-lock.json "
            f"({TRACKED_LOCKFILE.relative_to(REPO_ROOT)}) — it must run npm install in "
            "a sandboxed temp copy, not against the tracked directory"
        )
    finally:
        # Self-heal: never leave the tree dirty, even on a failing (pre-fix) run.
        TRACKED_LOCKFILE.write_bytes(before)
