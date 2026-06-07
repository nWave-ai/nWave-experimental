"""Step definitions — slice-04: D1 inventory-closure human-readable gate surfaces.

F-D1-HUMAN-READABLE-GATE-SURFACES slice-04. Layer 3 (subprocess / FS
acceptance): two driving ports — ``scripts/cli/check_reuse_first_design.py``
and ``scripts/cli/check_scorecard_freshness.py``. The only driven port is
the real filesystem (tmp_path repository carrying per-CLI minimal artefacts,
including an initialised git repo under scorecard/ for the freshness probe).
Example-based ATs (Mandate 11) — three Scenario Outlines × two Examples rows
parametrize-collapse the GREEN PATH × NEGATIVE PATH × NO-TTY decision-table
cells across the closure pair (max-density per
[[feedback_ats_max_pbt_parametrize_density_2026_05_19]]; carpaccio counts
each Outline as ONE AT — total 3 ATs, fits ``carpaccio_slice_max: 3``).

Step bodies delegate to ``ClosureSurfaceFixture`` — typed enum lookup plus a
composition call, no inline logic (Mandate-12 criterion 3). The When-step
asserts the repo filesystem-presence flags are unchanged by the gate
invocation via ``assert_state_delta`` over a port-exposed universe
(Mandate 8).

This slice is RED-for-the-right-reason against master: the slice-01 helper
module ``src/des/cli/human_surface.py`` exists and works (slice-01 SHIPPED
49b1b72349), but the two closure CLIs have NOT yet been wired to import and
call ``print_human_summary`` — so each Scenario Outline row FAILS because
the colored verdict line is missing from stderr (missing functionality,
Mandate 7). The DELIVER loop adds the per-CLI helper adoption; the present
scaffold drives that delivery. After slice-04 lands every D1 gate CLI in
the 9-gate inventory emits the human surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import ClosureSurfaceFixture
from .domain_types import (
    CLOSURE_CLI_BY_PHRASE,
    ClosureCli,
    StderrMode,
)


scenarios("../slice-04-closure-human-surface.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def closure_composition(tmp_path: Path) -> ClosureSurfaceFixture:
    """Production-wired composition root over a tmp_path repository."""
    return ClosureSurfaceFixture(repo_root=tmp_path / "repo")


@pytest.fixture
def closure_result_box() -> dict[str, object]:
    """Carrier for the per-row CLI result + invocation context across steps."""
    return {}


# --- Background -------------------------------------------------------------


@given("a tmp_path repository prepared for the D1 inventory closure pair")
def given_tmp_path_repo(closure_composition: ClosureSurfaceFixture) -> None:
    closure_composition.repo_root.mkdir(parents=True, exist_ok=True)


# --- Given (per-CLI staging) -----------------------------------------------


@given(parsers.parse("the staged repository satisfies the success path for {gate}"))
def given_success_path_closure(
    closure_composition: ClosureSurfaceFixture,
    closure_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: ClosureCli = CLOSURE_CLI_BY_PHRASE[gate]
    invocation_context = closure_composition.stage_for_cli(cli, success_path=True)
    closure_result_box["cli"] = cli
    closure_result_box["invocation_context"] = invocation_context
    closure_result_box["success"] = True


@given(parsers.parse("the staged repository satisfies the negative path for {gate}"))
def given_negative_path_closure(
    closure_composition: ClosureSurfaceFixture,
    closure_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: ClosureCli = CLOSURE_CLI_BY_PHRASE[gate]
    invocation_context = closure_composition.stage_for_cli(cli, success_path=False)
    closure_result_box["cli"] = cli
    closure_result_box["invocation_context"] = invocation_context
    closure_result_box["success"] = False


# --- When -------------------------------------------------------------------


@when(
    parsers.parse(
        "the operator runs {gate} against the repository inside a real terminal"
    )
)
def when_run_under_tty_closure(
    closure_composition: ClosureSurfaceFixture,
    closure_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: ClosureCli = CLOSURE_CLI_BY_PHRASE[gate]
    invocation_context = closure_result_box["invocation_context"]
    before = closure_composition.capture_universe()
    closure_result_box["result_tty"] = closure_composition.run_cli_capturing_surface(
        cli, StderrMode.TTY, invocation_context
    )
    after = closure_composition.capture_universe()
    # Each closure CLI is pure-function read over its staged inputs:
    # the file-presence flags (reuse-first feature-delta + diff-source;
    # scorecard.md + .git directory) MUST NOT change as a result of the
    # gate invocation. Universe is port-exposed presence flags (Mandate 8).
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "reuse_first_feature_delta.present",
            "reuse_first_diff_source.present",
            "scorecard.present",
            "scorecard_git_dir.present",
        },
        expected={
            "reuse_first_feature_delta.present": unchanged(),
            "reuse_first_diff_source.present": unchanged(),
            "scorecard.present": unchanged(),
            "scorecard_git_dir.present": unchanged(),
        },
    )


@when(
    parsers.parse(
        "the operator runs {gate} against the repository under a non terminal stderr"
    )
)
def when_run_under_pipe_closure(
    closure_composition: ClosureSurfaceFixture,
    closure_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: ClosureCli = CLOSURE_CLI_BY_PHRASE[gate]
    invocation_context = closure_result_box["invocation_context"]
    # The NO-TTY Outline captures BOTH a PIPE run AND a TTY companion run
    # to compare the structured surface byte content across channels. The
    # TTY companion is staged here so the Then-step can assert the existing
    # surface contract is unchanged across modes.
    before = closure_composition.capture_universe()
    closure_result_box["result_pipe"] = closure_composition.run_cli_capturing_surface(
        cli, StderrMode.PIPE, invocation_context
    )
    closure_result_box["result_tty_companion"] = (
        closure_composition.run_cli_capturing_surface(
            cli, StderrMode.TTY, invocation_context
        )
    )
    after = closure_composition.capture_universe()
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "reuse_first_feature_delta.present",
            "reuse_first_diff_source.present",
            "scorecard.present",
            "scorecard_git_dir.present",
        },
        expected={
            "reuse_first_feature_delta.present": unchanged(),
            "reuse_first_diff_source.present": unchanged(),
            "scorecard.present": unchanged(),
            "scorecard_git_dir.present": unchanged(),
        },
    )


# --- Then -------------------------------------------------------------------


@then(
    parsers.parse(
        "the existing structured surface for {gate} remains stable on the success path"
    )
)
def then_structured_surface_stable_success_closure(
    closure_composition: ClosureSurfaceFixture,
    closure_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: ClosureCli = CLOSURE_CLI_BY_PHRASE[gate]
    result = closure_result_box.get("result_tty") or closure_result_box.get(
        "result_pipe"
    )
    assert closure_composition.structured_surface_stable_for(
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
def then_structured_surface_stable_negative_closure(
    closure_composition: ClosureSurfaceFixture,
    closure_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: ClosureCli = CLOSURE_CLI_BY_PHRASE[gate]
    result = closure_result_box["result_tty"]
    assert closure_composition.structured_surface_stable_for(
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
def then_stderr_success_verdict_line_closure(
    closure_composition: ClosureSurfaceFixture,
    closure_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: ClosureCli = CLOSURE_CLI_BY_PHRASE[gate]
    result = closure_result_box["result_tty"]
    expected_verdict = closure_composition.success_verdict_for(cli)
    assert closure_composition.stderr_carries_verdict_line(result, expected_verdict), (
        f"stderr (TTY mode) missing {expected_verdict.value} line for {gate}; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )
    assert closure_composition.stderr_verdict_line_carries_color(
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
def then_stderr_negative_verdict_line_closure(
    closure_composition: ClosureSurfaceFixture,
    closure_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: ClosureCli = CLOSURE_CLI_BY_PHRASE[gate]
    result = closure_result_box["result_tty"]
    expected_verdict = closure_composition.negative_verdict_for(cli)
    assert closure_composition.stderr_carries_verdict_line(result, expected_verdict), (
        f"stderr (TTY mode) missing {expected_verdict.value} line for {gate}; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )
    assert closure_composition.stderr_verdict_line_carries_color(
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
def then_stderr_plain_success_line_closure(
    closure_composition: ClosureSurfaceFixture,
    closure_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: ClosureCli = CLOSURE_CLI_BY_PHRASE[gate]
    result = closure_result_box["result_pipe"]
    expected_verdict = closure_composition.success_verdict_for(cli)
    assert closure_composition.stderr_carries_verdict_line(result, expected_verdict), (
        f"stderr (pipe mode) missing {expected_verdict.value} line for {gate}; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )
    assert closure_composition.stderr_carries_no_ansi_escapes(result), (
        f"stderr (pipe mode) for {gate} carries ANSI escapes — color must be "
        f"stripped when stderr is not a TTY; stderr_raw=\n{result.stderr_raw!r}"
    )


@then(
    parsers.parse(
        "the existing structured surface for {gate} equals the surface observed when stderr is a real terminal"
    )
)
def then_structured_surface_matches_across_modes_closure(
    closure_composition: ClosureSurfaceFixture,
    closure_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: ClosureCli = CLOSURE_CLI_BY_PHRASE[gate]
    result_pipe = closure_result_box["result_pipe"]
    result_tty = closure_result_box["result_tty_companion"]
    assert closure_composition.structured_surface_matches_across_modes(
        cli, result_pipe, result_tty
    ), (
        f"structured surface for {gate} diverges across pipe vs tty stderr; "
        f"pipe stdout=\n{result_pipe.stdout!r}\npipe stderr_raw=\n"
        f"{result_pipe.stderr_raw!r}\ntty stdout=\n{result_tty.stdout!r}\n"
        f"tty stderr_raw=\n{result_tty.stderr_raw!r}"
    )
