"""conftest.py for `tests/scripts/analysis` -- K4 harness test isolation.

Mirrors the repo-root `tests/conftest.py::_clean_wave_active_floor` shape:
clean the shared, process-global state BEFORE and AFTER every test, never
just after, so a test that runs before the FIRST test in a session is not
silently affected by whatever a completely different, unrelated prior test
session left behind.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _bounded_launcher_prerequisites_on_path(tmp_path_factory, monkeypatch):
    """Every test in this directory sees `claude` resolvable on PATH, via a
    bounded, test-only stand-in -- not because that tool is installed on the
    machine running the suite.

    `preflight.treatment_launcher_link_step` (called from `treatment_steps`,
    reached from most of this directory's arm-construction tests) resolves
    the launcher with `shutil.which("claude")` and raises `SystemExit` when
    it is absent. That refusal is correct production behaviour for a real
    arm with no launcher; it is not a property these packaging/probe tests
    exercise. CI runners with no Claude CLI installed (observed: GitHub
    Actions run 35868878462, shard 4) hit the same gate these tests do not
    mean to probe.

    `socat` is deliberately NOT stubbed here: it is a real sandbox-bridge
    dependency some tests (e.g. `test_k4_row11_start_recipe.py::test_the_
    sandbox_bridge_survives_a_workspace_too_deep_for_a_unix_socket`) need to
    exercise for real, and `missing_sandbox_prerequisites`'s loud refusal
    for a genuinely-absent `socat` IS a property under test there. A test
    that wants a bounded `socat` stand-in provides its own per-file fixture
    (e.g. `test_k4_probe_workspace_cleanup.py`'s `_bounded_sandbox_
    prerequisites`), narrowing PATH further with its own
    `monkeypatch.setenv` -- `monkeypatch` restores in LIFO order, so that
    later, narrower `setenv` wins for the test and still reverts cleanly
    afterward.
    """
    bin_dir = tmp_path_factory.mktemp("bounded-launcher-bin")
    exe = bin_dir / "claude"
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")


# Stable-design report 2026-08-19 Sec.1.3: `preflight.main()` sets these
# env vars directly on `os.environ` (the SAME channel every other arm-
# specific fact travels through to setup subprocesses) -- never through
# `monkeypatch`, since production code has no fixture to hook. A test that
# calls `main()` therefore mutates process-global state that outlives the
# test itself unless something cleans it up; pytest runs this whole
# directory in one interpreter, so a leaked ceiling from one test can flip
# an unrelated, later test's `render_project_fragment` assertions (e.g. its
# own line-count budget) without either test doing anything wrong on its
# own. `K4_SUPERVISOR_OWNER_PID` (defect `il-supervisore-non-riavvia-...-
# si-autotermina-da-orfano`, 2026-08-24 fix) joined this SAME channel and
# carries the SAME leakage risk: a stale PID surviving into a later,
# unrelated test would make `prepare_examiner_fixture.main()` bind a
# freshly-started supervisor to a process that has nothing to do with
# that test's own owner.
_K4_WALL_CLOCK_ENV_VARS = (
    "K4_WALL_CLOCK_CEILING_MINUTES",
    "K4_CAMPAIGN_START_EPOCH",
    "K4_SUPERVISOR_OWNER_PID",
)


@pytest.fixture(autouse=True)
def _clean_k4_wall_clock_env():
    """Each test in this directory runs with NEITHER wall-clock env var
    set, unless it declares one itself (`monkeypatch.setenv`, which
    reverts on its own). Removed before AND after."""
    for name in _K4_WALL_CLOCK_ENV_VARS:
        os.environ.pop(name, None)
    yield
    for name in _K4_WALL_CLOCK_ENV_VARS:
        os.environ.pop(name, None)


@pytest.fixture(autouse=True)
def _stop_any_leaked_k4_supervisor(tmp_path):
    """Run 14 take 3 (K4 matrix): `pef.prepare()` now starts a keepalive
    supervisor -- `setsid`'d, detached, outliving the calling process by
    DESIGN -- so any test calling `prepare()` (or `probe_examiner_start_
    recipe`, which also starts one) for real leaves one running unless
    something tears it down. `pytest`'s own `tmp_path` is unique per test,
    so sweeping it after every test for a `supervisor.pid`
    (`pef.SUPERVISOR_PID_FILE_NAME`) anywhere under it and calling `pef.
    stop_supervisor` on each owning directory makes "a test forgot to
    tear down its own supervisor" unrepresentable -- no test below needs
    its own explicit cleanup to be correct, the SAME discipline `test_k4_
    row11_start_recipe.py`'s `workspace` fixture already applies to the
    plain (non-supervised) server case."""
    from scripts.analysis.k4 import prepare_examiner_fixture as pef

    yield
    for pid_file in tmp_path.rglob(pef.SUPERVISOR_PID_FILE_NAME):
        pef.stop_supervisor(pid_file.parent)
