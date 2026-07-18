"""Regression: ``des next`` ignores terminal ledger evidence and can crash.

RCA (team-lead dispatch, empirically reproduced): feature
``blast-radius-measured-tier``, slice-01, real commit ``1b07ff85d`` with a
verified Gate-Scope. The ledger
(``.nwave/telemetry/atdd-pure/blast-radius-measured-tier.jsonl``) carries
``SliceCommitVerified`` for slice-01, but the Slice Plan row's markdown
``Status`` column was never flipped from ``pending``. ``des next
--feature-id blast-radius-measured-tier`` nevertheless projects
``loop_state=SLICE_IN_PROGRESS, phase=D_DISTILL,
what="slice slice-01's acceptance tests are not yet authored.",
how="/nw-distill --feature-id blast-radius-measured-tier --slice slice-01"``
-- instructing the operator to re-author acceptance tests that are already
written, GREEN, reviewed and shipped. Following the tool's own ``how``
destroys delivered work (the "lying producing tool" class, GDP-3/GDP-6).

Two confirmed roots (code-read,
``src/des/application/deliver_loop_projection.py``):

1. ``_first_pending_row`` (:169-173) selects the first Slice Plan row whose
   MARKDOWN ``Status`` column reads ``pending``, with NO ledger
   consultation. A ledger-verified-but-markdown-un-flipped slice is still
   picked as "the pending slice".
2. ``_project_pending_slice`` (:176-237) walks its evidence chain starting
   at ``RedObserved`` and never consults the terminal
   ``SliceCommitVerified`` evidence at all.
3. RELATED, same function (:233): a fully EXAMINE-verified slice hits a
   bare ``raise NotImplementedError(...)`` -- a producing tool crashing
   with a raw traceback on a fully-finished slice is the same trust
   failure wearing a different hat.

The fixed contract (pinned here, GDP-3 + GDP-6): terminal evidence
(``SliceCommitVerified``) WINS over the markdown ``Status`` column and must
never be reported as "acceptance tests are not yet authored"; a genuinely
unfinished slice (zero ledger evidence) must still correctly route to
DISTILL (the anti-over-correction guard); an EXAMINE-verified slice must
resolve to an honest projection or INDETERMINATE, never a raw
``NotImplementedError``; and an unreadable/malformed ledger must degrade
LOUD to INDETERMINATE naming the read failure, never a raw
``LedgerIntegrityViolation`` traceback.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process): the REAL
``des.cli.next_step.main()`` CLI driver via ``capsys`` (witnesses a/b) and the
REAL ``des.application.deliver_loop_projection.project_next_step`` pure
composition core directly (witnesses c/d, which must observe an exception
that would otherwise escape the CLI shell uncaught). No subprocess fork --
``des next``'s own walking-skeleton budget is not this file's to spend.

Fixture-repo builder reused verbatim (shape, not import) from
``tests/des/acceptance/test_des_next_loop_projection.py`` -- the
``feature_delta_doctor``-clean ``[REF] Slice Plan`` table shape every
``project_next_step`` call needs to clear the structural preflight and reach
the real precondition walk.

GIT SAFETY: no git is used anywhere in this file -- every fixture is a plain
``tmp_path`` filesystem tree (feature-delta.md + JSONL ledger), matching the
design's own GDP-7 (agnostic) claim that a mid-loop projection needs no git
at all.

THIS FILE IS TEST-ONLY. No production code is touched by this authoring
pass. A crafter fixes ``deliver_loop_projection.py`` against this test; it
must NEVER be weakened or skipped to reach GREEN.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import (
    SLICE_COMMIT_VERIFIED,
    AtCompletionLedger,
    LedgerIntegrityViolation,
)
from des.application.deliver_loop_projection import project_next_step
from des.cli.next_step import main as next_step_main
from des.cli.record_examine_verdict import record_examine_verdict


# ---------------------------------------------------------------------------
# Fixture-repo builder -- same `feature_delta_doctor`-clean Slice Plan shape
# as tests/des/acceptance/test_des_next_loop_projection.py, parametrized on
# the row's markdown Status so a witness can pin the "verified but never
# flipped" shape that triggers the defect.
# ---------------------------------------------------------------------------


def _feature_delta_text(feature_id: str, slice_id: str, status: str) -> str:
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
        f"{status} | @walking_skeleton | walking skeleton |\n"
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
    repo: Path, feature_id: str, slice_id: str, *, status: str = "pending"
) -> None:
    delta_path = repo / "docs" / "feature" / feature_id / "feature-delta.md"
    delta_path.parent.mkdir(parents=True, exist_ok=True)
    delta_path.write_text(
        _feature_delta_text(feature_id, slice_id, status), encoding="utf-8"
    )


def _ledger(repo: Path, feature_id: str) -> AtCompletionLedger:
    return AtCompletionLedger(feature_id, repo)


def _run(
    capsys: pytest.CaptureFixture[str], repo: Path, feature_id: str
) -> tuple[int, dict]:
    exit_code = next_step_main(
        ["--feature-id", feature_id, "--repo", str(repo), "--format", "json"]
    )
    captured = capsys.readouterr()
    verdict = json.loads(captured.out)
    return exit_code, verdict


# ---------------------------------------------------------------------------
# Witness (a) -- THE headline regression: a SliceCommitVerified slice whose
# markdown Status was never flipped must NOT be projected as "acceptance
# tests are not yet authored" / routed to /nw-distill.
# ---------------------------------------------------------------------------

_FEATURE_ID_A = "des-next-terminal-evidence-regression"
_SLICE_ID = "slice-01"


def test_main_never_prescribes_reauthoring_a_terminal_verified_slice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ``SliceCommitVerified`` slice is DONE regardless of a stale markdown
    ``Status`` column; ``des next`` must never instruct re-authoring its
    already-shipped acceptance tests.

    Reproduces the live symptom (``blast-radius-measured-tier`` slice-01,
    commit ``1b07ff85d``) hermetically: markdown Status stays ``pending``,
    the ledger carries the real terminal ``SliceCommitVerified`` record.
    """
    _write_feature_delta(tmp_path, _FEATURE_ID_A, _SLICE_ID, status="pending")
    _ledger(tmp_path, _FEATURE_ID_A).append_gate_event(
        event=SLICE_COMMIT_VERIFIED, slice_id=_SLICE_ID, feature_id=_FEATURE_ID_A
    )

    exit_code, verdict = _run(capsys, tmp_path, _FEATURE_ID_A)

    assert exit_code == 0, f"expected a controlled exit 0 projection: {verdict!r}"
    what = str(verdict.get("what", "")).lower()
    how = str(verdict.get("how", ""))
    assert "not yet authored" not in what, (
        f"WRONG outcome produced: slice {_SLICE_ID} carries a terminal "
        f"SliceCommitVerified ledger record -- it is DONE -- yet des next "
        f"still reports its acceptance tests as not yet authored, ignoring "
        f"the terminal evidence entirely: {verdict!r}"
    )
    assert how != f"/nw-distill --feature-id {_FEATURE_ID_A} --slice {_SLICE_ID}", (
        f"WRONG outcome produced: des next's own HOW instructs re-running "
        f"/nw-distill on a slice that is already committed and "
        f"ledger-verified -- following it would destroy delivered work: "
        f"{verdict!r}"
    )


# ---------------------------------------------------------------------------
# Witness (b) -- anti-over-correction guard: a slice with ZERO ledger
# evidence must still correctly route to D_DISTILL. A fix that makes every
# slice look done is as bad as the lie this regression pins.
# ---------------------------------------------------------------------------

_FEATURE_ID_B = "des-next-terminal-evidence-guard"


def test_main_still_routes_a_genuinely_unauthored_slice_to_distill(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A slice with no ledger evidence at all is genuinely unauthored and
    must still project D_DISTILL / /nw-distill -- the terminal-evidence fix
    must not silently mark every slice as done."""
    _write_feature_delta(tmp_path, _FEATURE_ID_B, _SLICE_ID, status="pending")
    _ledger(tmp_path, _FEATURE_ID_B).append_gate_event(
        event="LedgerBootstrapped", slice_id="", feature_id=_FEATURE_ID_B
    )

    exit_code, verdict = _run(capsys, tmp_path, _FEATURE_ID_B)

    assert exit_code == 0, verdict
    assert verdict.get("loop_state") == "SLICE_IN_PROGRESS", verdict
    assert verdict.get("phase") == "D_DISTILL", (
        f"a slice with zero ledger evidence must still route to D_DISTILL "
        f"-- the terminal-evidence fix must not over-correct into treating "
        f"every slice as done: {verdict!r}"
    )
    assert (
        verdict.get("how")
        == f"/nw-distill --feature-id {_FEATURE_ID_B} --slice {_SLICE_ID}"
    ), verdict


# ---------------------------------------------------------------------------
# Witness (c) -- a fully EXAMINE-verified slice must never crash the caller
# with a raw NotImplementedError.
# ---------------------------------------------------------------------------

_FEATURE_ID_C = "des-next-examine-verified-no-crash"


def test_project_next_step_never_raises_on_fully_examine_verified_slice(
    tmp_path: Path,
) -> None:
    """RedObserved + ATReviewVerdict + a recorded ExamineVerdict together
    describe a fully EXAMINE-verified slice. ``project_next_step`` must
    resolve to an honest projection (or INDETERMINATE), never a bare
    ``NotImplementedError`` traceback -- a producing tool crashing on a
    fully-finished slice is the same trust failure the headline regression
    pins, wearing a different hat."""
    feature_id = _FEATURE_ID_C
    _write_feature_delta(tmp_path, feature_id, _SLICE_ID, status="pending")
    ledger = _ledger(tmp_path, feature_id)
    ledger.append_gate_event(
        event="RedObserved", slice_id=_SLICE_ID, feature_id=feature_id
    )
    ledger.append_review_verdict(_SLICE_ID, {}, feature_id=feature_id)

    charter_dir = tmp_path / "docs" / "product" / "expectations" / feature_id
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / "intent.md"
    charter_path.write_text("# Intent\n", encoding="utf-8")
    record_examine_verdict(
        tmp_path,
        feature_id,
        _SLICE_ID,
        charter_path,
        verdict="PASS",
        observations="Vera observed the feature works end to end.",
        examiner="nw-user-examiner",
        timestamp="2026-07-18T00:00:00Z",
    )

    try:
        step = project_next_step(tmp_path, feature_id)
    except NotImplementedError as exc:
        pytest.fail(
            f"WRONG outcome produced: a fully EXAMINE-verified slice must "
            f"resolve to an honest projection or INDETERMINATE, never a "
            f"raw NotImplementedError traceback: {exc}"
        )

    assert step.what and step.why and step.how, (
        f"an EXAMINE-verified slice's projection must self-explain "
        f"(what/why/how), not return a hollow value: {step!r}"
    )


# ---------------------------------------------------------------------------
# Witness (d) -- NEGATIVE / honesty witness: an unreadable or malformed
# ledger must degrade to a controlled INDETERMINATE, never a raw
# LedgerIntegrityViolation traceback.
# ---------------------------------------------------------------------------

_FEATURE_ID_D = "des-next-malformed-ledger-honesty"


@pytest.mark.negative_at
def test_project_next_step_degrades_to_indeterminate_on_unreadable_ledger(
    tmp_path: Path,
) -> None:
    """A malformed AT-completion ledger must never crash ``des next`` with a
    raw ``LedgerIntegrityViolation`` -- it must degrade LOUD to
    ``INDETERMINATE`` naming what could not be read (GDP-6: no
    silent-wrong, no confident next-step over unreadable evidence)."""
    feature_id = _FEATURE_ID_D
    _write_feature_delta(tmp_path, feature_id, _SLICE_ID, status="pending")

    ledger_path = (
        tmp_path / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text("this is not a JSON object\n", encoding="utf-8")

    try:
        step = project_next_step(tmp_path, feature_id)
    except LedgerIntegrityViolation as exc:
        pytest.fail(
            f"WRONG outcome produced: a malformed AT-completion ledger must "
            f"resolve to a controlled INDETERMINATE naming the read "
            f"failure, never an uncaught LedgerIntegrityViolation "
            f"traceback: {exc}"
        )

    assert step.loop_state == "INDETERMINATE", (
        f"a malformed ledger must degrade LOUD to INDETERMINATE, never "
        f"silently invent a next step: {step!r}"
    )
    reason = f"{step.what} {step.why}".lower()
    assert "ledger" in reason and (
        "malformed" in reason
        or "cannot" in reason
        or "unreadable" in reason
        or "integrity" in reason
        or "corrupt" in reason
    ), (
        f"the INDETERMINATE message must name the ledger read failure, not "
        f"a generic message: {step!r}"
    )
