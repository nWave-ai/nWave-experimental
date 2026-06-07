"""Step definitions — slice-03: D1 gate-class-triple human-readable gate surfaces.

F-D1-HUMAN-READABLE-GATE-SURFACES slice-03. Layer 3 (subprocess / FS
acceptance): three driving ports — ``des.cli.verify_environmental_e2e``
(``--mode verify-authored``), ``scripts/cli/verify_coverage_map.py``
(``verify`` subcommand), ``scripts/cli/check_robustness_density.py``. The
only driven port is the real filesystem (tmp_path repository carrying per-CLI
minimal artefacts). Example-based ATs (Mandate 11) — three Scenario Outlines
× three Examples rows parametrize-collapse the GREEN PATH × NEGATIVE PATH ×
NO-TTY decision-table cells across the gate-class triple (max-density per
[[feedback_ats_max_pbt_parametrize_density_2026_05_19]]; carpaccio counts
each Outline as ONE AT — total 3 ATs, fits ``carpaccio_slice_max: 3``).

Step bodies delegate to ``GateClassTripleSurfaceFixture`` — typed enum lookup
plus a composition call, no inline logic (Mandate-12 criterion 3). The When-
step asserts the repo filesystem-presence flags are unchanged by the gate
invocation via ``assert_state_delta`` over a port-exposed universe
(Mandate 8).

This slice is RED-for-the-right-reason against master: the slice-01 helper
module ``src/des/cli/human_surface.py`` exists and works (slice-01 SHIPPED
49b1b72349), but the three gate-class CLIs have NOT yet been wired to import
and call ``print_human_summary`` — so each Scenario Outline row FAILS
because the colored verdict line is missing from stderr (missing
functionality, Mandate 7). The DELIVER loop adds the per-CLI helper
adoption; the present scaffold drives that delivery.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import GateClassTripleSurfaceFixture
from .domain_types import (
    GATE_CLASS_CLI_BY_PHRASE,
    GateClassCli,
    StderrMode,
)


scenarios("../slice-03-gate-class-triple-human-surface.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def gate_class_composition(tmp_path: Path) -> GateClassTripleSurfaceFixture:
    """Production-wired composition root over a tmp_path repository."""
    return GateClassTripleSurfaceFixture(repo_root=tmp_path / "repo")


@pytest.fixture
def gate_class_result_box() -> dict[str, object]:
    """Carrier for the per-row CLI result + invocation context across steps."""
    return {}


# --- Background -------------------------------------------------------------


@given("a tmp_path repository prepared for the D1 gate-class triple")
def given_tmp_path_repo(gate_class_composition: GateClassTripleSurfaceFixture) -> None:
    gate_class_composition.repo_root.mkdir(parents=True, exist_ok=True)


# --- Given (per-CLI staging) -----------------------------------------------


@given(parsers.parse("the staged repository satisfies the success path for {gate}"))
def given_success_path_gate_class(
    gate_class_composition: GateClassTripleSurfaceFixture,
    gate_class_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: GateClassCli = GATE_CLASS_CLI_BY_PHRASE[gate]
    invocation_context = gate_class_composition.stage_for_cli(cli, success_path=True)
    gate_class_result_box["cli"] = cli
    gate_class_result_box["invocation_context"] = invocation_context
    gate_class_result_box["success"] = True


@given(parsers.parse("the staged repository satisfies the negative path for {gate}"))
def given_negative_path_gate_class(
    gate_class_composition: GateClassTripleSurfaceFixture,
    gate_class_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: GateClassCli = GATE_CLASS_CLI_BY_PHRASE[gate]
    invocation_context = gate_class_composition.stage_for_cli(cli, success_path=False)
    gate_class_result_box["cli"] = cli
    gate_class_result_box["invocation_context"] = invocation_context
    gate_class_result_box["success"] = False


# --- When -------------------------------------------------------------------


@when(
    parsers.parse(
        "the operator runs {gate} against the repository inside a real terminal"
    )
)
def when_run_under_tty_gate_class(
    gate_class_composition: GateClassTripleSurfaceFixture,
    gate_class_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: GateClassCli = GATE_CLASS_CLI_BY_PHRASE[gate]
    invocation_context = gate_class_result_box["invocation_context"]
    before = gate_class_composition.capture_universe()
    gate_class_result_box["result_tty"] = (
        gate_class_composition.run_cli_capturing_surface(
            cli, StderrMode.TTY, invocation_context
        )
    )
    after = gate_class_composition.capture_universe()
    # Each gate-class CLI is pure-function read over its staged inputs:
    # the file-presence flags (env-e2e feature-delta, coverage-map.md,
    # robustness declaration + AT-scope) MUST NOT change as a result of the
    # gate invocation. Universe is port-exposed presence flags (Mandate 8).
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "env_e2e_feature_delta.present",
            "coverage_map.present",
            "robustness_declaration.present",
            "robustness_at_scope.present",
        },
        expected={
            "env_e2e_feature_delta.present": unchanged(),
            "coverage_map.present": unchanged(),
            "robustness_declaration.present": unchanged(),
            "robustness_at_scope.present": unchanged(),
        },
    )


@when(
    parsers.parse(
        "the operator runs {gate} against the repository under a non terminal stderr"
    )
)
def when_run_under_pipe_gate_class(
    gate_class_composition: GateClassTripleSurfaceFixture,
    gate_class_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: GateClassCli = GATE_CLASS_CLI_BY_PHRASE[gate]
    invocation_context = gate_class_result_box["invocation_context"]
    # The NO-TTY Outline captures BOTH a PIPE run AND a TTY companion run to
    # compare the structured surface byte content across channels. The TTY
    # companion is staged here so the Then-step can assert the existing
    # surface contract is unchanged across modes.
    before = gate_class_composition.capture_universe()
    gate_class_result_box["result_pipe"] = (
        gate_class_composition.run_cli_capturing_surface(
            cli, StderrMode.PIPE, invocation_context
        )
    )
    gate_class_result_box["result_tty_companion"] = (
        gate_class_composition.run_cli_capturing_surface(
            cli, StderrMode.TTY, invocation_context
        )
    )
    after = gate_class_composition.capture_universe()
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "env_e2e_feature_delta.present",
            "coverage_map.present",
            "robustness_declaration.present",
            "robustness_at_scope.present",
        },
        expected={
            "env_e2e_feature_delta.present": unchanged(),
            "coverage_map.present": unchanged(),
            "robustness_declaration.present": unchanged(),
            "robustness_at_scope.present": unchanged(),
        },
    )


# --- Then -------------------------------------------------------------------


@then(
    parsers.parse(
        "the existing structured surface for {gate} remains stable on the success path"
    )
)
def then_structured_surface_stable_success(
    gate_class_composition: GateClassTripleSurfaceFixture,
    gate_class_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: GateClassCli = GATE_CLASS_CLI_BY_PHRASE[gate]
    result = gate_class_result_box.get("result_tty") or gate_class_result_box.get(
        "result_pipe"
    )
    assert gate_class_composition.structured_surface_stable_for(
        cli, result, success=True
    ), (
        f"existing structured surface for {gate} did not match the success-path "
        f"contract; stdout=\n{result.stdout!r}\nstderr_raw=\n{result.stderr_raw!r}"
    )


@then(
    parsers.parse(
        "the existing structured surface for {gate} remains stable on the negative path"
    )
)
def then_structured_surface_stable_negative(
    gate_class_composition: GateClassTripleSurfaceFixture,
    gate_class_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: GateClassCli = GATE_CLASS_CLI_BY_PHRASE[gate]
    result = gate_class_result_box["result_tty"]
    assert gate_class_composition.structured_surface_stable_for(
        cli, result, success=False
    ), (
        f"existing structured surface for {gate} did not match the negative-path "
        f"contract; stdout=\n{result.stdout!r}\nstderr_raw=\n{result.stderr_raw!r}"
    )


@then(
    parsers.parse(
        "the stderr carries the success colored verdict line summarising the {gate} outcome"
    )
)
def then_stderr_success_verdict_line(
    gate_class_composition: GateClassTripleSurfaceFixture,
    gate_class_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: GateClassCli = GATE_CLASS_CLI_BY_PHRASE[gate]
    result = gate_class_result_box["result_tty"]
    expected_verdict = gate_class_composition.success_verdict_for(cli)
    assert gate_class_composition.stderr_carries_verdict_line(
        result, expected_verdict
    ), (
        f"stderr (TTY mode) missing {expected_verdict.value} line for {gate}; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )
    assert gate_class_composition.stderr_verdict_line_carries_color(
        result, expected_verdict
    ), (
        f"{expected_verdict.value} line for {gate} missing matching ANSI color; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )


@then(
    parsers.parse(
        "the stderr carries the negative colored verdict line summarising the {gate} outcome"
    )
)
def then_stderr_negative_verdict_line_gate_class(
    gate_class_composition: GateClassTripleSurfaceFixture,
    gate_class_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: GateClassCli = GATE_CLASS_CLI_BY_PHRASE[gate]
    result = gate_class_result_box["result_tty"]
    expected_verdict = gate_class_composition.negative_verdict_for(cli)
    assert gate_class_composition.stderr_carries_verdict_line(
        result, expected_verdict
    ), (
        f"stderr (TTY mode) missing {expected_verdict.value} line for {gate}; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )
    assert gate_class_composition.stderr_verdict_line_carries_color(
        result, expected_verdict
    ), (
        f"{expected_verdict.value} line for {gate} missing matching ANSI color; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )


@then(
    parsers.parse(
        "the stderr carries a plain readable success line summarising the {gate} outcome with no ANSI escapes"
    )
)
def then_stderr_plain_success_line(
    gate_class_composition: GateClassTripleSurfaceFixture,
    gate_class_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: GateClassCli = GATE_CLASS_CLI_BY_PHRASE[gate]
    result = gate_class_result_box["result_pipe"]
    expected_verdict = gate_class_composition.success_verdict_for(cli)
    assert gate_class_composition.stderr_carries_verdict_line(
        result, expected_verdict
    ), (
        f"stderr (pipe mode) missing {expected_verdict.value} line for {gate}; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )
    assert gate_class_composition.stderr_carries_no_ansi_escapes(result), (
        f"stderr (pipe mode) for {gate} carries ANSI escapes — color must be "
        f"stripped when stderr is not a TTY; stderr_raw=\n{result.stderr_raw!r}"
    )


@then(
    parsers.parse(
        "the existing structured surface for {gate} equals the surface observed when stderr is a real terminal"
    )
)
def then_structured_surface_matches_across_modes(
    gate_class_composition: GateClassTripleSurfaceFixture,
    gate_class_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: GateClassCli = GATE_CLASS_CLI_BY_PHRASE[gate]
    result_pipe = gate_class_result_box["result_pipe"]
    result_tty = gate_class_result_box["result_tty_companion"]
    assert gate_class_composition.structured_surface_matches_across_modes(
        cli, result_pipe, result_tty
    ), (
        f"structured surface for {gate} diverges across pipe vs tty stderr; "
        f"pipe stdout=\n{result_pipe.stdout!r}\npipe stderr_raw=\n"
        f"{result_pipe.stderr_raw!r}\ntty stdout=\n{result_tty.stdout!r}\n"
        f"tty stderr_raw=\n{result_tty.stderr_raw!r}"
    )
