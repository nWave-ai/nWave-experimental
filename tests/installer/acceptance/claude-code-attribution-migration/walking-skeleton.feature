@attribution @real-io @driving_port
Feature: Fresh installation records the enabled preference
  As an nWave developer
  I want a fresh installation to record that I want the nWave credit
  So that I have no legacy hooks and my preference is captured

  @walking_skeleton @contract-shape:bounded-change
  Scenario: Fresh install records enabled preference and leaves no legacy hook
    Given a developer machine in the fresh state
    When the developer installs nWave
    Then the enabled attribution preference is recorded
    And no legacy commit hook is left on the machine
