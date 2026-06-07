@feature-fix-reverify-p4-tracked-before-fallback @walking_skeleton @wiring_e2e @driving_port @real-io
@contract-shape:pure-function
Feature: P4 recovers a carpaccio-split orphan
  As an operator re-verifying an orphaned carpaccio slice
  I want the reverify precondition to accept a slice whose acceptance test
  was committed earlier than its production code
  So that the canonical carpaccio-split orphan becomes recoverable instead
  of being permanently stuck.

  # AT-presence state machine (feature-delta DESIGN Contract table):
  #   in-commit ........................ accept (existing behaviour)
  #   tracked-before-unmodified ......... accept  <-- this slice
  #   never-authored .................... refuse  (slice-02)
  #   tag-dropped-by-commit ............. refuse  (slice-02)
  # Driving port: des.cli.reverify_slice_commit.main(argv) against a real
  # temp-git repo. P4 is a pure-function verdict (reads git, returns a verdict).

  @slice-01
  Scenario: An orphan whose acceptance test was committed before its code is recovered
    Given a buried slice whose acceptance test is tracked-before-unmodified
    When the operator re-verifies the slice
    Then the slice's acceptance-test presence is accepted
    And the slice is recorded as verified in the completion ledger
