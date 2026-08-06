"""Composition root for the nwave-flow-v2-enforcement slice-07b ATs.

The *only* place the production system is wired for slice-07b. One driving port
(Mandate-13 driving-port-only, Layer 3 composition):

  * PO-REVIEW VETO-GATE (DISCUSS exit, second gate-OUT check) -- the REAL
    ``SubagentStopService.validate`` built via the production composition root
    (``service_factory.create_subagent_stop_service``). The service is the SUT;
    the arranged precondition state is (a) a ``discuss`` wave-active floor under
    ``project_root`` (slice-04 anchor, shipped), (b) a VALUE-BEARING
    feature-delta (so the slice-07 structural gate-OUT PASSES and the review-gate
    branch is what decides), and (c) the keyless ``DiscussReviewVerdict`` ledger
    record in the shape under test. NO signing key is provisioned anywhere.
    The assertion is on the service's ``HookDecision`` (allow vs block +
    the ``DISCUSS_PO_REVIEW_*`` reason token).

Post-demotion (oss-review-verdict-demotion S3): re-authored keyless. The
HMAC/signing surface is REMOVED. The TAMPERED scenario is RETIRED (no signature
to tamper post-demotion). Records carry present fields only (no ``hmac_sha256``).
The env-var scrub (NWAVE_REVIEWER_SIGNING_KEY pop/restore) is RETAINED as
keyless-legitimate: the gate must decide without a key being present in any
resolution path.

State lives on the instance; every ``given_/when_/then_`` method mutates or
reads it. Step functions are thin delegations (Mandate-12: no business logic in
step bodies).

DISCUSS-side reason tokens the loud verdicts must carry (K1 named-LOUD;
DESIGN pin: ``reason = f"DISCUSS_PO_REVIEW_{token}: {detail}"``):
  * reviewer veto -> a vetoed-class token (vetoed / needs-revision / not-approved),
    and NEVER an indeterminate-class token.
  * absent -> an indeterminate-class token (indeterminate / absent),
    and NEVER a vetoed-class token (§22.7 honest-verdict split).

SUT STATE MACHINE (C2 -- AT module docstring requirement):
  review-gate states = {DISCUSS_RETURNING (structural gate-OUT PASS reached)}.
    DISCUSS_RETURNING --(keyless NEEDS_REVISION)----------> VETOED (block)
    DISCUSS_RETURNING --(verdict absent)-----------------> INDETERMINATE (block)
    DISCUSS_RETURNING --(keyless APPROVED current)-------> PASS (no objection,
                                                           NOT a GO -- §22.0)
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_slice_07b import GateDecision, PoReviewVerdictShape


# DESIGN-PINNED paths/shapes (feature-delta § slice-07b code-design).
_FEATURE_ID = "nwave-flow-v2-enforcement"
_FLOOR_FILE_REL = ".nwave/wave-active/active.json"
_FEATURE_DELTA_REL = f"docs/feature/{_FEATURE_ID}/feature-delta.md"
_LEDGER_REL = f".nwave/telemetry/atdd-pure/{_FEATURE_ID}.jsonl"
# Signing-key env -- referenced ONLY to guarantee it stays ABSENT. The env var
# is scrubbed around the service run (keyless-legitimate: the gate must decide
# without a key being present in any resolution path).
_SIGNING_KEY_ENV = "NWAVE_REVIEWER_SIGNING_KEY"

# DESIGN-PINNED DiscussReviewVerdict record contract.
_DISCUSS_REVIEW_EVENT = "DiscussReviewVerdict"
_SCHEMA_VERSION = "1.0.0"
_REVIEWER_AGENT_ID = "nw-product-owner-reviewer"
_VERDICT_APPROVED = "approved"
_VERDICT_NEEDS_REVISION = "needs-revision"

# Reason-token discriminants (K1 named-LOUD). The veto class and the
# indeterminate class are DISJOINT by design -- a block reason must carry its
# own class's token and NEVER the other class's (§22.7 honest-verdict split).
# Post-demotion: indeterminate set shrinks to indeterminate/absent.
_PO_VETO_TOKENS: tuple[str, ...] = (
    "vetoed",
    "needs-revision",
    "not-approved",
)
_PO_INDETERMINATE_TOKENS: tuple[str, ...] = (
    "indeterminate",
    "absent",
)

# A value-bearing slice-plan table (the MECC floor accepts this shape) -- seeds
# the slice-07 structural gate-OUT to PASS so the NEW review-gate branch is the
# deciding check. Re-declared here (each slice owns its vocabulary).
_VALUE_BEARING_SLICE_PLAN = """\
## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | A user can run the thing and see a confirmation | pending | @walking-skeleton | the thinnest e2e |
| slice-02 | A user gets a clear error when the input is malformed | pending | | the first error path |
"""

_FEATURE_DELTA_CONTENT = (
    f"# Feature Delta: {_FEATURE_ID}\n\n" + _VALUE_BEARING_SLICE_PLAN
)


@dataclass
class PoReviewGateComposition:
    """Drives the production DISCUSS PO-review veto-gate seam for the slice-07b ATs."""

    _project_root: Path | None = field(default=None)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)

    # ---- given ----------------------------------------------------------------

    def given_discuss_return_with_po_review(
        self, tmp_path: Path, shape: PoReviewVerdictShape
    ) -> None:
        """Arrange a discuss-wave return whose PO-review verdict has the given shape.

        The structural preconditions (discuss floor + value-bearing delta) are
        IDENTICAL across shapes; NO signing key is provisioned anywhere. The ONLY
        varying axis is the recorded verdict state, so the review-gate branch is
        what decides.
        """
        self._project_root = tmp_path
        self._arm_discuss_floor(tmp_path)
        self._seed_value_bearing_feature_delta(tmp_path)
        self._seed_review_verdict(tmp_path, shape)

    # ---- when -------------------------------------------------------------------

    def when_discuss_handoff_checked(self) -> None:
        """Drive SubagentStopService.validate with a discuss-wave return."""
        self._decision_action, self._decision_reason = self._run_subagent_stop_gate()

    # ---- then -------------------------------------------------------------------

    def then_handoff_blocked_by_reviewer_veto(self) -> None:
        """A keyless NEEDS_REVISION -> VETOED block (§22.0, mechanically enforced)."""
        assert self._gate_decision() is GateDecision.BLOCK, (
            "the DISCUSS PO-review gate must BLOCK the handoff to DESIGN when "
            "the ledger carries a keyless NEEDS_REVISION verdict "
            "(the reviewer veto is MECHANICAL, never skippable advisory text -- "
            f"§22.0 / O-3); it returned {self._decision_action!r}. "
            f"{self._observed()}"
        )

    def then_veto_names_reviewer_decision(self) -> None:
        """The veto reason names the reviewer decision read from the recorded verdict (K1)."""
        reason = (self._decision_reason or "").lower()
        assert any(token in reason for token in _PO_VETO_TOKENS), (
            "the PO-review block must NAME the reviewer decision (a vetoed-class "
            f"token, one of {_PO_VETO_TOKENS!r}) read from the ledger record -- "
            "never the agent's say-so, never a generic block; got "
            f"reason={self._decision_reason!r}. {self._observed()}"
        )
        assert not any(token in reason for token in _PO_INDETERMINATE_TOKENS), (
            "a reviewer VETO must be reported as a veto, NOT as an "
            "indeterminate mechanism failure (the §22.7 honest-verdict split); "
            f"got reason={self._decision_reason!r}. {self._observed()}"
        )

    def then_handoff_blocked_indeterminate(self) -> None:
        """Absent verdict -> INDETERMINATE degrade-LOUD block (§17)."""
        assert self._gate_decision() is GateDecision.BLOCK, (
            "the DISCUSS PO-review gate must BLOCK degrade-LOUD when the verdict "
            "is absent -- an absent verdict must NEVER be coerced to a silent "
            f"PASS (§17 no-silent-pass); it returned {self._decision_action!r}. "
            f"{self._observed()}"
        )
        reason = (self._decision_reason or "").lower()
        assert any(token in reason for token in _PO_INDETERMINATE_TOKENS), (
            "the degrade-LOUD block must name the INDETERMINATE cause (one of "
            f"{_PO_INDETERMINATE_TOKENS!r}) so the failure is loud, not masked; "
            f"got reason={self._decision_reason!r}. {self._observed()}"
        )

    def then_indeterminate_never_masquerades_as_veto(self) -> None:
        """INDETERMINATE is DISTINCT from VETOED -- never coerced (§22.7)."""
        reason = (self._decision_reason or "").lower()
        assert not any(token in reason for token in _PO_VETO_TOKENS), (
            "an absent verdict means 'the verdict mechanism could not run' "
            "(INDETERMINATE) -- it must NEVER masquerade as 'the reviewer said "
            f"no' (a vetoed-class token, {_PO_VETO_TOKENS!r}): collapsing them "
            "would let a missing verdict impersonate a reviewer decision (§22.7); "
            f"got reason={self._decision_reason!r}. {self._observed()}"
        )

    def then_handoff_allowed_no_objection_from_review(self) -> None:
        """A keyless APPROVED + artefact-current -> PASS = no objection (NOT a GO)."""
        assert self._gate_decision() is GateDecision.ALLOW, (
            "the DISCUSS PO-review gate must ALLOW the handoff when the ledger "
            "carries a keyless, artefact-current APPROVED verdict "
            "(PASS = 'no objection found', NOT an authorizing GO -- the GO stays "
            f"human, §22.0); it returned {self._decision_action!r}. "
            f"{self._observed()}"
        )

    # ---- driving-port invocation ------------------------------------------------

    def _run_subagent_stop_gate(self) -> tuple[str, str | None]:
        """Drive the REAL SubagentStopService.validate via the production composition root.

        Runs an atdd_pure discuss-wave return (execution-log-free path). The
        discuss floor + value-bearing delta + ledger record under project_root are
        the arranged preconditions the review-gate branch reads. NO signing key
        is written; the env var is scrubbed so the gate runs entirely keyless.
        """
        assert self._project_root is not None
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.subagent_stop_port import (
            SubagentStopContext,
            SubagentStopReturnKind,
        )

        prev_cwd = Path.cwd()
        prev_env = os.environ.pop(_SIGNING_KEY_ENV, None)
        try:
            os.chdir(self._project_root)
            service = service_factory.create_subagent_stop_service()
            decision = service.validate(
                SubagentStopContext(
                    project_id=_FEATURE_ID,
                    return_kind=SubagentStopReturnKind.ATDD_PURE,
                    cwd=str(self._project_root),
                    slice_id="slice-07b",
                    atdd_pure_phase="D_REFACTOR_COMMIT",
                )
            )
        finally:
            os.chdir(prev_cwd)
            if prev_env is not None:
                os.environ[_SIGNING_KEY_ENV] = prev_env
        return decision.action, decision.reason

    # ---- observable-surface reader ------------------------------------------

    def _gate_decision(self) -> GateDecision:
        assert self._decision_action is not None, (
            "the gate must be run (When) before asserting on its decision (Then)"
        )
        return (
            GateDecision.ALLOW
            if self._decision_action == "allow"
            else GateDecision.BLOCK
        )

    # ---- substrate plumbing (precondition state, NOT the SUT) ---------------

    def _arm_discuss_floor(self, root: Path) -> None:
        """Seed the slice-04 wave-active floor with a discuss COMMAND record."""
        floor_path = root / _FLOOR_FILE_REL
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        floor_path.write_text(
            json.dumps({"wave": "discuss", "provenance": "command"}),
            encoding="utf-8",
        )

    def _seed_value_bearing_feature_delta(self, root: Path) -> None:
        """Seed a value-bearing delta so the slice-07 STRUCTURAL gate-OUT passes."""
        delta_path = root / _FEATURE_DELTA_REL
        delta_path.parent.mkdir(parents=True, exist_ok=True)
        delta_path.write_text(_FEATURE_DELTA_CONTENT, encoding="utf-8")

    def _current_feature_delta_hash(self, root: Path) -> str:
        """The DISTILL-pinned seal: SHA-256 hex over the artefact's exact bytes."""
        return hashlib.sha256((root / _FEATURE_DELTA_REL).read_bytes()).hexdigest()

    def _seed_review_verdict(self, root: Path, shape: PoReviewVerdictShape) -> None:
        """Seed (or deliberately omit) the keyless DiscussReviewVerdict record.

        Post-demotion: records carry present fields only (no ``hmac_sha256``).
        ABSENT writes nothing; the reader returns None -> INDETERMINATE.
        """
        if shape is PoReviewVerdictShape.ABSENT:
            return  # No record -> the reader returns None -> INDETERMINATE.

        verdict = (
            _VERDICT_APPROVED
            if shape is PoReviewVerdictShape.APPROVED_CURRENT
            else _VERDICT_NEEDS_REVISION
        )
        record: dict[str, object] = {
            "event": _DISCUSS_REVIEW_EVENT,
            "schema_version": _SCHEMA_VERSION,
            "feature_id": _FEATURE_ID,
            "verdict": verdict,
            "reviewer_agent_id": _REVIEWER_AGENT_ID,
            "feature_delta_hash": self._current_feature_delta_hash(root),
            "timestamp": "2026-06-10T00:00:00+00:00",
        }

        ledger_path = root / _LEDGER_REL
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"decision.action={self._decision_action!r}; "
            f"decision.reason={self._decision_reason!r}; "
            f"project_root={self._project_root!r}"
        )
