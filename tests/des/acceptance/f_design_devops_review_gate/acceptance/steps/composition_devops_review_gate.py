"""Composition root for f-design-devops-review-gate slice-02 (DEVOPS + literal-lift).

THE SSOT-REUSE PROOF (brief §8 slice-02): the SAME generic review-verdict
mechanism the DESIGN wave uses serves the DEVOPS wave with ZERO new verdict logic
-- only the wave name changes. This composition deliberately REUSES the slice-01
driving-surface primitives VERBATIM (the stdlib registry scanner, the ``des`` CLI
subprocess runner, ``CliResult``, ``REPO_ROOT``) and parameterizes them to
``wave="devops"`` -- the test-side echo of the production-side "one generic core,
thin per-wave bindings" contract.

DRIVING SURFACE (Mandate-13 driving-port-only -- THREE real wired seams, no
direct-domain import for business logic):

  * Layer 3 composition (AT-5) -- the REAL spine
    ``wave_gate_stack_dispatch.resolve_stack("devops", "gate-out")`` reading the
    SHIPPED canonical wave-contract registry ``nWave/waves/devops.yaml`` in the
    repo (the registry HOME, NOT the flavor -- brief §2/§3 slice-06
    reconciliation; ADR-FLOW-006 D6: resolve_stack reads the registry as the SOLE
    gate-stack source). The observable is the ordered gate-id sequence the
    resolution returns. Reuses the slice-01 stdlib scanner over the SAME registry
    shape (``_scan_boundary_gate_ids``).

  * Layer 3 subprocess (AT-6..8) -- the REAL ``des record-devops-review`` /
    ``des verify-devops-review`` CLIs as black-box processes via the single
    ``des.cli.__main__`` dispatcher. The observable surface is the process exit
    code + the structured JSON verdict payload, nothing else.

  * Layer 3 composition (AT-9 -- the LITERAL-LIFT seam, brief slice-01 pt-4
    deferred to here) -- the REAL ``SubagentStopService.validate`` built via the
    production composition root (``service_factory.create_subagent_stop_service``),
    driven with a ``devops`` wave-active floor under project_root. The observable
    is the service's ``HookDecision`` (allow vs block + reason). This is the seam
    subagent_stop_service.py:307/311/317 keys on the hardcoded ``"discuss"``
    literal -- DELIVER LIFTS it to the active wave so a DEVOPS return dispatches
    the DEVOPS gate-out stack. The DISCUSS-regression safety of this same lift is
    covered by the shipped DISCUSS gate-out ATs
    (tests/des/acceptance/oss_review_verdict_demotion/ + nwave_flow_v2_enforcement/),
    not a separate pin here (carpaccio-ceiling de-dup).

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): the DEVOPS driving-surface declares
the load-bearing net-new seams reached from the dispatcher's, the CLI's, and the
live SubagentStop dispatch's real entry points:

  (seam-1) the canonical registry file ``nWave/waves/devops.yaml`` carrying the
           ``gate_stack.gate-out`` SSOT-A with the ``verify-devops-review`` row
           (brief §3: the registry HOME) -- resolved through the WIRED spine.
  (seam-2) the ``des verify-devops-review`` CONSUMER veto CLI -- reads the latest
           ``DevopsReviewVerdict`` ledger record, seals the feature-delta, and
           delegates to the (generalized) ``ReviewVerdictGate.evaluate`` core.
  (seam-3) the ``des record-devops-review`` PRODUCER CLI -- records a real
           platform-architect-reviewer verdict (BOTH approved AND needs-revision,
           O-4 / DDD-6).
  (seam-4) the LITERAL-LIFT in ``subagent_stop_service._discuss_gate_out_declarative``
           -- the hardcoded ``"discuss"`` (lines 307/311/317) lifted to the active
           wave so the DEVOPS gate-out fires on the live SubagentStop return.

Each slice-02 AT NAMES one of these seams, drives it through the REAL entry point,
and asserts an observable effect.

RED contract (fail-for-right-reason, atdd_pure active-RED -- NOT @skip):
  * AT-5: ``nWave/waves/devops.yaml`` does not exist at HEAD -> the spine resolves
    an EMPTY DEVOPS gate-out stack -> a semantic AssertionError naming the missing
    registry file / verify-devops-review row.
  * AT-6..8: ``verify-devops-review`` / ``record-devops-review`` are NOT registered
    in the ``des`` dispatcher ``_REGISTRY`` at HEAD -> the subprocess exits non-zero
    ("unknown subcommand") -> the observed verdict is none of
    pass/vetoed/indeterminate -> a semantic AssertionError naming the missing CLI seam.
  * AT-9: the live SubagentStop dispatch keys on the hardcoded ``"discuss"`` literal
    (subagent_stop_service.py:307), so a ``devops`` wave-active floor never matches
    -> the gate-out branch returns None -> the atdd_pure devops return ALLOWS clean
    -> a semantic AssertionError (ALLOWED where a BLOCK was expected). GREEN once
    DELIVER lifts the literal AND wires the devops verify gate.
  The DISCUSS-regression safety of the same lift is NOT pinned here (carpaccio-
  ceiling de-dup): it is already covered by the shipped DISCUSS gate-out ATs
  (tests/des/acceptance/oss_review_verdict_demotion/ + nwave_flow_v2_enforcement/),
  which run in this slice's regression check and the feature-end full-suite.
  Every dependency (pytest-bdd, the ``des`` dispatcher subprocess, the production
  composition root, the tmp work-tree) resolves cleanly -- the REDs are deliberate
  missing-functionality / regression-pin signals, not test bugs.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# REUSE the slice-01 driving-surface primitives VERBATIM (SSOT, no duplication):
# the stdlib registry scanner, the des CLI subprocess runner, the CliResult value,
# and the shipped repo-root anchor. The DEVOPS wave rides the SAME machinery.
from .composition_design_review_gate import (
    REPO_ROOT,
    CliResult,
    _run_des_subprocess,
    _scan_boundary_gate_ids,
)
from .domain_types_devops import GateOutcome, ReviewerVerdict, WaveBoundary, WaveFloor


# The SHIPPED canonical wave-contract registry dir (ADR-FLOW-006 D1).
_WAVES_DIR = REPO_ROOT / "nWave" / "waves"
_DEVOPS_REGISTRY_FILE = _WAVES_DIR / "devops.yaml"

# The DEVOPS wave whose gate-out stack is migrated to the canonical registry.
_DEVOPS_WAVE = "devops"

# The gate-id the DEVOPS gate-out stack MUST carry (brief §6 / §7 surface 1).
_VERIFY_DEVOPS_GATE_ID = "verify-devops-review"

# The reviewer whose verdict the DEVOPS producer records (brief §6).
_REVIEWER_AGENT_ID = "nw-platform-architect-reviewer"

# The feature under gate -- a synthetic feature id provisioned in the tmp tree.
_GATED_FEATURE_ID = "synthetic-devops-feature"

# DESIGN-PINNED wave-active floor path (slice-04 contract): a single JSON object
# at this FIXED relative path under project_root (the discriminant the live
# SubagentStop dispatch reads -- subagent_stop_service.py:305).
_FLOOR_FILE_REL = ".nwave/wave-active/active.json"

# Reason-token discriminants the AT-9 loud veto must carry (K1: a veto is
# named-LOUD, never a silent green). The devops veto must name the absent devops
# review verdict.
_DEVOPS_VETO_TOKENS: tuple[str, ...] = (
    "devops",
    "review",
    "verdict",
    "indeterminate",
    "absent",
)


def _devops_sequence_declared_in_registry_file(
    boundary: WaveBoundary,
) -> tuple[str, ...]:
    """Read the DEVOPS gate-id sequence DIRECTLY from the registry FILE.

    Independent read #1 of the AT-5 two-reads cross-check: a direct stdlib parse
    of the SHIPPED ``nWave/waves/devops.yaml`` file (the REUSED slice-01 scanner
    over the SAME registry shape), WITHOUT going through the spine. At HEAD the
    file is absent -> returns the empty tuple (the RED for AT-5).
    """
    try:
        text = _DEVOPS_REGISTRY_FILE.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError, OSError):
        return ()
    return _scan_boundary_gate_ids(text, boundary.value)


def _devops_sequence_resolved_by_spine(boundary: WaveBoundary) -> tuple[str, ...]:
    """Resolve the DEVOPS gate-id sequence through the WIRED spine entry.

    Independent read #2 of the AT-5 two-reads cross-check: drives the REAL
    ``wave_gate_stack_dispatch.resolve_stack("devops", boundary)`` -- the SAME
    spine entry the live SubagentStop gate-out caller uses
    (subagent_stop_service.py:311), with the wave parameterized to ``devops``. The
    spine reads the canonical registry as the SOLE gate-stack source
    (ADR-FLOW-006 D6). At HEAD ``nWave/waves/devops.yaml`` is absent -> the spine
    resolves the empty stack (the RED for AT-5).
    """
    from des.application import wave_gate_stack_dispatch

    resolved = wave_gate_stack_dispatch.resolve_stack(_DEVOPS_WAVE, boundary.value)
    return tuple(
        str(row["gate_id"])
        for row in resolved.rows
        if isinstance(row, dict) and "gate_id" in row
    )


@dataclass
class DevopsReviewGateComposition:
    """Drives the DEVOPS review-verdict gate through its THREE real wired seams.

    AT-5 reads the SHIPPED repo registry. AT-6..8 operate on a tmp work-tree
    carrying the feature-delta + the ledger. AT-9 drives the REAL
    SubagentStopService over a wave-active floor (the literal-lift seam).
    """

    repo_dir: Path
    feature_id: str = field(default=_GATED_FEATURE_ID)
    _resolved_boundary: WaveBoundary | None = field(default=None)
    _verify_result: CliResult | None = field(default=None)
    _record_result: CliResult | None = field(default=None)
    _seam_action: str | None = field(default=None)
    _seam_reason: str | None = field(default=None)

    # ---- paths --------------------------------------------------------------

    @property
    def _feature_delta_path(self) -> Path:
        return self.repo_dir / "docs" / "feature" / self.feature_id / "feature-delta.md"

    # ---- AT-5 given/when/then: registry -> spine seam ------------------------

    def given_devops_registry_file_is_shipped(self) -> None:
        """Arm the SUT to read the SHIPPED canonical devops registry from the repo.

        No fixture authoring of the expected output -- the registry FILE is the
        shipped artifact the SUT reads (Mandate-13 protocol-driver). At HEAD the
        file is absent; the absence is the RED.
        """
        # Nothing to set up beyond pointing at the shipped path -- the file itself
        # (or its absence) is the contract under test.

    def when_dispatcher_resolves_devops_gate_out_from_registry(
        self, boundary: WaveBoundary
    ) -> None:
        """Bind WHICH boundary the Then must cross-check (the reads happen in Then)."""
        self._resolved_boundary = boundary

    def then_resolved_sequence_equals_registry_declared(
        self, boundary: WaveBoundary
    ) -> None:
        """The spine-resolved DEVOPS sequence equals the registry-FILE-declared one.

        SSOT-reuse end-to-end wiring proof (Mandate-15 seam-1): two INDEPENDENT
        reads of the DEVOPS gate-out gate-id sequence must agree -- read #1 the
        registry FILE (stdlib parse, NOT the spine), read #2 the WIRED spine entry
        ``resolve_stack``. Agreement proves resolve_stack ACTUALLY reads the
        devops registry (NOT registry==registry). Non-empty so a both-empty
        trivial pass cannot satisfy it.

        RED at HEAD: ``nWave/waves/devops.yaml`` is absent -> read #1 empty ->
        semantic AssertionError naming the missing registry file.
        """
        self._assert_boundary_matches_when(boundary)
        declared = _devops_sequence_declared_in_registry_file(boundary)
        resolved = _devops_sequence_resolved_by_spine(boundary)
        assert declared, (
            "the DEVOPS gate-out gate stack must be DECLARED (non-empty) in the "
            f"canonical registry file {_DEVOPS_REGISTRY_FILE} (brief §3 "
            "reconciliation: the registry HOME, mirroring nWave/waves/design.yaml "
            "+ discuss.yaml; ADR-FLOW-006 D6 -- the dispatcher reads the registry "
            "as the SOLE gate-stack source) -- read #1 resolved EMPTY (the devops "
            f"registry file does not exist yet). {self._observed()}"
        )
        assert resolved == declared, (
            "the WIRED spine entry wave_gate_stack_dispatch.resolve_stack must "
            f"resolve the DEVOPS {boundary.value} stack to the SAME gate-id "
            "sequence the registry FILE declares (the SSOT-reuse wiring proof for a "
            "SECOND wave, AT-5) -- two independent reads (registry-FILE-declared vs "
            "spine-resolved) must agree, proving resolve_stack reads the devops "
            f"registry, not registry==registry; declared {declared!r}, spine-resolved "
            f"{resolved!r}. {self._observed()}"
        )

    def then_resolved_stack_includes_verify_devops_review(
        self, boundary: WaveBoundary
    ) -> None:
        """The resolved DEVOPS gate-out stack carries the verify-devops-review gate.

        Seam-named oracle (Mandate-15 seam-1 + seam-2): the gate-out stack the
        spine resolves must include the ``verify-devops-review`` CONSUMER veto
        gate-id (brief §6 / §7 surface 1). RED at HEAD: the registry file is absent
        -> the resolved stack is empty -> semantic AssertionError naming the
        missing row.
        """
        self._assert_boundary_matches_when(boundary)
        resolved = _devops_sequence_resolved_by_spine(boundary)
        assert _VERIFY_DEVOPS_GATE_ID in resolved, (
            f"the DEVOPS {boundary.value} stack the spine resolves must include the "
            f"{_VERIFY_DEVOPS_GATE_ID!r} gate (brief §6: the CONSUMER veto row that "
            "fires the DEVOPS review-verdict on the wave return) -- the resolved "
            f"sequence {resolved!r} does not carry it. {self._observed()}"
        )

    def _assert_boundary_matches_when(self, boundary: WaveBoundary) -> None:
        assert self._resolved_boundary is not None, (
            "the dispatcher resolution must run (When) before asserting (Then)"
        )
        assert self._resolved_boundary is boundary, (
            f"Then boundary {boundary.value!r} must match the boundary resolved in "
            f"When ({self._resolved_boundary.value!r}) -- scenario wiring drift"
        )

    # ---- AT-6..8 given: the gated DEVOPS feature substrate --------------------

    def given_devops_feature_with_no_recorded_verdict(self) -> None:
        """Provision a tmp DEVOPS feature with a feature-delta and an empty ledger.

        Precondition state ONLY (NOT the SUT): the feature-delta is the artefact
        the verify gate seals against (DEVOPS fail-closed default seal target,
        DDD-3); NO DevopsReviewVerdict is recorded. No fixture authors the expected
        verdict (No Fixture Theater): the verdict, when present, is written by
        ``des record-devops-review``, not the test.
        """
        self._write_devops_feature_delta()

    # ---- AT-7/AT-8 when: record a real reviewer verdict ----------------------

    def when_reviewer_records_verdict(self, verdict: ReviewerVerdict) -> None:
        """Record a real platform-architect-reviewer verdict via the PRODUCER CLI.

        Drives the REAL ``des record-devops-review --feature-id <id> --verdict <v>
        --reviewer-agent-id <a>`` as a subprocess (Mandate-13 seam-3). The agent
        NEVER hands the gate a verdict; it triggers the RECORDING (DDD-6 / §22.7).
        Writes BOTH approved AND needs-revision (O-4 both-outcomes).

        RED at HEAD: ``record-devops-review`` is not registered in the des
        dispatcher -> the subprocess exits non-zero ("unknown subcommand") and no
        record is written -> the verify When observes no recorded verdict.
        """
        self._record_result = self._run_des(
            [
                "record-devops-review",
                "--feature-id",
                self.feature_id,
                "--verdict",
                verdict.value,
                "--reviewer-agent-id",
                _REVIEWER_AGENT_ID,
                "--repo-root",
                str(self.repo_dir),
            ]
        )

    # ---- AT-6..8 when: verify the gate ---------------------------------------

    def when_devops_review_gate_is_verified(self) -> None:
        """Verify the DEVOPS review-verdict gate via the CONSUMER veto CLI.

        Drives the REAL ``des verify-devops-review --feature-id <id>`` as a
        subprocess (Mandate-13 seam-2). The observable is the process exit code +
        the JSON verdict payload. RED at HEAD: ``verify-devops-review`` is not
        registered in the des dispatcher -> the subprocess exits non-zero
        ("unknown subcommand") -> the observed verdict is none of
        pass/vetoed/indeterminate.
        """
        self._verify_result = self._run_des(
            [
                "verify-devops-review",
                "--feature-id",
                self.feature_id,
                "--repo-root",
                str(self.repo_dir),
            ]
        )

    # ---- AT-6..8 then: the projected gate verdict ----------------------------

    def then_gate_refuses_with_indeterminate(self) -> None:
        """The verify gate REFUSES the DEVOPS return with INDETERMINATE (absent).

        AT-6 (error path): no DevopsReviewVerdict recorded -> the SAME
        ReviewVerdictGate core returns INDETERMINATE("absent") -> exit 1 + verdict
        "indeterminate". Absence reads as a veto, NEVER a silent PASS (DDD-7).
        """
        self._assert_gate_verdict(GateOutcome.INDETERMINATE, expected_exit=1)

    def then_gate_passes_with_pass(self) -> None:
        """The verify gate PASSES the DEVOPS return with "no objection found".

        AT-7 (happy path): after an artefact-current APPROVED verdict is recorded,
        the SAME core returns PASS -> exit 0 + verdict "pass" (NOT a GO, §22.0).
        The record->verify loop closes for a SECOND wave through the SAME core.
        """
        self._assert_gate_verdict(GateOutcome.PASS, expected_exit=0)

    def then_gate_vetoes_with_vetoed(self) -> None:
        """The verify gate VETOES the DEVOPS return on a needs-revision verdict.

        AT-8 (error path): a recorded NEEDS_REVISION verdict -> the core returns
        VETOED -> exit 1 + verdict "vetoed". A reviewer veto is mechanically
        honored (DDD-6).
        """
        self._assert_gate_verdict(GateOutcome.VETOED, expected_exit=1)

    def _assert_gate_verdict(
        self, expected: GateOutcome, *, expected_exit: int
    ) -> None:
        result = self._verify_result
        assert result is not None, (
            "the DEVOPS review-verdict gate must be verified (When) before "
            "asserting its verdict (Then)"
        )
        observed_verdict = result.payload.get("verdict")
        assert observed_verdict == expected.value, (
            "the `des verify-devops-review` CONSUMER veto CLI must project the "
            f"DEVOPS review verdict as {expected.value!r} on exit {expected_exit} "
            "(brief §6 driving ports / DDD-7 GateVerdict projection: it reads the "
            "latest DevopsReviewVerdict ledger record, seals the feature-delta, and "
            "delegates to the SAME ReviewVerdictGate.evaluate core as DESIGN -- the "
            "SSOT-reuse proof) -- the CLI is not registered in the des dispatcher "
            f"yet, so the subprocess returned exit {result.exit_code} with verdict "
            f"{observed_verdict!r}. {self._cli_observed()}"
        )
        assert result.exit_code == expected_exit, (
            f"the verify gate must project verdict {expected.value!r} onto exit "
            f"{expected_exit} (PASS->0, VETOED/INDETERMINATE->1) -- observed exit "
            f"{result.exit_code}. {self._cli_observed()}"
        )

    # ---- AT-9 given: the live SubagentStop literal-lift seam -----------------

    def given_devops_floor_and_feature_delta_no_verdict(self) -> None:
        """Arm a DEVOPS wave-active floor + a feature-delta with no recorded verdict.

        AT-9 precondition state (NOT the SUT): the floor discriminant the live
        SubagentStop dispatch reads (subagent_stop_service.py:305) is set to
        ``devops``; the feature-delta is the artefact the lifted gate-out seals
        against; NO verdict is recorded. The SUT is the production
        ``SubagentStopService.validate`` composition root.
        """
        self._arm_floor(WaveFloor.DEVOPS)
        self._write_devops_feature_delta()

    # ---- AT-9 when: drive the REAL SubagentStop gate -------------------------

    def when_output_returned_through_live_subagent_stop_gate(
        self, floor: WaveFloor
    ) -> None:
        """Drive the REAL SubagentStopService.validate via the production root.

        Layer 3 composition: builds the production
        ``service_factory.create_subagent_stop_service()`` and drives
        ``validate(SubagentStopContext(...))`` with an atdd_pure return whose cwd
        carries the armed wave-active floor. The observable is the service's
        HookDecision (action + reason). For AT-9 (devops floor) the lifted gate-out
        must BLOCK.
        """
        action, reason = self._run_subagent_stop_gate(floor)
        self._seam_action, self._seam_reason = action, reason

    # ---- AT-9 then: the live gate decision -----------------------------------

    def then_live_gate_blocks_naming_absent_devops_verdict(self) -> None:
        """The live SubagentStop gate BLOCKS the DEVOPS return, naming the cause.

        AT-9: the lifted dispatch (active-wave == ``devops``) resolves the DEVOPS
        gate-out stack and fires ``verify-devops-review``, which finds no recorded
        verdict -> INDETERMINATE("absent") -> the service BLOCKS, naming the absent
        devops review verdict (K1: a veto is named-LOUD).

        RED at HEAD: the dispatch keys on the hardcoded ``"discuss"`` literal
        (subagent_stop_service.py:307), so a ``devops`` floor never matches -> the
        gate-out branch returns None -> the atdd_pure devops return ALLOWS clean ->
        this assertion fires (ALLOWED where a BLOCK was expected). GREEN once
        DELIVER lifts the literal to the active wave + wires the devops verify gate.
        """
        assert self._seam_action == "block", (
            "the live SubagentStopService.validate must BLOCK a DEVOPS-wave return "
            "(devops wave-active floor) whose review verdict is absent -- the "
            "gate-out dispatch must fire for the DEVOPS wave once the hardcoded "
            '"discuss" literal (subagent_stop_service.py:307/311/317) is LIFTED to '
            "the active wave (brief slice-01 pt-4 deferred to slice-02 / DDD-2). "
            f"the service returned action={self._seam_action!r}. {self._seam_observed()}"
        )
        reason = (self._seam_reason or "").lower()
        assert any(token in reason for token in _DEVOPS_VETO_TOKENS), (
            "the live DEVOPS gate-out block must NAME the absent devops review "
            f"verdict (one of {_DEVOPS_VETO_TOKENS!r}) so it surfaces as a loud, "
            f"attributable veto (K1); got reason={self._seam_reason!r}. "
            f"{self._seam_observed()}"
        )

    # ---- the des CLI subprocess (REUSED slice-01 driving surface) ------------

    def _run_des(self, subcommand_argv: list[str]) -> CliResult:
        """Run ``python -m des.cli.__main__ <subcommand> ...`` via the slice-01 runner."""
        return _run_des_subprocess(subcommand_argv, cwd=self.repo_dir)

    # ---- the SubagentStop driving surface (REAL production composition root) -

    def _run_subagent_stop_gate(self, floor: WaveFloor) -> tuple[str, str | None]:
        """Drive the REAL SubagentStopService.validate via the production root.

        Runs an atdd_pure return (execution-log-free path) whose cwd carries the
        armed wave-active floor. RED-for-right-reason for AT-9: the gate-out
        dispatch keys on the hardcoded ``"discuss"`` literal, so a devops floor
        return ALLOWS clean where a BLOCK is expected.
        """
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.subagent_stop_port import SubagentStopContext

        prev_cwd = Path.cwd()
        try:
            os.chdir(self.repo_dir)
            service = service_factory.create_subagent_stop_service()
            decision = service.validate(
                SubagentStopContext(
                    execution_log_path="",
                    project_id=self.feature_id,
                    step_id="",
                    cwd=str(self.repo_dir),
                    mode="atdd_pure",
                    slice_id="slice-02",
                    atdd_pure_phase="D_REFACTOR_COMMIT",
                )
            )
        finally:
            os.chdir(prev_cwd)
        return decision.action, decision.reason

    # ---- substrate plumbing (precondition state, NOT the SUT) ----------------

    def _arm_floor(self, floor: WaveFloor) -> None:
        """Seed the wave-active floor with a COMMAND record for the given wave."""
        floor_path = self.repo_dir / _FLOOR_FILE_REL
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        record: dict[str, object] = {"wave": floor.value, "provenance": "command"}
        floor_path.write_text(json.dumps(record), encoding="utf-8")

    def _write_devops_feature_delta(self) -> None:
        """Write the DEVOPS feature-delta the verify gate / gate-out seals against."""
        self._feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
        self._feature_delta_path.write_text(
            "# Feature Delta: synthetic DEVOPS feature fixture\n\n"
            "## Wave: DEVOPS\n\n"
            "### [REF] Inherited commitments\n\n"
            "| Origin | Commitment | DDD | Impact |\n"
            "|--------|------------|-----|--------|\n"
            "| n/a | a synthetic DEVOPS deliverable the gate seals against | n/a | "
            "the bytes the review verdict's content seal binds to |\n",
            encoding="utf-8",
        )

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"registry_file_exists={_DEVOPS_REGISTRY_FILE.is_file()}; "
            f"waves_dir={_WAVES_DIR}; resolved_boundary={self._resolved_boundary!r}"
        )

    def _cli_observed(self) -> str:
        verify = self._verify_result
        record = self._record_result
        return (
            "verify=(exit="
            + (str(verify.exit_code) if verify else "n/a")
            + ", payload="
            + (repr(verify.payload) if verify else "n/a")
            + ", stderr="
            + (repr(verify.stderr[:200]) if verify else "n/a")
            + "); record=(exit="
            + (str(record.exit_code) if record else "n/a")
            + ", stderr="
            + (repr(record.stderr[:200]) if record else "n/a")
            + ")"
        )

    def _seam_observed(self) -> str:
        return (
            f"seam.action={self._seam_action!r}; seam.reason={self._seam_reason!r}; "
            f"repo_dir={self.repo_dir!r}"
        )
