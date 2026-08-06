@activation_gating @driving_port @auto-marking
Feature: nWave silently adopts a project on its first real agent dispatch

  A brand-new project's first real agent dispatch adopts the project and lets
  that dispatch proceed. A deliberate opt-out remains sticky.

  Background:
    Given the global activation mode is "OPT_IN"
    And the nested ignore banner is present
    And the root ignore file uses the "SLASH_TRAILING" variant

  @contract-shape:bounded-change
  Scenario: A brand-new project's first agent dispatch adopts it and proceeds
    Given the project marker is "ABSENT"
    When an nWave agent is dispatched in this project
    Then the project is adopted and the agent dispatch proceeds
    And the project marker is written

  @contract-shape:unbounded-preservation
  Scenario: A deliberate opt-out survives a real agent dispatch
    Given the project marker is "DISABLED"
    When an nWave agent is dispatched in this project
    Then the marker still reflects the deliberate opt-out
