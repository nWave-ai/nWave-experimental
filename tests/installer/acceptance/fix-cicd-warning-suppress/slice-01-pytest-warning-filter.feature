@feature-fix-cicd-warning-suppress
Feature: pytest warnings filter suppresses PytestUnknownMarkWarning floods for known custom marks

  As a nWave developer running pre-push pytest gates
  I want pytest collection on pytest-bdd test files to emit ZERO PytestUnknownMarkWarning entries for the project's known custom mark namespace
  And I want the captured stdout volume on known-noisy test files to drop by at least 80% versus the pre-fix baseline
  So that the pre-push pytest stdout pipe never fills its buffer (friction #14 BlockingIOError root cause) and so that pre-push wall time recovers the wasted cycles eaten by non-actionable warning noise.

  Background:
    Given the repository carries pytest-bdd acceptance tests under "tests/installer/acceptance/"
    And the project's known custom mark namespace includes "@slice-NN", "@walking_skeleton", "@driving_port", "@real-io", "@contract-shape:*", "@feature-*", "@e2e_smoke", "@fast-path", "@matcher-collision-spike", "@coupled", "@infrastructure", "@partial-failure-tolerance"
    And pytest-bdd auto-converts each Gherkin tag on a scenario into a "pytest.mark.<tag>" object at collection time

  @slice-01 @walking_skeleton @driving_port @real-io @e2e_smoke @contract-shape:absent-warnings
  Scenario: pytest collection on a known-noisy pytest-bdd test file emits zero PytestUnknownMarkWarning entries for the project's known custom marks
    Given a known-noisy pytest-bdd test file at "tests/installer/acceptance/atdd-spine-ledger-enforcement-gate-v2/steps/test_slice_02_pre_tool_use_hook.py" whose scenarios carry tags from the known custom mark namespace
    And the project's "pyproject.toml" declares a pytest warnings filter that suppresses "PytestUnknownMarkWarning" for the known custom mark namespace
    When the developer runs the pytest collection command "pipenv run pytest <known-noisy-file> --collect-only -q"
    Then the captured combined output contains ZERO occurrences of the substring "PytestUnknownMarkWarning"
    And the pytest exit code is zero
    And no warning of class "PytestUnknownMarkWarning" is surfaced for any tag in the known custom mark namespace

  @slice-01 @driving_port @real-io @contract-shape:bounded-output-size
  Scenario: pytest collection on the same known-noisy test file reduces captured stdout line count by at least 80% versus the pre-fix baseline
    Given a known-noisy pytest-bdd test file at "tests/installer/acceptance/atdd-spine-ledger-enforcement-gate-v2/steps/test_slice_02_pre_tool_use_hook.py" whose scenarios carry tags from the known custom mark namespace
    And the project's "pyproject.toml" declares a pytest warnings filter that suppresses "PytestUnknownMarkWarning" for the known custom mark namespace
    When the developer runs the pytest collection command "pipenv run pytest <known-noisy-file> --collect-only -q"
    Then the captured combined output line count is at most 20% of the pre-fix baseline line count for the same command on the same file
    And the captured combined output line count is at most 15 lines
    And the pytest exit code is zero
