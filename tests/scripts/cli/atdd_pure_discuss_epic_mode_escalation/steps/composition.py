"""Composition root for the discuss-epic-mode slice-04 escalation slice.

Slice-04 value: a user who has never heard of epic-mode discovers it exactly at
the moment of need -- Phase 1.5 oversized-detection EXPLAINS which signals fired,
proposes epic-mode (naming ``--epic``), and ASKS confirmation; a silent giant plan
can no longer happen.

Honest mechanical-vs-prompt boundary (the central slice-04 decision)
====================================================================
The Phase 1.5 escalation is EMITTED by the Luna PO agent during an LLM-mediated
discuss session. That emission act is PROMPT-SURFACE -- not mechanically testable.
Per the DESIGN slice-02/04/05 text contracts section: the "code" of this slice is
SKILL / COMMAND text (the Phase 1.5 escalation message TEMPLATE); there is NO
``src/des`` surface; Phase 1.5 detection has no validator / gate / structured
detection config on the tip (verified 2026-06-11). DESIGN pins the ESC contract
(ESC-1..ESC-6) as the AT-citable specification.

What these ATs PIN (mechanical, via the suite-local reference producer):
  - ESC-1 trigger: 2+ fired signals -> an escalation; fewer -> none.
  - ESC-2 explain: the escalation NAMES each fired signal (not generic).
  - ESC-3 propose + name ``--epic``: the message proposes epic-mode and names the
    literal flag (discoverability floor, KPI-3).
  - ESC-4 ask confirmation: closed options (epic-mode / continue feature-level),
    NEVER an auto-switch (D-shape: explicit + escalated, never auto).
  - ESC-5 decline: the user declines -> standard feature-level DISCUSS continues,
    zero epic artifacts (observed on a real tmp_path tree).
  - ESC-6 guardrail: a right-sized request (fewer than 2 signals) -> zero
    escalation, zero new prompts.

What stays PROMPT-SURFACE (deliberately NOT an AT):
  - The exact wording of the Luna-authored escalation prose. The reference producer
    is a golden-file analogue of the contract-bearing CONTENT (signals named, flag
    named, options asked), NOT the literal sentence. A prose-grep of SKILL.md for
    ``--epic`` would be the presence-watcher anti-pattern + Fixture Theater; this
    suite instead discriminates input -> output behaviour (right-sized vs oversized
    inputs + a decline branch).

Active-RED contract (atdd_pure)
===============================
Slice-04 has NO net-new ``src/des`` detection seam (DESIGN reuse table: text-only;
Phase 1.5 detection is prose). The active-RED is therefore at the BEHAVIOUR layer,
mirroring slice-02's artifact-absence RED one level up: the Phase 1.5 escalation
contract is undefined on the current tip (the escalation message TEMPLATE is the
slice-04 deliverable). The designated GREEN wiring point is
``run_phase_1_5_detection()``; on the current tip it is a documented NO-OP that
imports nothing from the reference oracle -- so the detection produces no
escalation outcome (``ESCALATION_ABSENT``) and every ESC observation reads its
absent default -> semantic ``AssertionError`` -- a deliberate missing-functionality
RED, never a collection / import error.

S2 driving-port-only: this composition imports ZERO production code -- slice-04
drives no ``src/des`` seam (Phase 1.5 detection is prose; unlike slice-02, there is
not even a slice-01 gate-OUT leg, because the escalation contract has no validator
gate). The reference producer is suite-local test-support. S2 = PASS by
construction.

S3 dormant-seam reconciliation: slice-04 declares ZERO net-new ``src/des`` seams
(DESIGN: "no ``src/des`` surface; gates already cover the run"). No net-new seam
can ship dormant -- S3 = PASS by construction.

Layer 3 (FS acceptance): the only real driven adapter is the filesystem (the
decline-branch zero-epic-artifacts observation on a real tmp_path). The escalation
message itself is a pure-function observation. No PBT machinery (Mandate 9/11) --
the ESC is a finite, enumerable closed contract over the 5-signal closed list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import (
    EscalationDecision,
    EscalationOutcome,
    OversizedSignal,
)


@dataclass(frozen=True)
class EscalationObservation:
    """Read-only observation of the Phase 1.5 escalation outcome (ESC-1..ESC-4).

    On the current tip the escalation contract is undefined, so ``outcome`` is
    ``ESCALATION_ABSENT`` and every structural observation reads its empty default
    -- the active-RED state. At GREEN the slice-04 escalation procedure produces an
    ESC-conformant outcome.
    """

    outcome: EscalationOutcome
    named_signals: tuple[OversizedSignal, ...] = ()
    proposes_epic_mode: bool = False
    names_epic_flag: bool = False
    confirmation_options: tuple[EscalationDecision, ...] = ()
    message_text: str = ""


@dataclass
class EscalationComposition:
    """Composition root for the slice-04 Phase 1.5 escalation slice.

    ``repo_dir`` is a real tmp_path acting as the repository root. A submitted
    request carries a set of oversized signals (``submitted_signals``); the Phase
    1.5 detection is expected to escalate (ESC-1) when 2+ fired, naming them
    (ESC-2), proposing epic-mode + naming ``--epic`` (ESC-3), and asking
    confirmation (ESC-4). This composition observes that escalation outcome and the
    decline-branch filesystem invariant (ESC-5 zero epic artifacts).
    """

    repo_dir: Path
    submitted_signals: tuple[OversizedSignal, ...] = ()
    user_decision: EscalationDecision = EscalationDecision.CONTINUE_FEATURE
    _escalation: object = field(default=None, init=False, repr=False)
    _detected: bool = field(default=False, init=False, repr=False)

    # --- paths ---------------------------------------------------------------

    @property
    def _epic_workspace_root(self) -> Path:
        return self.repo_dir / "docs" / "epic"

    # --- Given: a maintainer submits a request with N signals ----------------

    def submit_request(self, signals: tuple[OversizedSignal, ...]) -> None:
        """Establish the submitted request's oversized-signal set + repo skeleton."""
        self.submitted_signals = signals
        self.repo_dir.mkdir(parents=True, exist_ok=True)

    def choose(self, decision: EscalationDecision) -> None:
        """Record the user's response to the confirmation ask (ESC-4/ESC-5)."""
        self.user_decision = decision

    # --- When: Phase 1.5 oversized-detection runs ----------------------------

    def run_phase_1_5_detection(self) -> None:
        """Run the Phase 1.5 oversized-detection + escalation procedure.

        PROMPT-SURFACE boundary: the escalation is the Luna PO agent emitting the
        explain+propose+confirm message during an LLM-mediated discuss session. The
        slice-04 deliverable is PROSE (the Phase 1.5 escalation message TEMPLATE in
        ``nWave/skills/nw-discuss/SKILL.md`` + ``nWave/tasks/nw/discuss.md``).

        DESIGNATED GREEN WIRING POINT (atdd_pure): on the current tip this is a
        documented NO-OP -- it imports nothing from the suite-local reference oracle
        yet, so the detection produces no escalation outcome. ``observe_escalation``
        therefore reads ``ESCALATION_ABSENT`` and every ESC pin fails -> semantic
        ``AssertionError`` (behaviour-absence active-RED).

        DELIVER (slice-04) makes the ATs GREEN at THIS exact seam by (i) wiring the
        suite-local reference producer here -- a golden-file analogue, NOT a
        ``src/des`` import -- AND (ii) authoring the prose deliverable (the Phase 1.5
        escalation contract + the REMOVE of the stale "propose splitting"/"slices"
        wording). Filling this seam is NOT a Driving-Port-Only-Boundary violation;
        importing ``src/des`` would be.
        """
        # GREEN (slice-04): the escalation outcome is a deterministic FUNCTION of the
        # fired-signal SET, witnessed against the suite-local reference producer (a
        # golden-file analogue of the LLM-mediated Phase 1.5 emission). This is
        # test-support, NOT a ``src/des`` import -- the production deliverable is the
        # PROSE escalation contract authored in the discuss skill/command text.
        from ._reference_oracle import build_escalation, detect_fired_signals

        self._escalation = build_escalation(
            detect_fired_signals(self.submitted_signals)
        )
        self._detected = True

    # --- observations: ESC contract on the escalation outcome ----------------

    def observe_escalation(self) -> EscalationObservation:
        """Observe the Phase 1.5 escalation against the ESC contract."""
        if not self._detected:
            return EscalationObservation(outcome=EscalationOutcome.ESCALATION_ABSENT)
        if self._escalation is None:
            return EscalationObservation(outcome=EscalationOutcome.NO_ESCALATION)
        message = self._escalation
        return EscalationObservation(
            outcome=EscalationOutcome.ESCALATED,
            named_signals=message.fired_signals,
            proposes_epic_mode=message.proposes_epic_mode,
            names_epic_flag=message.names_epic_flag,
            confirmation_options=message.confirmation_options,
            message_text=message.render(),
        )

    def resolve_decision(self) -> EscalationOutcome:
        """Resolve the post-escalation outcome from the user's decision (ESC-5).

        After an escalation, the user's recorded decision drives the outcome:
        SWITCH_TO_EPIC_MODE -> EPIC_MODE_CONFIRMED; CONTINUE_FEATURE ->
        FEATURE_LEVEL_CONTINUED (standard feature-level DISCUSS, zero epic
        artifacts). When no escalation occurred the outcome is the detection
        outcome itself (NO_ESCALATION / ESCALATION_ABSENT).
        """
        observation = self.observe_escalation()
        return _OUTCOME_BY_DECISION.get(
            (observation.outcome, self.user_decision), observation.outcome
        )

    def count_epic_workspaces(self) -> int:
        """Count ``docs/epic/{id}/`` workspaces produced by the run (ESC-5).

        A declined escalation continues standard feature-level DISCUSS and produces
        ZERO epic artifacts. A non-zero count means the run eagerly authored an
        epic-delta despite the decline -- an ESC-5 violation.
        """
        root = self._epic_workspace_root
        if not root.exists():
            return 0
        return sum(1 for child in root.iterdir() if child.is_dir())

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        Slice-04 mutates no repository state -- the decline branch's invariant is
        that ZERO epic workspaces exist. The observable universe is the epic
        workspace count (the decline must not author an epic-delta).
        """
        return {
            "epic_workspaces.count": self.count_epic_workspaces(),
        }


# Decision-resolution table (ESC-5). Module-level so ``resolve_decision`` stays a
# single typed lookup, no control flow in the service body (Mandate-12 criterion 3).
_OUTCOME_BY_DECISION: dict[
    tuple[EscalationOutcome, EscalationDecision], EscalationOutcome
] = {
    (
        EscalationOutcome.ESCALATED,
        EscalationDecision.SWITCH_TO_EPIC_MODE,
    ): EscalationOutcome.EPIC_MODE_CONFIRMED,
    (
        EscalationOutcome.ESCALATED,
        EscalationDecision.CONTINUE_FEATURE,
    ): EscalationOutcome.FEATURE_LEVEL_CONTINUED,
}
