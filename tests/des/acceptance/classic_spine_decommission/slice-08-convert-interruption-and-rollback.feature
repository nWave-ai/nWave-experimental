@feature-classic-spine-decommission
Feature: An architect's interrupted conversion is recoverable and reversible
  As a solution architect retiring the classic roadmap spine
  I want an interrupted conversion to resume cleanly from its journal and a
    rollback to restore the classic artifacts
  So that no feature is ever left half-converted in a limbo state

  # slice-08 of classic-spine-decommission. C7b: an interrupted conversion
  # resumes from the journal across every journalled side effect. C4b: a
  # --rollback restores the pre-conversion classic artifacts (M3).
  #
  # Layer 3 (subprocess / FS acceptance). Example-only -- sad paths enumerated
  # explicitly (Mandate 11). state-delta + Universe assertions (Mandate 8).
  #
  # Driving port: `des.cli.convert_to_atdd_pure` (main(argv), --rollback form).

  # --- C7b interruption: the journalled resumable execute ----------------------

  @slice-08 @driving_port @error @contract-shape:bounded-change
  Scenario Outline: An interrupted conversion never leaves a half-converted feature
    Given a classic feature "convert-target" that carries a recovered slice plan
    And the classic feature has 12 roadmap steps
    And roadmap steps "01-01" constitute slice "slice-01"
    And step "01-01" was committed at "aaaa111" whose commit exists and is reachable with green tests
    And the conversion is interrupted <interrupt_point>
    When the architect converts the feature a second time
    Then the feature is never left half-converted
    And the feature now runs on the atdd_pure spine

    Examples: interruption points across the four journalled side effects
      | interrupt_point                          |
      | after the slice plan heading is promoted |
      | after the ledger is seeded               |
      | after the config is flipped              |

  # --- C4b inverse-op: rollback restores the classic artifacts -----------------

  @slice-08 @driving_port @contract-shape:bounded-change
  Scenario: Rolling back a partial conversion restores the classic artifacts
    Given a classic feature "convert-target" that carries a recovered slice plan
    And the classic feature has 12 roadmap steps
    And roadmap steps "01-01" constitute slice "slice-01"
    And step "01-01" was committed at "aaaa111" whose commit exists and is reachable with green tests
    And the conversion is interrupted after the ledger is seeded
    When the architect rolls back the conversion
    Then the pre-conversion classic artifacts are restored
    And the feature is never left half-converted
