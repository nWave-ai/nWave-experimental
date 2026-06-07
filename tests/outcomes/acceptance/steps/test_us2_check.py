"""Step definitions for US-2 check scenarios (Tier-1 + Tier-2 verdict).

Per Mandate 5: invokes the real `nwave-ai outcomes` console subcommand
via subprocess (no in-process import). Real YAML filesystem under
tmp_path (Strategy C — real local).
"""

from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when


scenarios("../test_us2_check.feature")


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given(
    parsers.parse(
        '{outcome_id} has been registered with input shape "{input_shape}" '
        'and output shape "{output_shape}" and keywords "{keywords}"'
    )
)
def _register_precondition(
    run_cli,
    outcome_id: str,
    input_shape: str,
    output_shape: str,
    keywords: str,
) -> None:
    result = run_cli(
        "outcomes",
        "register",
        "--id",
        outcome_id,
        "--kind",
        "specification",
        "--summary",
        "US-2 precondition outcome",
        "--feature",
        "outcomes-registry",
        "--input-shape",
        input_shape,
        "--output-shape",
        output_shape,
        "--keywords",
        keywords,
        "--artifact",
        "nwave_ai/outcomes/cli.py",
    )
    assert result.exit_code == 0, (
        f"precondition register failed: exit={result.exit_code} "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(
    parsers.parse(
        'the author runs check with input shape "{input_shape}" and output '
        'shape "{output_shape}" and keywords "{keywords}"'
    )
)
def _run_check(
    run_cli,
    state: dict,
    input_shape: str,
    output_shape: str,
    keywords: str,
) -> None:
    state["check_result"] = run_cli(
        "outcomes",
        "check",
        "--input-shape",
        input_shape,
        "--output-shape",
        output_shape,
        "--keywords",
        keywords,
    )


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------


@then(parsers.parse("the CLI check exit code is {code:d}"))
def _check_exit_code(state: dict, code: int) -> None:
    result = state["check_result"]
    assert result.exit_code == code, (
        f"expected exit {code}, got {result.exit_code}\n"
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


@then(parsers.parse('stdout contains "{needle}"'))
def _stdout_contains(state: dict, needle: str) -> None:
    result = state["check_result"]
    assert needle in result.stdout, (
        f"expected {needle!r} in stdout; got stdout={result.stdout!r}"
    )
