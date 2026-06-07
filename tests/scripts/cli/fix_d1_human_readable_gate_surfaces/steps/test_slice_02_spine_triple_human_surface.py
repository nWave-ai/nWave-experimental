"""Step definitions — slice-02: D1 spine-triple human-readable gate surfaces.

F-D1-HUMAN-READABLE-GATE-SURFACES slice-02. Layer 3 (subprocess / FS
acceptance): three driving ports —
``des.cli.verify_slice_commit_completeness``, ``des.cli.carpaccio_slice_gate``,
``scripts/cli/at_review_verdict.py``. The only driven port is the real
filesystem (tmp_path repository carrying per-CLI minimal artefacts).
Example-based ATs (Mandate 11) — three Scenario Outlines × three Examples
rows parametrize-collapse the GREEN PATH × NEGATIVE PATH × NO-TTY decision-
table cells across the spine triple (max-density per
[[feedback_ats_max_pbt_parametrize_density_2026_05_19]]; carpaccio counts
each Outline as ONE AT — total 3 ATs, fits ``carpaccio_slice_max: 3``).

Step bodies delegate to ``SpineTripleSurfaceFixture`` — typed enum lookup
plus a composition call, no inline logic (Mandate-12 criterion 3). The When-
step asserts the repo filesystem-presence flags are unchanged by the gate
invocation via ``assert_state_delta`` over a port-exposed universe
(Mandate 8).

This slice is RED-for-the-right-reason against master: the slice-01 helper
module ``src/des/cli/human_surface.py`` exists and works (slice-01 SHIPPED
49b1b72349), but the three spine-triple CLIs have NOT yet been wired to
import and call ``print_human_summary`` — so each Scenario Outline row FAILS
because the colored verdict line is missing from stderr (missing
functionality, Mandate 7). The DELIVER loop adds the per-CLI helper
adoption; the present scaffold drives that delivery.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import SpineTripleSurfaceFixture
from .domain_types import (
    SPINE_GATE_CLI_BY_PHRASE,
    HumanSurfaceVerdict,
    SpineGateCli,
    StderrMode,
)


scenarios("../slice-02-spine-triple-human-surface.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def spine_composition(tmp_path: Path) -> SpineTripleSurfaceFixture:
    """Production-wired composition root over a tmp_path repository."""
    return SpineTripleSurfaceFixture(repo_root=tmp_path / "repo")


@pytest.fixture
def spine_result_box() -> dict[str, object]:
    """Carrier for the per-row CLI result + invocation context across steps."""
    return {}


# --- Background -------------------------------------------------------------


@given("a tmp_path repository prepared for the D1 spine-triple gates")
def given_tmp_path_repo(spine_composition: SpineTripleSurfaceFixture) -> None:
    spine_composition.repo_root.mkdir(parents=True, exist_ok=True)


# --- Given (per-CLI staging) -----------------------------------------------


@given(parsers.parse("the staged repository satisfies the success path for {gate}"))
def given_success_path(
    spine_composition: SpineTripleSurfaceFixture,
    spine_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: SpineGateCli = SPINE_GATE_CLI_BY_PHRASE[gate]
    invocation_context = spine_composition.stage_for_cli(cli, success_path=True)
    spine_result_box["cli"] = cli
    spine_result_box["invocation_context"] = invocation_context
    spine_result_box["success"] = True


@given(parsers.parse("the staged repository satisfies the negative path for {gate}"))
def given_negative_path(
    spine_composition: SpineTripleSurfaceFixture,
    spine_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: SpineGateCli = SPINE_GATE_CLI_BY_PHRASE[gate]
    invocation_context = spine_composition.stage_for_cli(cli, success_path=False)
    spine_result_box["cli"] = cli
    spine_result_box["invocation_context"] = invocation_context
    spine_result_box["success"] = False


# --- When -------------------------------------------------------------------


@when(
    parsers.parse(
        "the operator runs {gate} against the repository inside a real terminal"
    )
)
def when_run_under_tty(
    spine_composition: SpineTripleSurfaceFixture,
    spine_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: SpineGateCli = SPINE_GATE_CLI_BY_PHRASE[gate]
    invocation_context = spine_result_box["invocation_context"]
    before = spine_composition.capture_universe()
    spine_result_box["result_tty"] = spine_composition.run_cli_capturing_surface(
        cli, StderrMode.TTY, invocation_context
    )
    after = spine_composition.capture_universe()
    # Each spine-triple gate is pure-function read over its staged inputs:
    # the file-presence flags (feature-delta, the slice's .feature file, the
    # git repo, the ledger directory) MUST NOT change as a result of the
    # gate invocation. Universe is port-exposed presence flags (Mandate 8).
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "feature_delta.present",
            "feature_at.present",
            "git_dir.present",
            "ledger_dir.present",
        },
        expected={
            "feature_delta.present": unchanged(),
            "feature_at.present": unchanged(),
            "git_dir.present": unchanged(),
            "ledger_dir.present": unchanged(),
        },
    )


@when(
    parsers.parse(
        "the operator runs {gate} against the repository under a non terminal stderr"
    )
)
def when_run_under_pipe(
    spine_composition: SpineTripleSurfaceFixture,
    spine_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: SpineGateCli = SPINE_GATE_CLI_BY_PHRASE[gate]
    invocation_context = spine_result_box["invocation_context"]
    # The NO-TTY Outline captures BOTH a PIPE run AND a TTY companion run to
    # compare JSON event byte content across channels. The TTY companion is
    # staged here so the Then-step can assert the structured contract is
    # unchanged across modes.
    before = spine_composition.capture_universe()
    spine_result_box["result_pipe"] = spine_composition.run_cli_capturing_surface(
        cli, StderrMode.PIPE, invocation_context
    )
    spine_result_box["result_tty_companion"] = (
        spine_composition.run_cli_capturing_surface(
            cli, StderrMode.TTY, invocation_context
        )
    )
    after = spine_composition.capture_universe()
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "feature_delta.present",
            "feature_at.present",
            "git_dir.present",
            "ledger_dir.present",
        },
        expected={
            "feature_delta.present": unchanged(),
            "feature_at.present": unchanged(),
            "git_dir.present": unchanged(),
            "ledger_dir.present": unchanged(),
        },
    )


# --- Then -------------------------------------------------------------------


@then(parsers.parse("the stderr carries a single-line JSON success event for {gate}"))
def then_stderr_carries_success_event(
    spine_composition: SpineTripleSurfaceFixture,
    spine_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: SpineGateCli = SPINE_GATE_CLI_BY_PHRASE[gate]
    result = spine_result_box.get("result_tty") or spine_result_box.get("result_pipe")
    event = spine_composition.extract_event(cli, result, success=True)
    assert event is not None, (
        f"no single-line JSON success event for {gate} on stderr; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )


@then(parsers.parse("the stderr carries a single-line JSON negative event for {gate}"))
def then_stderr_carries_negative_event(
    spine_composition: SpineTripleSurfaceFixture,
    spine_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: SpineGateCli = SPINE_GATE_CLI_BY_PHRASE[gate]
    result = spine_result_box["result_tty"]
    event = spine_composition.extract_event(cli, result, success=False)
    assert event is not None, (
        f"no single-line JSON negative event for {gate} on stderr; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )


@then(
    parsers.parse(
        "the stderr carries a green colored PASS line summarising the {gate} outcome"
    )
)
def then_stderr_green_pass_line(
    spine_composition: SpineTripleSurfaceFixture,
    spine_result_box: dict[str, object],
    gate: str,
) -> None:
    result = spine_result_box["result_tty"]
    assert spine_composition.stderr_carries_verdict_line(
        result, HumanSurfaceVerdict.PASS
    ), (
        f"stderr (TTY mode) missing ✅ PASS line for {gate}; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )
    assert spine_composition.stderr_verdict_line_carries_color(
        result, HumanSurfaceVerdict.PASS
    ), (
        f"PASS line for {gate} missing green ANSI escape (\\x1b[32m); "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )


@then(
    parsers.parse(
        "the stderr carries the negative colored verdict line summarising the {gate} outcome"
    )
)
def then_stderr_negative_verdict_line(
    spine_composition: SpineTripleSurfaceFixture,
    spine_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: SpineGateCli = SPINE_GATE_CLI_BY_PHRASE[gate]
    result = spine_result_box["result_tty"]
    expected_verdict = spine_composition.negative_verdict_for(cli)
    assert spine_composition.stderr_carries_verdict_line(result, expected_verdict), (
        f"stderr (TTY mode) missing {expected_verdict.value} line for {gate}; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )
    assert spine_composition.stderr_verdict_line_carries_color(
        result, expected_verdict
    ), (
        f"{expected_verdict.value} line for {gate} missing matching ANSI color; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )


@then(
    parsers.parse(
        "the stderr carries a plain readable PASS line summarising the {gate} outcome with no ANSI escapes"
    )
)
def then_stderr_plain_pass_line(
    spine_composition: SpineTripleSurfaceFixture,
    spine_result_box: dict[str, object],
    gate: str,
) -> None:
    result = spine_result_box["result_pipe"]
    assert spine_composition.stderr_carries_verdict_line(
        result, HumanSurfaceVerdict.PASS
    ), (
        f"stderr (pipe mode) missing ✅ PASS line for {gate}; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )
    assert spine_composition.stderr_carries_no_ansi_escapes(result), (
        f"stderr (pipe mode) for {gate} carries ANSI escapes — color must be "
        f"stripped when stderr is not a TTY; stderr_raw=\n{result.stderr_raw!r}"
    )


@then(
    parsers.parse(
        "the JSON success event for {gate} equals the event observed when stderr is a real terminal"
    )
)
def then_json_event_matches_across_modes(
    spine_composition: SpineTripleSurfaceFixture,
    spine_result_box: dict[str, object],
    gate: str,
) -> None:
    cli: SpineGateCli = SPINE_GATE_CLI_BY_PHRASE[gate]
    result_pipe = spine_result_box["result_pipe"]
    result_tty = spine_result_box["result_tty_companion"]
    assert spine_composition.event_matches_across_modes(cli, result_pipe, result_tty), (
        f"JSON success event for {gate} diverges across pipe vs tty stderr; "
        f"pipe stderr_raw=\n{result_pipe.stderr_raw!r}\n"
        f"tty stderr_raw=\n{result_tty.stderr_raw!r}"
    )
