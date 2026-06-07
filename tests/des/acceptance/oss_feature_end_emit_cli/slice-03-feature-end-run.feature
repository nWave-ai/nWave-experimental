@feature-oss-feature-end-emit-cli @slice-03
Feature: A feature-end cycle runs the real gates then signs and emits, so the done-gate is satisfied by genuine runs and never by theater
  As an nWave orchestrator running an atdd_pure feature-end cycle by hand-dispatch
  I want a `des feature-end run` command that RUNS the two already-CLI'd feature-end
    gates -- the walking-skeleton gate and the environmental-e2e gate -- then signs
    the deep-review verdict and emits the two feature-end records
  So that a folded orchestrator-run feature-end leaves a genuine, verifiable ledger
    trace -- each gate-heartbeat record reflects a gate that actually ran -- and a
    cycle whose gate FAILS refuses loudly instead of certifying a false complete,
    while the cycle stays honest about the records it does not yet own

  # slice-03 of oss-feature-end-emit-cli (DDD-7 RATIFIED 2026-06-03). slice-01
  # shipped `des emit-feature-end` (the EMITTER of the 2 feature-end records);
  # slice-02 shipped `des feature-end sign` (the PRODUCER of the signed
  # verdict_hash). slice-03 ships the ORCHESTRATOR: the platform-agnostic
  # feature-end-cycle use-case that RUNS the 2 already-CLI'd gates --
  #   des walking-skeleton-gate      -> WalkingSkeletonGateRan heartbeat
  #   des verify-environmental-e2e   -> EnvironmentalE2eGateRan heartbeat
  # -- then SIGNS (reuse slice-02) + EMITS the 2 feature-end records (reuse
  # slice-01), exposed via a NEW `des feature-end run` thin shim AND invocable
  # unchanged by the SubagentStop hook shim (one use-case, two thin driving
  # adapters, DDD-7). The decision/orchestration logic lives in the use-case;
  # the `des feature-end run` CLI is a thin shim with zero orchestration logic.
  #
  # ANTI-THEATER INVARIANT (load-bearing, DDD-6 + feedback_earned_trust_
  # mechanical_evidence_not_llm_verdict): the cycle RUNS the REAL gate CLIs and
  # emits their REAL records. A WalkingSkeletonGateRan / EnvironmentalE2eGateRan
  # record present in the completion ledger means the gate ACTUALLY RAN (each
  # gate appends its heartbeat on ENTRY, BEFORE its verdict, RM-1) -- the cycle
  # does NOT mint a pass-record without running the gate. When a gate FAILS, the
  # cycle does NOT emit a fake pass / does NOT report feature-end complete -- it
  # fail-closes loudly (the same recompute-genuineness discipline slice-02
  # applies to a signed verdict). The fail-closed refusal is asserted to come
  # from the CYCLE's own structured marker, never a vacuous dispatcher miss.
  #
  # PARTIAL-DONE HONESTY (DDD-6 decomposition boundary): slice-03 runs the 2
  # gates whose CLIs EXIST. The 2 CoverageMapVerifiedAt{Distill,Deliver}Exit
  # records have NO coverage-map CLI yet (slice-04). So after slice-03's cycle,
  # `des verify-integrity` STILL reports those 2 records MISSING -- slice-03 does
  # NOT falsely certify the feature is fully done. The honest boundary is pinned.
  #
  # SINGLE ENTRY POINT (DDD-7, AD-26 1:1 mirror): `des feature-end run` registers
  # under the one `des.cli.__main__` dispatcher + the gate catalog, alongside the
  # slice-02 `sign` verb. `des feature-end --help` advertises BOTH `sign` and
  # `run`. No new top-level entry proliferates.
  #
  # Driving port: the real `des feature-end run` subcommand, invoked over the
  # single `des` entry point as a subprocess against a real git working tree, the
  # real gate CLIs, the real reviewer signing key, and the real AT-completion
  # ledger (Mandate-13 driving-port-only, Layer 3 subprocess -- the SAME surface
  # as slice-01 + slice-02). The records are read back through the production
  # `AtCompletionLedger` reader (the audit SUBSTRATE `des verify-integrity`
  # consumes, not the SUT). Example-only, no PBT (Mandate 9/11: a real-I/O
  # layer-3 surface running real gates).
  #
  # @coupled: every scenario pins ONE driving-port contract -- the `des
  # feature-end run` command's run/refuse behavior plus its dispatcher
  # reachability -- and cannot be split without severing that single-command
  # closure (the cycle's gate-run + sign + emit is one atomic orchestration).

  @slice-03 @walking_skeleton @driving_port @real-io @coupled @contract-shape:bounded-change
  Scenario: A feature-end cycle runs the gates and leaves their genuine records
    Given an orchestrator at the feature-end of a feature whose gates pass and whose coverage-map is human-signed
    When the orchestrator runs the feature-end cycle
    Then the cycle reports the feature-end is complete
    And the ledger carries a heartbeat for every gate the cycle ran
    And the ledger carries the batch-refactor and signed deep-review records
    And the ledger carries both coverage-map touchpoint records from a genuine signoff

  @slice-03 @driving_port @real-io @coupled @contract-shape:bounded-change
  Scenario: The gate heartbeats prove the gates actually ran rather than being minted
    Given an orchestrator at the feature-end of a feature whose gates pass
    When the orchestrator runs the feature-end cycle
    Then the walking-skeleton gate left a heartbeat showing it ran
    And the environmental-e2e gate left a heartbeat showing it ran

  @slice-03 @driving_port @real-io @coupled @error @contract-shape:unbounded-preservation
  Scenario: A cycle whose walking-skeleton gate fails refuses instead of certifying complete
    Given an orchestrator at the feature-end of a feature whose walking-skeleton gate fails
    When the orchestrator runs the feature-end cycle
    Then the cycle refuses to certify the feature-end is complete
    And the ledger carries no signed deep-review record

  @slice-03 @driving_port @real-io @coupled @error @contract-shape:unbounded-preservation
  Scenario: When the coverage-map is unsigned the integrity report stays honest that its records are still missing
    Given an orchestrator at the feature-end of a feature whose gates pass but whose coverage-map is not signed
    When the orchestrator runs the feature-end cycle
    Then the integrity report stays honest that the feature-end is not yet fully reconciled
    And the integrity report names the coverage-map touchpoint records as still missing

  @slice-03 @driving_port @real-io @coupled @contract-shape:unbounded-preservation
  Scenario: The cycle verb is reachable alongside the signing verb through the single entry point
    Given an orchestrator at the feature-end of a feature whose gates pass
    When the consolidated feature-end command surface is probed for its verbs
    Then the feature-end cycle verb is reachable through the single entry point
    And the feature-end signing verb is still reachable through the single entry point
