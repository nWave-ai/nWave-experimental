Feature: Dev Release (Stage 1)
  As Mike, the nwave-dev maintainer,
  I want to tag a set of commits as a dev release on demand
  So that I have an intentional, traceable snapshot without tag spam

  Background:
    Given the nwave-dev repo is on branch master
    And the current version in pyproject.toml is "2.17.6"
    And no existing dev tags for version "2.18.0"
    And all CI checks on HEAD are green

  Scenario: Happy path - first dev release for a new version
    Given Mike triggers workflow_dispatch on release-dev.yml
    And Mike leaves target_version as "auto"
    And Mike leaves dry_run as "false"
    When the pipeline checks CI status on HEAD commit via GitHub API
    Then all check-runs on HEAD are green
    And no tests are re-run inside the release pipeline
    When the pipeline calculates the next version
    Then the dev version is "2.18.0.dev1"
    And the version follows PEP 440 format
    When the pipeline builds dist packages
    Then dist packages (wheel + sdist) are built
    And SHA256 checksums are generated
    When the pipeline creates the git tag
    Then tag "v2.18.0.dev1" exists on nwave-dev
    And a GitHub pre-release is created for "v2.18.0.dev1"
    And Slack receives a success notification with version "2.18.0.dev1"

  Scenario: Sequential dev counter increments correctly
    Given a dev tag "v2.18.0.dev1" already exists
    And a dev tag "v2.18.0.dev2" already exists
    When Mike triggers a new dev release for version "2.18.0"
    Then the dev version is "2.18.0.dev3"
    And tag "v2.18.0.dev3" is created on nwave-dev

  Scenario: Dry run produces no side effects
    Given Mike triggers workflow_dispatch on release-dev.yml
    And Mike sets dry_run to "true"
    When the pipeline checks CI status on HEAD commit via GitHub API
    Then all check-runs on HEAD are green
    When the pipeline calculates the next version
    Then the pipeline reports "Would bump to: 2.18.0.dev1"
    And no git tag is created
    And no GitHub release is created
    And no TestPyPI upload occurs

  Scenario: CI failed on commit prevents tagging
    Given Mike triggers a dev release
    And CI on HEAD commit has a failed check-run
    When the pipeline checks CI status via GitHub API
    Then the pipeline stops with "CI failed on {sha}"
    And no git tag is created
    And no GitHub pre-release is created
    And Slack receives a failure notification mentioning "CI failed"
    And the pipeline exits with a non-zero status

  Scenario: CI still running on commit prevents tagging
    Given Mike triggers a dev release
    And CI on HEAD commit has a pending check-run
    When the pipeline checks CI status via GitHub API
    Then the pipeline stops with "CI still running on {sha}, retry later"
    And no git tag is created
    And no dist packages are built

  Scenario: No CI run found on commit prevents tagging
    Given Mike triggers a dev release
    And HEAD commit has no check-runs registered
    When the pipeline checks CI status via GitHub API
    Then the pipeline stops with "No CI run found for {sha}"
    And no git tag is created
    And no dist packages are built

  Scenario: Optional TestPyPI smoke test
    Given Mike triggers a dev release
    And the pipeline successfully creates tag "v2.18.0.dev1"
    When TestPyPI publish is enabled
    Then the wheel is uploaded to TestPyPI
    And the upload is for smoke-testing mechanics only
    And if TestPyPI upload fails, the dev tag still exists
    And the failure appears as a warning, not a pipeline failure

  Scenario: No conventional commits since last tag
    Given the last tag is "v2.17.6"
    And all commits since then are "chore" or "ci" type
    When Mike triggers a dev release with target_version as "auto"
    Then the pipeline reports "No version bump needed"
    And no tag is created
    And the pipeline exits cleanly with success status
