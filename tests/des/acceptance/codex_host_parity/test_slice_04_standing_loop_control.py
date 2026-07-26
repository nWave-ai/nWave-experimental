"""Active-RED acceptance contract for the standing-loop operator journey.

@feature-codex-host-parity
@slice-04
@contract-shape:real-io

The tests drive the future standing-loop composition root and use real isolated
project directories.  They intentionally do not create a second LoopRunner.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from .composition_slice_04_standing_loop import StandingLoopComposition
from .domain_types_slice_04_standing_loop import ContinuedWork, ManualOccurrence


pytestmark = [pytest.mark.acceptance]


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        if name in value:
            return value[name]
    elif hasattr(value, name):
        return getattr(value, name)
    raise AssertionError(
        f"WHAT: the StandingLoopFacade result omits required field {name!r}. "
        "WHY: the locked public receipt cannot prove its durable state without it. "
        "HOW: project the des.loop.command-result.v1 identity, resource, context, "
        "isolation, attestation, and diagnostic fields from the facade result."
    )


def _work(project_root: Path, *, context_mode: str = "reconstructed") -> ContinuedWork:
    return ContinuedWork(
        project_root=project_root,
        outcome="produce one bounded, inspectable continued-work result",
        context_mode=context_mode,
        max_tokens_per_tick=1200,
        max_wall_seconds=30,
        max_agent_concurrency=1,
        max_box_concurrency=1,
        continuity_proof_id=None,
    )


def _record_for(records: Any, project_root: Path) -> Any:
    candidates = records.values() if isinstance(records, dict) else records
    return next(
        record
        for record in candidates
        if _field(record, "project_root") == project_root
    )


def test_loop_inspection_discloses_context_and_limits_without_starting_work(
    tmp_path: Path,
) -> None:
    """Property: inspection explains the proposed continuation without starting it."""
    # covers: R1
    control = StandingLoopComposition()
    work = _work(tmp_path / "operator-project", context_mode="reconstructed")

    inspection = control.inspect(work)

    assert _field(inspection, "outcome") == work.outcome, (
        "WHAT: inspection must expose the declared outcome. "
        "WHY: the operator needs a truthful proposal before authorising work. "
        "HOW: report the durable continuation outcome from the control surface."
    )
    assert _field(inspection, "context_mode") == "reconstructed", (
        "WHAT: inspection must label reconstructed context exactly. "
        "WHY: reconstructed context cannot claim native-chat continuity. "
        "HOW: expose the evidence-backed context mode without promotion."
    )
    assert _field(inspection, "limits") == {
        "max_tokens_per_tick": 1200,
        "max_wall_seconds": 30,
        "max_agent_concurrency": 1,
        "max_box_concurrency": 1,
    }, (
        "WHAT: inspection must disclose every operator-relevant bound. "
        "WHY: hidden limits make a manual continuation unsafe to authorise. "
        "HOW: return the exact configured token, time, agent, and box limits."
    )
    assert _field(inspection, "started") is False, (
        "WHAT: inspection must not start work. WHY: a probe is not authorisation. "
        "HOW: leave desired state unarmed and create no occurrence or attestation."
    )


def test_loop_arm_records_intent_without_claiming_observed_execution(
    tmp_path: Path,
) -> None:
    """Property: arm records operator intent without misreporting backend fact."""
    # covers: R2
    control = StandingLoopComposition()
    work = _work(tmp_path / "operator-project")

    handle = control.arm(work, idempotency_key="arm-once")
    record = _record_for(control.list(work.project_root), work.project_root)
    unproved_native = control.arm(
        _work(tmp_path / "native-project", context_mode="native_chat"),
        idempotency_key="must-not-arm-without-proof",
    )

    assert _field(handle, "generation") == _field(record, "generation"), (
        "WHAT: arm and listing must agree on one generation. "
        "WHY: a changed generation changes occurrence identity. "
        "HOW: persist and list the same durable generation."
    )
    assert _field(record, "desired_state") == "ARMED", (
        "WHAT: an armed request must be represented as desired ARMED. "
        "WHY: operator intent is not an observed scheduler fact. "
        "HOW: store desired_state separately from observed_state."
    )
    assert _field(record, "observed_state") in {
        "SCHEDULED",
        "UNAVAILABLE",
        "DRIFTED",
    }, (
        "WHAT: listing must return a recognised observed state. "
        "WHY: it must never relabel desired ARMED as a proved backend fact. "
        "HOW: report scheduler observation or its explicit limitation."
    )
    assert _field(unproved_native, "status") == "refused"
    assert _field(_field(unproved_native, "diagnostic"), "code") == (
        "CONTEXT_CONTINUITY_UNPROVED"
    ), (
        "WHAT: native_chat armed without a concrete challenge-bound proof. "
        "WHY: a context label is not evidence that the original conversation resumed. "
        "HOW: require a fresh, project/host-bound ContinuityProofReceipt before mutation."
    )
    assert all(
        _field(_field(unproved_native, "diagnostic"), key)
        for key in ("what", "why", "how")
    )


def test_manual_loop_occurrence_writes_one_bounded_attestation(
    tmp_path: Path,
) -> None:
    """Property: one manual occurrence is bounded and attestable exactly once."""
    # covers: R3
    control = StandingLoopComposition()
    work = _work(tmp_path / "operator-project")
    handle = control.arm(work, idempotency_key="arm-once")
    occurrence = ManualOccurrence(_field(handle, "loop_id"), "manual-occurrence-1")

    attestation = control.tick(work.project_root, occurrence)
    replayed = control.tick(work.project_root, occurrence)

    assert _field(attestation, "occurrence_key") == occurrence.idempotency_key, (
        "WHAT: attestation must identify the manual occurrence. "
        "WHY: durable progress cannot be distinguished from a duplicate without it. "
        "HOW: persist the caller idempotency key with the completed occurrence."
    )
    assert _field(attestation, "budget") == {
        "max_tokens_per_tick": 1200,
        "max_wall_seconds": 30,
        "max_agent_concurrency": 1,
        "max_box_concurrency": 1,
    }, (
        "WHAT: attestation must retain the applied bounds. "
        "WHY: a successful-looking tick without resource accounting is not trustworthy. "
        "HOW: write the effective token, time, agent, and box limits atomically."
    )
    assert _field(attestation, "outcome") == "CHANGED", (
        "WHAT: the declared executable manual continuation did not make progress. "
        "WHY: NO_CHANGE is a legitimate distinct attestation for a no-op action, but "
        "it cannot satisfy this charter's promised inspectable progress outcome. "
        "HOW: execute the one semantic action through the canonical tick port and "
        "attest CHANGED only after its observed effect is durable."
    )
    assert _field(attestation, "requested_digest")
    assert _field(attestation, "observed_digest"), (
        "WHAT: a changed tick has no observed action digest. "
        "WHY: requested intent alone cannot prove progress occurred. "
        "HOW: atomically seal the observed semantic-action digest with CHANGED."
    )
    assert _field(attestation, "isolation")["receipt_id"]
    resources = _field(attestation, "resources")
    assert set(resources) == {"authorised", "consumed"}, (
        "WHAT: tick omitted its action digest, isolation receipt, or consumed resources. "
        "WHY: progress without bounded receipts is not a durable attestation. "
        "HOW: atomically seal requested/observed work and resource/isolation evidence."
    )
    authorised = resources["authorised"]
    consumed = resources["consumed"]
    assert set(consumed) == {
        "tokens",
        "wall_seconds",
        "agent_concurrency",
        "box_concurrency",
    }
    assert 0 < consumed["tokens"] <= authorised["max_tokens_per_tick"]
    assert 0 < consumed["wall_seconds"] <= authorised["max_wall_seconds"]
    assert 0 < consumed["agent_concurrency"] <= authorised["max_agent_concurrency"]
    assert 0 < consumed["box_concurrency"] <= authorised["max_box_concurrency"]
    assert _field(replayed, "id") == _field(attestation, "id"), (
        "WHAT: repeating one manual occurrence created a different attestation. "
        "WHY: duplicate callbacks must not repeat semantic progress. "
        "HOW: return the original durable occurrence receipt with replayed=true."
    )
    assert _field(replayed, "replayed") is True


def test_loop_recovery_preserves_identity_and_prior_evidence(
    tmp_path: Path,
) -> None:
    """Property: a fresh control surface recovers, never recreates, work."""
    # covers: R4
    original = StandingLoopComposition()
    work = _work(tmp_path / "operator-project")
    handle = original.arm(work, idempotency_key="arm-once")
    occurrence = ManualOccurrence(_field(handle, "loop_id"), "manual-occurrence-1")
    attestation = original.tick(work.project_root, occurrence)

    recovered = StandingLoopComposition().recover(work.project_root)

    assert _field(recovered, "declared_outcome") == work.outcome, (
        "WHAT: recovery must preserve the declared outcome. "
        "WHY: interruption must not replace the operator's scope. "
        "HOW: reload the original durable declaration rather than constructing a new one."
    )
    assert _field(recovered, "context_mode") == "reconstructed", (
        "WHAT: recovery must retain reconstructed context. "
        "WHY: a fresh invocation has no native-chat sentinel proof. "
        "HOW: preserve or downgrade context honestly; never promote it."
    )
    assert _field(recovered, "attestation_count") == 1, (
        "WHAT: recovery must show exactly one prior occurrence attestation. "
        "WHY: replaying durable work would duplicate progress. "
        "HOW: recover the stored occurrence instead of executing it again."
    )
    recovered_attestation = _field(recovered, "attestation")
    assert _field(recovered_attestation, "id") == _field(attestation, "id")
    assert _field(recovered_attestation, "outcome") == "CHANGED", (
        "WHAT: recovery cannot show the durable changed attestation it claims to preserve. "
        "WHY: a count alone cannot distinguish completed progress from no-change or a "
        "replayed occurrence. HOW: return the stored attestation unchanged."
    )
    assert _field(recovered_attestation, "observed_digest") == _field(
        attestation, "observed_digest"
    )
    assert _field(recovered, "applied") is False
    assert _field(recovered, "reconciliation_digest"), (
        "WHAT: recovery did not expose a non-mutating reconciliation digest. "
        "WHY: a fresh invocation must distinguish a plan from an applied recovery. "
        "HOW: return the durable identity/evidence plus a separately applicable plan."
    )


def test_loop_state_is_project_isolated_and_exhausted_limits_are_refused(
    tmp_path: Path,
) -> None:
    """Property: each project owns its state and a bounded refusal is truthful."""
    # covers: R5
    control = StandingLoopComposition()
    first = _work(tmp_path / "first-project")
    second = _work(tmp_path / "second-project")
    first_handle = control.arm(first, idempotency_key="first-arm")
    second_handle = control.arm(second, idempotency_key="second-arm")

    first_attestation = control.tick(
        first.project_root,
        ManualOccurrence(_field(first_handle, "loop_id"), "first-tick"),
    )
    second_attestation = control.tick(
        second.project_root,
        ManualOccurrence(_field(second_handle, "loop_id"), "second-tick"),
    )

    assert _field(first_attestation, "project_root") == first.project_root, (
        "WHAT: the first attestation must remain in its own project. "
        "WHY: cross-project progress would borrow another operator's state. "
        "HOW: bind occurrence, ledger, context, and isolation to one project root."
    )
    assert _field(second_attestation, "project_root") == second.project_root, (
        "WHAT: the second attestation must remain in its own project. "
        "WHY: resource accounting is per project and must not leak. "
        "HOW: isolate the second ledger and work environment from the first."
    )
    assert _field(second_attestation, "budget_verdict") in {
        "AVAILABLE",
        "REFUSED",
        "INDETERMINATE",
    }, (
        "WHAT: an exhausted or unprovable budget must be visible. "
        "WHY: a tick must not continue beyond authorised resources. "
        "HOW: return an explicit available, refused, or indeterminate budget verdict."
    )
    assert _field(first_attestation, "project_id") != _field(
        second_attestation, "project_id"
    )
    assert _field(first_attestation, "ledger_digest") != _field(
        second_attestation, "ledger_digest"
    ), (
        "WHAT: two projects share durable identity or ledger evidence. "
        "WHY: a tick must not borrow another project's context, limits, or progress. "
        "HOW: bind ledger, occurrence, isolation, and accounting to canonical ProjectId."
    )


@pytest.mark.negative_at
def test_stopped_loop_never_accepts_a_later_manual_occurrence(tmp_path: Path) -> None:
    """Negative: repeat stop remains stopped and blocks a later manual tick."""
    # covers: R6
    control = StandingLoopComposition()
    work = _work(tmp_path / "operator-project")
    handle = control.arm(work, idempotency_key="arm-once")

    first_stop = control.stop(work.project_root, handle)
    second_stop = control.stop(work.project_root, handle)
    after_stop = control.tick(
        work.project_root,
        ManualOccurrence(_field(handle, "loop_id"), "must-not-run-after-stop"),
    )

    assert _field(first_stop, "observed_state") == "STOPPED", (
        "WHAT: first stop must be observed STOPPED. "
        "WHY: a tombstone is not complete until cancellation is observed. "
        "HOW: persist the tombstone before cancellation and report the observation."
    )
    assert _field(second_stop, "observed_state") == "STOPPED", (
        "WHAT: repeated stop must preserve STOPPED. "
        "WHY: stop is required to be idempotent. "
        "HOW: return the existing stopped outcome without reviving or duplicating work."
    )
    assert _field(second_stop, "changed") is False
    assert _field(after_stop, "outcome") == "REFUSED_STOPPED", (
        "WHAT: a post-stop manual tick must be refused. "
        "WHY: tombstoned work has no authorisation to claim a new occurrence. "
        "HOW: revalidate the tombstone before claim and return REFUSED_STOPPED."
    )


@pytest.mark.negative_at
def test_stop_winning_the_tick_race_never_projects_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Race AT: CLI's ARMED precheck is not authority once stop reaches runner entry."""
    # covers: R6
    from des.application.loop_runner import LoopControlService, LoopRunner
    from des.cli import loop as loop_cli

    project = tmp_path / "racing-project"
    control = StandingLoopComposition()
    work = _work(project)
    handle = control.arm(work, idempotency_key="arm-before-race")
    loop_id = _field(handle, "loop_id")
    before = LoopControlService().last_attestation(project)
    assert before is None, "the race begins with no durable progress attestation"

    runner_entered = threading.Event()
    stop_completed = threading.Event()
    release_runner = threading.Event()
    original_execute_tick = LoopRunner.execute_tick

    def stop_after_cli_precheck() -> None:
        assert runner_entered.wait(timeout=5), (
            "runner never received the prechecked tick"
        )
        record = LoopControlService().list(project)[0]
        LoopControlService().stop(project, record)
        stop_completed.set()
        release_runner.set()

    stopper = threading.Thread(target=stop_after_cli_precheck, daemon=True)

    def racing_execute_tick(
        self: LoopRunner,
        occurrence: object,
        context: object,
        budget: object,
        isolation: object,
    ) -> object:
        runner_entered.set()
        assert release_runner.wait(timeout=5), (
            "WHAT: the test could not complete stop at the runner boundary. "
            "WHY: this would not exercise the CLI-precheck-to-runner race. "
            "HOW: preserve the explicit runner-entry synchronization seam."
        )
        assert stop_completed.is_set()
        return original_execute_tick(self, occurrence, context, budget, isolation)

    monkeypatch.setattr(LoopRunner, "execute_tick", racing_execute_tick)
    stopper.start()
    exit_code = loop_cli.main(
        [
            "tick",
            "--project",
            str(project),
            "--handle",
            str(loop_id),
            "--idempotency-key",
            "tick-racing-stop",
            "--format",
            "json",
        ]
    )
    stopper.join(timeout=5)
    assert not stopper.is_alive(), "stop race thread did not terminate"
    event = json.loads(capsys.readouterr().out)
    after = LoopControlService().last_attestation(project)

    assert exit_code == 5, (
        "WHAT: a stop that wins after CLI precheck returned a success exit. "
        "WHY: a precheck is stale once stop reaches the runner boundary. "
        "HOW: revalidate the durable tombstone immediately before claim/finalize and "
        "project HANDLE_STOPPED as a closed public refusal."
    )
    assert event["event_type"] == "LOOP_COMMAND_REFUSED"
    assert event["status"] == "refused"
    assert event["diagnostic"]["code"] == "HANDLE_STOPPED"
    assert "attestation" not in event, (
        "WHAT: a stop-winning race projected an attestation. WHY: a refusal cannot "
        "masquerade as completed progress. HOW: omit selection/attestation from every "
        "HANDLE_STOPPED public event."
    )
    assert after is before is None, (
        "WHAT: a stop-winning race created a durable attestation. "
        "WHY: no new occurrence may be claimed or finalized after stop. "
        "HOW: make tombstone validation and occurrence claim/finalization one atomic "
        "runner-side decision."
    )
