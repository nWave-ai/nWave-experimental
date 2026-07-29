"""``des next`` must project the slice the CALLER DECLARED, never the first
``pending`` row in table order.

DEFECT (defects.md ``des-next-is-not-lane-aware-misleads-parallel-worktrees``,
observed 2026-07-28 with eight parallel lanes live):
``deliver_loop_projection._first_pending_row`` returns the first Slice-Plan row
whose markdown ``Status`` reads ``pending``, in TABLE ORDER, with no notion of
who owns it. In an isolated worktree delivering slice-06, slices 01-05 stay
``pending`` forever -- no predecessor is ever committed THERE -- so ``des next``
projects slice-01 indefinitely and a sub-orchestrator following it would work
the wrong slice. The projection is advisory (it blocks nothing) but it is
actively MISLEADING in precisely the mode the method recommends for throughput.

THE LOAD-BEARING DESIGN CONSTRAINT, pinned by these witnesses:
the same table means two DIFFERENT things and the difference is NOT observable
from the table. Slices 01-08 all ``pending`` reads as "01 is next" for a single
sequential lane and as "whatever you own is next" for a parallel lane. Because
the two cases are indistinguishable in the data, the lane can only ever be a
DECLARED FACT. Deducing it from the current worktree path -- technically easy,
and the tempting shortcut -- would be deciding on an INFERRED SIGNAL, which the
2026-07-23 standing rule forbids; ``test_projection_never_infers_the_lane_from_
the_current_working_directory`` is the witness that keeps that shortcut out.

The third state is LOUD, never a silent fallback: with NO declaration and two
or more pending rows, the projection reports INDETERMINATE and names the
candidates WITHOUT privileging any of them (naming the first in the prose would
put the very lie back into circulation). With exactly ONE pending row and no
declaration it still projects -- that is not a fallback, it is a forced choice:
with a single candidate no guess is possible.

CONTRACT_SHAPE: pure-function -- every witness calls the real
``deliver_loop_projection.project_next_step`` (no mock of the unit under test)
and asserts on the returned frozen ``NextStep``.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest

from des.application.deliver_loop_projection import project_next_step
from des.cli.next_step import main as next_step_main


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Fixture-repo builder -- the same `feature_delta_doctor`-clean shape used by
# tests/bugs/des/test_des_next_honours_terminal_evidence.py, widened to carry
# an arbitrary number of slice rows so the multi-lane shape is expressible.
# ---------------------------------------------------------------------------

_MULTI_LANE_SLICES = (
    "slice-01",
    "slice-02",
    "slice-03",
    "slice-04",
    "slice-05",
    "slice-06",
)


def _feature_delta_text(slice_ids: tuple[str, ...]) -> str:
    rows = "".join(
        f"| {slice_id} | thinnest end-to-end read for {slice_id} | "
        f"pending | @walking_skeleton | walking skeleton |\n"
        for slice_id in slice_ids
    )
    return (
        "## Wave: DESIGN / [REF] Architecture & Contract Tests\n"
        "\n"
        "Some architecture prose.\n"
        "\n"
        "## Wave: DESIGN / [REF] ADR Refs\n"
        "\n"
        "- ADR-001\n"
        "\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n"
        "\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        f"{rows}"
        "\n"
        "## Reuse Analysis\n"
        "\n"
        "Reuse-Analysis: no-overlap\n"
        "\n"
        "## Test Reuse & Consolidation Analysis\n"
        "\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )


def _write_feature_delta(
    repo: Path, feature_id: str, slice_ids: tuple[str, ...]
) -> None:
    delta_path = repo / "docs" / "feature" / feature_id / "feature-delta.md"
    delta_path.parent.mkdir(parents=True, exist_ok=True)
    delta_path.write_text(_feature_delta_text(slice_ids), encoding="utf-8")


def _prose(step: object) -> str:
    """Every human-readable field of a ``NextStep``, lowercased and joined.

    A witness that only inspected ``slice_id`` would pass while the ``what`` /
    ``why`` / ``how`` prose still named the wrong slice -- and the prose is
    exactly what a sub-orchestrator reads and acts on.
    """
    return " ".join(
        str(getattr(step, field, ""))
        for field in ("what", "why", "how", "phase", "slice_id")
    ).lower()


# ---------------------------------------------------------------------------
# Witness (a) -- POSITIVE: the declared slice is the projected slice, even
# when five earlier rows sit `pending` above it in table order.
# ---------------------------------------------------------------------------

_FEATURE_ID_A = "des-next-lane-declared-slice"


def test_projection_honours_the_declared_slice_over_table_order(
    tmp_path: Path,
) -> None:
    """A caller declaring slice-06 must be projected slice-06's next step,
    not slice-01's, though slice-01 is the first ``pending`` row in the table.

    This is the parallel-lane shape verbatim: an isolated worktree delivering
    slice-06 in which no predecessor slice will ever be committed.
    """
    _write_feature_delta(tmp_path, _FEATURE_ID_A, _MULTI_LANE_SLICES)

    step = project_next_step(tmp_path, _FEATURE_ID_A, slice_id="slice-06")

    assert step.slice_id == "slice-06", (
        f"WRONG outcome produced: the caller DECLARED slice-06 -- the lane it "
        f"owns -- yet the projection reports slice_id={step.slice_id!r}, "
        f"selected by table position instead of by the declared fact: {step!r}"
    )


# ---------------------------------------------------------------------------
# Witness (b) -- NEGATIVE: the projection must never NAME a slice the caller
# did not declare. Pins the wrong output, not merely the absence of the right
# one: `slice_id` could be corrected while the prose still says "slice-01".
# ---------------------------------------------------------------------------


def test_projection_never_names_a_slice_the_caller_did_not_declare(
    tmp_path: Path,
) -> None:
    """With slice-06 declared, NO field of the projection may name slice-01.

    The sub-orchestrator acts on the ``what``/``why``/``how`` prose, so a
    correct ``slice_id`` alongside prose naming slice-01 is still the defect.
    """
    _write_feature_delta(tmp_path, _FEATURE_ID_A, _MULTI_LANE_SLICES)

    step = project_next_step(tmp_path, _FEATURE_ID_A, slice_id="slice-06")

    undeclared = [
        slice_id
        for slice_id in _MULTI_LANE_SLICES
        if slice_id != "slice-06" and slice_id in _prose(step)
    ]
    assert not undeclared, (
        f"WRONG outcome produced: the caller declared ONLY slice-06, yet the "
        f"projection names {undeclared} in its own prose -- an agent reading "
        f"this would be steered onto a lane it does not own: {step!r}"
    )


# ---------------------------------------------------------------------------
# Witness (c) -- NEGATIVE: with NO declaration and an ambiguous plan, the
# projection may still answer (refusing would break `des next` as an entry
# point on every fresh multi-slice feature -- measured: the real 7-slice
# `declared-facts-reachable-recorded` plan) but it must never answer SILENTLY.
# The assumption must ride in `what`, the field a caller actually reads.
# ---------------------------------------------------------------------------

_FEATURE_ID_C = "des-next-lane-undeclared"

_ASSUMPTION_MARKER = "assuming single-lane sequential order"


def test_projection_never_selects_by_table_position_without_saying_so(
    tmp_path: Path,
) -> None:
    """Six pending rows, nothing declared: answering is allowed, answering
    SILENTLY is not.

    This is the defect's core. The old projection named slice-01 as plain
    fact, so a parallel lane had no way to tell a derived answer from an
    assumed one. GDP-6 forbids the silent wrong, not the stated one.
    """
    _write_feature_delta(tmp_path, _FEATURE_ID_C, _MULTI_LANE_SLICES)

    step = project_next_step(tmp_path, _FEATURE_ID_C)

    assert _ASSUMPTION_MARKER in step.what.lower(), (
        f"WRONG outcome produced: six rows are pending, slice-01 was chosen "
        f"by table position alone, and the projection presents it as plain "
        f"fact -- a parallel lane cannot tell this answer was ASSUMED: "
        f"{step!r}"
    )


def test_projection_never_buries_the_assumption_outside_what(
    tmp_path: Path,
) -> None:
    """The assumption must be in ``what``, not only in ``why``.

    A caller that reads ``what`` and ``how`` -- the normal behaviour, and all
    the human ``--format`` line shows first -- would act on the step without
    ever seeing the caveat. Disclosure only in ``why`` is the silent wrong
    wearing a disclosure label.
    """
    _write_feature_delta(tmp_path, _FEATURE_ID_C, _MULTI_LANE_SLICES)

    step = project_next_step(tmp_path, _FEATURE_ID_C)

    assert _ASSUMPTION_MARKER in step.what.lower(), (
        f"WRONG outcome produced: the assumption is disclosed somewhere in "
        f"the payload but NOT in `what`, so a caller reading what/how acts on "
        f"a table-position guess it never saw flagged: what={step.what!r}"
    )


def test_projection_never_states_the_assumption_without_offering_the_remedy(
    tmp_path: Path,
) -> None:
    """Naming the assumption without naming the escape is a dead end.

    GDP-4: the report must route to the producing tool -- here, re-running
    with the declaration that removes the assumption entirely.
    """
    _write_feature_delta(tmp_path, _FEATURE_ID_C, _MULTI_LANE_SLICES)

    step = project_next_step(tmp_path, _FEATURE_ID_C)

    assert "--slice" in _prose(step), (
        f"WRONG outcome produced: the projection admits it assumed a "
        f"sequential lane but never tells the caller how to declare "
        f"otherwise, leaving the caveat unactionable: {step!r}"
    )


def test_projection_still_answers_usefully_on_a_fresh_multi_slice_feature(
    tmp_path: Path,
) -> None:
    """The stated assumption must not cost the answer.

    `des next` is the primary orientation command and a fresh 7-slice feature
    has 7 pending rows. A version that refuses there breaks the entry point in
    the commonest case -- measured on the real
    `declared-facts-reachable-recorded` plan, which refused outright before
    this correction. Over-correction is a defect of its own.
    """
    _write_feature_delta(tmp_path, _FEATURE_ID_C, _MULTI_LANE_SLICES)

    step = project_next_step(tmp_path, _FEATURE_ID_C)

    assert step.slice_id == "slice-01", (
        f"WRONG outcome produced: the projection withheld any slice on a "
        f"perfectly ordinary fresh feature, so `des next` -- the command the "
        f"session hook tells users to start with -- is now a dead end: "
        f"{step!r}"
    )
    assert step.loop_state != "INDETERMINATE", (
        f"WRONG outcome produced: an ordinary fresh multi-slice feature was "
        f"reported INDETERMINATE, breaking the primary entry point: {step!r}"
    )


# ---------------------------------------------------------------------------
# Witness (d) -- NEGATIVE, the load-bearing one: the lane must NEVER be
# inferred from the worktree/cwd. Deducing it is technically easy and would
# make witness (c) pass -- this keeps that shortcut out by construction.
# ---------------------------------------------------------------------------


def test_projection_never_varies_with_the_worktree_path_it_runs_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two identical plans, two very different paths, ONE identical verdict.

    Invariance is the property, so it is what this asserts. An earlier draft
    asserted a particular verdict instead -- which would have kept passing if
    the code started reading the path but happened to reach the same answer,
    and would have broken on any unrelated wording change. Here the two runs
    check each other: only genuine path-independence satisfies both.

    One tree is named for slice-06 at every level; the other is neutral. The
    lane was DECLARED in neither, so nothing may differ. Deciding on an
    inferred signal is forbidden (standing rule 2026-07-23) even when the
    inference would be RIGHT -- as it would be here, which is exactly why a
    witness rather than good intentions keeps it out.
    """
    lane_worktree = tmp_path / "wt" / "lane-slice-06" / "slice-06"
    neutral_worktree = tmp_path / "plain" / "checkout"
    for tree in (lane_worktree, neutral_worktree):
        (tree / "docs").mkdir(parents=True)
        _write_feature_delta(tree, _FEATURE_ID_C, _MULTI_LANE_SLICES)

    monkeypatch.chdir(lane_worktree)
    monkeypatch.setenv("PWD", str(lane_worktree))
    from_lane_path = project_next_step(lane_worktree, _FEATURE_ID_C)

    monkeypatch.chdir(neutral_worktree)
    monkeypatch.setenv("PWD", str(neutral_worktree))
    from_neutral_path = project_next_step(neutral_worktree, _FEATURE_ID_C)

    assert from_lane_path == from_neutral_path, (
        f"WRONG outcome produced: the SAME plan projected differently from "
        f"two different paths, so the projection is reading its lane out of "
        f"the worktree name -- an inferred signal standing in for a declared "
        f"fact. From {lane_worktree}: {from_lane_path!r}. From "
        f"{neutral_worktree}: {from_neutral_path!r}"
    )
    assert "slice-06" not in _prose(from_lane_path), (
        f"WRONG outcome produced: run from a tree named for slice-06 with "
        f"NOTHING declared, the projection named slice-06 -- it read the lane "
        f"off the path {os.getcwd()!r}: {from_lane_path!r}"
    )


# ---------------------------------------------------------------------------
# Witness (e) -- NEGATIVE: a declared slice absent from the plan is a caller
# error and must be reported as one, never silently re-resolved to some other
# row.
# ---------------------------------------------------------------------------


def test_projection_rejects_a_declared_slice_absent_from_the_plan(
    tmp_path: Path,
) -> None:
    """Declaring slice-99, which no Slice-Plan row carries, must degrade LOUD
    and name slice-99 -- never quietly project a DIFFERENT slice.

    Silently substituting another row would hand the caller a confident answer
    about a lane it never asked about, which is the defect in a new costume.
    """
    _write_feature_delta(tmp_path, _FEATURE_ID_A, _MULTI_LANE_SLICES)

    step = project_next_step(tmp_path, _FEATURE_ID_A, slice_id="slice-99")

    assert step.loop_state == "INDETERMINATE", (
        f"WRONG outcome produced: slice-99 is in no Slice-Plan row, so the "
        f"projection has nothing to project -- yet it answered with a "
        f"confident loop_state={step.loop_state!r}: {step!r}"
    )
    assert "slice-99" in _prose(step), (
        f"WRONG outcome produced: the rejection never names the slice the "
        f"caller actually declared, so the caller cannot tell WHICH "
        f"declaration was rejected: {step!r}"
    )
    assert step.slice_id != "slice-01", (
        f"WRONG outcome produced: the projection quietly resolved the absent "
        f"slice-99 to slice-01 -- answering about a lane the caller never "
        f"asked about: {step!r}"
    )


# ---------------------------------------------------------------------------
# Witness (f) -- ANTI-OVER-CORRECTION: a fix that makes the projection refuse
# to answer ANYTHING is as useless as the lie. With exactly one pending row
# and no declaration, the choice is FORCED by the data, not guessed.
# ---------------------------------------------------------------------------

_FEATURE_ID_F = "des-next-lane-single-pending"


def test_projection_still_projects_the_sole_pending_row_without_a_declaration(
    tmp_path: Path,
) -> None:
    """One pending row, nothing declared: still project it.

    This is not the old fallback returning by the back door. With a single
    candidate there is no guess available to make -- the data forces the
    choice. Withholding it here would break every legitimate single-lane
    caller to fix a defect that only exists when candidates compete.
    """
    _write_feature_delta(tmp_path, _FEATURE_ID_F, ("slice-01",))

    step = project_next_step(tmp_path, _FEATURE_ID_F)

    assert step.slice_id == "slice-01", (
        f"WRONG outcome produced: exactly one slice is pending, so no "
        f"ambiguity exists and no guess is possible -- yet the projection "
        f"refused to name it. Over-correction is as unusable as the defect: "
        f"{step!r}"
    )
    assert step.loop_state != "INDETERMINATE", (
        f"WRONG outcome produced: an unambiguous single-candidate plan was "
        f"reported INDETERMINATE: {step!r}"
    )


# ---------------------------------------------------------------------------
# Witness (g) -- the remedy must be REACHABLE from the user surface. The
# INDETERMINATE prose tells the caller to re-run with `--slice`; if the CLI
# carries no such flag, the report has replaced a misleading answer with an
# impossible instruction (GDP-4: the HOW invokes the producing tool).
# ---------------------------------------------------------------------------


def test_des_next_cli_accepts_the_declared_slice_its_own_how_prescribes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `--slice` flag named by the ambiguous report must exist on `des
    next` and must actually steer the projection.

    Witness (c) pins that the projection stops guessing; this one pins that
    the caller can DO something about it. A LOUD report whose prescribed
    remedy is unreachable is not an improvement over the defect -- it is the
    same dead end with better prose.
    """
    _write_feature_delta(tmp_path, _FEATURE_ID_A, _MULTI_LANE_SLICES)

    exit_code = next_step_main(
        [
            "--feature-id",
            _FEATURE_ID_A,
            "--repo",
            str(tmp_path),
            "--slice",
            "slice-06",
            "--format",
            "json",
        ]
    )
    verdict = json.loads(capsys.readouterr().out)

    assert exit_code == 0, f"expected a controlled exit 0 projection: {verdict!r}"
    assert verdict["slice_id"] == "slice-06", (
        f"WRONG outcome produced: the CLI accepted --slice slice-06 but the "
        f"projection still reports slice_id={verdict['slice_id']!r} -- the "
        f"declared fact never reached the core: {verdict!r}"
    )
