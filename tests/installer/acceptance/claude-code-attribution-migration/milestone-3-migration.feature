@attribution @real-io @driving_port
Feature: Upgrading dismantles the old commit hook
  As an nWave developer with the legacy hook installed
  I want the upgrade to retire the old hook and record the enabled preference
  So that I am never left with competing credit mechanisms or stale artifacts

  @error @contract-shape:bounded-change
  Scenario: Installing over a legacy hook retires it and enables the credit
    Given a developer machine in the legacy_hook state
    When the developer installs nWave
    Then the legacy commit hook is dismantled
    And the enabled attribution preference is recorded instead
