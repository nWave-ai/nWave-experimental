"""Unit tests for `classify_write` (the PostToolUse oracle-write
classifier's pure core, ADR-SSOT-002 Section 4/4b item 1).

Deliberately independent of `des.domain.oracle_execution_classifier` (a
concurrent lane is retiring that Python-only structure/pattern checker):
classification here is exit code plus a declared-symbol match against the
contract's own targets, never a Python-vocabulary text pattern.
"""

from __future__ import annotations

from pathlib import Path

from des.domain.oracle_write_classifier import (
    GREEN_AS_EXPECTED,
    GREEN_FOR_RED_TO_GREEN,
    RED_RIGHT_REASON,
    RED_WRONG_REASON,
    UNEXPECTEDLY_RED_FOR_GREEN_TO_GREEN,
    classify_write,
    declared_symbol_candidates,
    linked_verification_command,
)


_COMMAND = {
    "executable": {"kind": "toolchain", "name": "pytest"},
    "arguments": ["-q", "pkg/tests/test_widget.py"],
}


def _contract(route: str, *, justification: str = "") -> dict:
    return {
        "delivery-route": route,
        "targets": {"pkg/widget.py": {"justification": justification, "overlap": ""}},
        "verification-scope": {"commands": [_COMMAND]},
    }


def test_red_to_green_failure_citing_a_declared_symbol_is_right_reason(
    tmp_path: Path,
) -> None:
    result = classify_write(
        contract=_contract("RED_TO_GREEN", justification="creates MaintenanceWindow"),
        command=_COMMAND,
        repo_root=tmp_path,
        returncode=1,
        output="ImportError: cannot import name 'MaintenanceWindow'",
    )
    assert result.label == RED_RIGHT_REASON


def test_red_to_green_failure_citing_no_declared_symbol_is_suspect_and_wrong_reason(
    tmp_path: Path,
) -> None:
    result = classify_write(
        contract=_contract("RED_TO_GREEN", justification="creates MaintenanceWindow"),
        command=_COMMAND,
        repo_root=tmp_path,
        returncode=1,
        output="  File 'x.py', line 3\nSyntaxError: invalid syntax",
    )
    assert result.label == RED_WRONG_REASON


def test_red_to_green_already_green_is_flagged(tmp_path: Path) -> None:
    result = classify_write(
        contract=_contract("RED_TO_GREEN"),
        command=_COMMAND,
        repo_root=tmp_path,
        returncode=0,
        output="1 passed",
    )
    assert result.label == GREEN_FOR_RED_TO_GREEN


def test_green_to_green_passing_is_expected(tmp_path: Path) -> None:
    result = classify_write(
        contract=_contract("GREEN_TO_GREEN"),
        command=_COMMAND,
        repo_root=tmp_path,
        returncode=0,
        output="1 passed",
    )
    assert result.label == GREEN_AS_EXPECTED


def test_green_to_green_failure_citing_a_declared_symbol_is_flagged(
    tmp_path: Path,
) -> None:
    result = classify_write(
        contract=_contract("GREEN_TO_GREEN", justification="reuses MaintenanceWindow"),
        command=_COMMAND,
        repo_root=tmp_path,
        returncode=1,
        output="AssertionError: MaintenanceWindow.covers() returned False",
    )
    assert result.label == UNEXPECTEDLY_RED_FOR_GREEN_TO_GREEN


def test_declared_symbol_candidates_reads_justification_and_overlap() -> None:
    contract = {
        "targets": {
            "pkg/widget.py": {
                "justification": "creates Widget and Helper",
                "overlap": "pkg/widget.py:5 near Existing",
            }
        }
    }
    found = declared_symbol_candidates(contract)
    assert found == {"Widget", "Helper", "Existing"}


def test_linked_verification_command_finds_the_matching_entry() -> None:
    contract = _contract("RED_TO_GREEN")
    found = linked_verification_command(contract, "pkg/tests/test_widget.py")
    assert found == _COMMAND


def test_linked_verification_command_none_when_no_match() -> None:
    contract = _contract("RED_TO_GREEN")
    assert linked_verification_command(contract, "pkg/tests/test_other.py") is None
