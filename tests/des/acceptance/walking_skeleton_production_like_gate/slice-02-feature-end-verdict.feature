@feature-walking-skeleton-production-like-gate
Feature: The feature-end cycle acts on the walking-skeleton gate verdict
  As an nWave framework developer
  I want the feature-end cycle to proceed on a green gate and block on a red one
  So that a broken installed artifact cannot reach a done state

  # carpaccio slice-02 (DESIGN slice-02, part 1 of 2). The feature-end DES
  # SubagentStop branch invokes the gate; a PASS proceeds, a FAIL or a
  # missing-walking-skeleton-AT blocks. Layer 3 (subprocess / FS acceptance):
  # real composition root, example-only, no PBT (Mandate 9/11). State-mutating
  # steps assert via assert_state_delta over a port-exposed ledger universe
  # (Mandate 8).
  #
  # Driving port: the DES feature-end SubagentStop hook branch.

  @slice-02 @driving_port @contract-shape:bounded-change
  Scenario: A green gate run lets feature-end proceed
    Given a feature that ships a packaged CLI module with a passing walking-skeleton acceptance test
    When the feature-end cycle reaches the walking-skeleton gate
    Then the walking-skeleton gate reports PASS at tier of record T1
    And the feature-end cycle records a positive walking-skeleton verification
    And feature-end proceeds

  @slice-02 @driving_port @error @contract-shape:bounded-change
  Scenario: A red gate run blocks feature-end
    Given a feature that ships a packaged CLI module with a failing walking-skeleton acceptance test
    When the feature-end cycle reaches the walking-skeleton gate
    Then the walking-skeleton gate reports FAIL at tier of record T1
    And the feature is not marked done

  @slice-02 @driving_port @error @contract-shape:bounded-change
  Scenario: A feature shipping a CLI with no walking-skeleton test is blocked
    Given a feature that ships a packaged CLI module with no walking-skeleton acceptance test
    When the feature-end cycle reaches the walking-skeleton gate
    Then the walking-skeleton gate reports FAIL at tier of record T1
    And the gate diagnostic states no walking-skeleton test exists for an installer-shipped feature
    And the feature is not marked done
