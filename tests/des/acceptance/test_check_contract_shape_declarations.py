"""Acceptance tests -- `des check-contract-shape` (DISTILL, slice-01).

Charter: docs/product/expectations/check-contract-shape-declarations/
         des-check-contract-shape-flags-violations.md
Feature-delta: docs/feature/check-contract-shape-declarations/feature-delta.md

Contract under test (DOES NOT EXIST YET -- active-RED by design):
`src/des/cli/check_contract_shape_declarations.py:main(argv: list[str] | None = None) -> int`
runs the 3 Principle-11 mechanical Contract-Shape checks over an explicit,
caller-provided `--files <path> [<path> ...]` list (git-free), parsing test
functions + docstrings via stdlib `ast`:
  (a) every `def test_*` docstring contains the substring `CONTRACT_SHAPE:`;
  (b) every acceptance test (a test in a file whose path contains
      `/acceptance/`) docstring contains `Outcome anchor: DISCUSS Elevator
      Pitch`;
  (c) no test-function NAME matches the banned regex
      `^test_.*(returns_\\d+|exit_code|calls_.*_once|status_code|http_\\d+)`.

Exit 0 (all clean) / 1 (>=1 violation) / 2 (malformed input: a missing,
unreadable, or unparseable file -- degrade-LOUD diagnostic naming the file,
NEVER a traceback).

JSON verdict schema this AT specifies (no prior precedent to reuse -- this
suite IS the schema's spec, per ADR-025 DISTILL-authors-the-AT contract):
    {
      "verdict": "clean" | "violations_found" | "malformed_input",
      "violation_count": <int>,
      "violations": [
        {"target": "<file>::<test_name>", "check": "a"|"b"|"c", "how": "<remediation text>"}
      ],
      "diagnostic": "<message>"   # populated only on malformed_input
    }
main() prints exactly this JSON object as its stdout (one `json.loads`
covers the whole captured.out), matching the established
`tests/des/acceptance/test_verify_catalog_coherence.py` precedent.

Active-RED scaffolding (P1-P4, `nw-distill-red-scaffolding`): the module is
absent today, so the import happens INSIDE a helper called from each test
body (hidden-import), never at module top -- collection stays green
(COLLECT >= 5) and the absence surfaces as a semantic AssertionError
(MISSING_FUNCTIONALITY) at runtime, never a collection ImportError (BROKEN).

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the real `des.cli.check_contract_shape_declarations`
CLI driver (`main(argv)`), captured via `capsys` -- no subprocess fork.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Hidden-import helper (P1 + P3): keep the absent module out of collection
# scope; the absence surfaces as a runtime AssertionError inside a test body.
# ---------------------------------------------------------------------------


def _import_check_contract_shape():
    try:
        from des.cli.check_contract_shape_declarations import main
    except ModuleNotFoundError as exc:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: "
            "src/des/cli/check_contract_shape_declarations.py does not exist "
            f"yet ({exc}). Implement `main(argv: list[str] | None = None) "
            "-> int` running the 3 Principle-11 mechanical checks per the "
            "DESIGN contract (feature-delta [REF] Code-Design) before this "
            "AT can pass."
        ) from exc
    return main


# ---------------------------------------------------------------------------
# Fixture test-file builders -- write REAL `.py` test files into tmp_path so
# the tmp fixture content (never this AT file's own content) is what
# `check_contract_shape_declarations` scans.
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _clean_unit_module() -> str:
    return (
        '"""Fixture: a compliant non-acceptance test module."""\n'
        "\n"
        "def test_customer_completes_checkout_successfully():\n"
        '    """CONTRACT_SHAPE: bounded-change\n'
        "\n"
        "    Verifies the customer completes checkout with a valid cart.\n"
        '    """\n'
        "    assert True\n"
    )


def _clean_acceptance_module() -> str:
    return (
        '"""Fixture: a compliant acceptance test module (carries the anchor)."""\n'
        "\n"
        "def test_customer_receives_order_confirmation():\n"
        '    """CONTRACT_SHAPE: pure-function\n'
        "\n"
        "    Outcome anchor: DISCUSS Elevator Pitch\n"
        '    """\n'
        "    assert True\n"
    )


def _check_a_violation_module(docstring_body: str | None) -> str:
    """A non-acceptance test whose docstring lacks `CONTRACT_SHAPE:` --
    `docstring_body is None` renders no docstring at all; a string renders a
    docstring that is present but missing the required substring."""
    lines = [
        '"""Fixture: check (a) violation -- missing CONTRACT_SHAPE tag."""',
        "",
        "def test_customer_completes_checkout_without_shape_tag():",
    ]
    if docstring_body is not None:
        lines.append(f'    """{docstring_body}"""')
    lines.append("    assert True")
    lines.append("")
    return "\n".join(lines)


def _check_c_violation_module(banned_name: str) -> str:
    """A test whose NAME matches the banned regex, but whose docstring IS
    compliant -- isolates check (c) from check (a)."""
    return (
        '"""Fixture: check (c) violation -- banned test-function name."""\n'
        "\n"
        f"def {banned_name}():\n"
        '    """CONTRACT_SHAPE: bounded-change\n'
        "\n"
        "    Verifies a technically-framed outcome (deliberately banned name).\n"
        '    """\n'
        "    assert True\n"
    )


def _check_b_violation_module(docstring_body: str) -> str:
    """An acceptance-path test with a CONTRACT_SHAPE tag but WITHOUT the
    `Outcome anchor: DISCUSS Elevator Pitch` line -- isolates check (b)."""
    return (
        '"""Fixture: check (b) violation -- acceptance test missing the '
        'outcome anchor."""\n'
        "\n"
        "def test_customer_places_order_without_outcome_anchor():\n"
        f'    """{docstring_body}"""\n'
        "    assert True\n"
    )


def _run(capsys: pytest.CaptureFixture[str], *files: Path) -> tuple[int, dict]:
    main = _import_check_contract_shape()
    exit_code = main(["--files", *[str(f) for f in files]])
    captured = capsys.readouterr()
    verdict = json.loads(captured.out)
    return exit_code, verdict


def _violation_by_check(verdict: dict, check_id: str) -> dict:
    matches = [v for v in verdict.get("violations", []) if v.get("check") == check_id]
    assert matches, (
        f"expected >=1 violation for check '{check_id}' in verdict: {verdict!r}"
    )
    return matches[0]


# ---------------------------------------------------------------------------
# Scenario 1 -- POSITIVE: a fully-compliant scope (unit + acceptance files)
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def test_main_returns_zero_for_a_fully_compliant_test_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch

    Every test in scope carries a `CONTRACT_SHAPE:` docstring, no banned
    name, and the acceptance-path test also carries the Outcome anchor ->
    `main` returns 0 and reports zero violations.
    """
    unit_file = _write(tmp_path / "unit" / "test_clean_unit.py", _clean_unit_module())
    acceptance_file = _write(
        tmp_path / "acceptance" / "test_clean_acceptance.py",
        _clean_acceptance_module(),
    )

    exit_code, verdict = _run(capsys, unit_file, acceptance_file)

    assert exit_code == 0, (
        f"expected exit 0 for a fully-compliant scope, got {exit_code}: {verdict!r}"
    )
    assert verdict["verdict"] == "clean", verdict
    assert verdict.get("violation_count", -1) == 0, verdict
    assert verdict.get("violations", ["nonempty"]) == [], verdict


# ---------------------------------------------------------------------------
# Scenario 2 -- POSITIVE: check (a) violation -- missing CONTRACT_SHAPE tag
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "docstring_body",
    [
        None,
        "Verifies the checkout flow completes successfully.",
    ],
    ids=["no_docstring_at_all", "docstring_without_contract_shape_tag"],
)
def test_main_reports_check_a_violation_and_how_to_fix(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    docstring_body: str | None,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    A test whose docstring lacks `CONTRACT_SHAPE:` (absent docstring, or a
    docstring missing the substring) makes `main` return non-zero; the
    verdict names that `file::test`, identifies check (a), and carries a HOW
    mentioning `CONTRACT_SHAPE:`.
    """
    violating_file = _write(
        tmp_path / "unit" / "test_missing_shape.py",
        _check_a_violation_module(docstring_body),
    )

    exit_code, verdict = _run(capsys, violating_file)

    assert exit_code != 0, (
        f"expected non-zero exit on a check (a) violation, got 0: {verdict!r}"
    )
    assert verdict["verdict"] == "violations_found", verdict
    violation = _violation_by_check(verdict, "a")
    assert (
        str(violating_file) in violation["target"]
        and "test_customer_completes_checkout_without_shape_tag" in violation["target"]
    ), violation
    assert "CONTRACT_SHAPE:" in violation.get("how", ""), (
        f"HOW must mention adding a `CONTRACT_SHAPE:` docstring line: {violation!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 -- POSITIVE: check (c) violation -- banned regex test name
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "banned_name",
    [
        "test_returns_200",
        "test_checkout_exit_code",
        "test_service_calls_charge_once",
        "test_returns_status_code",
        "test_payment_http_500",
    ],
)
def test_main_reports_check_c_violation_and_how_to_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], banned_name: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    A test-function name matching the banned regex (technically-framed
    names: `returns_<digits>`, `exit_code`, `calls_..._once`, `status_code`,
    `http_<digits>`) makes `main` return non-zero; the verdict names the
    `file::test`, identifies check (c), and carries a rename HOW.
    """
    violating_file = _write(
        tmp_path / "unit" / "test_banned_name.py",
        _check_c_violation_module(banned_name),
    )

    exit_code, verdict = _run(capsys, violating_file)

    assert exit_code != 0, (
        f"expected non-zero exit on a check (c) violation ({banned_name}), "
        f"got 0: {verdict!r}"
    )
    assert verdict["verdict"] == "violations_found", verdict
    violation = _violation_by_check(verdict, "c")
    assert (
        str(violating_file) in violation["target"]
        and banned_name in violation["target"]
    ), violation
    how_text = violation.get("how", "").lower()
    assert "rename" in how_text or "outcome-named" in how_text, (
        f"HOW must instruct renaming to an outcome-named test: {violation!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 4 -- POSITIVE: check (b) violation -- acceptance test missing the
# Outcome anchor
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "docstring_body",
    [
        "CONTRACT_SHAPE: bounded-change",
        "CONTRACT_SHAPE: bounded-change\n\n    Outcome: something else entirely",
    ],
    ids=["anchor_missing_entirely", "anchor_present_but_wrong_text"],
)
def test_main_reports_check_b_violation_and_how_to_fix(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    docstring_body: str,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    An acceptance-path test (its file path contains `/acceptance/`) with a
    `CONTRACT_SHAPE:` docstring but WITHOUT the `Outcome anchor: DISCUSS
    Elevator Pitch` line makes `main` return non-zero; the verdict names the
    `file::test`, identifies check (b), and carries a HOW mentioning the
    outcome anchor.
    """
    violating_file = _write(
        tmp_path / "acceptance" / "test_missing_anchor.py",
        _check_b_violation_module(docstring_body),
    )

    exit_code, verdict = _run(capsys, violating_file)

    assert exit_code != 0, (
        f"expected non-zero exit on a check (b) violation, got 0: {verdict!r}"
    )
    assert verdict["verdict"] == "violations_found", verdict
    violation = _violation_by_check(verdict, "b")
    assert (
        str(violating_file) in violation["target"]
        and "test_customer_places_order_without_outcome_anchor" in violation["target"]
    ), violation
    how_text = violation.get("how", "")
    assert "Outcome anchor" in how_text or "DISCUSS Elevator Pitch" in how_text, (
        f"HOW must mention the Outcome anchor requirement: {violation!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 5 -- NEGATIVE AT: degrade-LOUD on a missing/unparseable file --
# never a silent exit 0, never a traceback.
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_main_does_not_silently_pass_on_a_missing_or_unparseable_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    A `--files` scope naming a path that does not exist on disk must NOT
    produce a clean exit 0 (that WRONG outcome is what this negative AT
    asserts is absent) -- `main` must return exit 2 (malformed input) with a
    diagnostic naming the missing file, and it must never raise/crash with a
    raw traceback.
    """
    main = _import_check_contract_shape()
    missing_path = tmp_path / "does_not_exist" / "test_absent.py"

    try:
        exit_code = main(["--files", str(missing_path)])
    except Exception as exc:
        pytest.fail(
            "degrade-LOUD violation: a missing --files path must return exit "
            f"2 + diagnostic, not raise {type(exc).__name__}: {exc}"
        )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err

    assert exit_code == 2, (
        "degrade-LOUD violation: a missing/unparseable file must return exit "
        f"2 (malformed input); got {exit_code}. WRONG outcome (a silent exit "
        "0) must NOT be produced."
    )
    assert "Traceback" not in combined_output, (
        "degrade-LOUD violation: a missing file crashed with a raw traceback "
        f"instead of a diagnostic verdict:\n{combined_output}"
    )
    assert str(missing_path) in combined_output, (
        f"diagnostic must name the missing file {missing_path!s}: {combined_output!r}"
    )
