"""WalkingSkeletonFeatureEndGate -- the feature-end cycle's walking-skeleton step.

Application service for feature `walking-skeleton-production-like-gate`,
slice-02 (DESIGN / Where the Gate Fires -- Point 1). The DES feature-end
`SubagentStop` integrity branch invokes this service after the existing
`verify_deliver_integrity` check:

  1. emit the `WalkingSkeletonGateRan` heartbeat record  -- BEFORE the verdict
     (RM-1: "no gate ran" becomes a representable RED, never a silent proceed).
  2. evaluate the walking-skeleton gate against the delivered artifact.
  3. PASS -> write the `WalkingSkeletonTierVerified` positive-proof record;
     feature-end proceeds.
     FAIL -> feature-end is blocked; the feature is not marked done.

The service owns ONLY the feature-end orchestration -- the heartbeat / verdict
/ positive-record sequencing. The build, install, facet checks and AT run live
in the `WalkingSkeletonGate` domain service; the ledger writes live in the
`AtCompletionLedger` driven adapter. This service composes them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.domain.gate_outcome import GateOutcome, GateVerdict


if TYPE_CHECKING:
    from pathlib import Path

    from des.domain.tier_ladder import TierCapability
    from des.domain.walking_skeleton_gate import FeatureUnderGate, WalkingSkeletonGate
    from des.ports.driven_ports.at_completion_ledger_port import (
        AtCompletionLedgerPort,
    )


@dataclass(frozen=True)
class FeatureEndVerdict:
    """The user-observable outcome of the feature-end walking-skeleton step.

    `proceeds` is whether feature-end may continue (a PASS or NOT_APPLICABLE
    verdict); a FALSE `proceeds` blocks the feature from being marked done.
    """

    outcome: GateOutcome
    proceeds: bool


class WalkingSkeletonFeatureEndGate:
    """Application service: the feature-end cycle's walking-skeleton gate step."""

    def __init__(
        self, gate: WalkingSkeletonGate, ledger: AtCompletionLedgerPort
    ) -> None:
        self._gate = gate
        self._ledger = ledger

    def run(
        self,
        feature: FeatureUnderGate,
        tier_capability: TierCapability,
        prefix: Path,
    ) -> FeatureEndVerdict:
        """Emit the heartbeat, evaluate the gate, record the positive proof."""
        self._ledger.append_walking_skeleton_gate_ran()
        outcome = self._gate.evaluate(feature, tier_capability, prefix)
        if outcome.verdict is GateVerdict.PASS:
            self._ledger.append_walking_skeleton_tier_verified(
                tier_of_record=outcome.tier_of_record.value
            )
        return FeatureEndVerdict(
            outcome=outcome,
            proceeds=outcome.verdict in (GateVerdict.PASS, GateVerdict.NOT_APPLICABLE),
        )


__all__ = ["FeatureEndVerdict", "WalkingSkeletonFeatureEndGate"]
