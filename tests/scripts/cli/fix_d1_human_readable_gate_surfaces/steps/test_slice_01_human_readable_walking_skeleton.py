"""Step definitions — slice-01: human-readable gate surface walking skeleton.

F-D1-HUMAN-READABLE-GATE-SURFACES slice-01. Layer 3 (subprocess / FS
acceptance): the ``des.cli.run_contract_gate`` CLI is the driving port; the
only driven port is the real filesystem (tmp_path repository carrying a
minimal pytest suite). Example-based ATs (Mandate 11) — three scenarios cover
the GREEN PATH × FAIL PATH × NO-TTY PRESERVATION decision-table cells.

Step bodies delegate to ``HumanSurfaceFixture`` — typed lookup plus a
composition call, no inline logic (Mandate-12 criterion 3). The When-step
asserts the repo filesystem is unchanged by the gate invocation (verify is a
pure-function read over the contract suite) via ``assert_state_delta`` over
a port-exposed universe (Mandate 8).

This slice is RED-for-the-right-reason against the slice-01 production
``human_surface`` scaffold + the ``run_contract_gate`` extension — the helper
module's ``print_human_summary`` raises ``AssertionError`` AND the gate has
not yet been wired to call it (Mandate 7). The DELIVER loop adds the real
ANSI emit + TTY detection + ``run_contract_gate`` extension; the present
scaffold drives that delivery.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition import HumanSurfaceFixture
from .domain_types import (
    STDERR_MODE_BY_PHRASE,
    SUITE_OUTCOME_BY_PHRASE,
    StderrMode,
    SuiteOutcome,
)


scenarios("../slice-01-human-readable-walking-skeleton.feature")


# --- Fixtures --------------------------------------------------------------


@pytest.fixture
def composition(tmp_path: Path) -> HumanSurfaceFixture:
    """Production-wired composition root over a tmp_path repository."""
    return HumanSurfaceFixture(repo_root=tmp_path / "repo")


@pytest.fixture
def result_box() -> dict[str, object]:
    """Carrier for the CLI result + scenario-derived state across steps."""
    return {}


# --- Background -------------------------------------------------------------


@given(
    "a tmp_path repository carrying a minimal pytest suite the contract gate can run"
)
def given_tmp_path_repo(composition: HumanSurfaceFixture) -> None:
    composition.repo_root.mkdir(parents=True, exist_ok=True)


# --- Given ------------------------------------------------------------------


@given("the minimal pytest suite is configured to pass")
def given_suite_passing(
    composition: HumanSurfaceFixture, result_box: dict[str, object]
) -> None:
    outcome: SuiteOutcome = SUITE_OUTCOME_BY_PHRASE[
        "the minimal pytest suite is configured to pass"
    ]
    composition.stage_minimal_repo(outcome)


@given("the minimal pytest suite is configured to fail")
def given_suite_failing(
    composition: HumanSurfaceFixture, result_box: dict[str, object]
) -> None:
    outcome: SuiteOutcome = SUITE_OUTCOME_BY_PHRASE[
        "the minimal pytest suite is configured to fail"
    ]
    composition.stage_minimal_repo(outcome)


# --- When -------------------------------------------------------------------


@when(
    "the operator runs the contract gate against the repository inside a real terminal"
)
def when_run_under_tty(
    composition: HumanSurfaceFixture, result_box: dict[str, object]
) -> None:
    mode: StderrMode = STDERR_MODE_BY_PHRASE[
        "the operator runs the contract gate against the repository inside a real terminal"
    ]
    before = composition.capture_universe()
    result_box["result_tty"] = composition.run_contract_gate(mode)
    after = composition.capture_universe()
    # The contract gate is a pure-function read over the staged repo: it
    # collects + runs tests, but the staged repo files are not modified.
    # Universe is port-exposed file-presence flags (Mandate 8).
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "tests_dir.present",
            "pyproject.present",
            "conftest.present",
        },
        expected={
            "tests_dir.present": unchanged(),
            "pyproject.present": unchanged(),
            "conftest.present": unchanged(),
        },
    )


@when(
    "the operator runs the contract gate against the repository under a non terminal stderr"
)
def when_run_under_pipe(
    composition: HumanSurfaceFixture, result_box: dict[str, object]
) -> None:
    mode: StderrMode = STDERR_MODE_BY_PHRASE[
        "the operator runs the contract gate against the repository under a non terminal stderr"
    ]
    # AT3 captures BOTH a TTY run AND a PIPE run to compare JSON event byte
    # content across channels. The TTY companion run is staged here so the
    # Then-step can assert the structured contract is unchanged.
    before = composition.capture_universe()
    result_box["result_pipe"] = composition.run_contract_gate(mode)
    result_box["result_tty_companion"] = composition.run_contract_gate(StderrMode.TTY)
    after = composition.capture_universe()
    assert_state_delta(
        before=before,
        after=after,
        universe={
            "tests_dir.present",
            "pyproject.present",
            "conftest.present",
        },
        expected={
            "tests_dir.present": unchanged(),
            "pyproject.present": unchanged(),
            "conftest.present": unchanged(),
        },
    )


# --- Then -------------------------------------------------------------------


@then(
    parsers.parse(
        "the stderr carries a single-line JSON ContractGateResult event with passed {passed_value}"
    )
)
def then_stderr_carries_event(
    composition: HumanSurfaceFixture,
    result_box: dict[str, object],
    passed_value: str,
) -> None:
    expected_passed = {"true": True, "false": False}[passed_value]
    result = result_box.get("result_tty") or result_box.get("result_pipe")
    event = composition.extract_contract_gate_event(result)
    assert event is not None, (
        "no single-line JSON ContractGateResult event found on stderr; "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )
    assert event.get("passed") is expected_passed, (
        f"expected passed={expected_passed}; got event={event!r}"
    )


@then(
    "the stderr carries a green colored PASS line summarising the contract gate outcome"
)
def then_stderr_green_pass_line(
    composition: HumanSurfaceFixture, result_box: dict[str, object]
) -> None:
    result = result_box["result_tty"]
    assert composition.stderr_carries_pass_line(result), (
        f"stderr missing ✅ PASS line; stderr_raw=\n{result.stderr_raw!r}"
    )
    assert composition.stderr_pass_line_is_green(result), (
        f"PASS line missing green ANSI escape (\\x1b[32m); "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )


@then(
    "the stderr carries a red colored FAIL line summarising the contract gate outcome"
)
def then_stderr_red_fail_line(
    composition: HumanSurfaceFixture, result_box: dict[str, object]
) -> None:
    result = result_box["result_tty"]
    assert composition.stderr_carries_fail_line(result), (
        f"stderr missing ❌ FAIL line; stderr_raw=\n{result.stderr_raw!r}"
    )
    assert composition.stderr_fail_line_is_red(result), (
        f"FAIL line missing red ANSI escape (\\x1b[31m); "
        f"stderr_raw=\n{result.stderr_raw!r}"
    )


@then(
    "the stderr carries a plain readable PASS line summarising the contract gate outcome with no ANSI escapes"
)
def then_stderr_plain_pass_line(
    composition: HumanSurfaceFixture, result_box: dict[str, object]
) -> None:
    result = result_box["result_pipe"]
    assert composition.stderr_carries_pass_line(result), (
        f"stderr (pipe mode) missing ✅ PASS line; stderr_raw=\n{result.stderr_raw!r}"
    )
    assert composition.stderr_carries_no_ansi_escapes(result), (
        f"stderr (pipe mode) carries ANSI escapes — color must be stripped "
        f"when stderr is not a TTY; stderr_raw=\n{result.stderr_raw!r}"
    )


@then(
    "the JSON event byte content equals the JSON event observed when stderr is a real terminal"
)
def then_json_event_byte_identical(
    composition: HumanSurfaceFixture, result_box: dict[str, object]
) -> None:
    result_pipe = result_box["result_pipe"]
    result_tty = result_box["result_tty_companion"]
    assert composition.json_event_byte_content_matches(result_pipe, result_tty), (
        f"JSON ContractGateResult event diverges across pipe vs tty stderr; "
        f"pipe stderr_raw=\n{result_pipe.stderr_raw!r}\n"
        f"tty stderr_raw=\n{result_tty.stderr_raw!r}"
    )


@then("the gate exits zero")
def then_exit_zero(
    composition: HumanSurfaceFixture, result_box: dict[str, object]
) -> None:
    result = result_box["result_tty"]
    assert result.exit_code == 0, (
        f"expected exit 0 (PASS verdict); got {result.exit_code}: "
        f"stderr=\n{result.stderr_raw!r}"
    )


@then("the gate exits with a failure code")
def then_exit_failure(
    composition: HumanSurfaceFixture, result_box: dict[str, object]
) -> None:
    result = result_box["result_tty"]
    assert result.exit_code != 0, (
        f"expected non-zero exit (FAIL verdict); got {result.exit_code}: "
        f"stderr=\n{result.stderr_raw!r}"
    )
