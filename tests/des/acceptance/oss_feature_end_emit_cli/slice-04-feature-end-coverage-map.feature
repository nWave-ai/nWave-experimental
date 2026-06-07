@feature-oss-feature-end-emit-cli @slice-04
Feature: A feature-end cycle runs the real coverage-map verify, so the last two done-gate records are minted only on a genuine human signoff and never by theater
  As an nWave orchestrator running an atdd_pure feature-end cycle by hand-dispatch
  I want the `des feature-end run` cycle to RUN the real coverage-map verify and
    emit the two coverage-map touchpoint records only when a human has genuinely
    signed the coverage-map
  So that an orchestrator-run feature-end whose coverage-map is human-signed leaves
    a fully reconciled done-gate trace, while a feature-end whose coverage-map is
    unsigned refuses loudly and mints no coverage-map record -- the heartbeat is
    present if and only if a real signoff was verified

  # slice-04 of oss-feature-end-emit-cli (option (b) RATIFIED, Ale 2026-06-03;
  # OQ-3=(i) -- mechanism-complete = R2 closed). slice-03 shipped the cycle that
  # RUNS the walking-skeleton + env-e2e gates then signs + emits the 2
  # feature-end records, but left the cycle PARTIAL-DONE-HONEST: it does NOT
  # emit the 2 CoverageMapVerifiedAt{Distill,Deliver}Exit records, so
  # `des verify-integrity` STILL reports them missing.
  #
  # slice-04 closes that gap RM-1-HONEST (option (b), NOT a bare presence
  # heartbeat). It PORTS the §5.3 coverage-map verify core into
  # src/des/application/coverage_map_verify_service (reuse-by-relocation, stdlib
  # + PyYAML only) and EXTENDS run_feature_end_cycle to RUN it in-process after
  # the env-e2e leg. On a GENUINE human-signed PASS the cycle appends BOTH
  # coverage-map records -- the heartbeat is written ONLY after a REAL verify
  # pass (heartbeat-present <=> verify-ran-and-passed). On an UNSIGNED
  # (`_pending_` digest) coverage-map the verify core REFUSES, the cycle
  # fail-closes (FeatureEndCycleRefused exit 2), and NEITHER coverage-map record
  # is minted.
  #
  # ANTI-THEATER / RM-1 (load-bearing, per feedback_earned_trust_mechanical_
  # evidence_not_llm_verdict + the upstream fix-distill-human-signoff human-only
  # signoff invariant): the signed digest is a HUMAN act by hard upstream design
  # (the automated producer renders only `_pending_`; there is NO automated
  # signer). An autonomous OSS cycle CANNOT mint the signoff -- so on a
  # genuinely-unsigned feature the cycle REFUSES, and that refusal is CORRECT
  # (no human signoff <=> no coverage-map record <=> the feature-end is genuinely
  # incomplete). The SIGNED scenario stages a GENUINELY-signed coverage-map (the
  # fixture computes the REAL §5.3 canonical digest over the body -- a minted /
  # `_pending_` digest cannot equal the real canonicalization). DIVERGENCE PAIR:
  # a stub impl that ALWAYS emits cannot pass the unsigned scenario, and a stub
  # that NEVER emits cannot pass the signed scenario -- the pair pins the real
  # behaviour.
  #
  # Driving port: the real `des feature-end run` subcommand over the single `des`
  # entry point as a subprocess against a real git tree, the real reviewer
  # signing key, the staged coverage-map artifact, and the real AT-completion
  # ledger (Mandate-13 driving-port-only, Layer 3 subprocess -- the SAME surface
  # as slice-03). The coverage-map records are read back through the production
  # AtCompletionLedger reader (the audit SUBSTRATE `des verify-integrity`
  # consumes, not the SUT). Example-only, no PBT (Mandate 9/11: a real-I/O
  # layer-3 surface running a real verify).
  #
  # @coupled: every scenario pins ONE driving-port contract -- the `des
  # feature-end run` cycle's coverage-map verify leg (run-and-emit on a genuine
  # signoff, fail-close on an unsigned/stale one) -- and cannot be split without
  # severing that single-command closure.

  @slice-04 @walking_skeleton @driving_port @real-io @coupled @contract-shape:bounded-change @covers:coverage-map-verify-leg-emits-on-signed-pass
  Scenario: A feature-end cycle whose coverage-map is human-signed emits all six done-gate records
    Given an orchestrator at the feature-end of a feature that carries a human-signed coverage-map
    When the orchestrator runs the feature-end cycle through its coverage-map verify leg
    Then the cycle reports the feature-end is complete with the coverage-map verified
    And the two coverage-map touchpoint records are now recorded
    And the feature-end is reported as fully reconciled

  # Parametrized refusal family (Mandate 11 -- layer-3 example-only, NOT PBT):
  # every materially-distinct way a coverage-map can FAIL the ported §5.3 verify
  # core is one example row. Each row MUST refuse from the cycle's OWN fail-closed
  # marker (FeatureEndCycleRefused, not a vacuous dispatcher miss) and mint NEITHER
  # coverage-map record. The rows span the verify core's distinct refusal causes:
  #   unsigned              -- `_pending_` digest (the only thing the producer renders)
  #   stale-digest          -- well-formed hex that != the §5.3 canonical digest
  #   missing-signoff-block -- the `## Signoff` block is absent entirely
  #   attestation-gap       -- a signed map omitting an omission-class-id the SSOT requires
  #   malformed             -- the coverage-map file is not parseable as UTF-8
  # This is the AT-2/AT-3 pair generalized into the full C6 negative-robustness
  # decision-table over the refusal causes, each pinned to no-record-minted (the
  # anti-laundering invariant: heartbeat present IFF a real signed verify passed).
  @slice-04 @driving_port @real-io @coupled @error @contract-shape:unbounded-preservation @covers:coverage-map-verify-leg-refuses-on-bad-signoff
  Scenario Outline: A feature-end cycle whose coverage-map fails the verify core refuses and mints no coverage-map record
    Given an orchestrator at the feature-end of a feature whose coverage-map fails the verify core with a <defect> defect
    When the orchestrator runs the feature-end cycle through its coverage-map verify leg
    Then the cycle refuses to certify the feature-end is complete from its own check
    And no coverage-map touchpoint record is recorded

    Examples: verify-core refusal causes
      | defect                |
      | unsigned              |
      | stale-digest          |
      | missing-signoff-block |
      | attestation-gap       |
      | malformed             |
