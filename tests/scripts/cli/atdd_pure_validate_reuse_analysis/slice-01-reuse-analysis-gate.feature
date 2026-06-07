@feature-fix-design-reuse-first-gate
Feature: The Reuse Analysis gate clears or rejects a feature-delta's reuse table

  A solution architect running DESIGN authors the Reuse Analysis table -- the
  `## Reuse Analysis` section of the feature-delta, a five-column table
  (Existing Component, File, Overlap, Decision, Justification). Before that
  feature-delta flows downstream, the architect runs the Reuse Analysis check
  to confirm the section is present and structurally well formed, so a missing
  or malformed table is caught at DESIGN authoring time instead of flowing on
  silently as the gate-or-residue policy forbids.

  The Reuse Analysis check is the structural half of reuse-first enforcement:
  it asserts the section exists and its table is well formed. The judgment
  half -- "could this CREATE_NEW have been an EXTEND?", "is an overlapping
  component silently omitted?" -- belongs to the solution-architect reviewer's
  veto (slice-03), a separate concern. A passing structural check is the
  verdict `structurally-accepted` -- explicitly NOT a claim that reuse-first
  was honoured.

  # DDD-1..DDD-11. Driving port: the validate-feature-delta CLI invoked with
  # --require-reuse-analysis. Invoked as DESIGN skill-prose parity with the
  # --require-slice-plan precedent (nw-discuss/SKILL.md:30) -- no DES exit_gate.
  # Layer 3 (subprocess/FS acceptance) -- example-only, no PBT (Mandate 9/11):
  # the Reuse Analysis shapes form a finite enumerable closed set.

  Background:
    Given a feature-delta authored for a code feature

  @slice-01 @walking_skeleton @wiring_e2e @driving_port @contract-shape:unbounded-preservation
  Scenario: A well-formed Reuse Analysis table clears the structural check
    Given the feature-delta carries a well-formed Reuse Analysis table
    When the architect runs the Reuse Analysis check on the feature-delta
    Then the Reuse Analysis is structurally accepted
    And the check leaves the feature-delta unchanged

  @slice-01 @error @driving_port @contract-shape:unbounded-preservation
  Scenario: A feature-delta with no Reuse Analysis table is rejected
    Given the feature-delta carries no Reuse Analysis section
    When the architect runs the Reuse Analysis check on the feature-delta
    Then the Reuse Analysis is rejected for a missing Reuse Analysis
    And the check leaves the feature-delta unchanged

  @slice-01 @driving_port @contract-shape:unbounded-preservation
  Scenario: This feature's own Reuse Analysis table clears the structural check
    Given the feature-delta carries this feature's own Reuse Analysis table
    When the architect runs the Reuse Analysis check on the feature-delta
    Then the Reuse Analysis is structurally accepted
    And the check leaves the feature-delta unchanged
