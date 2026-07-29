"""Acceptance tests -- `des next` (DISTILL, slice-01, walking skeleton).

Charter/feature-delta: docs/feature/des-next-loop-projection/feature-delta.md
  ([REF] Slice Plan slice-01 row, [REF] Architecture & Contract Tests,
  [REF] Options Considered -- Option 1, [REF] Component Overview,
  [REF] SF-Impact -- Published Contract).

Contract under test (DOES NOT EXIST YET -- active-RED by design):
`src/des/application/deliver_loop_projection.py::project_next_step` +
`src/des/cli/next_step.py::main(argv) -> int`. `main` parses
`--feature-id/--repo/--format {json,human}`, calls `project_next_step`, and
in `--format json` mode prints exactly ONE JSON `NextStepProjected` object to
stdout (mirroring the `des verify-red-green` / `des record-examine-verdict`
single-JSON-line precedent), matching the published SF-Impact contract shape:
`{event, schema_version, feature_id, loop_state, slice_id, phase, step_kind,
what, why, how}`.

Slice-01 pins the THREE mid-loop judgment-bearing phases (feature-delta
"What the contract AT pins, per slice" table): for each of AT-authoring
absent, GREEN absent, and EXAMINE absent, `step_kind == "wave-command"` and
`how` is EXACTLY `/nw-{wave}` derived from the matching
`nWave/waves/{wave}.yaml` filename -- never a `des dispatch` envelope string
(the design's Non-Goals section: `des next` never renders a wave's own
dispatch envelope for a judgment-bearing step).

Precondition-order grounding (feature-delta "Per-slice precondition order",
walked in this exact sequence):
  1. `RedObserved` for the slice absent -> phase `D_DISTILL`
     -> `/nw-distill --feature-id {feature_id} --slice {slice_id}`.
  2. `RedObserved` present, `ATReviewVerdict` absent -> phase `A_GREEN`
     -> `/nw-deliver --feature-id {feature_id}`.
  3. `ATReviewVerdict` present, `ExamineVerdictRecorded` absent -> phase
     `C_REVIEWER_AUDIT` -> `/nw-deliver --feature-id {feature_id}`.
Phase literals grounded against `src/des/domain/atdd_pure_phases.py`
(`ATDDPurePhase.D_DISTILL / A_GREEN / C_REVIEWER_AUDIT`).

Ledger-seeding grounding (Test Reuse & Consolidation Analysis: "commit_slice
ledger-fixture pattern... des-next's per-state ATs... reuse this seeding
helper"): every seeded record goes through the REAL, already-shipped
`AtCompletionLedger` writer API (`append_gate_event` / `append_review_verdict`,
`src/des/adapters/driven/logging/at_completion_ledger.py`) -- never a
hand-written JSONL line -- so each record carries a genuine `seq` +
`record_hash` the M7 fail-closed reader accepts. `RedObserved` has no
dedicated ledger-append producer yet (today it is a seal file written by
`des verify-red-green`, keyed by test-file path -- see Reuse Analysis'
declared-imports list for `deliver_loop_projection.py`, which names
`AtCompletionLedger` but NOT `verify_red_green`); this AT PINS the executable
contract by seeding `RedObserved` as a slice-scoped `AtCompletionLedger`
event via `append_gate_event`, consistent with the design's literal
precondition-order prose ("`RedObserved` for the slice absent") and with the
declared-imports list -- the concrete gap (wiring a real producer) is a
DELIVER/follow-on concern, not a reason to leave the composition contract
unpinned.

GDP-7 (agnostic, no git/tool dependency) grounding: the fixture repo is
deliberately NEVER `git init`-ed. The design's own Option-1 assessment claims
"GDP-7 (agnostic) | Full -- filesystem + JSONL + YAML-by-regex reads only, no
git/tool dep", which is incompatible with reusing the git-backed
`verify_deliver_integrity._shipped_slices` (it depends on
`CommitTrailerReadPort`, degrading to `Indeterminate` outside a git
work-tree). This AT holds the design to its own GDP-7 claim: a mid-loop
projection over a single `pending`, unshipped slice must resolve to a
wave-command verdict WITHOUT git being present at all.

Active-RED scaffolding (P1-P4, `nw-distill-red-scaffolding`): the CLI module
is absent today, so the import happens INSIDE a helper called from each test
body (hidden-import), never at module top -- collection stays green
(COLLECT >= 4) and the absence surfaces as a semantic AssertionError
(MISSING_FUNCTIONALITY) at runtime, never a collection ImportError (BROKEN).

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the real `des.cli.next_step` CLI driver (`main(argv)`),
captured via `capsys` -- no subprocess fork.

CONTRACT_SHAPE: pure-function -- `project_next_step` reads only, returns a
frozen `NextStep` value; the CLI shell adds no mutation beyond stdout.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Hidden-import helper (P1 + P3): keep the absent module out of collection
# scope; the absence surfaces as a runtime AssertionError inside a test body.
# ---------------------------------------------------------------------------


def _import_next_step():
    try:
        from des.cli.next_step import main
    except ModuleNotFoundError as exc:
        raise AssertionError(
            "MISSING_FUNCTIONALITY: src/des/cli/next_step.py (and/or "
            "src/des/application/deliver_loop_projection.py) does not exist "
            f"yet ({exc}). Implement `main(argv) -> int` composing "
            "`project_next_step(repo_root, feature_id)` per the DESIGN "
            "contract (feature-delta [REF] Component Overview) before this "
            "AT can pass."
        ) from exc
    return main


# ---------------------------------------------------------------------------
# Fixture-repo builder -- reuses the `feature_delta_doctor` CLEAN_FEATURE_DELTA
# shape (tests/des/unit/cli/test_feature_delta_doctor.py) so the preflight
# `feature_delta_doctor.diagnose()` step (Component Overview step 1) reports
# zero gaps and `project_next_step` reaches the real precondition walk.
# ---------------------------------------------------------------------------

_FEATURE_ID = "sample-loop-feature"
_SLICE_ID = "slice-01"


def _feature_delta_text(feature_id: str, slice_id: str) -> str:
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
        f"| {slice_id} | thinnest end-to-end read across the 4 SSOTs | "
        "pending | @walking_skeleton | walking skeleton |\n"
        "\n"
        "## Reuse Analysis\n"
        "\n"
        "Reuse-Analysis: no-overlap\n"
        "\n"
        "## Test Reuse & Consolidation Analysis\n"
        "\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )


def _write_feature_delta(repo: Path, feature_id: str, slice_id: str) -> None:
    delta_path = repo / "docs" / "feature" / feature_id / "feature-delta.md"
    delta_path.parent.mkdir(parents=True, exist_ok=True)
    delta_path.write_text(_feature_delta_text(feature_id, slice_id), encoding="utf-8")


def _ledger(repo: Path, feature_id: str):
    from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

    return AtCompletionLedger(feature_id, repo)


def _bootstrap_ledger(repo: Path, feature_id: str) -> None:
    """Make the ledger FILE exist with zero decision-relevant records.

    Distinguishes "this slice legitimately has no evidence yet" (this AT's
    happy path) from "the ledger file itself is absent for a brand-new
    feature" (feature-delta slice-04(b): INDETERMINATE, not this AT's
    concern) -- `AtCompletionLedger.read_records()` treats a missing FILE as
    an empty list, but the design pins ledger-absence itself as a DISTINCT,
    INDETERMINATE-producing signal from ledger-present-but-empty-for-this-
    slice. `LedgerBootstrapped` matches no precondition-order event name, so
    it is inert to every predicate `project_next_step` evaluates.
    """
    _ledger(repo, feature_id).append_gate_event(
        event="LedgerBootstrapped", slice_id="", feature_id=feature_id
    )


def _seed_red_observed(repo: Path, feature_id: str, slice_id: str) -> None:
    _ledger(repo, feature_id).append_gate_event(
        event="RedObserved", slice_id=slice_id, feature_id=feature_id
    )


def _seed_at_review_verdict(repo: Path, feature_id: str, slice_id: str) -> None:
    """Seed an APPROVED `ATReviewVerdict` (D04b: presence alone no longer
    satisfies the AT-review-done predicate -- see
    `_has_approved_review_verdict_for_slice`, `deliver_loop_projection.py`)."""
    _ledger(repo, feature_id).append_review_verdict(
        slice_id, {"verdict": "APPROVED"}, feature_id=feature_id
    )


def _arm_examine_gate(repo: Path, feature_id: str) -> None:
    """Charter dir + >=1 `.md` file arms `commit_slice._examine_gate_armed`
    (env-var-independent activation path) -- reused verbatim per the design's
    Reuse Analysis row for the examine-gate predicates."""
    charter_dir = repo / "docs" / "product" / "expectations" / feature_id
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "intent.md").write_text("# Intent\n", encoding="utf-8")


def _run(
    capsys: pytest.CaptureFixture[str], repo: Path, feature_id: str
) -> tuple[int, dict]:
    main = _import_next_step()
    exit_code = main(
        ["--feature-id", feature_id, "--repo", str(repo), "--format", "json"]
    )
    captured = capsys.readouterr()
    verdict = json.loads(captured.out)
    return exit_code, verdict


# ---------------------------------------------------------------------------
# Scenario 1 -- POSITIVE, parametrized: the 3 mid-loop judgment-bearing
# phases, each naming the correct wave-command door.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def _seed_at_authoring_pending(repo: Path) -> None:
    _bootstrap_ledger(repo, _FEATURE_ID)


def _seed_green_pending(repo: Path) -> None:
    _bootstrap_ledger(repo, _FEATURE_ID)
    _seed_red_observed(repo, _FEATURE_ID, _SLICE_ID)


def _seed_examine_pending(repo: Path) -> None:
    _bootstrap_ledger(repo, _FEATURE_ID)
    _seed_red_observed(repo, _FEATURE_ID, _SLICE_ID)
    _seed_at_review_verdict(repo, _FEATURE_ID, _SLICE_ID)
    _arm_examine_gate(repo, _FEATURE_ID)


@pytest.mark.parametrize(
    "seed_fn, expected_phase, expected_how",
    [
        (
            _seed_at_authoring_pending,
            "D_DISTILL",
            f"/nw-distill --feature-id {_FEATURE_ID} --slice {_SLICE_ID}",
        ),
        (
            _seed_green_pending,
            "A_GREEN",
            f"/nw-deliver --feature-id {_FEATURE_ID}",
        ),
        (
            _seed_examine_pending,
            "C_REVIEWER_AUDIT",
            f"/nw-deliver --feature-id {_FEATURE_ID}",
        ),
    ],
    ids=["at_authoring_pending", "green_pending", "examine_pending"],
)
def test_main_names_the_wave_command_for_the_pending_mid_loop_phase(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    seed_fn,
    expected_phase: str,
    expected_how: str,
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch

    Given a feature mid-slice-loop (`sample-loop-feature`, one `pending`
    slice, `slice-01`), `des next --feature-id sample-loop-feature` names the
    correct next wave-command (AT-authoring, GREEN, or EXAMINE pending) with
    its exact `/nw-*` invocation -- the thinnest end-to-end read across all 4
    SSOTs (Slice Plan, ledger, phase order, wave registry).
    """
    _write_feature_delta(tmp_path, _FEATURE_ID, _SLICE_ID)
    seed_fn(tmp_path)

    exit_code, verdict = _run(capsys, tmp_path, _FEATURE_ID)

    assert exit_code == 0, f"expected exit 0 (a step was projected): {verdict!r}"
    assert verdict.get("event") == "NextStepProjected", verdict
    assert verdict.get("feature_id") == _FEATURE_ID, verdict
    assert verdict.get("slice_id") == _SLICE_ID, verdict
    assert verdict.get("loop_state") == "SLICE_IN_PROGRESS", (
        f"a single pending, mid-cycle slice must report SLICE_IN_PROGRESS: {verdict!r}"
    )
    assert verdict.get("phase") == expected_phase, (
        f"expected phase {expected_phase!r} for this ledger state: {verdict!r}"
    )
    assert verdict.get("step_kind") == "wave-command", (
        f"every judgment-bearing mid-loop step routes to a wave command, "
        f"never a producing-tool: {verdict!r}"
    )
    assert verdict.get("how") == expected_how, (
        f"expected how={expected_how!r} derived from nWave/waves/*.yaml, "
        f"got: {verdict!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 2 -- NEGATIVE AT: a judgment-bearing step NEVER renders a raw
# `des dispatch` envelope string, and NEVER classifies as producing-tool.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "seed_fn",
    [_seed_at_authoring_pending, _seed_green_pending, _seed_examine_pending],
    ids=["at_authoring_pending", "green_pending", "examine_pending"],
)
def test_main_never_renders_a_raw_des_dispatch_envelope_for_a_wave_command_step(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], seed_fn
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch

    For every mid-loop judgment-bearing phase (AT-authoring, GREEN, EXAMINE
    pending), `how` names a `/nw-*` wave command whose prose carries the
    wave's own methodology (DISTILL's taxonomy, DELIVER's quality gates) --
    it must NEVER be a raw `des dispatch --phase ...` envelope string, and
    the step must NEVER classify as `producing-tool` (that WRONG outcome
    is what this negative AT asserts is absent -- Non-Goals: routing
    judgment-bearing steps around the raw envelope, never rendering a wave's
    own dispatch envelope itself).
    """
    _write_feature_delta(tmp_path, _FEATURE_ID, _SLICE_ID)
    seed_fn(tmp_path)

    exit_code, verdict = _run(capsys, tmp_path, _FEATURE_ID)

    assert exit_code == 0, verdict
    how = verdict.get("how", "")
    assert "des dispatch" not in how, (
        f"WRONG outcome produced: a judgment-bearing step must never render "
        f"a raw `des dispatch` envelope: {verdict!r}"
    )
    assert verdict.get("step_kind") != "producing-tool", (
        f"WRONG outcome produced: a judgment-bearing mid-loop step must "
        f"never classify as producing-tool: {verdict!r}"
    )
    assert how.startswith("/nw-"), (
        f"how must be a `/nw-*` wave-command invocation: {verdict!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 -- NEGATIVE AT: an empty Slice Plan TABLE (heading present, zero
# data rows) must resolve to a graceful, controlled INDETERMINATE outcome --
# never an unhandled `carpaccio_format.GateError` traceback. Promotes Vera's
# examine probe-6 FAIL (empirical: this exact shape crashed `des next`
# uncaught) to a deterministic AT, per "the examiner is the frontier --
# promote every caught class to a deterministic gate". Distinct from the
# already-graceful sibling case (Slice Plan SECTION entirely absent, Vera
# probe 5 PASS): here the section header is well-formed, only the DATA is
# empty -- the negative oracle: "when records are missing/malformed/too
# sparse, must NOT silently invent AND must not crash -- it may say plainly
# it cannot tell" (feature-delta.md).
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def _feature_delta_text_empty_slice_plan_table(feature_id: str) -> str:
    """Same well-formed shape as `_feature_delta_text` (canonical header,
    LOCKED_REF_SECTIONS all present, doctor-clean) MINUS the one data row --
    heading + header row + separator row, zero slice rows. This is exactly
    the shape `carpaccio_format._build_slice_rows` raises
    `GateError(2, {"error": "the slice-plan table has no slice rows"})` for,
    uncaught by `project_next_step` / `next_step.main` today."""
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
        "\n"
        "## Reuse Analysis\n"
        "\n"
        "Reuse-Analysis: no-overlap\n"
        "\n"
        "## Test Reuse & Consolidation Analysis\n"
        "\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )


@pytest.mark.negative_at
def test_main_never_crashes_on_empty_slice_plan_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch's negative oracle -- "when
    records are missing/malformed/too sparse, must NOT silently invent AND
    must not crash -- it may say plainly it cannot tell".

    Given a feature-delta whose `[REF] Slice Plan` HEADING is present but
    the table carries zero data rows (header + separator only), `des next`
    must resolve to a controlled, non-crash outcome -- exit 0 with a
    `NextStepProjected` JSON object reporting `loop_state=INDETERMINATE`
    and a human message naming the empty-table cause -- NEVER an unhandled
    `carpaccio_format.GateError` traceback (Vera examine probe 6, FAIL:
    this exact shape raised uncaught today).
    """
    feature_id = _FEATURE_ID
    delta_path = tmp_path / "docs" / "feature" / feature_id / "feature-delta.md"
    delta_path.parent.mkdir(parents=True, exist_ok=True)
    delta_path.write_text(
        _feature_delta_text_empty_slice_plan_table(feature_id), encoding="utf-8"
    )

    main = _import_next_step()
    exit_code = main(
        ["--feature-id", feature_id, "--repo", str(tmp_path), "--format", "json"]
    )
    captured = capsys.readouterr()

    assert exit_code == 0, (
        f"WRONG outcome produced: an empty slice-plan table must resolve to "
        f"a controlled exit 0 (INDETERMINATE), never a non-zero exit from an "
        f"uncaught GateError/traceback: exit_code={exit_code!r}, "
        f"stdout={captured.out!r}, stderr={captured.err!r}"
    )
    verdict = json.loads(captured.out)
    assert verdict.get("loop_state") == "INDETERMINATE", (
        f"an empty slice-plan table must resolve to INDETERMINATE -- "
        f"'say plainly it cannot tell', never silently invent a step: {verdict!r}"
    )
    reason = f"{verdict.get('what', '')} {verdict.get('why', '')}".lower()
    assert "slice" in reason and (
        "empty" in reason or "no slice" in reason or "no data" in reason
    ), (
        f"the INDETERMINATE message must name the empty-table cause, not a "
        f"generic message: {verdict!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 4 -- slice-03: the feature-end branch (feature-delta.md [REF]
# Slice Plan slice-03 row). Reached when every declared Slice Plan row is
# NOT `pending` (`_select_row` finds none) -- distinct SSOT
# (`EBatchRefactorCompleted`) from the per-slice precondition walk
# slice-01/02 cover. Before this feature was extended, `project_next_step`
# hard-coded `INDETERMINATE` for this entire branch ("a later slice's
# scope") -- D36's reproduced symptom: an all-shipped feature got a mute
# `INDETERMINATE` instead of the `des feature-end run` instruction.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------

_ALL_SHIPPED_SLICE_IDS = ("slice-01", "slice-02")


def _feature_delta_text_all_shipped(feature_id: str, slice_ids) -> str:
    """Same canonical, doctor-clean shape as `_feature_delta_text`, but every
    declared row's Status column reads `shipped` (never `pending`) -- the
    precondition `_select_row` needs to fall through to the feature-end
    branch."""
    rows = "\n".join(
        f"| {slice_id} | thing shipped | shipped | | done |" for slice_id in slice_ids
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
        f"{rows}\n"
        "\n"
        "## Reuse Analysis\n"
        "\n"
        "Reuse-Analysis: no-overlap\n"
        "\n"
        "## Test Reuse & Consolidation Analysis\n"
        "\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )


def _write_feature_delta_all_shipped(repo: Path, feature_id: str, slice_ids) -> None:
    delta_path = repo / "docs" / "feature" / feature_id / "feature-delta.md"
    delta_path.parent.mkdir(parents=True, exist_ok=True)
    delta_path.write_text(
        _feature_delta_text_all_shipped(feature_id, slice_ids), encoding="utf-8"
    )


def _seed_slice_commit_verified(repo: Path, feature_id: str, slice_id: str) -> None:
    _ledger(repo, feature_id).append_gate_event(
        event="SliceCommitVerified", slice_id=slice_id, feature_id=feature_id
    )


def _seed_feature_end_complete(repo: Path, feature_id: str) -> None:
    ledger = _ledger(repo, feature_id)
    ledger.append_feature_end_event(
        "EBatchRefactorCompleted", None, feature_id=feature_id
    )
    ledger.append_feature_end_event(
        "FeatureEndReviewVerdict", "deadbeefcafe", feature_id=feature_id
    )


def test_main_names_feature_end_run_when_every_slice_shipped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: DISCUSS Elevator Pitch, feature-delta.md [REF] Slice
    Plan slice-03 row.

    Given every declared Slice Plan row carries a `SliceCommitVerified`
    ledger record (all shipped) and no `EBatchRefactorCompleted` record
    exists yet, `des next` reports `loop_state=FEATURE_END_PENDING` and
    names `des feature-end run` as the producing-tool `how` -- generalizing
    the F-56 `FeatureEndPending` last-slice notice to this projection's
    terminal branch (D36 reproduced symptom: this used to be a mute
    `INDETERMINATE`).
    """
    feature_id = "des-next-feature-end-pending"
    _write_feature_delta_all_shipped(tmp_path, feature_id, _ALL_SHIPPED_SLICE_IDS)
    for slice_id in _ALL_SHIPPED_SLICE_IDS:
        _seed_slice_commit_verified(tmp_path, feature_id, slice_id)

    exit_code, verdict = _run(capsys, tmp_path, feature_id)

    assert exit_code == 0, f"expected exit 0 (a step was projected): {verdict!r}"
    assert verdict.get("loop_state") == "FEATURE_END_PENDING", (
        f"every slice shipped + no completion evidence must report "
        f"FEATURE_END_PENDING, never a mute INDETERMINATE: {verdict!r}"
    )
    assert verdict.get("how") == "des feature-end run", (
        f"the feature-end branch must name the exact producing-tool "
        f"invocation: {verdict!r}"
    )
    assert verdict.get("step_kind") == "producing-tool", verdict


def test_main_reports_done_when_feature_end_cycle_completed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: feature-delta.md [REF] Slice Plan slice-03 row.

    Given every declared slice shipped AND an `EBatchRefactorCompleted`
    ledger record exists for the feature, `des next` reports
    `loop_state=DONE` -- the feature-end cycle already ran.
    """
    feature_id = "des-next-feature-end-done"
    _write_feature_delta_all_shipped(tmp_path, feature_id, _ALL_SHIPPED_SLICE_IDS)
    for slice_id in _ALL_SHIPPED_SLICE_IDS:
        _seed_slice_commit_verified(tmp_path, feature_id, slice_id)
    _seed_feature_end_complete(tmp_path, feature_id)

    exit_code, verdict = _run(capsys, tmp_path, feature_id)

    assert exit_code == 0, verdict
    assert verdict.get("loop_state") == "DONE", (
        f"a recorded EBatchRefactorCompleted must report DONE: {verdict!r}"
    )


@pytest.mark.negative_at
def test_main_never_reports_done_without_completion_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: pure-function

    Negative oracle for the feature-end branch: a Slice Plan whose rows are
    all `shipped` but NO `EBatchRefactorCompleted` ledger record exists must
    NEVER report `DONE` -- a false-DONE would fabricate completion over a
    cycle that never ran (GDP-6 no-silent-wrong), the mirror image of the
    positive test above.
    """
    feature_id = "des-next-feature-end-not-done"
    _write_feature_delta_all_shipped(tmp_path, feature_id, _ALL_SHIPPED_SLICE_IDS)
    for slice_id in _ALL_SHIPPED_SLICE_IDS:
        _seed_slice_commit_verified(tmp_path, feature_id, slice_id)

    exit_code, verdict = _run(capsys, tmp_path, feature_id)

    assert exit_code == 0, verdict
    assert verdict.get("loop_state") != "DONE", (
        f"WRONG outcome produced: DONE must never be reported without an "
        f"EBatchRefactorCompleted ledger record: {verdict!r}"
    )


@pytest.mark.negative_at
def test_main_reports_indeterminate_on_status_ledger_drift_in_feature_end_branch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: pure-function

    Negative oracle, table-ahead-of-ledger direction: a Slice Plan row whose
    Status column reads `shipped` but carries NO `SliceCommitVerified`
    ledger record must resolve to `INDETERMINATE` naming the disagreement --
    never a false `FEATURE_END_PENDING` (which would silently trust the
    markdown Status column alone). Mirrors the existing ledger-ahead-of-table
    `_DriftedSlice` case in the opposite direction.
    """
    feature_id = "des-next-feature-end-drift"
    _write_feature_delta_all_shipped(tmp_path, feature_id, ("slice-01",))
    # Deliberately NOT seeding SliceCommitVerified for slice-01.

    exit_code, verdict = _run(capsys, tmp_path, feature_id)

    assert exit_code == 0, verdict
    assert verdict.get("loop_state") == "INDETERMINATE", (
        f"a Status='shipped' row with no SliceCommitVerified ledger record "
        f"must report INDETERMINATE, never a guessed FEATURE_END_PENDING: "
        f"{verdict!r}"
    )
    # `what` only (not `why`): the PRE-fix generic INDETERMINATE's `why` text
    # happens to contain the substring "slice-01" (it names this feature's
    # OWN slice-01, an unrelated self-reference) -- checking `why` too would
    # let a stale, non-drift-naming message pass by coincidence.
    what = verdict.get("what", "").lower()
    assert "slice-01" in what, (
        f"the INDETERMINATE message must name the drifted slice in `what`: {verdict!r}"
    )
    assert "slicecommitverified" in what, (
        f"the `what` must name the missing ledger evidence: {verdict!r}"
    )
