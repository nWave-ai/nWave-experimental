# Journey: Install Local Candidate (forge:install-local-candidate)
# Designer: Luna (leanux-designer)
# Epic: modern_CLI_installer
# Tags: @horizontal @install @release @local-dev

@horizontal @install @release @local-dev
Feature: Install Local Candidate
  As a developer preparing release or testing installation
  I want to install and validate a locally-built nWave candidate
  So that I can verify the release is ready for CI/CD and PyPI

  Background:
    Given the user has a terminal open
    And the user is in the nWave project root directory
    And Python 3.10+ is installed
    And pipx is installed and in PATH

  # ============================================================================
  # Happy Path - Complete Install Journey
  # ============================================================================

  @happy-path @p0
  Scenario: Successful candidate installation with all checks passing
    Given a wheel exists at "dist/nwave-${version}-py3-none-any.whl"
    And ~/.claude is writable
    When the user runs "forge:install-local-candidate"
    Then the pre-flight checks should run
    And all pre-flight checks should pass with checkmarks
    And the release readiness validation should pass
    And the candidate should be installed via pipx
    And the doctor verification should pass
    And the release report should display
    And the test checklist should be shown

  @happy-path @p0
  Scenario: Release readiness shows all PyPI requirements met
    Given a wheel exists with valid metadata
    And CHANGELOG.md has an entry for ${version}
    When the release readiness validation runs
    Then "twine check" should pass with checkmark
    And "Metadata complete" should pass with checkmark
    And "Entry points" should pass with "nw CLI defined"
    And "CHANGELOG exists" should pass with "Recent entry OK"
    And "Version format" should pass with "PEP 440 valid"
    And "License bundled" should pass with checkmark
    And "README bundled" should pass with checkmark
    And the status should show "READY FOR PYPI"

  @happy-path @p0
  Scenario: Doctor verification matches install-nwave pattern
    Given the candidate has been installed successfully
    When the doctor verification runs
    Then "Core installation" should show ${install_path}
    And "Agent files" should show "${agent_count} OK"
    And "Command files" should show "${command_count} OK"
    And "Template files" should show "${template_count} OK"
    And "Config valid" should show "nwave.yaml OK"
    And "Permissions" should show "All accessible"
    And "Version match" should show ${candidate_version}
    And the status should show "HEALTHY"

  @happy-path @p0
  Scenario: Release report provides complete summary
    Given doctor verification has passed
    When the release report displays
    Then the header should show "FORGE: CANDIDATE INSTALLED"
    And the release summary should show version, branch, timestamps, and size
    And the install manifest should show agent, command, and template counts
    And the release readiness section should show all checks passed
    And the test checklist should list verification steps

  # ============================================================================
  # Pre-flight Checks
  # ============================================================================

  @preflight @p0
  Scenario: Pre-flight validates Python version
    Given the user runs "forge:install-local-candidate"
    When the pre-flight checks run
    Then the Python version check should verify 3.10+
    And the check should display "Python version [check] 3.12.1 (3.10+ OK)"

  @preflight @p0
  Scenario: Pre-flight validates pipx availability
    Given pipx is installed
    When the pre-flight checks run
    Then the pipx check should verify installation
    And the check should display "pipx available [check] v1.4.3 installed"

  @preflight @p0
  Scenario: Pre-flight validates install path writable
    Given ~/.claude directory is writable
    When the pre-flight checks run
    Then the permission check should pass
    And the check should display "~/.claude writable [check] Permissions OK"

  @preflight @p0
  Scenario: Pre-flight validates wheel exists
    Given a wheel exists at "dist/nwave-${version}-py3-none-any.whl"
    When the pre-flight checks run
    Then the wheel existence check should pass
    And the check should display "Wheel exists [check] ${wheel_path}"

  @preflight @p0
  Scenario: Pre-flight validates wheel format
    Given a valid wheel file exists
    When the pre-flight checks run
    Then the wheel format check should pass
    And the check should display "Wheel format [check] Valid .whl"

  # ============================================================================
  # Pre-flight Error Paths - Fixable
  # ============================================================================

  @preflight @error @fixable @p0
  Scenario: Pre-flight offers to build when no wheel found
    Given no wheel exists in dist/
    When the user runs "forge:install-local-candidate"
    Then the pre-flight check should fail for "Wheel exists"
    And the error should display "No wheel found in dist/"
    And the prompt should ask "Run forge:build-local now? [Y/n]"

  @preflight @error @fixable @p0
  Scenario: User accepts auto-chain to build-local
    Given the pre-flight check failed for no wheel
    And the user sees "Run forge:build-local now? [Y/n]"
    When the user types "Y" or presses Enter
    Then forge:build-local should run
    And after successful build, install-local-candidate should resume
    And the message should display "Resuming install-local-candidate..."

  @preflight @error @fixable @p1
  Scenario: User declines auto-chain to build-local
    Given the pre-flight check failed for no wheel
    And the user sees "Run forge:build-local now? [Y/n]"
    When the user types "n"
    Then the install should abort
    And the message should display "Build a wheel first with: forge:build-local"

  @preflight @warning @p1
  Scenario: Pre-flight prompts when multiple wheels found
    Given multiple wheels exist in dist/
    When the user runs "forge:install-local-candidate"
    Then a warning should display "Multiple wheels found in dist/"
    And the list of wheels should be shown with numbers
    And the prompt should ask "Select wheel to install [1-N, or 'c' to cancel]:"

  @preflight @warning @p1
  Scenario: User selects wheel from multiple options
    Given the user sees multiple wheel options
    When the user types "1"
    Then the first wheel should be selected
    And the message should display "Selected: nwave-${version}-py3-none-any.whl"
    And the installation should continue

  # ============================================================================
  # Pre-flight Error Paths - Blocking
  # ============================================================================

  @preflight @error @blocking @p0
  Scenario: Pre-flight fails for missing pipx
    Given pipx is NOT installed
    When the user runs "forge:install-local-candidate"
    Then the pre-flight check should fail for "pipx available"
    And the error should display "pipx not installed"
    And instructions should show "pip install pipx && pipx ensurepath"

  @preflight @error @blocking @p0
  Scenario: Pre-flight fails for Python version too old
    Given the user has Python 3.8 installed
    When the user runs "forge:install-local-candidate"
    Then the pre-flight check should fail for "Python version"
    And the error should display "Python version too old"
    And upgrade suggestions should be provided

  @preflight @error @blocking @p1
  Scenario: Pre-flight fails for permission denied
    Given ~/.claude directory is NOT writable
    When the user runs "forge:install-local-candidate"
    Then the pre-flight check should fail for "~/.claude writable"
    And the error should display "Cannot write to ~/.claude/"
    And permission fix suggestions should be provided
    And NWAVE_INSTALL_PATH alternative should be mentioned

  # ============================================================================
  # Release Readiness Validation
  # ============================================================================

  @release-readiness @p0
  Scenario: Release readiness runs twine check
    Given a wheel exists with complete metadata
    When the release readiness validation runs
    Then twine check should execute against the wheel
    And "twine check" should pass with checkmark

  @release-readiness @p0
  Scenario: Release readiness validates metadata completeness
    Given a wheel exists with all required metadata fields
    When the release readiness validation runs
    Then "Metadata complete" should pass with "All fields set"

  @release-readiness @p0
  Scenario: Release readiness validates entry points
    Given a wheel exists with nw CLI entry point
    When the release readiness validation runs
    Then "Entry points" should pass with "nw CLI defined"

  @release-readiness @p0
  Scenario: Release readiness validates version format
    Given a wheel exists with PEP 440 compliant version
    When the release readiness validation runs
    Then "Version format" should pass with "PEP 440 valid"

  @release-readiness @p0
  Scenario: Release readiness validates license bundled
    Given a wheel exists with LICENSE file included
    When the release readiness validation runs
    Then "License bundled" should pass with "LICENSE in wheel"

  @release-readiness @p0
  Scenario: Release readiness validates README bundled
    Given a wheel exists with README.md included
    When the release readiness validation runs
    Then "README bundled" should pass with "README.md OK"

  # ============================================================================
  # Release Readiness - Warnings
  # ============================================================================

  @release-readiness @warning @p1
  Scenario: Release readiness warns for missing CHANGELOG entry
    Given a wheel exists with valid metadata
    And CHANGELOG.md has NO entry for ${version}
    When the release readiness validation runs
    Then "CHANGELOG exists" should show warning with "No recent entry"
    And the status should show "WARNINGS (non-blocking)"
    And the prompt should ask "Continue anyway? [Y/n]"

  @release-readiness @warning @p1
  Scenario: User continues despite CHANGELOG warning
    Given the CHANGELOG warning is displayed
    When the user types "Y" or presses Enter
    Then the installation should continue
    And the warning should be noted in the release report

  # ============================================================================
  # Release Readiness - Errors
  # ============================================================================

  @release-readiness @error @blocking @p0
  Scenario: Release readiness fails for invalid wheel
    Given a wheel exists with invalid metadata
    When the release readiness validation runs
    Then "twine check" should fail with "Invalid metadata"
    And the status should show "FAILED"
    And fix instructions should mention pyproject.toml

  @release-readiness @error @blocking @p1
  Scenario: Release readiness fails for missing description
    Given a wheel exists without description metadata
    When the release readiness validation runs
    Then "twine check" should fail
    And the error should show "Missing required metadata: description"
    And the fix should suggest adding [project.description]

  # ============================================================================
  # Install Candidate
  # ============================================================================

  @install @p0
  Scenario: Install shows progress phases
    Given release readiness has passed
    When the install process runs
    Then a phase table should display
    And the phase "Uninstalling previous" should show progress then checkmark
    And the phase "Installing from wheel" should show progress bar
    And the phase "Symlinking nw" should show checkmark when complete
    And the install duration should be displayed

  @install @p0
  Scenario: Install removes previous installation first
    Given a previous version of nwave is installed
    When the install process runs
    Then "Uninstalling previous" should show "Removed"
    And the new version should be installed

  @install @p0
  Scenario: Install uses pipx with force flag
    Given release readiness has passed
    When the install process runs
    Then the command should be "pipx install ${wheel_path} --force"
    And the --force flag ensures replacement of existing install

  @install @p0
  Scenario: Install verifies nw command is available
    Given the wheel has been installed
    When the symlink verification runs
    Then "which nw" should return a valid path
    And "Symlinking nw" should show "Available"

  # ============================================================================
  # Install - Errors
  # ============================================================================

  @install @error @blocking @p0
  Scenario: Install fails due to dependency conflict
    Given release readiness has passed
    When the install process runs
    And a dependency version conflict occurs
    Then the phase "Installing from wheel" should show failure
    And the error should display the dependency issue
    And suggested fixes should be provided

  @install @error @blocking @p1
  Scenario: Install fails but nw not in PATH
    Given the wheel has been installed
    But nw is not in PATH
    Then the phase "Symlinking nw" should show failure
    And instructions should show "pipx ensurepath"

  # ============================================================================
  # Doctor Verification
  # ============================================================================

  @doctor @p0
  Scenario: Doctor verifies core installation
    Given the candidate has been installed
    When the doctor verification runs
    Then "Core installation" should verify ${install_path} exists

  @doctor @p0
  Scenario: Doctor verifies agent files installed
    Given the candidate has been installed
    When the doctor verification runs
    Then "Agent files" should count files in ${install_path}/agents/
    And the count should match the wheel bundled count

  @doctor @p0
  Scenario: Doctor verifies command files installed
    Given the candidate has been installed
    When the doctor verification runs
    Then "Command files" should count files in appropriate location
    And the count should match the wheel bundled count

  @doctor @p0
  Scenario: Doctor verifies template files installed
    Given the candidate has been installed
    When the doctor verification runs
    Then "Template files" should count files in appropriate location
    And the count should match the wheel bundled count

  @doctor @p0
  Scenario: Doctor verifies config is valid
    Given the candidate has been installed
    When the doctor verification runs
    Then "Config valid" should verify nwave.yaml parses correctly

  @doctor @p0
  Scenario: Doctor verifies version matches wheel
    Given the candidate has been installed
    When the doctor verification runs
    Then "Version match" should verify "nw --version" output
    And the output should match ${candidate_version}

  @doctor @p0
  Scenario: Doctor shows nw version output
    Given the candidate has been installed
    When the doctor verification runs
    Then the nw --version output should be displayed
    And it should show "nWave Framework v${candidate_version}"
    And it should show "Candidate: ${branch}-${date}-${sequence}"
    And it should show "Installed: ${install_path}"

  # ============================================================================
  # Doctor - Errors
  # ============================================================================

  @doctor @error @blocking @p0
  Scenario: Doctor fails for missing agents
    Given the candidate has been installed
    But agent files were not copied to ~/.claude
    When the doctor verification runs
    Then "Agent files" should show failure with "0 found"
    And the status should show "UNHEALTHY"
    And repair instructions should be provided

  @doctor @error @blocking @p1
  Scenario: Doctor fails for version mismatch
    Given the candidate has been installed
    But "nw --version" shows a different version
    When the doctor verification runs
    Then "Version match" should show failure
    And the wheel version vs installed version should be shown
    And reinstall instructions should be provided

  # ============================================================================
  # Release Report
  # ============================================================================

  @report @p0
  Scenario: Release report shows release summary
    Given doctor verification has passed
    When the release report displays
    Then the release summary should show:
      | Field       | Value                    |
      | Version     | ${candidate_version}     |
      | Branch      | ${branch}                |
      | Built       | ${build_timestamp}       |
      | Installed   | ${install_timestamp}     |
      | Size        | ${wheel_size}            |

  @report @p0
  Scenario: Release report shows install manifest
    Given doctor verification has passed
    When the release report displays
    Then the install manifest should show:
      | Component | Count              |
      | Agents    | ${agent_count}     |
      | Commands  | ${command_count}   |
      | Templates | ${template_count}  |
      | Location  | ${install_path}    |

  @report @p0
  Scenario: Release report shows all checks passed
    Given doctor verification has passed
    When the release report displays
    Then the release readiness section should show all checkmarks
    And "twine check" should show "Passed"
    And "Doctor" should show "HEALTHY"

  @report @p0
  Scenario: Release report includes test checklist
    Given doctor verification has passed
    When the release report displays
    Then the test checklist should include:
      | Step                                    |
      | Restart Claude Code (Cmd+Q then reopen) |
      | Run: /nw:version                        |
      | Run: /nw:help                           |
      | Test an agent: /nw:product-owner        |
      | Run: nw doctor                          |

  @report @p0
  Scenario: Release report shows next steps
    Given doctor verification has passed
    When the release report displays
    Then local testing instructions should be shown
    And CI/CD readiness confirmation should be shown
    And the release command should show "twine upload dist/nwave-${version}-py3-none-any.whl"
    And the documentation URL should be displayed

  # ============================================================================
  # Shared Artifact Consistency
  # ============================================================================

  @integration @horizontal @p0
  Scenario: Candidate version is consistent across all steps
    Given forge:install-local-candidate has completed successfully
    Then the version in release readiness should be "${candidate_version}"
    And the version in doctor verification should be "${candidate_version}"
    And the version in release report should be "${candidate_version}"
    And all versions should match the wheel filename

  @integration @horizontal @p0
  Scenario: Agent count is consistent across doctor and report
    Given forge:install-local-candidate has completed successfully
    Then ${agent_count} in doctor should match ${agent_count} in report
    And ${agent_count} should match actual files in ${install_path}

  @integration @horizontal @p0
  Scenario: Install path is consistent across doctor and report
    Given forge:install-local-candidate has completed successfully
    Then ${install_path} in doctor should match ${install_path} in report
    And ${install_path} should be a valid directory

  # ============================================================================
  # Cross-Journey Integration
  # ============================================================================

  @integration @cross-journey @p0
  Scenario: forge:install-local-candidate consumes wheel from build-local
    Given forge:build-local has completed with wheel at ${wheel_path}
    When the user runs "forge:install-local-candidate"
    Then the wheel from forge:build-local should be detected
    And the same version should be used throughout

  @integration @cross-journey @p0
  Scenario: Doctor verification matches install-nwave pattern
    Given forge:install-local-candidate doctor verification runs
    Then the checks should match install-nwave Step 5
    And the health check format should be identical
    And the component list should be identical

  @integration @cross-journey @p1
  Scenario: Auto-chain from install to build works seamlessly
    Given no wheel exists in dist/
    And the user runs "forge:install-local-candidate"
    And accepts the prompt to run forge:build-local
    When forge:build-local completes successfully
    Then forge:install-local-candidate should resume automatically
    And the newly built wheel should be installed

  # ============================================================================
  # Use Case Scenarios
  # ============================================================================

  @use-case @p0
  Scenario: Developer missed install prompt during build
    Given the developer declined install during forge:build-local
    And a wheel exists from the previous build
    When the developer runs "forge:install-local-candidate"
    Then the existing wheel should be detected
    And the full installation and verification should complete
    And the release report should be generated

  @use-case @p0
  Scenario: Developer performs full release rehearsal
    Given the developer wants to simulate CI/CD release
    When the developer runs "forge:install-local-candidate"
    Then all release readiness checks should run
    And twine check should validate PyPI compatibility
    And the release report should confirm CI/CD readiness

  @use-case @p1
  Scenario: Developer fixes installation issues
    Given the developer is debugging installation problems
    When the developer runs "forge:install-local-candidate" repeatedly
    Then each run should provide detailed doctor diagnostics
    And error messages should guide troubleshooting
    And the developer can iterate without rebuilding

  @use-case @p1
  Scenario: Developer iterates on release scripts
    Given the developer is improving release automation
    When the developer runs "forge:install-local-candidate" after script changes
    Then the installation should use the existing wheel
    And the developer can verify release script behavior
    And no rebuild is required

  @use-case @p1
  Scenario: Developer validates release artifacts
    Given the developer is preparing a release
    When the developer runs "forge:install-local-candidate"
    Then the release readiness section should show all requirements
    And any missing artifacts (CHANGELOG, LICENSE) should be flagged
    And the developer knows exactly what CI/CD will check

  # ============================================================================
  # Candidate Version Format
  # ============================================================================

  @version @p0
  Scenario: Candidate version follows correct format
    Given a wheel has been built with base version "1.3.0"
    And the date is "2026-02-01"
    And this is the first build today
    When the version is displayed
    Then it should follow format "M.m.p-dev-YYYYMMDD-seq"
    And an example would be "1.3.0-dev-20260201-001"

  @version @p0
  Scenario: Candidate version is PEP 440 compliant
    Given a candidate version is generated
    When validated against PEP 440
    Then it should be a valid dev release identifier
    And twine check should accept it

  @version @p1
  Scenario: Daily sequence increments correctly
    Given a wheel was already built today with sequence "001"
    When a new wheel is built
    Then the sequence should be "002"
    And the version should be "1.3.0-dev-${date}-002"

  # ============================================================================
  # Emotional Journey Validation
  # ============================================================================

  @ux @emotional @p1
  Scenario: User feels confident throughout installation
    Given the user starts installation feeling "focused"
    When the installation progresses
    Then the user should feel "trust" during release readiness
    And the user should feel "anticipation" during install
    And the user should feel "satisfaction" after install completes
    And the user should feel "trust" during doctor verification
    And the user should feel "celebratory" at release report
    And the user should feel "guided" at next steps

  # ============================================================================
  # CI/CD Mode
  # ============================================================================

  @ci @p1
  Scenario: Install works in non-interactive CI mode
    Given the environment variable CI=true is set
    And a wheel exists in dist/
    When the user runs "forge:install-local-candidate"
    Then no interactive prompts should appear
    And the installation should complete automatically
    And exit code should be 0 on success

  @ci @p1
  Scenario: Install with --json flag outputs machine-readable report
    Given a wheel exists in dist/
    When the user runs "forge:install-local-candidate --json"
    Then the output should be valid JSON
    And it should include release_summary, install_manifest, and release_readiness
    And CI/CD can parse the output

  @ci @p1
  Scenario: Install with --strict fails on any warnings
    Given a wheel exists without CHANGELOG entry
    When the user runs "forge:install-local-candidate --strict"
    Then the CHANGELOG warning should become a failure
    And the installation should abort
    And exit code should be non-zero

  @ci @p1
  Scenario: Install writes release report to file
    Given a wheel exists in dist/
    When the user runs "forge:install-local-candidate --output release-report.md"
    Then the release report should be written to release-report.md
    And CI/CD can archive the report as an artifact
