@feature-fix-design-reuse-first-gate-cli @slice-02
Feature: The reuse-first CLI detects NEW components from the feature's real commit range

  slice-01 proved the walking skeleton against a fixture-injected list of NEW
  component names. slice-02 promotes the detector to the empirical ground
  truth: the reuse-first check reads the NEW components the feature's commit
  range actually introduced -- by comparing the feature branch against the
  trunk -- and requires each one to be named in the feature-delta's Reuse
  Analysis section. A NEW component the architect's commits genuinely added,
  but never reasoned about in the Reuse Analysis, is the recurrence vector the
  gate-or-residue policy targets: this slice catches it from the commits
  themselves, not from a hand-maintained list.

  The trunk the feature diverged from and the source tree that counts as
  feature code are the conventional defaults; making them overridable is
  deferred configurability polish (slice-04), not part of this core.

  # DDD-3 / DDD-6 / DDD-7. Driving port: scripts/cli/check_reuse_first_design.py
  # invoked via main(argv). Driven ports (real I/O): a real feature repository
  # under tmp_path (real commits on the trunk and a feature commit) plus the
  # feature-delta on the real filesystem. The detector reads the feature's real
  # commit-range name-status (added paths + their NEW class declarations) -- the
  # name-status seam slice-03's file-component detection consumes.
  # Layer 3 (FS + subprocess acceptance) with a real driven adapter -> @real-io,
  # example-based, assert_state_delta (Mandate 9 v2 OR-reduction: at least one
  # real driven adapter -> example-based, no PBT). Finite verdict set (PASS /
  # FAIL / preservation) -> example scenarios, no @given.

  Background:
    Given a feature whose source tree is tracked in a repository

  @slice-02 @walking_skeleton @wiring_e2e @driving_port @real-io @contract-shape:bounded-change
  Scenario: A feature whose committed NEW component is named in the Reuse Analysis section clears the reuse-first check
    Given the feature's commits add a NEW component to the source tree
    And the feature names that NEW component in its Reuse Analysis section
    When the architect runs the reuse-first check on the feature's commit range
    Then the feature's commit range passes the reuse-first check
    And the reuse-first check reports one NEW component
    And the reuse-first check leaves the feature repository unchanged

  @slice-02 @error @driving_port @real-io @contract-shape:bounded-change
  Scenario: A feature whose committed NEW component is absent from the Reuse Analysis section is rejected
    Given the feature's commits add a NEW component to the source tree
    And the feature does not name that NEW component in its Reuse Analysis section
    When the architect runs the reuse-first check on the feature's commit range
    Then the feature's commit range is rejected by the reuse-first check
    And the reuse-first check reports one NEW component
    And the reuse-first check leaves the feature repository unchanged

  @slice-02 @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: Running the reuse-first check against the real commit range mutates no observable
    Given the feature's commits add a NEW component named in its Reuse Analysis section
    When the architect runs the reuse-first check on the feature's commit range
    Then the reuse-first check produced a structured verdict for the commit range
    And the reuse-first check leaves the feature repository unchanged
