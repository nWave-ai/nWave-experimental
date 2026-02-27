# Feature: Coexistence Verification
# Based on: architecture-design.md - Roadmap Step 02-02
# Acceptance Criteria:
#   - Install plugin + custom installer simultaneously, verify both work
#   - No duplicate hook registrations
#   - Disable plugin -> custom installer still works; disable installer -> plugin still works
#   - Migration guide documents switchover procedure
# Date: 2026-02-27

Feature: Coexistence Verification and Migration
  As a developer with an existing nWave installation
  I want the plugin and custom installer to coexist without conflicts
  So that I can migrate to the plugin at my own pace

  Background:
    Given the nWave source tree is available
    And a clean output directory for the plugin build
    And default build configuration for the nWave source tree

  # --- Happy Path: Independent Operation ---

  Scenario: Plugin installs to a different location than custom installer
    When the plugin assembler builds the plugin
    Then the plugin target directory differs from the custom installer target directory
    And no files overlap between plugin and custom installer paths

  Scenario: Plugin operates independently when custom installer is absent
    Given only the plugin is installed
    When a user invokes a slash command
    Then the command is discovered from the plugin directory
    And no errors reference missing custom installer files

  Scenario: Custom installer operates independently when plugin is absent
    Given only the custom installer is active
    When a user invokes a slash command
    Then the command is discovered from the custom installer directory
    And no errors reference missing plugin files

  # --- Happy Path: Simultaneous Operation ---

  Scenario: Both plugin and custom installer active without conflicts
    Given the plugin is installed
    And the custom installer is also active
    When a user invokes a slash command
    Then the command executes successfully from one of the two sources

  Scenario: No duplicate hook registrations when both are active
    Given the plugin hook registrations are in the plugin directory
    And the custom installer hook registrations are in the settings file
    When both are active simultaneously
    Then each DES enforcement event is handled by exactly one source
    And no event triggers duplicate enforcement

  # --- Error Paths ---

  Scenario: Conflicting versions between plugin and custom installer are detected
    Given the plugin is version "2.18.0"
    And the custom installer is version "2.17.0"
    When a version consistency check runs
    Then a warning is raised about version mismatch between installation methods

  Scenario: Removing custom installer does not corrupt plugin installation
    Given both plugin and custom installer are active
    When the custom installer is uninstalled
    Then the plugin continues to operate normally
    And no plugin files are affected by the uninstall

  Scenario: Removing plugin does not corrupt custom installer
    Given both plugin and custom installer are active
    When the plugin is removed
    Then the custom installer continues to operate normally
    And no custom installer files are affected by the removal

  # --- Edge Cases ---

  @property
  Scenario: Plugin and custom installer paths never overlap
    Given any valid installation of both plugin and custom installer
    Then the set of files owned by the plugin is disjoint from the set owned by the custom installer
