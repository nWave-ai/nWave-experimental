"""Domain types for slice-04 -- the feature-end cycle's REAL coverage-map leg.

slice-04 of oss-feature-end-emit-cli (option (b) RATIFIED, Ale 2026-06-03;
OQ-3=(i) -- mechanism-complete = R2 closed). Every domain noun in the slice-04
Gherkin is expressed once here as a typed enum / NewType; step bodies and the
composition service consume these typed parameters (Mandate-12 criterion 1 --
domain types module exists with typed enums for every domain noun used in the
Gherkin).

WHAT SLICE-04a ADDS over slice-03
---------------------------------
slice-03 shipped the feature-end-cycle use-case that RUNS the 2 already-CLI'd
gates (walking-skeleton + environmental-e2e) then signs + emits the 2
feature-end records. slice-03 left the cycle PARTIAL-DONE-HONEST: it does NOT
emit the 2 ``CoverageMapVerifiedAt{Distill,Deliver}Exit`` records, so
``des verify-integrity`` STILL reports them missing.

slice-04 closes that gap -- but RM-1-HONEST (option (b), NOT a bare presence
heartbeat). It PORTS the §5.3 coverage-map verify core into
``src/des/application/coverage_map_verify_service`` (reuse-by-relocation, stdlib
+ PyYAML only) and EXTENDS ``run_feature_end_cycle`` to RUN it in-process after
the env-e2e leg. On a GENUINE human-signed PASS the cycle appends BOTH
``CoverageMapVerifiedAtDistillExit`` + ``CoverageMapVerifiedAtDeliverExit``
(``append_coverage_map_verified_at_{distill,deliver}_exit``) -- so the
heartbeat is written ONLY after a REAL verify pass (heartbeat-present <=>
gate-ran-and-passed). On an UNSIGNED / ``_pending_`` / stale-digest /
structurally-incomplete coverage-map the verify core REFUSES, the cycle
fail-closes (``CycleRefusal`` -> ``FeatureEndCycleRefused`` exit 2), and the 2
coverage-map records are NEVER minted.

ANTI-THEATER / RM-1 (load-bearing, per ``feedback_earned_trust_mechanical_
evidence_not_llm_verdict`` + the upstream ``fix-distill-human-signoff``
human-only signoff invariant): the signed digest is a HUMAN act by hard upstream
design (``_pending_`` is the only thing the automated producer renders; there is
NO automated signer). An autonomous OSS orchestrator-run cycle CANNOT mint the
signoff -- so on a genuinely-unsigned feature the cycle REFUSES, and that refusal
is CORRECT (no human signoff <=> no ``CoverageMapVerified*`` record <=> the
feature-end is genuinely incomplete). The PASS scenario stages a GENUINELY-signed
coverage-map (the fixture builder computes the REAL §5.3 canonical digest over
the body and records it -- a minted/``_pending_`` digest cannot equal the real
canonicalization), so a stub impl that ALWAYS emits cannot pass the unsigned
scenario and a stub that NEVER emits cannot pass the signed scenario -- the
divergence pair pins the real behaviour.

DRIVING PORT (Mandate-13, Layer-3 subprocess): the SUT is exercised through the
PRODUCTION single entry point -- the real ``des feature-end run`` subcommand over
the ``des.cli.__main__`` dispatcher (the SAME driving surface as slice-03). The
composition NEVER imports the cycle use-case / the ported verify core and calls
them at the step boundary; the only entry is the real subprocess. The
coverage-map records are read back through the production ``AtCompletionLedger``
reader (the audit SUBSTRATE ``des verify-integrity`` consumes), and the
post-cycle ledger is fed to the real ``des verify-integrity`` consumer to pin the
ALL-6-RECONCILED boundary that slice-03's partial-done honesty boundary becomes
once slice-04 ships.

S1 (step-text uniqueness): every literal step string in the slice-04 feature is
unique within the feature directory. slice-03's steps speak of "whose gates
pass" / "runs the feature-end cycle" / "still missing"; slice-04's steps speak
of "carries a human-signed coverage-map" / "carries an unsigned coverage-map" /
"the coverage-map verify passes for real" / "all six feature-end records" /
"fully reconciled". No literal is shared across the slice step files.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-feature-end-cycle-demo").
FeatureId = NewType("FeatureId", str)


class CoverageMapRecord(str, Enum):
    """A coverage-map touchpoint record the slice-04 cycle leg emits on a PASS.

    These are the 2 records slice-03 left UN-emitted (partial-done honesty
    boundary). slice-04's REAL coverage-map verify leg appends BOTH on a
    genuine human-signed PASS -- RM-1: present <=> the verify actually ran and
    passed. On a refusal NEITHER is minted.

    DISTILL_EXIT -- `CoverageMapVerifiedAtDistillExit`.
    DELIVER_EXIT -- `CoverageMapVerifiedAtDeliverExit`.
    """

    DISTILL_EXIT = "CoverageMapVerifiedAtDistillExit"
    DELIVER_EXIT = "CoverageMapVerifiedAtDeliverExit"


class CoverageMapSignoff(str, Enum):
    """The signoff state of the coverage-map the cycle's verify leg inspects.

    The discriminator the divergence-pair pins: the cycle's behaviour MUST
    differ between a genuinely-signed map and an unsigned one. A stub that
    always-emits fails on UNSIGNED; a stub that never-emits fails on SIGNED.

    SIGNED   -- the `## Signoff` block carries a real `reviewed-content-digest`
                that MATCHES the §5.3 canonical digest of the body, and the
                omission-classes attestation covers every class-id. The verify
                core PASSES; the cycle emits both coverage-map records.
    UNSIGNED -- the `## Signoff` block carries a `_pending_` digest (the only
                thing the automated producer renders; no human signed). The
                verify core REFUSES (`SignoffMissing`); the cycle fail-closes
                and emits NO coverage-map record.
    """

    SIGNED = "signed"
    UNSIGNED = "unsigned"


class CoverageMapDefect(str, Enum):
    """A materially-distinct way a coverage-map FAILS the ported §5.3 verify core.

    The Scenario-Outline refusal-family discriminator (Mandate 11 layer-3
    example-only): each value stages a coverage-map artifact that the REAL ported
    verify core REFUSES for a DISTINCT cause, so the cycle fail-closes and mints
    NEITHER coverage-map record. The DSL emerges from this enum -- ONE parsed
    Given step covers all five rows instead of five literal Given decorators
    (Mandate-12 typed-parameter template).

    UNSIGNED              -- `_pending_` digest (the only thing the automated
                             producer renders; no human signed). Verify core
                             refuses `SignoffMissing`.
    STALE_DIGEST          -- a well-formed lowercase-hex digest that does NOT equal
                             the §5.3 canonical digest of the body. Verify core
                             refuses `SignoffStale` from its OWN digest recompute.
    MISSING_SIGNOFF_BLOCK -- the `## Signoff` section is absent entirely. Verify
                             core refuses on the structural / missing-digest gate.
    ATTESTATION_GAP       -- a genuinely-digest-matched signoff that OMITS an
                             omission-class-id the Layer-1 SSOT requires. Verify
                             core refuses on the attestation-incomplete gate.
    MALFORMED             -- the coverage-map file is not parseable as UTF-8.
                             Verify core refuses `MalformedInput`.
    """

    UNSIGNED = "unsigned"
    STALE_DIGEST = "stale-digest"
    MISSING_SIGNOFF_BLOCK = "missing-signoff-block"
    ATTESTATION_GAP = "attestation-gap"
    MALFORMED = "malformed"


class CycleOutcome(str, Enum):
    """The user-observable verdict of one `des feature-end run` invocation.

    SUCCEEDED -- every gate AND the REAL coverage-map verify reached PASS, the
                 deep-review verdict was signed, and all 6 feature-end records
                 were emitted (exit zero). The done-gate is fully reconciled.
    REFUSED   -- the cycle fail-closed (non-zero exit) because the coverage-map
                 verify REFUSED (unsigned / `_pending_` digest). The
                 anti-theater invariant: an unsigned coverage-map yields NO fake
                 coverage-map record and NO false "feature-end complete" report.
    """

    SUCCEEDED = "succeeded"
    REFUSED = "refused"
