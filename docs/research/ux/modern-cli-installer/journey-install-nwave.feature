# Journey: Install nWave for the First Time
# Designer: Luna (leanux-designer)
# Epic: modern_CLI_installer
# Tags: @horizontal @e2e @installation

@horizontal @e2e @installation
Feature: Install nWave for the First Time
  As a developer who saw an nWave demo
  I want to install nWave with a single command
  So that I can start using it in Claude Code immediately

  Background:
    Given the user has a terminal open
    And the user has Python 3.10+ installed
    And the user has Claude Code installed

  # Happy Path - Complete Journey
  @happy-path @p0
  Scenario: Successful first-time installation
    Given the user has pipx installed
    When the user runs "pipx install nwave"
    Then the download progress bar should appear
    And the version "${version}" from pyproject.toml should be displayed
    And the pre-flight checks should run
    And all pre-flight checks should pass with green checkmarks
    And the doctor verification should run automatically
    And the doctor should show "HEALTHY" status
    And the ASCII logo should be displayed
    And the welcome message should show "nWave v${version} installed successfully!"
    And the user should see "IMPORTANT: Restart Claude Code to activate"
    And the next steps should include "/nw:version"

  @happy-path @p0
  Scenario: Verify installation in Claude Code
    Given nWave has been installed successfully
    And the user has restarted Claude Code
    When the user types "/nw:version" in Claude Code
    Then the version should match "${version}" from the installation
    And the install path should match "~/.claude/agents/nw/"
    And the agent count should match the doctor output

  # Pre-flight Checks
  @preflight @p0
  Scenario: Pre-flight check validates Python version
    Given the user runs the installer
    When the pre-flight checks run
    Then the Python version check should verify 3.10+
    And the check should display "✓ Python version" with the actual version

  @preflight @p0
  Scenario: Pre-flight check validates pipx isolation
    Given the user runs the installer
    When the pre-flight checks run
    Then the pipx isolation check should verify isolated environment
    And the check should display "✓ pipx isolation"

  @preflight @p0
  Scenario: Pre-flight check validates write permissions
    Given the user runs the installer
    When the pre-flight checks run
    Then the permissions check should verify "~/.claude/" is writable
    And the check should display "✓ Write permissions"

  @preflight @p1
  Scenario: Pre-flight check detects Claude Code
    Given the user runs the installer
    When the pre-flight checks run
    Then the Claude Code check should verify installation
    And the check should display "✓ Claude Code" with the path

  # Error Paths
  @error @p0
  Scenario: pipx not installed
    Given the user does NOT have pipx installed
    When the user runs "pipx install nwave"
    Then the error message should display "✗ pipx not found"
    And the message should include "Install it first:"
    And the message should include "pip install pipx"
    And the message should include "pipx ensurepath"

  @error @p0
  Scenario: Python version too old
    Given the user has Python 3.8 installed
    When the user runs "pipx install nwave"
    Then the error message should display "Python 3.10+ required"
    And the message should show the current Python version
    And the message should suggest upgrade options

  @error @p1
  Scenario: Permission denied on install path
    Given the user does NOT have write permission to "~/.claude/"
    When the pre-flight checks run
    Then the error should display "✗ Write permissions"
    And the message should include how to fix permissions

  @error @p1
  Scenario: Claude Code not found
    Given the user does NOT have Claude Code installed
    When the pre-flight checks run
    Then the warning should display "Claude Code not found"
    And the message should include the installation URL

  # Step 4: Framework Installation
  @happy-path @p0
  Scenario: Framework installation shows progress bars
    Given pre-flight checks have passed
    When the framework installation begins
    Then a spinner should appear for "Checking source files"
    And a progress bar should appear for "Building distribution"
    And the backup creation should show "✅ Backup created at ${backup_path}"
    And progress bars should show for Agents, Commands, Templates installation
    And each component should show a count and ✅ when complete

  @happy-path @p0
  Scenario: Backup is created before installation
    Given an existing nWave installation exists
    When the framework installation begins
    Then a backup should be created at "${backup_path}"
    And the backup should contain agents, commands, and manifest
    And the backup path should include a timestamp

  @happy-path @p0
  Scenario: Installation validation shows component counts
    Given all components have been installed
    When the installation validation runs
    Then a validation table should display
    And the table should show "🤖 Agents ✅ ${agent_count}"
    And the table should show "⚡ Commands ✅ ${command_count}"
    And the table should show "📋 Templates ✅ ${template_count}"
    And the table should show "📜 Manifest ✅ Created"
    And the final status should show "✨ Validation: PASSED"

  @integration @horizontal
  Scenario: Component counts are consistent across Steps 4, 5, and 7
    Given nWave has been installed successfully
    Then ${agent_count} in Step 4 validation should match Step 5 doctor
    And ${agent_count} in Step 5 doctor should match Step 7 /nw:version
    And ${command_count} should be consistent across Steps 4, 5, 7
    And ${template_count} should be consistent across Steps 4, 5, 7

  # Configurable Install Path
  @config @p0
  Scenario: Install path resolution uses default when no override
    Given NWAVE_INSTALL_PATH is not set
    And config/installer.yaml does not specify install_dir
    When the installer resolves the install path
    Then the install path should be "~/.claude/agents/nw/"
    And the pre-flight output should show "Using default: ~/.claude/agents/nw/"

  @config @p0
  Scenario: Install path respects environment variable override
    Given NWAVE_INSTALL_PATH is set to "~/my-claude/agents/nw/"
    When the installer resolves the install path
    Then the install path should be "~/my-claude/agents/nw/"
    And the pre-flight output should show "NWAVE_INSTALL_PATH=~/my-claude/agents/nw/"
    And all subsequent paths should use the custom location

  @config @p1
  Scenario: Install path uses config file when env var not set
    Given NWAVE_INSTALL_PATH is not set
    And config/installer.yaml has paths.install_dir = "~/custom-claude/"
    When the installer resolves the install path
    Then the install path should be "~/custom-claude/"

  @config @p1
  Scenario: Environment variable takes precedence over config file
    Given NWAVE_INSTALL_PATH is set to "~/env-path/"
    And config/installer.yaml has paths.install_dir = "~/config-path/"
    When the installer resolves the install path
    Then the install path should be "~/env-path/"
    And the env var should take precedence

  # Shared Artifact Consistency
  @integration @horizontal
  Scenario: Version is consistent across all displays
    Given nWave has been installed successfully
    Then the version in the download progress should be "${version}"
    And the version in the welcome message should be "${version}"
    And the version in "/nw:version" should be "${version}"
    And all versions should match pyproject.toml

  @integration @horizontal
  Scenario: Install path is consistent across all displays
    Given nWave has been installed successfully
    Then the install path in pre-flight should be "~/.claude/agents/nw/"
    And the install path in doctor should be "~/.claude/agents/nw/"
    And the install path in "/nw:version" should be "~/.claude/agents/nw/"

  @integration @horizontal
  Scenario: Agent count is consistent across displays
    Given nWave has been installed successfully
    Then the agent count in doctor should match actual files
    And the agent count in "/nw:version" should match doctor output

  # Emotional Journey Validation
  @ux @emotional
  Scenario: User feels confident throughout installation
    Given the user starts installation feeling "excited"
    When the installation progresses
    Then the user should feel "anticipation" during download
    And the user should feel "confidence" during pre-flight checks
    And the user should feel "trust" during doctor verification
    And the user should feel "delighted" at the welcome message

  # Non-Interactive Mode (CI/CD)
  @ci @p0
  Scenario: Installation works in non-interactive mode
    Given the environment variable CI=true is set
    When the user runs "pipx install nwave"
    Then no interactive prompts should appear
    And the installation should complete silently
    And exit code should be 0 on success

  @ci @p0
  Scenario: Machine-readable output in CI mode
    Given the environment variable CI=true is set
    And the flag "--format json" is used
    When the user runs "pipx install nwave --format json"
    Then the output should be valid JSON
    And the JSON should include "success": true
    And the JSON should include "version": "${version}"
