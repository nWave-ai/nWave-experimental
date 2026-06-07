Feature: Global configuration handling during uninstall
  As a developer who has configured global rigor preferences
  I want to choose whether to keep or delete my global config during uninstall
  So that my preferences survive a reinstall cycle without being silently lost

  Background:
    Given a temporary home directory for uninstall testing
    And a temporary project with nWave installed

  # --- Happy Path: Prompt and choices ---

  Scenario: User keeps global config during uninstall
    Given the global config file exists with rigor profile "custom"
    When the uninstaller runs and the user chooses to keep global config
    Then the global config file is preserved with rigor profile "custom"
    And the rest of the uninstall completes normally

  Scenario: User deletes global config during uninstall
    Given the global config file exists with rigor profile "custom"
    When the uninstaller runs and the user chooses to delete global config
    Then the global config file no longer exists
    And the rest of the uninstall completes normally

  Scenario: Empty global config directory is cleaned up after file deletion
    Given the global config file is the only file in the global config directory
    When the uninstaller runs and the user chooses to delete global config
    Then the global config file no longer exists
    And the global config directory is removed

  Scenario: Global config directory preserved when it contains other files
    Given the global config file exists with rigor profile "custom"
    And the global config directory contains other files
    When the uninstaller runs and the user chooses to delete global config
    Then the global config file no longer exists
    And the global config directory still exists

  # --- No global config: no prompt ---

  Scenario: No global config file -- uninstall proceeds without prompt
    Given no global config file exists
    When the uninstaller runs
    Then no prompt about global configuration is shown
    And the uninstall completes normally

  # --- Force mode ---

  Scenario: Force mode preserves global config without prompting
    Given the global config file exists with rigor profile "custom"
    When the uninstaller runs with force mode enabled
    Then the global config file is preserved with rigor profile "custom"
    And no prompt about global configuration is shown

  # --- Dry-run mode ---

  Scenario: Dry-run mode reports global config status without modifying files
    Given the global config file exists with rigor profile "custom"
    When the uninstaller runs in dry-run mode
    Then the global config file is preserved with rigor profile "custom"
    And the dry-run output mentions global configuration
