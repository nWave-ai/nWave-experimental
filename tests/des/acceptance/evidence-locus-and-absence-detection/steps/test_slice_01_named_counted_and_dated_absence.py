"""pytest-bdd binding: a committed slice with no reachable examine verdict is
named, counted and dated (slice-01 walking skeleton).

Driving port: the real `des` CLI dispatcher, invoked IN-PROCESS (Mandate-13
driving-port-only, Layer 3 in-process composition). Step bodies delegate to the
composition root (`composition.py`); no production module is imported-and-
called at the step boundary, and no business logic lives in a step body
(Mandate-12 criterion 3: each body is a single delegation).

The `scenarios(...)` call binds every scenario in the `.feature` file via the
RELATIVE path from this steps/ module -- the proven-collecting form used by
the sibling suite gate-trailer-read-git-port-extract. This routes the scenario
@tags through pytest-bdd's tag-to-dynamic-mark pipeline, which the project's
filterwarnings makes --strict-markers-safe. Each step decorator's literal text
is unique within this feature directory (S1 step-text-uniqueness invariant;
this is the only step file in the directory).

RED scaffold (empirically confirmed at authorship HEAD, 2026-07-29): the
subcommand `des.cli.__main__._REGISTRY` carries no `verify-examine-attestation`
row, and `src/des/cli/verify_examine_attestation.py` does not exist. Every
Then-step below asserts on a parsed report/exit-code that the RED-at-HEAD run
cannot produce (empty stdout, exit code 2) -- each fails with a semantic
`AssertionError` (nw-distill-red-scaffolding P1-P4), never a collection/import
error.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import EvidenceLocusComposition


scenarios("../slice-01-named-counted-and-dated-absence.feature")


@pytest.fixture
def composition() -> Iterator[EvidenceLocusComposition]:
    comp = EvidenceLocusComposition()
    yield comp
    comp.cleanup()


# --- Given ---------------------------------------------------------------


@given("a committed slice whose examine verdict is unreachable")
def given_unreachable_slice(composition: EvidenceLocusComposition) -> None:
    composition.given_committed_slice_with_unreachable_verdict()


@given(
    "two committed slices whose examine verdicts are unreachable, authored on "
    "different dates"
)
def given_two_unreachable_slices(composition: EvidenceLocusComposition) -> None:
    composition.given_two_committed_slices_with_unreachable_verdicts()


@given(
    "every committed slice's bare identifier is present somewhere in the examine ledger"
)
def given_every_slice_reachable(composition: EvidenceLocusComposition) -> None:
    composition.given_every_committed_slice_reachable_in_ledger()


@given("the operator has already run the evidence-attestation detector once")
def given_prior_run(composition: EvidenceLocusComposition) -> None:
    composition.given_prior_report_run_once()


# --- When ------------------------------------------------------------------


@when("the operator runs the evidence-attestation detector")
def when_runs_detector(composition: EvidenceLocusComposition) -> None:
    composition.when_operator_runs_detector()


@when(
    "an unrelated file is touched under the telemetry directory and the "
    "detector is run again"
)
def when_touch_and_rerun(composition: EvidenceLocusComposition) -> None:
    composition.when_unrelated_file_touched_under_telemetry_and_detector_rerun()


# --- Then --------------------------------------------------------------------


@then("the report names the unattested slice")
def then_names_slice(composition: EvidenceLocusComposition) -> None:
    composition.then_report_names_the_unattested_slice()


@then("the report names the commit the unattested slice came from")
def then_names_commit(composition: EvidenceLocusComposition) -> None:
    composition.then_report_names_the_unattested_commit()


@then(parsers.parse("the report states the count as {expected_count:d}"))
def then_states_count(
    composition: EvidenceLocusComposition, expected_count: int
) -> None:
    composition.then_report_states_the_count(expected_count)


@then(
    parsers.parse('the report states the oldest unattested date as "{expected_date}"')
)
def then_states_oldest_date(
    composition: EvidenceLocusComposition, expected_date: str
) -> None:
    composition.then_report_states_oldest_date(expected_date)


@then("the command exits non-zero")
def then_exits_non_zero(composition: EvidenceLocusComposition) -> None:
    composition.then_command_exits_non_zero()


@then("the report names no unattested slice")
def then_names_no_slice(composition: EvidenceLocusComposition) -> None:
    composition.then_report_names_no_unattested_slice()


@then("the report does not read as a success summary")
def then_not_success(composition: EvidenceLocusComposition) -> None:
    composition.then_report_does_not_read_as_success()


@then("the report is unchanged from the first run")
def then_unchanged(composition: EvidenceLocusComposition) -> None:
    composition.then_report_unchanged_from_first_run()
