@feature-oss-feature-end-emit-cli @slice-01
Feature: An orchestrator emits the feature-end records so the done-gate can certify the terminal
  As an nWave orchestrator running an atdd_pure feature-end cycle by hand
  I want a `des emit-feature-end` command that writes the two feature-end
    records -- the batch-refactor-completed mark and the deep-review verdict
    bound to a signed reviewer hash -- to the tamper-evident completion ledger
  So that an orchestrator-run feature-end leaves a verifiable trace and the
    done-gate certifies a genuine terminal instead of refusing on records that
    have no emitter -- and so a hand-fabricated verdict with no signed hash is
    mechanically refused, never silently accepted

  # slice-01 of oss-feature-end-emit-cli -- the R2 walking-skeleton, the
  # thinnest end-to-end vertical: a single `des emit-feature-end` command that
  # wraps the EXISTING tamper-evident completion ledger and is dispatched
  # through the real `des` single entry point. It closes the narrowest part of
  # the R2 done-gate gap -- the 2 feature-end records that, today, have no
  # emitter (the other 4 gate-records already do). Closes
  # F-ATDD-PURE-FEATURE-END-CYCLE-UNWIRED (backlog.md:738).
  #
  # RED scaffold (ADR-025 + ADR-028): these ATs FAIL on master for the RIGHT
  # reason -- `emit-feature-end` is not yet a registered subcommand of the
  # `des` dispatcher, so dispatching it errors (unknown-subcommand), no record
  # is appended, and the read-back / refusal assertions fail with a semantic
  # AssertionError. They PASS once slice-01 lands the new
  # `des.cli.emit_feature_end` module (thin over
  # `AtCompletionLedger.append_feature_end_event`) and registers it in the
  # `__main__` dispatcher registry + the gate catalog (the 1:1 mirror this
  # feature must honour, slice-04's AD-26 lesson).
  #
  # ANTI-THEATER INVARIANT (load-bearing, DDD-3 + feedback_earned_trust_
  # mechanical_evidence_not_llm_verdict): the deep-review verdict record cannot
  # exist without a bound signed reviewer hash. A `--record FeatureEndReviewVerdict`
  # WITHOUT a `--verdict-hash` is REFUSED (non-zero exit) -- the feature's
  # raison d'etre, because a hand-fabricated verdict is theater. The
  # batch-refactor-completed record, conversely, carries NO hash.
  #
  # @coupled: the three scenarios pin ONE CLI contract. The two records are the
  # divergence-verification PAIR the done-gate reads as a set (the done-gate's
  # `feature_end_events()` requires BOTH `EBatchRefactorCompleted` AND
  # `FeatureEndReviewVerdict` before a feature is closeable), and the refusal
  # scenario pins the same command's input contract -- they share the single
  # `des emit-feature-end` driving-port closure and cannot be split without
  # severing that contract.
  #
  # Driving port: the real `des emit-feature-end` subcommand, invoked over the
  # single `des` entry point as a subprocess against a real git working tree and
  # a real AT-completion ledger (Mandate-13 driving-port-only, Layer 3
  # subprocess). The completion ledger is read back through the production
  # ledger reader -- the audit SUBSTRATE the done-gate consumes, not the SUT.
  # Example-only, no PBT (Mandate 9/11: a real-I/O layer-3 surface).

  @slice-01 @walking_skeleton @driving_port @real-io @coupled @contract-shape:bounded-change
  Scenario: An orchestrator records that the batch refactor ran
    Given an orchestrator at the feature-end of a feature
    When the orchestrator records that the batch refactor completed
    Then the completion ledger carries the batch-refactor-completed record
    And the command reports success

  @slice-01 @driving_port @real-io @coupled @contract-shape:bounded-change
  Scenario: An orchestrator records the deep-review verdict bound to its signed hash
    Given an orchestrator at the feature-end of a feature
    When the orchestrator records the deep-review verdict with its signed hash
    Then the completion ledger carries the deep-review-verdict record
    And the deep-review-verdict record carries the signed hash
    And the command reports success

  @slice-01 @driving_port @real-io @coupled @error @contract-shape:unbounded-preservation
  Scenario: A deep-review verdict without its signed hash is refused
    Given an orchestrator at the feature-end of a feature
    When the orchestrator records the deep-review verdict without a signed hash
    Then the command refuses the record
    And the completion ledger carries no deep-review-verdict record

  @slice-01 @driving_port @real-io @coupled @error @contract-shape:bounded-change
  Scenario: A batch-refactor record with a signed hash is refused (verdict-only symmetry)
    Given an orchestrator at the feature-end of a feature
    When the orchestrator records the batch-refactor completion with a signed verdict hash
    Then the command refuses the record
    And the completion ledger carries no batch-refactor-completed record
