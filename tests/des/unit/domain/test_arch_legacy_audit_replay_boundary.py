"""Arch boundary guard: the legacy audit-replay reader is untouched by the
f-finalize-verify-single-spine REDUCE.

The REDUCE deletes the classic finalize leg from `des verify-integrity` (the
`workflow.mode == classic` branch, the `resolve_workflow_mode` dispatch, and
`--roadmap-only`). The Out-of-Scope boundary (`feature-delta.md`
`## Wave: DISCUSS / [REF] Out of Scope`) declares the legacy-5-phase
audit-replay reader -- `des.domain.phase_event.PhaseEventParser` -- a HARD
do-not-touch: removing the classic SPINE is NOT removing the legacy audit-log
replay, and the verify gate never imported the parser.

This is an ARCHITECTURAL contract, not a port-to-port acceptance test: it
asserts the standalone replay reader still imports and parses a v2.0
pipe-delimited entry unchanged. It therefore lives in the unit/arch tree (the
`test_arch_` prefix is excluded from the DISTILL S2 driving-port-only boundary
check) rather than masquerading as an AT that imports a domain class at the
step boundary. Relocated here from the slice-01 acceptance set per the
C_REVIEWER_AUDIT Tier-2 S2 finding.
"""

from __future__ import annotations

from des.domain.phase_event import PhaseEvent, PhaseEventParser


# A legacy v2.0 pipe-delimited audit-replay entry (the format PhaseEventParser
# owns). The boundary guard parses THIS through the untouched reader.
_LEGACY_ENTRY = "01-01|GREEN|EXECUTED|PASS|2026-02-02T10:00:00Z"


def test_legacy_audit_replay_reader_yields_recorded_phase_event_unchanged() -> None:
    """The legacy replay reader parses a v2.0 entry into the recorded event.

    Guards the Out-of-Scope boundary: the REDUCE removes the classic finalize
    leg without disturbing `PhaseEventParser`. A real assertion (not a smoke
    import) over every recorded field proves the standalone reader still
    yields the entry unchanged.
    """
    event = PhaseEventParser().parse(_LEGACY_ENTRY)

    assert isinstance(event, PhaseEvent)
    assert event.step_id == "01-01"
    assert event.phase_name == "GREEN"
    assert event.status == "EXECUTED"
    assert event.outcome == "PASS"
    assert event.timestamp == "2026-02-02T10:00:00Z"
