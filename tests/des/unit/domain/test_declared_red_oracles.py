"""The expected-red rule has exactly ONE definition, and it is WIRED.

`tests/build/test_pytest_touched_files_gate.py` already pins the conjuncts
through the touched-file gate's re-export. What that file cannot see is the
reason this module exists at all: the SECOND consumer (`pytest-fast-gate`,
whole-tree collection) rejected the same commit after the gate alone had been
repaired. So the two properties asserted here are the ones a third per-gate
patch would silently break — single definition, and actual wiring into the root
conftest (catalogued != wired).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.domain.declared_red_oracles import expected_red_reason


PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONFTEST = PROJECT_ROOT / "tests" / "conftest.py"
TOUCHED_FILE_GATE = PROJECT_ROOT / "scripts" / "hooks" / "pytest_touched_files.py"

_DECLARED = {"tests/t.py": ("probe-id", {"des.cli.update", "src.des.cli.update"})}


@pytest.mark.fast_gate
def test_the_root_conftest_wires_the_translation():
    """The seam that covers fast-gate, quick-tiers and CI at once."""
    source = CONFTEST.read_text(encoding="utf-8")
    assert "from des.domain.declared_red_oracles import" in source, (
        "the root conftest must read the SHARED rule; a local copy of the "
        "discrimination is the defect this module closes"
    )
    assert "def pytest_make_collect_report(" in source, (
        "a rule the conftest imports but never hooks protects nothing — the "
        "translation must happen where the collect report is BUILT, before any "
        "consumer counts it as an error"
    )


@pytest.mark.fast_gate
def test_the_touched_file_gate_owns_no_second_copy_of_the_rule():
    source = TOUCHED_FILE_GATE.read_text(encoding="utf-8")
    assert "from des.domain.declared_red_oracles import" in source
    assert 're.compile(r"ModuleNotFoundError' not in source, (
        "the gate must not re-implement the missing-module match; two copies "
        "of the discrimination drift, which is exactly the defect being closed"
    )


def test_a_declared_missing_target_is_the_declared_reason():
    reason = expected_red_reason(
        "tests/t.py",
        "E   ModuleNotFoundError: No module named 'des.cli.update'",
        _DECLARED,
    )
    assert reason is not None
    assert "probe-id" in reason


def test_an_undeclared_missing_module_is_not_the_declared_reason():
    assert (
        expected_red_reason(
            "tests/t.py",
            "E   ModuleNotFoundError: No module named 'requests'",
            _DECLARED,
        )
        is None
    )


def test_a_mix_of_declared_and_undeclared_missing_modules_still_blocks():
    """The check is ALL-of, not any-of: one undeclared module poisons it."""
    assert (
        expected_red_reason(
            "tests/t.py",
            "ModuleNotFoundError: No module named 'des.cli.update'\n"
            "ModuleNotFoundError: No module named 'requests'",
            _DECLARED,
        )
        is None
    )


def test_a_collection_error_that_is_not_a_missing_module_still_blocks():
    assert (
        expected_red_reason("tests/t.py", "E   SyntaxError: invalid syntax", _DECLARED)
        is None
    )


def test_a_file_no_contract_declares_still_blocks():
    assert (
        expected_red_reason(
            "tests/other.py",
            "E   ModuleNotFoundError: No module named 'des.cli.update'",
            _DECLARED,
        )
        is None
    )
