@feature-fix-walking-skeleton-feature-end-wiring
Feature: The walking-skeleton gate heartbeat is wired into the feature-end U4 enforcer
  As an nWave framework developer
  I want the feature-end completion enforcer and the verify_deliver_integrity
    CLI to require the walking-skeleton gate heartbeat alongside the env-e2e
    heartbeat, the batch refactor and the deep-review verdict
  So that a feature that never ran the walking-skeleton gate is mechanically
    blocked at feature-end, never silently shipped as the shipped-but-unread
    walking_skeleton_events reader allows today

  # carpaccio slice-01 (the only slice -- F-WALKING-SKELETON-FEATURE-END-WIRING
  # is a single ~10 LOC frozenset+union extension, sibling to env-e2e slice-02
  # commit 7af95a3d2). Layer 3 (subprocess / FS acceptance): the U4 enforcer
  # `_missing_feature_end_cycle_records` and the `_verify_atdd_pure` CLI mirror
  # are invoked against per-scenario tmp repos with real `AtCompletionLedger`
  # writes -- example-only, no PBT (Mandate 9/11).
  #
  # CONTRACT SOURCE: the SSOT for "feature is closeable" is the
  # `_REQUIRED_FEATURE_END_RECORDS` frozenset at
  # `src/des/adapters/drivers/hooks/subagent_stop_handler.py:754-760`. This
  # slice extends it from 3 records to 4 by adding `WalkingSkeletonGateRan`,
  # and extends the union read at line 783-785 to include
  # `walking_skeleton_events()`. The CLI mirror at
  # `src/des/cli/verify_deliver_integrity.py:329-336` carries the same
  # extension so the CLI verdict matches the hook block.
  #
  # The RCA `docs/analysis/rca-atdd-pure-feature-end-cycle-unwired-2026-05-24.md`
  # identifies this as the 5th sibling of the env-e2e pre-7af95a3d2 defect
  # class -- the `walking_skeleton_events()` reader was shipped at
  # `at_completion_ledger.py:290-303` with ZERO callers in `src/des/cli/` or
  # `src/des/adapters/drivers/`. Same shipped-but-unread state env-e2e was in.
  #
  # Driving port: the U4 SubagentStop hook branch
  # (`_missing_feature_end_cycle_records`) and the `_verify_atdd_pure` CLI.

  # Mandate 9 + 11: at layer 3 the U4 enforcer decision over the required-record
  # frozenset is example-pinned via parametrize-collapse, one row per
  # presence/absence cell -- never PBT-generated. The `<missing_outcome>` column
  # carries the typed outcome enum so the assertion observes both "is the
  # walking-skeleton heartbeat in the missing set" AND the diagnostic shape
  # from the single port-exposed missing-record set (Mandate 8 universe-bound).
  @slice-01 @driving_port @parametrize-collapse @contract-shape:bounded-change
  Scenario Outline: The U4 enforcer treats the walking-skeleton heartbeat as <missing_outcome> when the ledger is <ledger_state>
    Given a feature whose feature-end ledger is staged in the <ledger_state> condition
    When the feature-end completion enforcer checks the required feature-end records
    Then the walking-skeleton heartbeat is <missing_outcome> in the missing-record set
    And the feature is not permitted to be declared done when the missing-record set is non-empty

    Examples:
      | ledger_state                                | missing_outcome |
      | complete with the walking-skeleton heartbeat | absent          |
      | complete without the walking-skeleton heartbeat | present         |

  # AT-2: the `_verify_atdd_pure` CLI mirror must report the same
  # missing-record verdict as the U4 hook -- a feature whose ledger holds
  # every required record EXCEPT the walking-skeleton heartbeat ships as
  # `FeatureEndCycleIncomplete` from the CLI, not as a silent pass. This is
  # the parity assertion: hook block <=> CLI block.
  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The verify_deliver_integrity CLI mirrors the U4 hook on a missing walking-skeleton heartbeat
    Given a feature whose feature-end ledger is staged in the complete without the walking-skeleton heartbeat condition
    When the verify_deliver_integrity CLI runs on the feature
    Then the CLI exits with a feature-end-cycle-incomplete verdict
    And the verdict names the walking-skeleton heartbeat as a missing required record

  # AT-3 BACKWARD-COMPAT: an in-flight feature whose happy-path AT helpers
  # seed BOTH the env-e2e heartbeat AND the walking-skeleton heartbeat still
  # passes the U4 enforcer -- the frozenset extension does not regress
  # sibling features that have been migrated to the co-shipped fixture
  # seeding. This is the regression-pin against the critical risk identified
  # in the RCA section 6 ("every in-flight feature blocks at feature-end with
  # FeatureEndCycleIncomplete until the emission lands").
  @slice-01 @driving_port @real-io @regression-pin @contract-shape:bounded-change
  Scenario: An in-flight feature with both heartbeats seeded passes the U4 enforcer
    Given a feature whose feature-end ledger is staged in the complete with the walking-skeleton heartbeat condition
    When the feature-end completion enforcer checks the required feature-end records
    Then the missing-record set is empty
    And the feature is permitted to be declared done
