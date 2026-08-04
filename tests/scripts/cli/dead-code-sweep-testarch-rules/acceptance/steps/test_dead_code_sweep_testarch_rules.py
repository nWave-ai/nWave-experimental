"""Tier A step definitions -- the 2026-08-03 dead-code-sweep regression net.

CONTRACT_SHAPE: pure-function

Pins BOTH halves of techdebt.md item
``dead-code-sweep-2026-08-03-testarch-rules-eight-of-ten-unwired``: the 6
confirmed-dead ``des.testarch.rules`` modules stay removed, AND the 2 exception
modules (``assert_state_delta``, ``pbt_layer_mode``) -- kept because
``registry_conformance_composition.py`` reads their classification constants
live -- stay present. A filesystem-existence + pytest-collection check, no
business logic inlined (Mandate-12 criterion 3).

Honest tagging: @component (auto-``unit`` under ``tests/build/``), NEVER
@wiring_e2e/@subprocess -- in-process filesystem reads + an in-process pytest
collection call, no real subprocess spawn.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pytest_bdd import given, parsers, scenarios, then, when


scenarios("../dead-code-sweep-testarch-rules.feature")

_REPO_ROOT = Path(__file__).resolve().parents[6]
_RULES_DIR = _REPO_ROOT / "src" / "des" / "testarch" / "rules"
_SUITE_DIR = (
    _REPO_ROOT / "tests" / "build" / "at_mandate_mechanical_enforcement" / "acceptance"
)

_RETIRED_MODULES = (
    "sad_path_pbt.py",
    "composition_root.py",
    "technical_call_smell.py",
    "registration_contract.py",
    "seam_tag_honesty.py",
    "driving_port_boundary.py",
)

_EXCEPTION_MODULES = (
    "assert_state_delta.py",
    "pbt_layer_mode.py",
)


# --- fixtures ----------------------------------------------------------------


@given("the des.testarch.rules package directory", target_fixture="rules_dir")
def given_rules_dir() -> Path:
    return _RULES_DIR


@given(
    "the at-mandate-mechanical-enforcement acceptance suite",
    target_fixture="suite_dir",
)
def given_suite_dir() -> Path:
    return _SUITE_DIR


# --- When ----------------------------------------------------------------


@when(
    "I list the 6 modules retired by the 2026-08-03 dead-code sweep",
    target_fixture="retired_paths",
)
def when_list_retired(rules_dir: Path) -> tuple[Path, ...]:
    return tuple(rules_dir / name for name in _RETIRED_MODULES)


@when(
    parsers.parse(
        "I list the 2 modules registry_conformance's drift-guard still reads live constants from"
    ),
    target_fixture="exception_paths",
)
def when_list_exceptions(rules_dir: Path) -> tuple[Path, ...]:
    return tuple(rules_dir / name for name in _EXCEPTION_MODULES)


@when("I collect it with pytest", target_fixture="collect_result")
def when_collect(suite_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", str(suite_dir)],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


# --- Then ----------------------------------------------------------------


@then("none of the 6 retired modules exist on disk")
def then_retired_absent(retired_paths: tuple[Path, ...]) -> None:
    still_present = [str(p) for p in retired_paths if p.exists()]
    assert still_present == [], f"retired module(s) still on disk: {still_present}"


@then("both exception modules still exist on disk")
def then_exceptions_present(exception_paths: tuple[Path, ...]) -> None:
    missing = [str(p) for p in exception_paths if not p.exists()]
    assert missing == [], f"exception module(s) unexpectedly missing: {missing}"


@then("collection succeeds with no dangling import to a retired module")
def then_collection_clean(
    collect_result: subprocess.CompletedProcess[str],
) -> None:
    assert collect_result.returncode == 0, (
        "pytest --collect-only failed for the at-mandate-mechanical-enforcement "
        f"suite:\nstdout:\n{collect_result.stdout}\nstderr:\n{collect_result.stderr}"
    )
    combined = collect_result.stdout + collect_result.stderr
    for name in _RETIRED_MODULES:
        module = name.removesuffix(".py")
        assert f"des.testarch.rules.{module}" not in combined, (
            f"collection output still references retired module {module}"
        )
