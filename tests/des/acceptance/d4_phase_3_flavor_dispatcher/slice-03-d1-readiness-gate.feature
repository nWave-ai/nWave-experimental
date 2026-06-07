@feature-d4-phase-3-flavor-dispatcher
Feature: D1 readiness gate verifies the five first-dispatch invariants in one invocation

  As D4 Phase 3 slice-03 author of the readiness pre-dispatch gate
  I want a single gate invocation to verify the five first-dispatch invariants
  (slice plan heading, slice tags per scenario, AT-review verdict ledger
  record, gate output produceable, pre-commit pytest scope satisfiable) and
  emit one combined diagnostic naming every failed invariant
  So that operators starting a NEW feature first dispatch see all blockers
  at once instead of debugging five cascading friction roundtrips
  (closes friction #57 first-dispatch friction stack structurally)

  Background:
    Given the readiness gate composition is available

  @walking_skeleton @driving_port @real-io @slice-03 @contract-shape:unbounded-preservation
  Scenario: A workspace missing the feature delta refuses dispatch with the absent-feature diagnostic
    Given a feature workspace with no feature delta authored
    When the operator runs the readiness gate for the workspace
    Then the readiness verdict refuses dispatch
    And the diagnostic names the slice plan invariant as failed
    And the diagnostic remediation mentions the missing slice plan heading
    And the system filesystem is unchanged

  @driving_port @real-io @slice-03 @error @contract-shape:unbounded-preservation
  Scenario: A workspace missing the slice plan heading refuses dispatch and cites that single invariant
    Given a feature workspace with a feature delta lacking the slice plan heading
    When the operator runs the readiness gate for the workspace
    Then the readiness verdict refuses dispatch
    And the diagnostic names the slice plan invariant as failed
    And the diagnostic remediation mentions the missing slice plan heading

  @driving_port @real-io @slice-03 @contract-shape:unbounded-preservation
  Scenario: A workspace satisfying every first-dispatch invariant clears the readiness gate
    Given a feature workspace satisfying every first-dispatch invariant
    When the operator runs the readiness gate for the workspace
    Then the readiness verdict clears the dispatch
    And the diagnostic names every first-dispatch invariant as satisfied
