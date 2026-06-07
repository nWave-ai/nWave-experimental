"""Closed-world type-invariant guard for the D_DISTILL routing-only node.

slice-01 of oss-hook-side-phase-injection (the DISTILL-wave hook keystone, D1).

D_DISTILL is a ROUTING-ONLY node: it names the upstream DISTILL-wave
acceptance-designer return the SubagentStop G-DISTILL-EXIT gate intercepts. It
is NOT a member of the per-slice carpaccio A->G cycle, so it is an EXPLICIT
ASSERTED EXCLUSION from the `LEGAL_TRANSITIONS` matrix.

This is a structural closed-world guard (a type invariant), NOT a behavioral
test (Mandate 9/11 example-only is for the .feature ATs; this pins a data
invariant). The reviewer adjudicated it legitimate per the slice-01 design:
there is NO transition-validator function in-tree, so only the data half of
the assertion applies -- D_DISTILL must never appear as a source key of
`LEGAL_TRANSITIONS` (it has no legal forward edge: DISTILL is upstream of the
carpaccio cycle, not a member of it).
"""

from __future__ import annotations

from des.domain.atdd_pure_phases import LEGAL_TRANSITIONS, ATDDPurePhase


def test_d_distill_is_an_asserted_exclusion_from_legal_transitions() -> None:
    """D_DISTILL is a routing-only node -- absent from LEGAL_TRANSITIONS keys.

    Every per-slice carpaccio phase (A->G) IS a source key of the transition
    matrix; D_DISTILL, being an upstream routing node, is deliberately absent.
    """
    assert ATDDPurePhase.D_DISTILL not in LEGAL_TRANSITIONS

    # The remaining seven canonical carpaccio phases ARE source keys -- the
    # exclusion is specific to D_DISTILL, not a hole in the matrix.
    carpaccio_phases = {
        phase for phase in ATDDPurePhase if phase is not ATDDPurePhase.D_DISTILL
    }
    assert carpaccio_phases == set(LEGAL_TRANSITIONS.keys())
