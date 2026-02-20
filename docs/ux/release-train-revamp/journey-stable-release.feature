Feature: Stable Release (Stage 3)
  As Mike, the nwave-dev maintainer,
  I want to promote a validated RC to stable status
  So that the public gets a tested release via standard pip install

  Background:
    Given the nwave-dev repo has tag "v2.18.0rc1"
    And the commit behind "v2.18.0rc1" is "abc123d"
    And the nWave public repo exists at nwave-ai/nwave
    And the current nwave-ai version on the public repo is "1.1.5"
    And the public_version floor in pyproject.toml is "1.1.0"
    And Trusted Publisher (OIDC) is configured for PyPI

  Scenario: Happy path - promote RC to stable
    Given Mike triggers workflow_dispatch on release-prod.yml
    And Mike sets source_rc_tag to "v2.18.0rc1"
    When the pipeline validates the source RC tag
    Then commit "abc123d" is checked out
    And the stable version is "2.18.0"
    When the pipeline checks CI status on commit "abc123d" via GitHub API
    Then all check-runs on "abc123d" are green
    And no tests are re-run inside the release pipeline
    When the pipeline builds from commit "abc123d"
    Then dist packages are built from the same source as RC and dev
    When the pipeline bumps the version on nwave-dev
    Then pyproject.toml version is "2.18.0"
    And framework-catalog.yaml version is "2.18.0"
    And a commit "chore(release): v2.18.0 [skip ci]" is created
    And tag "v2.18.0" exists on nwave-dev
    And a GitHub Release (not pre-release) is created with changelog
    When the pipeline publishes to PyPI
    Then "nwave-ai" stable version is available on production PyPI
    And "pip install nwave-ai" installs this version (latest stable)
    When the pipeline syncs to nWave public repo
    Then the public repo is updated with source code
    And pyproject.toml is patched: name "nwave-ai", version "1.1.6"
    And the commit message contains full traceability chain
    And tag "v1.1.6" exists on the public repo
    And a GitHub Release is created on the public repo
    When the pipeline creates the dev marker
    Then tag "nWave_v1.1.6" exists on nwave-dev
    And Slack receives a success notification with install instructions

  Scenario: Dry run validates all logic but produces no side effects
    Given Mike triggers workflow_dispatch on release-prod.yml
    And Mike sets source_rc_tag to "v2.18.0rc1"
    And Mike sets dry_run to "true"
    When the pipeline validates the source RC tag
    Then commit "abc123d" is checked out
    And the stable version is "2.18.0"
    When the pipeline checks CI status on commit "abc123d" via GitHub API
    Then all check-runs on "abc123d" are green
    When the pipeline builds dist packages
    Then dist packages (wheel + sdist) are built
    When the pipeline calculates the nwave-ai version
    Then the nwave-ai version is "1.1.6" (auto-bump from "1.1.5")
    When the pipeline composes the pyproject.toml patch
    Then the patch shows name "nwave-ai", version "1.1.6"
    When the pipeline composes the full traceability commit message
    Then the message contains "Source: nwave-dev@abc123d"
    And the message contains "Dev tag: v2.18.0.dev3"
    And the message contains "RC tag: v2.18.0rc1"
    And the message contains "Stable tag: v2.18.0"
    And the pipeline reports "Would have: tagged v2.18.0, bumped nwave-dev to 2.18.0, published to PyPI, synced to nWave public as v1.1.6, created marker nWave_v1.1.6"
    And no stable tag is created on nwave-dev
    And no version bump commit is created on nwave-dev
    And no GitHub Release is created
    And no package is published to PyPI
    And no sync to nWave public repo occurs
    And no marker tag is created on nwave-dev
    And no Slack notification is sent

  Scenario: Version floor override takes effect
    Given the public_version floor is set to "2.0.0" in nwave-dev pyproject.toml
    And the current nwave-ai version on the public repo is "1.1.5"
    When the pipeline calculates the nwave-ai version
    Then the nwave-ai version is "2.0.0" (floor overrides auto-bump)
    And not "1.1.6"

  Scenario: Auto-bump when floor is below current
    Given the public_version floor is "1.1.0"
    And the current nwave-ai version on the public repo is "1.1.5"
    When the pipeline calculates the nwave-ai version
    Then the nwave-ai version is "1.1.6" (patch bump from current)

  Scenario: Source RC tag does not exist
    Given Mike triggers stable promotion with source_rc_tag "v2.18.0rc99"
    And tag "v2.18.0rc99" does not exist
    When the pipeline validates the source RC tag
    Then the pipeline fails with "Tag v2.18.0rc99 not found"
    And the error lists available RC tags: "v2.18.0rc1"
    And no stable tag is created
    And nothing is published to PyPI
    And no sync to public repo occurs

  Scenario: CI failed on source RC commit blocks stable promotion
    Given Mike triggers stable promotion with source_rc_tag "v2.18.0rc1"
    And tag "v2.18.0rc1" exists pointing to commit "abc123d"
    And CI on commit "abc123d" has a failed check-run
    When the pipeline checks CI status via GitHub API
    Then the pipeline stops with "CI failed on abc123d"
    And no stable tag is created
    And nothing is published to PyPI
    And no sync to public repo occurs
    And Slack receives a failure notification

  Scenario: CI still running on source RC commit blocks stable promotion
    Given Mike triggers stable promotion with source_rc_tag "v2.18.0rc1"
    And tag "v2.18.0rc1" exists pointing to commit "abc123d"
    And CI on commit "abc123d" has a pending check-run
    When the pipeline checks CI status via GitHub API
    Then the pipeline stops with "CI still running on abc123d, retry later"
    And no stable tag is created
    And no dist packages are built

  Scenario: No CI run found on source RC commit blocks stable promotion
    Given Mike triggers stable promotion with source_rc_tag "v2.18.0rc1"
    And tag "v2.18.0rc1" exists pointing to commit "abc123d"
    And commit "abc123d" has no check-runs registered
    When the pipeline checks CI status via GitHub API
    Then the pipeline stops with "No CI run found for abc123d"
    And no stable tag is created
    And no dist packages are built

  Scenario: Full traceability chain in public repo commit
    Given the stable release promoted from RC "v2.18.0rc1"
    And the RC promoted from dev "v2.18.0.dev3"
    When inspecting the nWave public repo commit for "v1.1.6"
    Then the commit message contains "Source: nwave-dev@abc123d"
    And the commit message contains "Dev tag: v2.18.0.dev3"
    And the commit message contains "RC tag: v2.18.0rc1"
    And the commit message contains "Stable tag: v2.18.0"
    And the commit message contains the pipeline run URL

  Scenario: Reverse traceability from public to dev
    Given the stable release created marker tag "nWave_v1.1.6" on nwave-dev
    When querying nwave-dev for tag "nWave_v1.1.6"
    Then the tag points to the commit that was released
    And the tag annotation contains "Published as nwave-ai v1.1.6"

  Scenario: PyPI stable version collision
    Given "nwave-ai" version "2.18.0" already exists on PyPI as stable
    When the pipeline attempts to publish "2.18.0"
    Then the pipeline fails with a clear error
    And no sync to public repo occurs
    And Slack receives a failure notification
    And Mike investigates the version collision
