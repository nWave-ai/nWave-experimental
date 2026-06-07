@feature-fix-design-reuse-first-gate-cli @slice-01
Feature: The reuse-first CLI clears or rejects a feature whose code introduces a NEW component

  A solution architect running DESIGN authors a feature whose code introduces a
  NEW component class. Before the feature flows downstream, the architect runs
  the reuse-first check to confirm the NEW component is named in the
  feature-delta's Reuse Analysis section -- so a NEW component introduced
  without any reuse analysis is caught at DESIGN authoring time instead of
  flowing on silently as the gate-or-residue policy forbids.

  The reuse-first CLI is the git-diff-driven half of reuse-first enforcement:
  it asserts every NEW component the feature's commit range introduces is
  named in the feature-delta's Reuse Analysis section. The well-formedness
  half -- "is the Reuse Analysis table itself structurally valid?" -- belongs
  to the sibling validate-feature-delta --require-reuse-analysis gate
  (F-DESIGN-REUSE-FIRST-GATE), a complementary orthogonal concern. A passing
  reuse-first check is the verdict PASS -- explicitly NOT a claim that the
  reuse analysis itself is structurally well-formed.

  # DDD-1..DDD-7. Driving port: scripts/cli/check_reuse_first_design.py
  # invoked via main(argv). Hook-invocable standalone CLI in scripts/cli/
  # with no DES coupling (sibling check_robustness_density.py precedent).
  # Layer 3 (in-process subprocess-equivalent / FS acceptance) -- example
  # only, no PBT (Mandate 9/11): the walking-skeleton verdict set is a
  # finite enumerable closed set.

  Background:
    Given a feature whose design wave has authored a feature-delta

  @slice-01 @walking_skeleton @wiring_e2e @driving_port @contract-shape:unbounded-preservation
  Scenario: A feature whose NEW component is justified in the Reuse Analysis section clears the reuse-first check
    Given the feature carries one NEW component named in its Reuse Analysis section
    When the architect runs the reuse-first check on the feature
    Then the feature passes the reuse-first check
    And the reuse-first check leaves the feature-delta and the diff source unchanged

  @slice-01 @error @driving_port @contract-shape:unbounded-preservation
  Scenario: A feature whose NEW component is absent from the Reuse Analysis section is rejected
    Given the feature carries one NEW component absent from its Reuse Analysis section
    When the architect runs the reuse-first check on the feature
    Then the feature is rejected by the reuse-first check
    And the reuse-first check leaves the feature-delta and the diff source unchanged

  @slice-01 @driving_port @contract-shape:unbounded-preservation
  Scenario: Invoking the reuse-first check on a justified feature does not mutate any observable
    Given the feature carries one NEW component named in its Reuse Analysis section
    When the architect runs the reuse-first check on the feature
    Then the reuse-first check produced a structured verdict
    And the reuse-first check leaves the feature-delta and the diff source unchanged
