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


# Stable-design report 2026-08-19 Sec.1.3: `preflight.main()` sets these two
# env vars directly on `os.environ` (the SAME channel every other arm-
# specific fact travels through to setup subprocesses) -- never through
# `monkeypatch`, since production code has no fixture to hook. A test that
# calls `main()` therefore mutates process-global state that outlives the
# test itself unless something cleans it up; pytest runs this whole
# directory in one interpreter, so a leaked ceiling from one test can flip
# an unrelated, later test's `render_project_fragment` assertions (e.g. its
# own line-count budget) without either test doing anything wrong on its
# own.
_K4_WALL_CLOCK_ENV_VARS = (
    "K4_WALL_CLOCK_CEILING_MINUTES",
    "K4_CAMPAIGN_START_EPOCH",
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
