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


def _contract_with_target(target_path: str, *, decision: str, **fields: str) -> dict:
    return {"targets": {target_path: {"decision": decision, **fields}}}


def test_declared_symbol_candidates_reads_camel_case_from_justification() -> None:
    contract = _contract(
        justification="The new MaintenanceWindow model, FK to Check, mirrors Channel."
    )

    symbols = declared_symbol_candidates(contract)

    assert "MaintenanceWindow" in symbols
    assert "Check" in symbols
    assert "Channel" in symbols


def test_declared_symbol_candidates_includes_the_dotted_path_of_create_new_targets() -> (
    None
):
    """SF friction report 2026-08-20, item 1: `_DECLARED_SYMBOL_RE` is
    PascalCase-only -- a `ModuleNotFoundError: No module named
    'pkg.snake_case_module'` from a CREATE_NEW target is unrecognizable
    BY CONSTRUCTION (no valid Python module name is ever uppercase-
    first), so `UNACCEPTABLE_FIXTURE`/`INDETERMINATE` lies about a
    legitimate RED. A CREATE_NEW target's own repo-relative path,
    converted to Python's dotted-module form, is ALSO declared evidence
    -- the contract already states the exact target that does not exist
    yet; a missing-module error naming that SAME path is the missing-
    feature reason, not an oracle defect."""
    contract = _contract_with_target("pkg/snake_case_module.py", decision="CREATE_NEW")

    symbols = declared_symbol_candidates(contract)

    assert "pkg.snake_case_module" in symbols


def test_declared_symbol_candidates_omits_the_dotted_path_of_extend_targets() -> None:
    """An EXTEND target already exists -- a `ModuleNotFoundError` naming
    it would be a genuine surprise, never an expected missing-feature
    shape, so only CREATE_NEW targets contribute this evidence."""
    contract = _contract_with_target("pkg/existing_module.py", decision="EXTEND")

    symbols = declared_symbol_candidates(contract)

    assert "pkg.existing_module" not in symbols


def test_module_not_found_error_for_a_create_new_target_is_red_not_a_lying_refusal() -> (
    None
):
    """The exact SF friction scenario end to end: a CREATE_NEW target's
    module genuinely does not exist yet, `python -m pytest` reports
    `ModuleNotFoundError`, and the classifier must recognize this as the
    missing-feature RED reason, never an `UNACCEPTABLE_BUILD` or a
    silent `INDETERMINATE` that discards the evidence a legitimate RED
    already carries."""
    contract = _contract_with_target("pkg/snake_case_module.py", decision="CREATE_NEW")
    output = "ModuleNotFoundError: No module named 'pkg.snake_case_module'\n"

    assert (
        classify_probe_output(
            returncode=1,
            output=output,
            declared_symbols=declared_symbol_candidates(contract),
        )
        == RED
    )


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


def test_declared_symbol_candidates_strips_the_src_prefix_for_create_new_targets() -> (
    None
):
    """Reviewer verdict on 911f21c81 (verified empirically): `pythonpath =
    ["src", "."]` (see pyproject.toml) means the interpreter's own import
    root is `src/`, so a genuinely missing `src/des/domain/foo_module.py`
    module raises `ModuleNotFoundError: No module named
    'des.domain.foo_module'` -- NEVER `'src.des.domain.foo_module'`. The
    contract-derived dotted path emitted the `src.`-prefixed form only,
    so on the dominant real-contract shape (targets under `src/des/...`,
    see docs/delivery-contracts/) the match never fires and the verdict
    stays the same lying INDETERMINATE the friction report named -- the
    bug 911f21c81 claimed to fix. Fix: emit BOTH the full dotted path and
    the `src/`-stripped one when the target path starts with `src/`."""
    contract = _contract_with_target(
        "src/des/domain/foo_module.py", decision="CREATE_NEW"
    )

    symbols = declared_symbol_candidates(contract)

    assert "des.domain.foo_module" in symbols
    assert "src.des.domain.foo_module" in symbols


def test_module_not_found_error_for_a_src_rooted_create_new_target_is_red() -> None:
    """End-to-end reviewer scenario: the real pytest output names the
    `src/`-stripped dotted path (the actual import root), and the
    classifier must still recognize it as the missing-feature RED
    reason -- the dominant real-contract shape, not the edge case."""
    contract = _contract_with_target(
        "src/des/domain/foo_module.py", decision="CREATE_NEW"
    )
    output = "ModuleNotFoundError: No module named 'des.domain.foo_module'\n"

    assert (
        classify_probe_output(
            returncode=1,
            output=output,
            declared_symbols=declared_symbol_candidates(contract),
        )
        == RED
    )
