@feature-walking-skeleton-production-like-gate
Feature: The gate verifies the artifact at the highest available environment tier
  As an nWave framework developer
  I want the gate to escalate to a container tier when Docker is present, with
    the clean-prefix tier always running first
  So that an OS-level packaging bug is caught at the highest fidelity available

  # carpaccio slice-07 (DESIGN slice-04, part 1 of 3). T2 escalation: when the
  # environment reports Docker, the gate runs the walking-skeleton AT inside a
  # clean container image and records T2 as the tier of record, the
  # clean-prefix tier always running first as its floor. RM-4 records a
  # tier-debt when a clean-prefix-only run lands on an OS-sensitive feature.
  # Layer 3 (subprocess / FS acceptance): real composition root over a stubbed
  # EnvironmentProbe (Docker is non-deterministic -- fake per the infra
  # policy). Example-only, no PBT (Mandate 9/11).
  #
  # Driving port: `des.cli.walking_skeleton_gate`.

  @slice-07 @driving_port @contract-shape:bounded-change
  Scenario: Docker present escalates the gate to the container tier
    Given a feature that ships a packaged CLI module with a walking-skeleton acceptance test
    And the environment reports Docker available
    When the feature-end gate verifies the walking skeleton with the container tier requested
    Then the walking-skeleton gate reports PASS at tier of record T2
    And the gate ran the prerequisite first tier before the container tier

  @slice-07 @driving_port @error @contract-shape:bounded-change
  Scenario: The container tier catches an OS-level bug the first tier missed
    Given a feature whose walking-skeleton acceptance test passes at the first tier
    And the artifact relies on a path layout that does not resolve on the container's operating system
    And the environment reports Docker available
    When the feature-end gate verifies the walking skeleton with the container tier requested
    Then the walking-skeleton gate reports FAIL at tier of record T2
    And the feature is not marked done

  # RM-4 -- the T1->T2 escalation gap becomes a recorded debt. Parametrize-
  # collapse: the gate's tier-debt decision over the OS-sensitivity axis.
  @slice-07 @driving_port @contract-shape:bounded-change
  Scenario Outline: A first-tier-only run records a tier debt only when OS fidelity is owed
    Given a feature that ships a packaged CLI module with a walking-skeleton acceptance test
    And the feature is classified as <os_sensitivity>
    And the environment reports only Python and pip
    When the feature-end gate verifies the walking skeleton
    Then the walking-skeleton gate reports PASS at tier of record T1
    And the gate <tier_debt_outcome>

    Examples: OS-sensitive features owe a tracked container-tier debt
      | os_sensitivity | tier_debt_outcome                          |
      | OS-sensitive   | writes a walking-skeleton tier-debt record |
      | OS-neutral     | writes no tier-debt record                 |
