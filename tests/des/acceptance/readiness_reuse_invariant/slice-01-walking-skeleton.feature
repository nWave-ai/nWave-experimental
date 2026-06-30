@feature-fix-readiness-gate-reuse-first-invariant
Feature: The readiness gate refuses a feature carrying no reuse-first analysis and no design-skip witness

  As a maintainer who owns the no-duplication / SSOT guarantee
  I want the DELIVER-entry readiness gate to refuse a feature whose first
  crafter dispatch carries neither a Reuse Analysis nor an explicit
  DESIGN-skip witness
  So that a feature which skips the optional DESIGN wave cannot slip past the
  reuse-first guarantee the way fix-actionable-veto-recovery did

  @walking-skeleton @driving_port @real-io @slice-01 @contract-shape:unbounded-preservation
  Scenario: A complete workspace with no reuse analysis and no witness is refused on the reuse-first dimension
    Given a complete feature workspace with no Reuse Analysis and no Design Skipped witness
    When the maintainer runs the readiness gate before first crafter dispatch
    Then the readiness gate refuses the dispatch
    And the reuse-first invariant is reported as failed
    And the remediation names both the Reuse Analysis section and the Design Skipped witness
    And the five pre-existing first-dispatch invariants are still reported as satisfied
    And the feature workspace files are unchanged after the gate ran

  @driving_port @real-io @slice-01 @error @contract-shape:unbounded-preservation
  Scenario: A workspace whose only witness heading carries an empty rationale is refused
    Given a complete feature workspace with no Reuse Analysis and a Design Skipped witness with an empty rationale
    When the maintainer runs the readiness gate before first crafter dispatch
    Then the readiness gate refuses the dispatch
    And the reuse-first invariant is reported as failed
    And the five pre-existing first-dispatch invariants are still reported as satisfied

  @driving_port @real-io @slice-01 @error @contract-shape:unbounded-preservation
  Scenario: A malformed reuse analysis with no witness is refused and names the malformed cause
    Given a complete feature workspace with a malformed Reuse Analysis and no Design Skipped witness
    When the maintainer runs the readiness gate before first crafter dispatch
    Then the readiness gate refuses the dispatch
    And the reuse-first invariant is reported as failed
    And the remediation names the malformed reuse cause
    And the five pre-existing first-dispatch invariants are still reported as satisfied

  @driving_port @real-io @slice-01 @error @contract-shape:unbounded-preservation
  Scenario: An unjustified create-new reuse analysis with no witness is refused and names the unjustified cause
    Given a complete feature workspace with an unjustified create-new Reuse Analysis and no Design Skipped witness
    When the maintainer runs the readiness gate before first crafter dispatch
    Then the readiness gate refuses the dispatch
    And the reuse-first invariant is reported as failed
    And the remediation names the unjustified create-new cause
    And the five pre-existing first-dispatch invariants are still reported as satisfied
