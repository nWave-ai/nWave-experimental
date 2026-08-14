@activation_gating @driving_port @hook-gate
Feature: nWave hooks run only in active projects and never block an inactive one

  A single gate sits at the one place every hook is dispatched. In an inactive
  project the gate allows the hook through without running any nWave logic and
  without ever blocking. In an active project the hook is dispatched to its
  handler as before. The gate never activates a project: only the explicit
  project-enable command owns that decision. The gate is transparent to
  handlers: the original hook input reaches the handler intact.

  Background:
    Given the global activation mode is "OPT_IN"

  @contract-shape:unbounded-preservation
  Scenario: An inactive project lets a hook pass without blocking
    Given the project marker is "ABSENT"
    When a "PRE_TOOL_USE" hook fires
    Then the hook is allowed without blocking
    And the gate never blocks the hook

  @contract-shape:unbounded-preservation
  Scenario: An agent dispatch cannot silently activate an inactive project
    Given the project marker is "ABSENT"
    When an nWave agent is dispatched in this project
    Then the hook is allowed without blocking
    And the gate never blocks the hook
    And the project state is unchanged

  @contract-shape:bounded-change
  Scenario: An active project dispatches its hook to the handler
    Given the project marker is "ENABLED"
    When a "PRE_TOOL_USE" hook fires
    Then the hook is dispatched to its handler

  @contract-shape:unbounded-preservation
  Scenario: The handler reads the same hook input the gate received
    Given the project marker is "ENABLED"
    When a "PRE_TOOL_USE" hook fires
    Then the handler receives the original hook input intact
