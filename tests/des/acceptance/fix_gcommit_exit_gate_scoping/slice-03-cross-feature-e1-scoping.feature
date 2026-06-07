@feature-fix-gcommit-exit-gate-scoping
Feature: The exit-gate completeness check is scoped to the committing feature

  As the U2 G_COMMIT exit gate that checks a slice commit is complete before
    certifying it on the spine's hot path
  I want the completeness check to look ONLY at the committing feature's own
    specification files, not at every feature that happens to share the same
    slice number elsewhere on the tree
  So that a commit for one feature is certified on its own merits even when a
    second, unrelated feature sits beside it on the working tree -- nobody is
    forced to hold the second feature off-tree just to commit the first

  # slice-03 (E1 cross-feature scoping).
  #
  # At HEAD the exit gate checks slice-commit completeness with NO feature
  # scope (`subagent_stop_handler.py:618-630`), so the check falls back to a
  # WHOLE-TREE scan for every specification file carrying the slice's number
  # (`slice_at_completeness.feature_files_for_slice:74`,
  # `rglob("*.feature")`). A co-resident SECOND feature that happens to carry
  # the SAME slice number is then demanded inside the FIRST feature's commit ->
  # the completeness check reports the first feature's commit incomplete,
  # naming the SECOND feature's specification file -> the operator is forced to
  # hold the second feature off-tree to commit the first.
  #
  # OBSERVABLE OUTCOME: a commit for the committing feature is certified
  # complete even when a second feature carrying the same slice number sits
  # beside it on the working tree. The completeness check no longer cross-binds
  # the second feature's specification into the first feature's check.
  #
  # GENUINE INCOMPLETENESS PRESERVED (anti-vacuity guard): a commit that
  # genuinely omits the committing feature's OWN slice specification must STILL
  # be reported incomplete -- scoping the check must not turn it into an
  # always-pass.
  #
  # SINGLE-CERTIFICATION PRESERVED (the seam discriminator): scoping the
  # completeness check must NOT make the gate certify the commit twice. Exactly
  # one certification record must be written for the slice -- the rejected
  # alternative seam (re-using the gate's verify-then-record mode) would run the
  # contract check a second time AND write a DUPLICATE certification record.
  #
  # SUT contract-shape: bounded-change -- the only declared mutation is the
  # feature scope threaded into the completeness check; the universe is the
  # gate's block/allow decision, the completeness verdict it carries, and the
  # certification records written.
  #
  # Driving port (Mandate-13): the real `handle_subagent_stop` SubagentStop
  # hook, driven as a Layer-3 composition/wiring black-box -- the same gate the
  # U2 G_COMMIT exit-gate runs behind in production. The AT never imports the
  # completeness function nor the contract-gate function.
  #
  # Layer 3+ -> example-only (Mandate 9, 11). All three ATs share the ONE
  # E1-scoping contract closure (@coupled): the same indivisible behaviour
  # (scope the completeness check to the committing feature) under three
  # perturbations of the SAME composition root -- cross-feature isolation
  # (AT-A), genuine own-feature incompleteness still caught (AT-B), and the
  # single-certification seam discriminator (AT-C).

  @slice-03 @coupled @walking_skeleton @wiring_e2e @driving_port @real-io @contract-shape:bounded-change
  Scenario: A feature's commit is certified complete though a second feature shares its slice number on the tree
    Given the committing feature has committed its own slice specification
    And a second feature carrying the same slice number sits beside it on the tree
    When the exit gate checks the committing feature's slice commit
    Then the slice commit's completeness check passes
    And the second feature's specification was not demanded in the commit

  @slice-03 @coupled @error @driving_port @real-io @contract-shape:bounded-change
  Scenario: A commit that omits the committing feature's own slice specification is still rejected
    Given the committing feature authored its own slice specification but kept it out of the commit
    And a second feature carrying the same slice number sits beside it on the tree
    When the exit gate checks the committing feature's slice commit
    Then the slice commit's completeness check fails for the committing feature's own missing specification

  @slice-03 @coupled @driving_port @real-io @contract-shape:bounded-change
  Scenario: Scoping the completeness check certifies the verified commit exactly once
    Given the committing feature has committed its own slice specification
    And a second feature carrying the same slice number sits beside it on the tree
    When the exit gate checks the committing feature's slice commit
    Then the slice commit is certified exactly once for the slice
