"""Domain types for the atdd_pure_phase_count slice-02 acceptance steps.

Mandate-12 (SSOT via types): every domain noun in the Gherkin is expressed once
as a typed enum here. The DSL emerges from these typed concepts -- step
decorators take enum-typed parameters via ``parsers.parse``, never raw strings
where a domain enum exists.

slice-02 contract surface: the legacy 7-phase vocabulary is collapsed to the
canonical 3, and a read-only resolver maps any (possibly legacy) phase name to
its canonical phase -- replaying historical ledger entries losslessly. An
unknown phase name is rejected with a typed error, never silently mapped.
"""

from __future__ import annotations

from enum import Enum


class CanonicalPhase(str, Enum):
    """The 3 canonical delivery phases after the 7->3 reduction."""

    A_GREEN = "A_GREEN"
    C_REVIEWER_AUDIT = "C_REVIEWER_AUDIT"
    D_REFACTOR_COMMIT = "D_REFACTOR_COMMIT"


class LegacyPhase(str, Enum):
    """The legacy 7-phase vocabulary names that must replay onto the canonical 3.

    Each legacy name carries the canonical phase it replays to (the lossless
    backward-compat mapping the resolver implements). Members whose names equal
    a canonical phase (``C_REVIEWER_AUDIT``) replay to themselves.
    """

    A_GREEN_ATS = "A_GREEN_ATS"
    B_COVERAGE_CLEANUP = "B_COVERAGE_CLEANUP"
    C_REVIEWER_AUDIT = "C_REVIEWER_AUDIT"
    E_BATCH_REFACTOR = "E_BATCH_REFACTOR"
    F_FINAL_REVIEW = "F_FINAL_REVIEW"
    G_COMMIT = "G_COMMIT"


class ResolveOutcome(str, Enum):
    """Observable outcome class of a phase-name resolution at the driving port.

    THREE distinct outcomes (per architecture.md:188-190 resolution contract):
    a canonical name resolves to a phase; ``D_GAP_ROUTING`` resolves to the
    routing/seam outcome (NOT a phase, NOT unknown); an unknown name is rejected.
    The seam outcome is what keeps a pre-reduction ledger that carries
    ``D_GAP_ROUTING`` entries replayable losslessly -- the caller treats it as a
    routing event, never raising and never mapping it to a wrong phase.
    """

    RESOLVED = "resolved"  # exit 0, canonical name reported
    SEAM = "seam"  # exit 0, routing/seam event (D_GAP_ROUTING -> no phase)
    REJECTED = "rejected"  # non-zero exit, typed-error signal (no silent map)


class SeamPhase(str, Enum):
    """Live enum members the runtime resolves to the routing/seam outcome.

    ``D_GAP_ROUTING`` is the retired routing node (``_CANONICAL_NAME_OF`` maps it
    to ``None``): the runtime neither treats it as a canonical delivery phase nor
    refuses it -- it is a recognised routing/seam event on the replay path.
    """

    D_GAP_ROUTING = "D_GAP_ROUTING"
