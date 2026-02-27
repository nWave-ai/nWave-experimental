# Feature: Plugin Build Walking Skeleton
# Based on: architecture-design.md - Roadmap Step 01-01
# Status: IMPLEMENT FIRST (simplest possible build producing a plugin directory)
# Date: 2026-02-27

Feature: Plugin Build Walking Skeleton
  As a developer distributing nWave
  I want to build a plugin directory from the nWave source tree
  So that I can verify the build pipeline produces a valid plugin before adding complexity

  Background:
    Given the nWave source tree is available
    And a clean output directory for the plugin build

  @walking_skeleton
  Scenario: Simplest plugin build produces a directory with metadata
    Given default build configuration for the nWave source tree
    When the plugin assembler builds the plugin
    Then the plugin directory contains a metadata file with the project version
    And the plugin directory contains at least 1 agent definition
    And the plugin directory contains at least 1 command definition
    And the plugin directory contains at least 1 skill file

  @walking_skeleton
  Scenario: Developer verifies a freshly built plugin is structurally complete
    Given the plugin assembler has produced a plugin directory
    When the plugin validator checks the output
    Then the plugin passes structural validation
    And the validation report confirms all required sections are present

  @walking_skeleton
  Scenario: Built plugin includes DES enforcement hooks
    Given default build configuration for the nWave source tree
    When the plugin assembler builds the plugin
    Then the plugin directory contains hook registrations
    And hook commands reference the plugin root for execution
    And the DES module is importable from the plugin directory
