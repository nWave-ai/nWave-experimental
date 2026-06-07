@feature-walking-skeleton-production-like-gate
Feature: A green downstream verification clears the deferral and unblocks done
  As an nWave framework developer who deferred a verification to CI
  I want a green downstream walking-skeleton run of the bound artifact to clear
    the marker and write the positive verification record
  So that a deferred feature can reach done once CI has verified it

  # carpaccio slice-06 (DESIGN slice-03, part 3 of 3). The deferral lifecycle
  # completes: a green downstream verification of the bound artifact clears the
  # marker AND writes the positive record, so the done-gate then allows done.
  # Layer 3 (subprocess / FS acceptance): real composition root, example-only,
  # no PBT (Mandate 9/11). State-mutating steps assert via assert_state_delta
  # over a port-exposed marker+ledger universe (Mandate 8).
  #
  # Driving port: `des.cli.walking_skeleton_gate` (the downstream verification).

  @slice-06 @driving_port @contract-shape:bounded-change
  Scenario: A green downstream verification of the bound artifact clears the marker
    Given a feature carries a walking-skeleton-unverified marker bound to an artifact hash
    When a downstream verification runs green against the bound artifact
    Then the marker is cleared and a positive walking-skeleton verification record is written
    And the feature can be marked done
