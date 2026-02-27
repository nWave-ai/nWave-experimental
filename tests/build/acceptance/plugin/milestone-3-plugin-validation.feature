# Feature: Plugin Validation and Build Verification
# Based on: architecture-design.md - Roadmap Step 01-03
# Acceptance Criteria:
#   - Build fails if any expected component is missing
#   - hooks.json validates against expected schema
#   - Plugin structure matches Claude Code plugin spec
# Date: 2026-02-27

Feature: Plugin Validation and Build Verification
  As a developer distributing nWave
  I want the build pipeline to validate the plugin before distribution
  So that only structurally correct plugins reach users

  Background:
    Given the nWave source tree is available
    And a clean output directory for the plugin build
    And default build configuration for the nWave source tree

  # --- Happy Path: Structural Validation ---

  @milestone_3
  Scenario: Valid plugin passes all structural checks
    Given the plugin assembler has produced a plugin directory
    When the plugin validator checks the output
    Then the validation result is success
    And no validation errors are reported

  @milestone_3
  Scenario: Validation confirms all required plugin sections exist
    Given the plugin assembler has produced a plugin directory
    When the plugin validator checks the output
    Then the validation report confirms agents section is present
    And the validation report confirms skills section is present
    And the validation report confirms commands section is present
    And the validation report confirms hooks section is present
    And the validation report confirms metadata section is present

  @milestone_3
  Scenario: Validation confirms hook configuration is well-formed
    Given the plugin assembler has produced a plugin directory
    When the plugin validator checks the output
    Then the hook configuration is valid according to the expected schema
    And every hook entry has a command and event type

  # --- Happy Path: Completeness Verification ---

  @milestone_3
  Scenario: Validation counts match expected component totals
    Given the plugin assembler has produced a plugin directory
    When the plugin validator checks the output
    Then the validation report shows 23 agents
    And the validation report shows at least 98 skill files
    And the validation report shows at least 21 command files

  # --- Error Paths ---

  @milestone_3
  Scenario: Validation fails when metadata file is missing
    Given a plugin directory without a metadata file
    When the plugin validator checks the output
    Then the validation result is failure
    And the validation error mentions missing metadata

  @milestone_3
  Scenario: Validation fails when agents directory is empty
    Given a plugin directory with an empty agents section
    When the plugin validator checks the output
    Then the validation result is failure
    And the validation error mentions missing agents

  @milestone_3
  Scenario: Validation fails when hooks configuration is missing
    Given a plugin directory without hook registrations
    When the plugin validator checks the output
    Then the validation result is failure
    And the validation error mentions missing hooks

  @milestone_3
  Scenario: Validation fails when DES module is absent
    Given a plugin directory without the DES enforcement module
    When the plugin validator checks the output
    Then the validation result is failure
    And the validation error mentions missing DES module

  @milestone_3
  Scenario: Validation reports all errors at once rather than stopping at first
    Given a plugin directory missing metadata, agents, and hooks
    When the plugin validator checks the output
    Then the validation result is failure
    And the validation error list contains at least 3 distinct errors

  # --- Edge Cases ---

  @milestone_3
  Scenario: Validation succeeds with minimum viable plugin
    Given a plugin directory with exactly 1 agent, 1 skill, 1 command, and valid hooks
    When the plugin validator checks the output
    Then the validation result is success

  @property
  Scenario: Validation is a pure function with no side effects
    Given any plugin directory state
    When the plugin validator checks the output twice
    Then both validation results are identical
    And the plugin directory is unchanged after validation
