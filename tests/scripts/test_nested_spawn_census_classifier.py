"""The spawn census must count what RUNS a suite, never what merely NAMES one.

The census exists to produce two numbers the whole suite-speed arithmetic rests
on: how many nested pytest invocations a run makes, and what each costs. A
name-based matcher gets both wrong in the same direction at once -- it counts a
0.25s capability probe as a suite run, so the count inflates and the per-invocation
floor deflates.

The argv strings below are real shapes taken from this repo's gate, not invented
ones: the interpreter probe and the capability probe are what
``pytest_interpreter()`` / ``can_import()`` actually spawn.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from perf.nested_spawn_census import _classify


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "argv",
    [
        "/repo/.venv/bin/python3 -m pytest tests/des/unit/cli/test_a.py -q",
        "/repo/.venv/bin/python3 -m des.cli.__main__ run-contract-gate "
        "--repo /tmp/sandbox",
    ],
)
def test_a_child_that_runs_a_suite_is_counted(argv: str) -> None:
    assert _classify(argv) == "nested_pytest"


@pytest.mark.parametrize(
    "argv",
    [
        # can_import(interpreter, "pytest") -- imports and exits, runs no test
        "/repo/.venv/bin/python3 -c import pytest",
        # can_import(interpreter, "xdist") reached through the same gate path
        "/repo/.venv/bin/python3 -c import xdist; import pytest",
    ],
)
def test_a_child_that_only_names_pytest_is_excluded_but_visible(argv: str) -> None:
    """Excluded from the count, and classified rather than silently dropped.

    Were these counted, a run making many capability probes would report a large
    nested count with a small floor -- the exact shape that would make the
    "invocations x floor accounts for the run" arithmetic look confirmed when it
    is not.
    """
    assert _classify(argv) == "interpreter_probe"


@pytest.mark.parametrize(
    "argv",
    [
        "git -C /repo rev-parse HEAD",
        "/repo/.venv/bin/python3 -c import nwave_ai",
        "/bin/true",
        # pytest_interpreter() resolving the binary. It IS a probe, but it never
        # names pytest, so it was never a candidate for the nested count and needs
        # no exclusion -- "other" is the honest answer, not "interpreter_probe".
        # Asserting the latter would have claimed the classifier defends against a
        # spawn that could not have reached the defence in the first place.
        "uv run --project /repo python -c import sys; print(sys.executable)",
    ],
)
def test_an_unrelated_spawn_is_neither(argv: str) -> None:
    assert _classify(argv) == "other"
