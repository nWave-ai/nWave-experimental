"""Typed domain vocabulary for the atdd_pure 3-phase-count reduction ATs.

Mandate-12 SSOT: every domain noun the Gherkin scenarios speak is expressed
once here as a typed enum / dataclass. Step bodies coerce the Gherkin literal
into one of these types and delegate to the composition root — they never
inline business logic.

The SUT is the atdd_pure runtime phase model (ADR-001: the 7-member
`ATDDPurePhase` enum + 7-link `LEGAL_TRANSITIONS` collapse to the 3 canonical
phases `A_GREEN`, `C_REVIEWER_AUDIT`, `D_REFACTOR_COMMIT`). Per Mandate-13 the
ATs do NOT import `ATDDPurePhase` directly (it is the SUT). They observe the
phase model through the operator-facing phase-report diagnostic
(`python -m des.cli.phases --format json`), whose every field is DERIVED from
the production enum + transition matrix (NOT a hand-restated literal).
"""

from __future__ import annotations

from enum import Enum


class CanonicalPhase(str, Enum):
    """The 3 canonical atdd_pure DELIVER phases after the reduction (ADR-001).

    The complete post-reduction phase vocabulary the spine reports. Names per
    architecture.md §3 summary (A_GREEN_ATS renamed to A_GREEN; C kept; E/F/G
    collapsed into D_REFACTOR_COMMIT).
    """

    A_GREEN = "A_GREEN"
    C_REVIEWER_AUDIT = "C_REVIEWER_AUDIT"
    D_REFACTOR_COMMIT = "D_REFACTOR_COMMIT"


class RetiredPhase(str, Enum):
    """The 5 phase names the 7->3 reduction removes from the runtime vocabulary.

    Post-reduction these MUST be absent from the phase report.
    `B_COVERAGE_CLEANUP` folds into `A_GREEN`; `E_BATCH_REFACTOR`,
    `F_FINAL_REVIEW`, `G_COMMIT` fold into `D_REFACTOR_COMMIT`; `D_GAP_ROUTING`
    drops to the DISTILL/DELIVER seam (ADR-001 §3). `D_DISTILL` is deliberately
    NOT here — it is the retained upstream-return marker, never a DELIVER phase,
    unchanged by the reduction.
    """

    B_COVERAGE_CLEANUP = "B_COVERAGE_CLEANUP"
    D_GAP_ROUTING = "D_GAP_ROUTING"
    E_BATCH_REFACTOR = "E_BATCH_REFACTOR"
    F_FINAL_REVIEW = "F_FINAL_REVIEW"
    G_COMMIT = "G_COMMIT"


class TransitionTarget(str, Enum):
    """Targets of a legal transition the phase report may carry.

    The terminal sentinel (`TERMINAL`) is a `PhaseExit` outcome, not a phase —
    it is the target of the final canonical phase's only edge.
    """

    A_GREEN = "A_GREEN"
    C_REVIEWER_AUDIT = "C_REVIEWER_AUDIT"
    D_REFACTOR_COMMIT = "D_REFACTOR_COMMIT"
    TERMINAL = "TERMINAL"
