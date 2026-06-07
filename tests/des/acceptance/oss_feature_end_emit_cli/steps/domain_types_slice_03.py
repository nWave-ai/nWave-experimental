"""Domain types for slice-03 -- the `des feature-end run` feature-end-cycle CLI.

slice-03 of oss-feature-end-emit-cli (DDD-7 RATIFIED 2026-06-03). Every domain
noun in the slice-03 Gherkin is expressed once here as a typed enum / dataclass
/ NewType; step bodies and the composition service consume these typed
parameters (Mandate-12 criterion 1 -- domain types module exists with typed
enums for every domain noun used in Gherkin).

WHAT SLICE-03 ADDS over slice-01 + slice-02
-------------------------------------------
slice-01 shipped `des emit-feature-end` -- the EMITTER of the 2 feature-end
records. slice-02 shipped `des feature-end sign` -- the PRODUCER of the signed
`verdict_hash`. slice-03 ships the ORCHESTRATOR: the platform-agnostic
feature-end-cycle use-case (the `build_feature_end_gate(manifest)->service`
factory, DDD-7) that RUNS the 2 already-CLI'd feature-end gates whose CLIs
exist --

  des walking-skeleton-gate    -> ledger `WalkingSkeletonGateRan` heartbeat
  des verify-environmental-e2e  -> ledger `EnvironmentalE2eGateRan` heartbeat

-- then SIGNS the deep-review verdict (reuse slice-02) and EMITS the 2
feature-end records (reuse slice-01). Exposed via a NEW `des feature-end run`
thin shim AND invocable unchanged by the SubagentStop hook shim (the SAME
use-case, two thin driving adapters, DDD-7). The orchestration/decision logic
lives in the use-case; the `des feature-end run` CLI is a thin shim with zero
orchestration logic.

ANTI-THEATER INVARIANT (load-bearing, DDD-6 + feedback_earned_trust_mechanical_
evidence_not_llm_verdict): the cycle RUNS the REAL gate CLIs and emits their
REAL records. A `WalkingSkeletonGateRan` / `EnvironmentalE2eGateRan` record
reflects an ACTUAL gate invocation (the gate ran and reported). The cycle does
NOT mint a pass-record without running the gate. When a gate FAILS, the cycle
does NOT emit a fake pass / does NOT report feature-end complete -- it
fail-closes loudly (the same recompute-genuineness discipline slice-02 applies
to a signed verdict).

VERDICT-LAUNDERING CLOSE-OUT (ATs REVISED 2026-06-03): there is NO
`GateOutcomeUnderCycle` verdict-injection enum any more. The first A_GREEN cycle
DERIVED each gate's pass/fail from a `--walking-skeleton-outcome` INPUT FLAG the
test supplied -- so it minted the heartbeats without running the gate, and no AT
could catch it because the AT handed the cycle the verdict. The revision drops
that seam: the test stages only the gate ENVIRONMENT (an installable feature
workspace), and the cycle MUST run the real gates and read their REAL verdicts.
The gate verdict the scenario stages is now a property of the staged workspace,
not a typed cycle input.

PARTIAL-DONE HONESTY (decomposition boundary, DDD-6): slice-03 runs the 2
gates whose CLIs EXIST. The 2 `CoverageMapVerifiedAt{Distill,Deliver}Exit`
records have NO coverage-map CLI yet (slice-04). So after slice-03's cycle,
`des verify-integrity` STILL reports those 2 records MISSING -- slice-03 does
NOT falsely certify the feature is fully done. This honest boundary is pinned
by an AT.

SINGLE ENTRY POINT (DDD-7, AD-26 1:1 mirror): `des feature-end run` registers
under the one `des.cli.__main__` dispatcher + the gate catalog, alongside the
slice-02 `sign` verb. `des feature-end --help` advertises BOTH `sign` and
`run`. No new top-level entry proliferates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-feature-end-cycle-demo").
FeatureId = NewType("FeatureId", str)


class FeatureEndGate(str, Enum):
    """A feature-end gate the cycle RUNS, identified by the ledger record it emits.

    Each gate's CLI already exists; the cycle's job is to RUN it and let it
    emit its heartbeat record. The record is the observable proof the gate
    actually ran (anti-theater: a record present means the gate was reached).

    WALKING_SKELETON -- `des walking-skeleton-gate` -> `WalkingSkeletonGateRan`.
    ENVIRONMENTAL_E2E -- `des verify-environmental-e2e --mode run`
                         -> `EnvironmentalE2eGateRan`.
    """

    WALKING_SKELETON = "WalkingSkeletonGateRan"
    ENVIRONMENTAL_E2E = "EnvironmentalE2eGateRan"


class FeatureEndRecord(str, Enum):
    """A feature-end completion-ledger record the cycle's sign+emit leg writes.

    These are the slice-01 records the cycle EMITS after running the gates and
    signing the deep-review verdict (reuse slice-01 + slice-02).

    BATCH_REFACTOR_COMPLETED -- `EBatchRefactorCompleted`; the E_BATCH_REFACTOR
                                cycle ran. No signed hash.
    DEEP_REVIEW_VERDICT      -- `FeatureEndReviewVerdict`; binds the signed
                                deep-review `verdict_hash` (tamper-evident).
    """

    BATCH_REFACTOR_COMPLETED = "EBatchRefactorCompleted"
    DEEP_REVIEW_VERDICT = "FeatureEndReviewVerdict"


class CoverageMapRecord(str, Enum):
    """A coverage-map touchpoint record that slice-03 does NOT yet emit (slice-04).

    The 2 records whose coverage-map CLI does not exist yet (DDD-6 decomposition
    boundary). After slice-03's cycle, `des verify-integrity` STILL reports
    these MISSING -- the partial-done honesty AT asserts exactly this.

    DISTILL_EXIT -- `CoverageMapVerifiedAtDistillExit`.
    DELIVER_EXIT -- `CoverageMapVerifiedAtDeliverExit`.
    """

    DISTILL_EXIT = "CoverageMapVerifiedAtDistillExit"
    DELIVER_EXIT = "CoverageMapVerifiedAtDeliverExit"


class CycleOutcome(str, Enum):
    """The user-observable verdict of one `des feature-end run` invocation.

    SUCCEEDED -- every gate the cycle ran reported PASS, the deep-review verdict
                 was signed, and the 2 feature-end records were emitted (exit
                 zero). The done-gate's feature-end leg is satisfied for the
                 records slice-03 owns.
    REFUSED   -- the cycle fail-closed (non-zero exit) because a gate FAILED (or
                 a sign/emit precondition was violated). The anti-theater
                 invariant: a failed gate yields NO fake pass-record and NO
                 false "feature-end complete" report.
    """

    SUCCEEDED = "succeeded"
    REFUSED = "refused"


class FeatureEndVerb(str, Enum):
    """The consolidated `des feature-end <verb>` subcommand surface (DDD-7).

    SIGN -- produce a signed FeatureEndReviewVerdict hash (slice-02).
    RUN  -- run the feature-end cycle: the 4-gate orchestration + sign + emit
            (slice-03, the new verb). EMIT (slice-01) stays reachable as the
            top-level `des emit-feature-end` the cycle reuses.
    """

    SIGN = "sign"
    RUN = "run"


@dataclass(frozen=True)
class FeatureEndCycleResult:
    """The observable result of one `des feature-end run` invocation.

    Universe entries are port-exposed only (Mandate 8): the command outcome
    (succeeded / refused, derived from the exit code), the set of gate-heartbeat
    records read back from the completion ledger, the set of feature-end records
    emitted, and whether the failure (when refused) carried the cycle's own
    structured fail-closed marker (`refused_by_cycle`) versus a vacuous
    dispatcher miss -- never an internal use-case struct.
    """

    outcome: CycleOutcome
    exit_code: int
    gate_records: frozenset[str]
    feature_end_records: frozenset[str]
    refused_by_cycle: bool
