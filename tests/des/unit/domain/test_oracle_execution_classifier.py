"""Unit tests for the oracle-execution outcome classifier (K4 Run 13).

Language-agnostic by design (roadmap: "language agnostic is an outcome
constraint, not authorization to build or retain a universal language-
adapter framework"): no Python-vocabulary DIAGNOSIS survives here (no
`SystemCheckError`/unittest `ERROR:`-block parsing) -- a nonzero exit is
RED (a declared symbol named in the output), `UNACCEPTABLE_BUILD` (a
language-neutral build/compile-broken marker matched, the real tool's own
output quoted rather than diagnosed), or INDETERMINATE (informational
only, this classifier makes no claim about why).
"""

from __future__ import annotations

from des.domain.oracle_execution_classifier import (
    GREEN,
    INDETERMINATE,
    RED,
    UNACCEPTABLE_BUILD,
    classify_probe_output,
    declared_symbol_candidates,
)


def _contract(justification: str = "", overlap: str = "") -> dict:
    return {
        "targets": {
            "hc/api/models.py": {"justification": justification, "overlap": overlap}
        }
    }


def test_declared_symbol_candidates_reads_camel_case_from_justification() -> None:
    contract = _contract(
        justification="The new MaintenanceWindow model, FK to Check, mirrors Channel."
    )

    symbols = declared_symbol_candidates(contract)

    assert "MaintenanceWindow" in symbols
    assert "Check" in symbols
    assert "Channel" in symbols


def test_zero_exit_is_green() -> None:
    assert (
        classify_probe_output(returncode=0, output="OK", declared_symbols=set())
        == GREEN
    )


def test_nonzero_exit_naming_a_declared_symbol_is_red_any_language() -> None:
    """K4 Run 13 admission case: `ImportError: cannot import name
    'MaintenanceWindow'` is the missing-feature reason once
    `MaintenanceWindow` is a symbol the contract's own targets already
    declare -- a plain token match, so this holds for a Go
    `undefined: NotBuiltYet` line exactly the same way. Checked BEFORE the
    build-marker table, so a real declared-symbol match always wins."""
    python_output = (
        "ImportError: cannot import name 'MaintenanceWindow' from 'hc.api.models'"
    )
    go_output = "--- FAIL: TestFoo\nundefined: NotBuiltYet\n"

    assert (
        classify_probe_output(
            returncode=1, output=python_output, declared_symbols={"MaintenanceWindow"}
        )
        == RED
    )
    assert (
        classify_probe_output(
            returncode=1, output=go_output, declared_symbols={"NotBuiltYet"}
        )
        == RED
    )


def test_nonzero_exit_matching_a_build_marker_is_unacceptable_build() -> None:
    """K4 sister defect discipline: the marker table is language-neutral --
    a Go compile failure is caught the same way a Python SyntaxError is,
    without ever claiming the WRONG language broke."""
    outputs = [
        "SyntaxError: invalid syntax",
        "# command-line-arguments\n./foo_test.go:1:1: syntax error\n",
        "./foo_test.go:1:1: cannot find package\n",
        "src/main.ts(3,5): error TS2304: Cannot find name 'Foo'.\n",
        "error[E0433]: failed to resolve\n",
        "error: could not compile `pkg` due to previous error\n",
    ]
    for output in outputs:
        assert (
            classify_probe_output(returncode=1, output=output, declared_symbols=set())
            == UNACCEPTABLE_BUILD
        )


def test_nonzero_exit_matching_neither_is_indeterminate() -> None:
    """A fixture/setup gap the classifier has no vocabulary for -- an
    honest "don't know," never a fabricated diagnosis."""
    output = (
        "ERROR: test_it_notifies (Test)\n"
        "django.core.exceptions.ValidationError: kind is required\n"
    )

    assert (
        classify_probe_output(returncode=1, output=output, declared_symbols=set())
        == INDETERMINATE
    )
