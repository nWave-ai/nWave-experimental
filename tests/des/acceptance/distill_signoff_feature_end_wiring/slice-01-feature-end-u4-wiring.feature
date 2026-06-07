@feature-fix-distill-signoff-feature-end-wiring
Feature: The coverage-map touchpoint heartbeats are wired into the feature-end U4 enforcer
  As an nWave framework developer
  I want the feature-end completion enforcer and the verify_deliver_integrity
    CLI to require BOTH the coverage-map-verified-at-distill-exit and the
    coverage-map-verified-at-deliver-exit heartbeats alongside the env-e2e
    and walking-skeleton heartbeats, the batch refactor and the deep-review
    verdict
  So that a feature that never ran the coverage-map verification at either
    touchpoint is mechanically blocked at feature-end, never silently shipped
    as the shipped-but-unread coverage_map_touchpoint_events reader allows
    today (residue F-SLICE-06-U4-CONSUMER-MISSING)

  # carpaccio slice-01 (the only slice -- F-DISTILL-SIGNOFF-FEATURE-END-WIRING
  # is a single ~12 LOC frozenset+union extension, 5th sibling of env-e2e
  # slice-02 commit 7af95a3d2 and walking-skeleton-feature-end-wiring slice-01
  # commit a65a28575). Layer 3 (subprocess / FS acceptance): the U4 enforcer
  # `_missing_feature_end_cycle_records` and the `_verify_atdd_pure` CLI mirror
  # are invoked against per-scenario tmp repos with real `AtCompletionLedger`
  # writes -- example-only, no PBT (Mandate 9/11).
  #
  # CONTRACT SOURCE: the SSOT for "feature is closeable" is the
  # `_REQUIRED_FEATURE_END_RECORDS` frozenset at
  # `src/des/adapters/drivers/hooks/subagent_stop_handler.py:758-765`. This
  # slice extends it from 4 records to 6 by adding
  # `CoverageMapVerifiedAtDistillExit` AND `CoverageMapVerifiedAtDeliverExit`,
  # and extends the union read at line 797 to include
  # `coverage_map_touchpoint_events()`. The CLI mirror at
  # `src/des/cli/verify_deliver_integrity.py:332-344` carries the same
  # extension so the CLI verdict matches the hook block.
  #
  # The Gate D slice-06 commit `a8c9dc9d8` shipped the gate-side emission
  # (writers + reader exist) but explicitly named the U4 consumer as the
  # named residue F-SLICE-06-U4-CONSUMER-MISSING -- "the gate emits the
  # heartbeats but the consumer does not yet enforce them". This slice
  # closes that residue.
  #
  # Driving port: the U4 SubagentStop hook branch
  # (`_missing_feature_end_cycle_records`) and the `_verify_atdd_pure` CLI.

  # Mandate 9 + 11: at layer 3 the U4 enforcer decision over the required-record
  # frozenset is example-pinned via parametrize-collapse, one row per
  # presence/absence cell per touchpoint -- never PBT-generated. The
  # `<missing_outcome>` column carries the typed outcome enum so the
  # assertion observes both "is this touchpoint heartbeat in the missing
  # set" AND the diagnostic shape from the single port-exposed
  # missing-record set (Mandate 8 universe-bound).
  @slice-01 @driving_port @parametrize-collapse @contract-shape:bounded-change
  Scenario Outline: The U4 enforcer treats the <touchpoint> heartbeat as <missing_outcome> when the ledger is <ledger_state>
    Given a feature whose feature-end ledger is staged in the <ledger_state> condition
    When the feature-end completion enforcer checks the required feature-end records
    Then the <touchpoint> heartbeat is <missing_outcome> in the missing-record set
    And the feature is not permitted to be declared done when the missing-record set is non-empty

    Examples:
      | ledger_state                                                              | touchpoint    | missing_outcome |
      | complete with both coverage-map heartbeats                                 | distill-exit  | absent          |
      | complete with both coverage-map heartbeats                                 | deliver-exit  | absent          |
      | complete without the coverage-map distill-exit heartbeat                   | distill-exit  | present         |
      | complete without the coverage-map deliver-exit heartbeat                   | deliver-exit  | present         |

  # AT-2: the `_verify_atdd_pure` CLI mirror must report the same
  # missing-record verdict as the U4 hook -- a feature whose ledger holds
  # every required record EXCEPT the coverage-map deliver-exit heartbeat
  # ships as `FeatureEndCycleIncomplete` from the CLI, not as a silent
  # pass. This is the parity assertion: hook block <=> CLI block.
  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The verify_deliver_integrity CLI mirrors the U4 hook on a missing coverage-map deliver-exit heartbeat
    Given a feature whose feature-end ledger is staged in the complete without the coverage-map deliver-exit heartbeat condition
    When the verify_deliver_integrity CLI runs on the feature
    Then the CLI exits with a feature-end-cycle-incomplete verdict
    And the verdict names the deliver-exit heartbeat as a missing required record

  # AT-3 BACKWARD-COMPAT: an in-flight feature whose happy-path AT helpers
  # seed every prior heartbeat AND the two coverage-map touchpoint
  # heartbeats still passes the U4 enforcer -- the frozenset extension does
  # not regress sibling features that have been migrated to the co-shipped
  # fixture seeding. This is the regression-pin against the critical risk
  # mirrored from walking-skel-wire slice-01 ("every in-flight feature
  # blocks at feature-end with FeatureEndCycleIncomplete until the seeding
  # lands").
  @slice-01 @driving_port @real-io @regression-pin @contract-shape:bounded-change
  Scenario: An in-flight feature with both coverage-map heartbeats seeded passes the U4 enforcer
    Given a feature whose feature-end ledger is staged in the complete with both coverage-map heartbeats condition
    When the feature-end completion enforcer checks the required feature-end records
    Then the missing-record set is empty
    And the feature is permitted to be declared done
