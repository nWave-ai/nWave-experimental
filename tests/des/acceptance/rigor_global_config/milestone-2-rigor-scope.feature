Feature: Rigor profile scope selection
  As a developer who sets rigor preferences
  I want to choose whether my rigor profile saves globally or for this project only
  So that I can have a personal default that follows me while still overriding per-project

  The /nw:rigor command is a markdown file executed by the main Claude instance.
  These tests verify the CONFIG WRITE RESULT -- the file contents after a save operation --
  not the interactive flow itself.

  Background:
    Given a temporary project directory exists
    And a temporary global configuration directory exists

  # --- Happy Path: Global scope writes ---

  Scenario: Global scope writes rigor to the global config file
    Given the global config file does not exist yet
    When rigor profile "custom" with agent model "opus" is saved with scope "global"
    Then the global config file contains rigor profile "custom"
    And the global config file contains agent model "opus"
    And the project config rigor key is unchanged

  Scenario: Project scope writes rigor to the project config file
    Given the project config has no rigor key
    When rigor profile "lean" with agent model "haiku" is saved with scope "project"
    Then the project config contains rigor profile "lean"
    And the project config contains agent model "haiku"
    And the global config file is not modified

  # --- Read-modify-write preserves other keys ---

  Scenario: Global save preserves existing non-rigor keys in global config
    Given the global config file has an update check frequency of "weekly"
    When rigor profile "standard" is saved with scope "global"
    Then the global config file contains rigor profile "standard"
    And the global config file still has update check frequency "weekly"

  Scenario: Project save preserves existing non-rigor keys in project config
    Given the project config has audit logging enabled
    When rigor profile "thorough" is saved with scope "project"
    Then the project config contains rigor profile "thorough"
    And the project config still has audit logging enabled

  # --- Directory creation ---

  Scenario: Global config directory created automatically on first global save
    Given the global config directory does not exist
    When rigor profile "custom" with agent model "opus" is saved with scope "global"
    Then the global config directory is created
    And the global config file contains rigor profile "custom"

  # --- Error paths ---

  Scenario: Global save overwrites previous global rigor profile
    Given the global config has rigor profile "standard"
    When rigor profile "exhaustive" with agent model "opus" is saved with scope "global"
    Then the global config file contains rigor profile "exhaustive"
    And the global config file contains agent model "opus"

  Scenario: Save succeeds when global config file contains corrupt data
    Given the global config file contains invalid content
    When rigor profile "standard" is saved with scope "global"
    Then the global config file contains rigor profile "standard"

  Scenario: Corrupt global config file is replaced with valid structure on save
    Given the global config file contains invalid content
    When rigor profile "standard" is saved with scope "global"
    Then the global config file is valid
    And the global config file contains rigor profile "standard"
