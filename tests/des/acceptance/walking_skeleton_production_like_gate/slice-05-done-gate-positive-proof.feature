@feature-walking-skeleton-production-like-gate
Feature: Marking a feature done requires positive verification, not marker-absence
  As an nWave framework developer
  I want the done-gate to require a positive walking-skeleton verification
    record, so hand-removing a deferral marker cannot unblock done
  So that "feature done" rests on proof-of-verification, not absence-of-block

  # carpaccio slice-05 (DESIGN slice-03, part 2 of 3). RM-3 trust inversion:
  # the done-gate trusts PRESENCE of a positive WalkingSkeletonTierVerified
  # record, not ABSENCE of a marker -- a hand-`rm` of the marker cannot unblock
  # done because the positive record was never written. Parse-error of a marker
  # defaults to the safe side (RM-3 ST-20); a green run of a stale artifact
  # cannot clear a newer marker (RM-3 ST-26). Layer 3 (subprocess / FS
  # acceptance): real composition root, example-only, no PBT (Mandate 9/11).
  #
  # Driving port: `des.cli.walking_skeleton_done_gate`.

  # RM-3 ST-17 -- presence-of-proof, not absence-of-block.
  @slice-05 @driving_port @error @contract-shape:bounded-change
  Scenario: Hand-removing the deferral marker does not unblock feature done
    Given a feature carries a walking-skeleton-unverified marker
    And the marker has been removed by hand without any verification record being written
    When the done-gate evaluates whether the feature can be marked done
    Then the done-gate refuses because no positive walking-skeleton verification record exists
    And the feature remains not marked done

  # RM-3 ST-20 -- parse-error defaults to the safe side. Parametrize-collapse:
  # the done-gate's verdict over the three marker read-states.
  @slice-05 @driving_port @contract-shape:bounded-change
  Scenario Outline: The done-gate verdict over each marker read-state
    Given a feature whose deferral marker directory holds <marker_state>
    And a positive walking-skeleton verification record exists for the feature
    When the done-gate evaluates whether the feature can be marked done
    Then the done-gate verdict is <done_allowed>

    Examples: marker-absent allows done; present or unparseable blocks
      | marker_state          | done_allowed |
      | no marker             | allowed      |
      | an unverified marker  | blocked      |
      | an unparseable marker | blocked      |

  # RM-3 ST-26 -- a green run of a stale artifact cannot clear a newer marker.
  @slice-05 @driving_port @error @contract-shape:bounded-change
  Scenario: A green run of a stale artifact cannot clear a marker written for a later fix
    Given a feature carries a walking-skeleton-unverified marker bound to a later artifact hash
    When a downstream verification runs green against an older artifact
    Then the marker is not cleared because the verified artifact does not match the marker
    And the feature remains not marked done
