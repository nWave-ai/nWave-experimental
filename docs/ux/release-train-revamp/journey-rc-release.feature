Feature: RC Release / Promote to Beta (Stage 2)
  As Mike, the nwave-dev maintainer,
  I want to promote a validated dev release to RC status
  So that beta testers can exercise it via standard pip tooling on production PyPI

  Background:
    Given the nwave-dev repo has tag "v1.1.22.dev3"
    And the commit behind "v1.1.22.dev3" is "abc123d"
    And no existing RC tags for version "1.1.22"
    And the nWave-beta repo exists at nwave-ai/nWave-beta
    And Trusted Publisher (OIDC) is configured for PyPI

  Scenario: Happy path - promote dev to first RC
    Given Mike triggers workflow_dispatch on release-rc.yml
    And Mike sets source_dev_tag to "v1.1.22.dev3"
    When the pipeline validates the source tag
    Then commit "abc123d" is checked out
    When the pipeline checks CI status on commit "abc123d" via GitHub API
    Then all check-runs on "abc123d" are green
    And no tests are re-run inside the release pipeline
    When the pipeline calculates the RC version
    Then the RC version is "1.1.22rc1"
    When the pipeline builds from commit "abc123d"
    Then dist packages are built from the same source as dev3
    When the pipeline creates the RC tag
    Then tag "v1.1.22rc1" exists on nwave-dev
    And a GitHub pre-release is created for "v1.1.22rc1"
    When the pipeline publishes to PyPI
    Then "nwave-ai" version "1.1.22rc1" is available on production PyPI
    And the package has a pre-release marker
    And "pip install nwave-ai" does NOT install this version
    And "pip install --pre nwave-ai" does install this version
    When the pipeline syncs to nWave-beta
    Then the nWave-beta repo is updated with source code
    And the nWave-beta commit message contains "Source: nwave-dev@abc123d"
    And the nWave-beta commit message contains "Dev tag: v1.1.22.dev3"
    And tag "v1.1.22rc1" exists on nWave-beta
    And a GitHub pre-release is created on nWave-beta
    And Slack receives a success notification with RC install instructions

  Scenario: Dry run validates all logic but produces no side effects
    Given Mike triggers workflow_dispatch on release-rc.yml
    And Mike sets source_dev_tag to "v1.1.22.dev3"
    And Mike sets dry_run to "true"
    When the pipeline validates the source tag
    Then commit "abc123d" is checked out
    When the pipeline checks CI status on commit "abc123d" via GitHub API
    Then all check-runs on "abc123d" are green
    When the pipeline calculates the RC version
    Then the RC version is calculated as "1.1.22rc1"
    When the pipeline builds dist packages
    Then dist packages (wheel + sdist) are built
    When the pipeline composes the traceability commit message
    Then the message contains "Source: nwave-dev@abc123d"
    And the message contains "Dev tag: v1.1.22.dev3"
    And the pipeline reports "Would have: tagged v1.1.22rc1, published 1.1.22rc1 to PyPI, synced to nWave-beta"
    And no RC tag is created on nwave-dev
    And no GitHub pre-release is created
    And no package is published to PyPI
    And no sync to nWave-beta occurs
    And no Slack notification is sent

  Scenario: Sequential RC counter increments correctly
    Given an RC tag "v1.1.22rc1" already exists
    When Mike triggers RC promotion from "v1.1.22.dev5"
    Then the RC version is "1.1.22rc2"
    And tag "v1.1.22rc2" is created

  Scenario: Source dev tag does not exist
    Given Mike triggers RC promotion with source_dev_tag "v1.1.22.dev99"
    And tag "v1.1.22.dev99" does not exist
    When the pipeline validates the source tag
    Then the pipeline fails with "Tag v1.1.22.dev99 not found"
    And the error message lists available dev tags: "v1.1.22.dev1, v1.1.22.dev2, v1.1.22.dev3"
    And no RC tag is created
    And nothing is published to PyPI

  Scenario: CI failed on source commit blocks RC promotion
    Given Mike triggers RC promotion from "v1.1.22.dev3"
    And the commit behind "v1.1.22.dev3" has a failed CI check-run
    When the pipeline checks CI status via GitHub API
    Then the pipeline fails with "CI failed on abc123d"
    And no RC tag is created
    And nothing is published to PyPI

  Scenario: CI still running on source commit blocks RC promotion
    Given Mike triggers RC promotion from "v1.1.22.dev3"
    And the commit behind "v1.1.22.dev3" has a pending CI check-run
    When the pipeline checks CI status via GitHub API
    Then the pipeline fails with "CI still running on abc123d, retry later"
    And no RC tag is created

  Scenario: No CI run found on source commit blocks RC promotion
    Given Mike triggers RC promotion from "v1.1.22.dev3"
    And the commit behind "v1.1.22.dev3" has no check-runs registered
    When the pipeline checks CI status via GitHub API
    Then the pipeline fails with "No CI run found for abc123d"
    And no RC tag is created

  Scenario: PyPI version collision
    Given "nwave-ai" version "1.1.22rc1" already exists on PyPI
    When the pipeline attempts to publish "1.1.22rc1"
    Then the pipeline logs a warning "v1.1.22rc1 already on PyPI"
    And the pipeline continues with nWave-beta sync
    And the overall status is success with warnings

  Scenario: OIDC token acquisition fails
    Given Trusted Publisher is not configured for this workflow
    When the pipeline attempts to publish to PyPI
    Then the pipeline fails with "Trusted Publisher not configured"
    And the RC tag on nwave-dev still exists
    And no sync to nWave-beta occurs
    And Slack receives a failure notification

  Scenario: Beta tester installs RC from PyPI
    Given "nwave-ai" version "1.1.22rc1" is published on production PyPI
    When a beta tester runs "pip install --pre nwave-ai==1.1.22rc1"
    Then nwave-ai 1.1.22rc1 is installed successfully
    And "nwave-ai version" shows "1.1.22rc1"

  Scenario: Cross-repo traceability is complete
    Given the RC promotion from "v1.1.22.dev3" completed successfully
    When inspecting the nWave-beta commit for "v1.1.22rc1"
    Then the commit message contains the source nwave-dev commit SHA
    And the commit message contains the source dev tag
    And the commit message contains the pipeline run URL
