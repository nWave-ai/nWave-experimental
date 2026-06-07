# Feature: Stale Artifact Cleanup During Update
# Based on: docs/analysis/rca-stale-nw-colon-commands-windows.md
# Proves: installer plugins remove stale artifacts from previous versions
# Date: 2026-04-01

Feature: Stale artifact cleanup during nWave update
  As a user updating nWave to a new version
  I want outdated files from previous versions removed automatically
  So that I see only current commands, templates, and scripts without confusion

  # ── Walking Skeleton ────────────────────────────────────────────────

  @walking_skeleton @acceptance @install-cleanup
  Scenario: User updates and old hierarchical command files are removed
    Given the user has legacy commands installed in the "commands/nw/" directory
    And the legacy directory contains "deliver.md" and "design.md" command files
    And the current version installs commands as skills

    When the user runs the nWave installer
    Then the legacy "commands/nw/" directory no longer exists
    And the installer reports successful cleanup of legacy commands

  # ── Stale Command Cleanup ───────────────────────────────────────────

  @acceptance @install-cleanup
  Scenario: Installer removes commands that no longer exist in the current version
    Given the user has a skills directory with stale command "nw-old-removed-command"
    And the current version does not include "nw-old-removed-command"

    When the skills plugin installs the current command set
    Then "nw-old-removed-command" is no longer present in the skills directory
    And only commands from the current version remain installed

  # ── Template Cleanup ────────────────────────────────────────────────

  @acceptance @install-cleanup
  Scenario: Installer removes stale template files not in the current version
    Given the user has a templates directory with "old-workflow-template.yaml" from a previous version
    And the current version does not ship "old-workflow-template.yaml"

    When the templates plugin installs the current template set
    Then "old-workflow-template.yaml" is no longer present in the templates directory
    And only templates from the current version remain installed

  # ── Agent Cleanup ────────────────────────────────────────────────────

  @acceptance @install-cleanup
  Scenario: Installer removes stale agent definitions not in current version
    Given the user has an agents directory with "nw-old-retired-agent.md" from a previous version
    And the current version does not include "nw-old-retired-agent.md"

    When the agents plugin installs the current agent set
    Then "nw-old-retired-agent.md" is no longer present in the agents directory
    And only agent definitions from the current version remain installed

  # ── Utility Script Cleanup ──────────────────────────────────────────

  @acceptance @install-cleanup
  Scenario: Installer removes stale utility scripts not in the current set of distributed scripts
    Given the user has a scripts directory with "legacy_migration_helper.py" from a previous version
    And the current set of distributed scripts does not include "legacy_migration_helper.py"

    When the utilities plugin installs the current script set
    Then "legacy_migration_helper.py" is no longer present in the scripts directory
    And only utility scripts from the current set of distributed scripts remain installed

  # ── Idempotency ─────────────────────────────────────────────────────

  @acceptance @install-cleanup @property
  Scenario: First install succeeds with expected files
    Given the user has a clean installation directory
    And the current version includes 2 skills and 1 template

    When the user runs the nWave installer
    Then the installer reports success for all plugins
    And the expected skills and templates are installed

  @acceptance @install-cleanup @property
  Scenario: Second install produces identical result to the first
    Given the user has a clean installation directory
    And the current version includes 2 skills and 1 template
    And a previous install has already completed successfully

    When the user runs the nWave installer
    Then the installed files are identical to the previous install
    And no duplicate files or directories exist

  # ── Cross-Installation Detection ────────────────────────────────────

  @acceptance @install-cleanup
  Scenario: Installer warns when plugin-format commands coexist with CLI commands
    Given the user has CLI-installed commands in the skills directory as "nw-deliver"
    And the user also has a plugin-installed "nw" plugin active

    When the user runs the nWave installer
    Then the installer warns about conflicting command sources
    And the warning recommends removing one installation method

  # ── Infrastructure Failure ──────────────────────────────────────────

  @acceptance @install-cleanup @infrastructure-failure
  Scenario: Cleanup handles read-only stale files gracefully
    Given the user has a stale template file "old-config.yaml" that is read-only
    And the current version does not ship "old-config.yaml"

    When the templates plugin attempts to clean up stale files
    Then the installer reports the cleanup failure with a clear message
    And the installation continues without crashing

  @acceptance @install-cleanup @infrastructure-failure
  Scenario: Cleanup handles missing target directory gracefully
    Given the user has never installed nWave before
    And no commands, templates, or scripts directories exist

    When the user runs the nWave installer for the first time
    Then the installer creates the necessary directories
    And the installation completes successfully without cleanup errors
