# Journey: Build nWave Local Candidate (forge:build-local-candidate)
# Designer: Luna (leanux-designer)
# Epic: modern_CLI_installer
# Tags: @horizontal @build @local-dev

@horizontal @build @local-dev
Feature: Build nWave Local Candidate
  As a developer modifying or extending nWave
  I want to build a pipx-compatible candidate wheel with semantic versioning
  So that I can test my changes locally before releasing

  # Version Strategy:
  # - Bumps version using conventional commits OR --force-version
  # - Creates candidate: M.m.p-dev-YYYYMMDD-seq
  # - Example: 1.2.0 → 1.3.0-dev-20260201-001 → ... → 1.3.0-dev-20260201-005
  # - Final release (1.3.0) happens via CI/CD on main branch

  Background:
    Given the user has a terminal open
    And the user is in the nWave project root directory
    And Python 3.10+ is installed

  # ============================================================================
  # Happy Path - Complete Build Journey
  # ============================================================================

  @happy-path @p0
  Scenario: Successful local build with all checks passing
    Given the user has the build package installed
    And pyproject.toml is valid with version "${version}"
    And the nWave/ source directory exists
    When the user runs "forge:build-local-candidate"
    Then the pre-flight checks should run
    And all pre-flight checks should pass with checkmarks
    And the build process should show progress phases
    And the wheel validation should pass
    And the success summary should display
    And the wheel should be created at "dist/nwave-${candidate_version}-py3-none-any.whl"
    And the user should be prompted "Install locally now? [Y/n]"

  @happy-path @p0
  Scenario: User accepts prompted local install
    Given a successful build has completed
    And the user sees "Install locally now? [Y/n]"
    When the user types "Y" or presses Enter
    Then the install command should run "pipx install ${wheel_path} --force"
    And the forge:install-local-candidate journey should continue

  @happy-path @p1
  Scenario: User declines prompted local install
    Given a successful build has completed
    And the user sees "Install locally now? [Y/n]"
    When the user types "n"
    Then the manual install command should be displayed
    And the command should be "pipx install ${wheel_path} --force"
    And the development mode alternative should be shown
    And the docs URL should be displayed

  # ============================================================================
  # Pre-flight Checks
  # ============================================================================

  @preflight @p0
  Scenario: Pre-flight check validates Python version
    Given the user runs "forge:build-local-candidate"
    When the pre-flight checks run
    Then the Python version check should verify 3.10+
    And the check should display "Python version [check] 3.12.1 (3.10+ OK)"

  @preflight @p0
  Scenario: Pre-flight check validates build package
    Given the user has the build package installed
    When the pre-flight checks run
    Then the build package check should verify installation
    And the check should display "build package [check] v1.2.1 installed"

  @preflight @p0
  Scenario: Pre-flight check validates pyproject.toml
    Given pyproject.toml exists and is valid
    When the pre-flight checks run
    Then the pyproject.toml check should pass
    And the check should display "pyproject.toml [check] Valid, v${version}"

  @preflight @p0
  Scenario: Pre-flight check validates source directory
    Given the nWave/ source directory exists
    When the pre-flight checks run
    Then the source directory check should pass
    And the check should display "Source directory [check] nWave/ found"

  @preflight @p0
  Scenario: Pre-flight check validates dist directory
    Given the dist/ directory is writable
    When the pre-flight checks run
    Then the dist directory check should pass
    And the check should display "dist/ directory [check] Writable"

  # ============================================================================
  # Pre-flight Error Paths - Fixable
  # ============================================================================

  @preflight @error @fixable @p0
  Scenario: Pre-flight auto-repair for missing build package
    Given the user does NOT have the build package installed
    When the user runs "forge:build-local-candidate"
    Then the pre-flight check should fail for "build package"
    And the error should display "Pre-flight check failed: build package missing"
    And the prompt should ask "Install it now? [Y/n]"

  @preflight @error @fixable @p0
  Scenario: User accepts auto-repair for missing build package
    Given the pre-flight check failed for missing build package
    And the user sees "Install it now? [Y/n]"
    When the user types "Y" or presses Enter
    Then the installer should run "pip install build"
    And a spinner should show "Installing build package..."
    And the message should display "build v1.2.1 installed successfully"
    And pre-flight checks should resume

  @preflight @error @fixable @p1
  Scenario: User declines auto-repair for missing build package
    Given the pre-flight check failed for missing build package
    And the user sees "Install it now? [Y/n]"
    When the user types "n"
    Then the build should abort
    And the message should display "Build cancelled. Install build package manually:"
    And the command should show "pip install build"

  # ============================================================================
  # Pre-flight Error Paths - Blocking
  # ============================================================================

  @preflight @error @blocking @p0
  Scenario: Pre-flight fails for Python version too old
    Given the user has Python 3.8 installed
    When the user runs "forge:build-local-candidate"
    Then the pre-flight check should fail for "Python version"
    And the error should display "Python version too old"
    And the message should show "Required: Python 3.10+"
    And the message should show "Found: Python 3.8.10"
    And upgrade suggestions should be provided

  @preflight @error @blocking @p0
  Scenario: Pre-flight fails for missing pyproject.toml
    Given pyproject.toml does NOT exist
    When the user runs "forge:build-local-candidate"
    Then the pre-flight check should fail
    And the error should display "pyproject.toml not found"
    And the message should show "forge:build-local-candidate must be run from the nWave project root directory"
    And the current directory should be displayed

  @preflight @error @blocking @p0
  Scenario: Pre-flight fails for invalid pyproject.toml
    Given pyproject.toml has a syntax error on line 42
    When the user runs "forge:build-local-candidate"
    Then the pre-flight check should fail for "pyproject.toml"
    And the error should display "pyproject.toml invalid"
    And the error should show "Error at line 42: ${error_message}"
    And the relevant line should be highlighted

  @preflight @error @blocking @p1
  Scenario: Pre-flight fails for missing source directory
    Given the nWave/ source directory does NOT exist
    When the user runs "forge:build-local-candidate"
    Then the pre-flight check should fail for "Source directory"
    And the error should display "nWave/ directory not found"

  @preflight @error @blocking @p1
  Scenario: Pre-flight fails for permission denied on dist
    Given the dist/ directory is NOT writable
    When the user runs "forge:build-local-candidate"
    Then the pre-flight check should fail for "dist/ directory"
    And the error should display "Cannot write to dist/ directory"
    And permission fix suggestions should be provided

  # ============================================================================
  # Version Bumping
  # ============================================================================

  @versioning @p0
  Scenario: Version bump from conventional commits
    Given pre-flight checks have passed
    And the current version in pyproject.toml is "${base_version}"
    And there are commits with "feat:" prefix since last tag
    When the version resolution runs
    Then the bump type should be "MINOR"
    And the new version should be higher than "${base_version}"
    And the candidate version should follow format "M.m.p-dev-YYYYMMDD-seq"

  @versioning @p0
  Scenario: Version bump detects breaking changes
    Given pre-flight checks have passed
    And there are commits with "BREAKING CHANGE:" since last tag
    When the version resolution runs
    Then the bump type should be "MAJOR"
    And the major version should be incremented

  @versioning @p0
  Scenario: Version bump detects fix commits
    Given pre-flight checks have passed
    And there are only commits with "fix:" prefix since last tag
    When the version resolution runs
    Then the bump type should be "PATCH"
    And only the patch version should be incremented

  @versioning @p0
  Scenario: Force version override
    Given pre-flight checks have passed
    And the current version is "1.2.0"
    When the user runs "forge:build-local-candidate --force-version 2.0.0"
    Then the new version should be "2.0.0"
    And the candidate version should be "2.0.0-dev-${date}-001"

  @versioning @error @p0
  Scenario: Force version rejected when too low
    Given pre-flight checks have passed
    And the current version is "1.3.0"
    When the user runs "forge:build-local-candidate --force-version 1.2.0"
    Then the error should display "Force version rejected"
    And the message should show "Force version must be higher than current"

  @versioning @p1
  Scenario: Daily sequence increments on same day
    Given a candidate "1.3.0-dev-20260201-001" was built earlier today
    When the user runs "forge:build-local-candidate" again
    Then the candidate version should be "1.3.0-dev-20260201-002"

  @versioning @warning @p1
  Scenario: Warning when no commits since last tag
    Given pre-flight checks have passed
    And there are no commits since the last tag
    When the version resolution runs
    Then a warning should display "No commits since last tag"
    And the build should proceed with the current version as candidate

  # ============================================================================
  # Build Process
  # ============================================================================

  @build @p0
  Scenario: Build process shows progress phases
    Given pre-flight checks have passed
    When the build process runs
    Then a phase table should display
    And the phase "Cleaning dist/" should show progress then checkmark
    And the phase "Processing source" should show file count
    And the phase "Running build backend" should show progress bar
    And all phases should complete with checkmarks
    And the build duration should be displayed

  @build @p0
  Scenario: Build cleans old wheel files
    Given pre-flight checks have passed
    And an old wheel exists at "dist/nwave-2.0.0-py3-none-any.whl"
    When the build process runs
    Then the old wheel should be removed
    And the phase should show "Cleaning dist/ [check] Removed old"

  @build @error @p0
  Scenario: Build fails due to backend error
    Given pre-flight checks have passed
    When the build process runs
    And the build backend encounters an error
    Then the phase "Running build backend" should show failure
    And the error message should be displayed
    And a suggested fix should be provided
    And the build should abort

  @build @warning @p1
  Scenario: Build warns about existing wheel with same version
    Given pre-flight checks have passed
    And a wheel exists at "dist/nwave-${candidate_version}-py3-none-any.whl"
    When the build process starts
    Then a warning should display "Existing wheel found with same version"
    And the existing wheel timestamp should be shown
    And the prompt should ask "Overwrite existing wheel? [Y/n]"

  @build @warning @p1
  Scenario: User accepts overwriting existing wheel
    Given the warning about existing wheel is displayed
    When the user types "Y" or presses Enter
    Then the old wheel should be removed
    And the build should continue

  # ============================================================================
  # Wheel Validation
  # ============================================================================

  @validation @p0
  Scenario: Wheel validation checks all required aspects
    Given a wheel has been built successfully
    When the wheel validation runs
    Then the wheel filename should be displayed
    And the validation table should show all checks
    And "Wheel format" should pass with checkmark
    And "Metadata present" should pass with checkmark
    And "Entry points" should pass with "nw CLI defined"
    And "Agents bundled" should pass with "${agent_count}"
    And "Commands bundled" should pass with "${command_count}"
    And "Templates bundled" should pass with "${template_count}"
    And "pipx compatible" should pass with "Verified"
    And the final status should show "Wheel validation passed!"

  @validation @p0
  Scenario: Wheel validation verifies bundled content counts
    Given a wheel has been built successfully
    When the wheel validation runs
    Then ${agent_count} should match the source nWave/agents/ count
    And ${command_count} should match the source count
    And ${template_count} should match the source count

  # ============================================================================
  # Success Summary
  # ============================================================================

  @summary @p0
  Scenario: Success summary displays complete information
    Given wheel validation has passed
    When the success summary displays
    Then the header should show "FORGE: BUILD COMPLETE"
    And the celebration message should show "nWave v${version} wheel built successfully!"
    And the artifact table should show wheel path, size, and timestamp
    And the contents table should show agent, command, and template counts

  @summary @p0
  Scenario: Success summary shows correct wheel path
    Given wheel validation has passed
    When the success summary displays
    Then the wheel path should be "dist/nwave-${candidate_version}-py3-none-any.whl"
    And the wheel file should exist at that path

  # ============================================================================
  # Install Prompt Flow
  # ============================================================================

  @prompt @p0
  Scenario: Install prompt shows after successful build
    Given the success summary has displayed
    When the prompt appears
    Then the message should show "Test this wheel locally?"
    And the description should explain what will happen
    And the prompt should ask "Install locally now? [Y/n]"
    And the default should be "Y"

  @prompt @p0
  Scenario: Accepting install prompt triggers pipx install
    Given the install prompt is displayed
    When the user accepts with "Y"
    Then a spinner should show "Installing wheel locally..."
    And the command should be "pipx install ${wheel_path} --force"
    And the --force flag ensures replacement of existing install

  @prompt @p1
  Scenario: Declining install prompt shows manual instructions
    Given the install prompt is displayed
    When the user declines with "n"
    Then the manual install command should be displayed
    And the development mode command "pip install -e ." should be shown
    And the documentation URL should be displayed

  # ============================================================================
  # Shared Artifact Consistency
  # ============================================================================

  @integration @horizontal @p0
  Scenario: Version is consistent across all steps
    Given forge:build-local-candidate has completed successfully
    Then the version in pre-flight should be "${version}"
    And the version in wheel filename should be "${version}"
    And the version in summary should be "${version}"
    And the version in install prompt should be "${version}"
    And all versions should match pyproject.toml

  @integration @horizontal @p0
  Scenario: Agent count is consistent across validation and summary
    Given forge:build-local-candidate has completed successfully
    Then ${agent_count} in validation should match ${agent_count} in summary
    And ${agent_count} should match actual files bundled in wheel

  @integration @horizontal @p0
  Scenario: Wheel path is consistent across summary and install prompt
    Given forge:build-local-candidate has completed successfully
    Then ${wheel_path} in summary should match ${wheel_path} in install prompt
    And ${wheel_path} should point to an existing file

  # ============================================================================
  # Cross-Journey Integration
  # ============================================================================

  @integration @cross-journey @p0
  Scenario: forge:build-local-candidate hands off to install-local correctly
    Given forge:build-local-candidate has completed successfully
    And the user accepts the install prompt
    When the handoff to install-local occurs
    Then ${wheel_path} should be passed to install-local
    And the install flow should use the local wheel instead of PyPI
    And the rest of the forge:install-local-candidate journey should proceed

  @integration @cross-journey @p1
  Scenario: Local wheel install matches PyPI install experience
    Given a local wheel has been built
    When the user installs via "pipx install ${wheel_path} --force"
    Then the installation experience should match "pipx install nwave"
    And the same pre-flight checks should run
    And the same doctor verification should run
    And the same celebration should display

  # ============================================================================
  # Use Case Scenarios
  # ============================================================================

  @use-case @p0
  Scenario: Developer verifies build after code changes
    Given the developer has modified files in nWave/agents/
    When the developer runs "forge:build-local-candidate"
    Then the build should complete successfully
    And the modified agents should be bundled in the wheel
    And the developer can test the changes locally

  @use-case @p0
  Scenario: Developer performs pre-release validation
    Given the developer is preparing a PR or release
    When the developer runs "forge:build-local-candidate"
    Then all pre-flight checks should pass
    And the wheel should be valid
    And the developer has confidence the release will work

  @use-case @p1
  Scenario: Developer tests custom agents in installed context
    Given the developer has added custom agents to nWave/agents/
    When the developer runs "forge:build-local-candidate"
    And accepts the install prompt
    Then the custom agents should be available in Claude Code
    And the agents should work as if installed from PyPI

  @use-case @p1
  Scenario: Developer validates updated dependencies
    Given the developer has updated dependencies in pyproject.toml
    When the developer runs "forge:build-local-candidate"
    Then the build should verify dependencies resolve correctly
    And the wheel should include all required dependencies
    And the developer knows the dependencies work together

  # ============================================================================
  # Emotional Journey Validation
  # ============================================================================

  @ux @emotional @p1
  Scenario: User feels confident throughout build process
    Given the user starts build feeling "focused"
    When the build progresses
    Then the user should feel "confident" after pre-flight passes
    And the user should feel "anticipation" during build progress
    And the user should feel "trust" during validation
    And the user should feel "accomplished" at success summary
    And the user should feel "guided" at install prompt

  # ============================================================================
  # CI/CD Mode
  # ============================================================================

  @ci @p1
  Scenario: Build works in non-interactive CI mode
    Given the environment variable CI=true is set
    When the user runs "forge:build-local-candidate"
    Then no interactive prompts should appear
    And the install prompt should be skipped
    And the build should complete silently
    And exit code should be 0 on success

  @ci @p1
  Scenario: Build with --no-prompt flag skips install prompt
    Given the user wants to build without being prompted
    When the user runs "forge:build-local-candidate --no-prompt"
    Then the build should complete normally
    And the install prompt should be skipped
    And the wheel path should be printed for scripting

  @ci @p1
  Scenario: Build with --install flag auto-installs
    Given the user wants to build and install in one command
    When the user runs "forge:build-local-candidate --install"
    Then the build should complete normally
    And the install should proceed automatically without prompting
    And the full forge:install-local-candidate flow should complete
