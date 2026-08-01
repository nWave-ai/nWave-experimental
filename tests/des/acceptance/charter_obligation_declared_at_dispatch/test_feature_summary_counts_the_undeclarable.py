# @feature-charter-obligation-declared-at-dispatch
"""ATs -- the end-of-feature summary COUNTS the third state.

Feature `charter-obligation-declared-at-dispatch`, Slice Plan row 3:
"When I read the end-of-feature summary, I can see how many pieces of work
nobody could tell were user-visible or not, instead of that count being
invisible."

CONTRACT_SHAPE: pure-function (a read-only query over the ledger; the report is
a function of the records and mutates nothing).

THE POPULATION, named once here and asserted throughout: the DECLARED SLICE SET
of the feature -- the set of distinct `slice_id` values carrying at least one
`CharterObligationDeclared` record on the feature's examine ledger, taken
latest-record-wins per `(feature_id, slice_id)` (the same last-line-wins
semantics `_latest_examine_verdict` already applies on that ledger,
`commit_slice.py:806-829`). Every count below is a count OVER THAT SET, and the
three buckets partition it exactly. A count with no named population is
unfalsifiable, so the report must NAME it too (R17).

Driving surface: `des report-delivery-metrics` -- the shipped read-side query
CLI -- driven IN-PROCESS (L2 default). Its Given runs the REAL producer
(`des dispatch`) for every declaration, so the population under test is the one
the system actually writes.

ACTIVE-RED TODAY. `--metric` accepts only `agent-usage-by-stage` and
`time-to-green` (`report_delivery_metrics.py:_METRICS`), so
`charter-obligation-coverage` does not exist and no count is produced.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.des.acceptance.charter_obligation_declared_at_dispatch.composition import (
    dispatch,
    provision_project,
    report_charter_obligation_coverage,
)
from tests.des.acceptance.charter_obligation_declared_at_dispatch.domain_types import (
    CharterObligation,
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return provision_project(tmp_path / "project")


def _declare(project: Path, assignments: dict[str, str | None]) -> None:
    """Run a REAL dispatch per slice: `slice_id -> lane` (None = no lane)."""
    for slice_id, lane in sorted(assignments.items()):
        dispatch(project, slice_id, lane=lane)


def _coverage_report(project: Path) -> dict[str, object]:
    exit_code, stdout, stderr = report_charter_obligation_coverage(project)
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            "`des report-delivery-metrics --metric charter-obligation-coverage` "
            f"emitted no JSON report ({exc}). exit={exit_code}, "
            f"stdout={stdout[:600]!r}, stderr={stderr[-800:]!r}"
        ) from None
    assert isinstance(payload, dict), payload
    return payload


def _counts(report: dict[str, object]) -> dict[str, int]:
    obligations = report.get("obligations")
    assert isinstance(obligations, dict), (
        "the report must carry an `obligations` map bucketed by the THREE "
        f"declared values; report={report!r}"
    )
    return {key: int(value) for key, value in obligations.items()}


# ---------------------------------------------------------------------------
# The three buckets, and the third one is the point
# ---------------------------------------------------------------------------


def test_the_summary_shows_how_much_work_nobody_could_classify(
    project: Path,
) -> None:
    """@driving_port @real-io

    THE THIRD STATE REACHES THE AGGREGATE (GDP-8 arity corollary). A summary
    that reports only what was REQUIRED and what was EXEMPT leaves the
    undeclarable work invisible -- which is the state the operator most needs
    to see, because it is the one nobody decided.
    """
    # covers: R13
    _declare(
        project,
        {
            "slice-01": "bugfix",
            "slice-02": "prefactoring",
            "slice-03": None,
            "slice-04": None,
        },
    )

    report = _coverage_report(project)
    counts = _counts(report)

    for value in CharterObligation:
        assert value.value in counts, (
            f"the aggregate omits the {value.value!r} bucket entirely -- a "
            f"state that never reaches the summary was not counted. "
            f"buckets={sorted(counts)}"
        )
    assert counts[CharterObligation.INDETERMINATE.value] == 2, (
        "two dispatches named no lane, so two pieces of work are "
        f"undeclarable; the summary says "
        f"{counts[CharterObligation.INDETERMINATE.value]}"
    )
    assert counts[CharterObligation.REQUIRED.value] == 1, counts
    assert counts[CharterObligation.EXEMPT.value] == 1, counts


@pytest.mark.parametrize(
    "assignments",
    [
        {"slice-01": "bugfix"},
        {"slice-01": "bugfix", "slice-02": "prefactoring"},
        {"slice-01": None, "slice-02": None, "slice-03": None},
        {
            "slice-01": "bugfix",
            "slice-02": "bugfix",
            "slice-03": "prefactoring",
            "slice-04": "charter",
            "slice-05": None,
        },
    ],
    ids=["single-required", "required-plus-exempt", "all-undeclared", "mixed-five"],
)
def test_the_three_buckets_conserve_against_the_declared_slice_set(
    project: Path, assignments: dict[str, str | None]
) -> None:
    """@driving_port @real-io @property

    CONSERVATION over the NAMED population. `required + exempt + indeterminate`
    must equal the size of the declared slice set -- no slice lost, none
    double-counted, none invented. Without this law the three numbers are
    three unrelated tallies and the summary cannot be falsified.

    Example-pinned rather than generator-driven: this is a Layer-3 AT over a
    real CLI and a real ledger (Mandate 9 -- PBT full is reserved for layers
    1-2), so the partition is enumerated explicitly.
    """
    # covers: R14
    _declare(project, assignments)

    report = _coverage_report(project)
    counts = _counts(report)

    total = sum(counts.get(value.value, 0) for value in CharterObligation)
    assert total == len(assignments), (
        f"the three buckets total {total} over a declared slice set of "
        f"{len(assignments)} ({sorted(assignments)}) -- the partition leaks. "
        f"counts={counts}"
    )


def test_redeclaring_a_slice_moves_it_between_buckets_instead_of_duplicating_it(
    project: Path,
) -> None:
    """@driving_port @real-io

    The ledger is append-only, so a re-dispatch leaves TWO records for one
    slice. Latest-record-wins keeps the population a SET of slices, not a count
    of lines -- otherwise a slice re-dispatched three times inflates the
    summary threefold and every conservation claim above becomes vacuous.
    """
    # covers: R15
    _declare(project, {"slice-01": None})
    _declare(project, {"slice-01": "bugfix"})

    report = _coverage_report(project)
    counts = _counts(report)

    total = sum(counts.get(value.value, 0) for value in CharterObligation)
    assert total == 1, (
        "one slice declared twice must count ONCE; the summary counts "
        f"{total} (counts={counts})"
    )
    assert counts.get(CharterObligation.REQUIRED.value) == 1, (
        "the LATEST declaration decides the bucket; the slice was re-declared "
        f"as REQUIRED but the summary says {counts}"
    )
    assert counts.get(CharterObligation.INDETERMINATE.value) == 0, (
        f"the superseded declaration is still being counted: {counts}"
    )


# ---------------------------------------------------------------------------
# NEGATIVE -- an empty population is could-not-verify, never a silent zero
# ---------------------------------------------------------------------------


def test_a_feature_with_no_declarations_says_so_instead_of_reporting_zeroes(
    project: Path,
) -> None:
    """@driving_port @real-io @error

    NEGATIVE observation and GDP-6 in its exact shape: three zeroes read as
    "nothing owed anything", which is indistinguishable from "nobody has
    declared anything yet". The report degrades LOUD -- the same
    `status: could-not-verify` contract its sibling metrics already honour
    (`report_delivery_metrics.py:_render_agent_usage` / `_render_time_to_green`).
    """
    # covers: R16
    report = _coverage_report(project)

    assert report.get("status") == "could-not-verify", (
        "a feature with ZERO declarations must report could-not-verify, not a "
        f"silent zero; report={report!r}"
    )
    reason = str(report.get("reason", ""))
    assert reason.strip(), (
        f"the could-not-verify status must NAME why it could not look: {report!r}"
    )


def test_the_summary_names_the_population_its_counts_are_taken_over(
    project: Path,
) -> None:
    """@driving_port @real-io

    A count with no named population is unfalsifiable: the reader cannot tell
    whether "2 indeterminate" is 2 of 2 or 2 of 40, and cannot check it. The
    report must name the declared slice set the partition covers.
    """
    # covers: R17
    _declare(project, {"slice-01": "bugfix", "slice-02": None})

    report = _coverage_report(project)

    population = report.get("population")
    assert population is not None, (
        "the report states counts without naming the population they are "
        f"taken over; report={report!r}"
    )
    assert sorted(str(item) for item in population) == ["slice-01", "slice-02"], (
        "the named population must be the DECLARED SLICE SET, so a reader can "
        f"re-derive every count from it; population={population!r}"
    )
    counts = _counts(report)
    total = sum(counts.get(value.value, 0) for value in CharterObligation)
    assert total == len(list(population)), (
        f"the counts ({total}) do not add up to the population the report "
        f"itself names ({len(list(population))}) -- the summary contradicts "
        "its own denominator"
    )
