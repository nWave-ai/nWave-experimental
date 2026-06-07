"""Environmental-e2e feature-end done-gate -- pure function over record presence.

Feature `fix-oss-environmental-e2e-gate`, slice-02 (DESIGN / Where the Gate
Lives -- presence-of-proof done-gate). The done-gate is a pure function over
the {HEARTBEAT, VERIFIED} 2^2 powerset: feature-end may declare a feature done
ONLY when both records are present in the AT-completion ledger. The verdict
enum is closed -- one row per cell of the powerset -- so the diagnostic names
which record(s) are absent, not just go/no-go (Mandate 8 universe-bound).

Trust model -- principle 13 (presence-of-proof, not absence-of-block): the
done-gate passes only when (a) no `environmental-e2e-unverified` deferral
marker exists AND (b) an `EnvironmentalE2eVerified` ledger record exists. A
hand-`rm` of the marker satisfies (a) but not (b); done still blocks. This
module evaluates (b); marker absence is enforced upstream.

Stdlib-only, no I/O. The caller provides the set of recorded ledger event
names; this function returns the typed verdict.
"""

from __future__ import annotations

from enum import Enum

from des.ports.driven_ports.at_completion_ledger_port import (
    ENVIRONMENTAL_E2E_GATE_RAN,
    ENVIRONMENTAL_E2E_VERIFIED,
)


class DoneGateVerdict(str, Enum):
    """The closed verdict enum returned by the feature-end done-gate.

    One row per cell of the {HEARTBEAT, VERIFIED} powerset: the success row
    (`PERMITTED`) plus three named missing-record diagnostics. The diagnostic
    names which record(s) are absent -- not a generic boolean blocker -- so
    the caller asserts both the gate's go/no-go AND its diagnostic shape
    from a single port-exposed verdict token.
    """

    PERMITTED = "permitted"
    BLOCKED_MISSING_VERIFICATION = "blocked-missing-verification"
    BLOCKED_MISSING_HEARTBEAT = "blocked-missing-heartbeat"
    BLOCKED_MISSING_BOTH = "blocked-missing-both"


def evaluate_done_gate(recorded_events: frozenset[str]) -> DoneGateVerdict:
    """Compute the done-gate verdict over the set of recorded env-e2e events.

    Pure function over the 2^2 {HEARTBEAT, VERIFIED} powerset:

    | heartbeat | verified | verdict                       |
    |-----------|----------|-------------------------------|
    | True      | True     | PERMITTED                     |
    | True      | False    | BLOCKED_MISSING_VERIFICATION  |
    | False     | True     | BLOCKED_MISSING_HEARTBEAT     |
    | False     | False    | BLOCKED_MISSING_BOTH          |

    `recorded_events` carries the ledger event names (e.g. from
    `AtCompletionLedger.environmental_e2e_events()`); any event name not in
    `{ENVIRONMENTAL_E2E_GATE_RAN, ENVIRONMENTAL_E2E_VERIFIED}` is ignored.
    """
    has_heartbeat = ENVIRONMENTAL_E2E_GATE_RAN in recorded_events
    has_verified = ENVIRONMENTAL_E2E_VERIFIED in recorded_events
    if has_heartbeat and has_verified:
        return DoneGateVerdict.PERMITTED
    if has_heartbeat:
        return DoneGateVerdict.BLOCKED_MISSING_VERIFICATION
    if has_verified:
        return DoneGateVerdict.BLOCKED_MISSING_HEARTBEAT
    return DoneGateVerdict.BLOCKED_MISSING_BOTH


__all__ = ["DoneGateVerdict", "evaluate_done_gate"]
