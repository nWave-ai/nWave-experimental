@feature-walking-skeleton-production-like-gate
Feature: An owed container-tier verification is tracked until CI settles it
  As an nWave framework developer without a local container runtime
  I want an open tier debt to block done and a downstream container-tier run
    to settle it
  So that "the container tier silently didn't run" is a tracked record, not
    silence

  # carpaccio slice-08 (DESIGN slice-04, part 2 of 3). RM-4: the tier-debt
  # lifecycle. The done-gate blocks an unsettled tier-debt on an OS-sensitive
  # feature; a downstream container-tier run settles it. RM-9: feature-end
  # defers the container tier to CI by default even when Docker is present
  # locally, tracked via the tier-debt record. Layer 3 (subprocess / FS
  # acceptance): real composition root, example-only, no PBT (Mandate 9/11).
  # State-mutating steps assert via assert_state_delta over a port-exposed
  # tier+marker universe (Mandate 8).
  #
  # Driving port: `des.cli.walking_skeleton_gate` + `walking_skeleton_done_gate`.

  @slice-08 @driving_port @error @contract-shape:bounded-change
  Scenario: An OS-sensitive feature with an open tier debt cannot be marked done
    Given an OS-sensitive feature carries an open walking-skeleton tier-debt record
    When the done-gate evaluates whether the feature can be marked done
    Then the done-gate refuses because the container-tier debt is unsettled
    And the feature remains not marked done

  @slice-08 @driving_port @contract-shape:bounded-change
  Scenario: A downstream container-tier run settles the tier debt
    Given an OS-sensitive feature carries an open walking-skeleton tier-debt record
    When a downstream verification runs the walking skeleton green at the container tier
    Then the tier-debt record is cleared
    And the feature can be marked done

  # RM-9 -- feature-end stays fast: T2 is deferred to CI by default even when
  # Docker is present locally, tracked via the tier-debt record.
  @slice-08 @driving_port @contract-shape:bounded-change
  Scenario: Feature-end defers the container tier to CI by default
    Given an OS-sensitive feature carries an open walking-skeleton tier-debt record
    When the feature-end gate verifies the walking skeleton without an explicit tier request
    Then the walking-skeleton gate reports PASS at tier of record T1
    And the gate writes a walking-skeleton tier-debt record for the container tier to settle
