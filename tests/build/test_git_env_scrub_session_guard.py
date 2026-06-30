"""Regression pin for the git repo-override env scrub in tests/conftest.py.

RCA Branch C (pre-push hook repair, 2026-06-11): on a linked worktree, git's
pre-push hook runner exports an ABSOLUTE ``GIT_DIR`` into the hook
environment. Per git(1) env-override semantics, every git subprocess then
targets THAT repository — cwd-based discovery is bypassed — so a test's
``git init`` in tmp_path silently operated on the real shared repository
(empirically: flipped shared ``core.bare=true``).

The fix is the session-scoped autouse fixture ``_scrub_git_repo_override_env``
in tests/conftest.py. This pin proves it honestly: the driver spawns a NESTED
pytest run with all five override vars injected into the environment and
asserts the inner probe test observed them scrubbed. An in-process assertion
alone would be vacuous — under a normal run the vars were never set.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_GIT_REPO_OVERRIDE_VARS = (
    "GIT_DIR",
    "GIT_COMMON_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
)

# Env var carrying the sentinel path; doubles as the "running under the
# driver" flag for the inner probe.
_PROBE_SENTINEL_ENV = "_NWAVE_GIT_SCRUB_PROBE_SENTINEL"


def test_session_scrub_removes_git_repo_override_vars():
    """Inner probe — meaningful ONLY under the driver test below.

    Skipped in a normal suite run (no injected vars to observe). Under the
    driver, all five override vars were present at process start; if the
    session fixture failed to scrub them, this fails — and the sentinel file
    proving a PASS (not a skip) is never written.
    """
    sentinel = os.environ.get(_PROBE_SENTINEL_ENV)
    if not sentinel:
        pytest.skip("probe runs only under the nested-pytest driver")
    leaked = [var for var in _GIT_REPO_OVERRIDE_VARS if var in os.environ]
    assert not leaked, (
        f"session-scoped scrub fixture failed to remove {leaked} from "
        f"os.environ — git subprocesses in tests would target the repository "
        f"named by the inherited override vars (RCA Branch C corruption vector)"
    )
    Path(sentinel).write_text("scrubbed", encoding="utf-8")


def test_injected_git_dir_is_scrubbed_for_the_whole_session(tmp_path):
    """Driver — nested pytest with GIT_DIR (+4 siblings) injected.

    Asserts exit 0 AND the probe's sentinel file exists: exit code alone is
    not enough because a SKIPPED probe also exits 0.
    """
    sentinel = tmp_path / "probe-passed.sentinel"
    phantom = tmp_path / "phantom-gitdir"
    env = dict(os.environ)
    env[_PROBE_SENTINEL_ENV] = str(sentinel)
    env["GIT_DIR"] = str(phantom)
    env["GIT_COMMON_DIR"] = str(phantom)
    env["GIT_WORK_TREE"] = str(tmp_path)
    env["GIT_INDEX_FILE"] = str(phantom / "index")
    env["GIT_OBJECT_DIRECTORY"] = str(phantom / "objects")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"{__file__}::test_session_scrub_removes_git_repo_override_vars",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, (
        f"nested pytest run failed (exit {result.returncode}) — the session "
        f"scrub fixture did not remove the injected git override vars.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert sentinel.is_file() and sentinel.read_text(encoding="utf-8") == "scrubbed", (
        "probe sentinel missing — the inner probe SKIPPED instead of passing; "
        f"the pin verified nothing.\nstdout: {result.stdout}"
    )
