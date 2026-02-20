Feature: Pipeline Modularization
  As Mike, the nwave-dev maintainer,
  I want the release pipeline split into reusable workflows and composite actions
  So that each stage is independently triggerable, testable, and maintainable

  Background:
    Given the current release.yml is 1075 lines in a single file
    And the target structure uses reusable workflows (prefixed with _)
    And composite actions live under .github/actions/{name}/action.yml

  Scenario: Three caller workflows replace the monolith
    When the pipeline is modularized
    Then release-dev.yml exists as a caller workflow for Stage 1
    And release-rc.yml exists as a caller workflow for Stage 2
    And release-prod.yml exists as a caller workflow for Stage 3
    And each caller workflow uses workflow_dispatch trigger
    And release.yml (the monolith) is removed or archived

  Scenario: Reusable workflows extracted for shared pipeline stages
    When the pipeline is modularized
    Then _reusable-build.yml handles build + test + artifact upload
    And _reusable-publish-pypi.yml handles PyPI publishing via OIDC
    And _reusable-sync-repo.yml handles cross-repo rsync + commit + tag
    And each reusable workflow has clearly defined inputs and outputs

  Scenario: Composite actions extracted for repeated step bundles
    When the pipeline is modularized
    Then .github/actions/setup-python-env/action.yml handles Python + pipenv setup
    And .github/actions/verify-version/action.yml handles version consistency checks
    And .github/actions/generate-changelog/action.yml handles changelog from conventional commits

  Scenario: Secrets are passed explicitly, not inherited
    Given the cross-repo sync uses RELEASETRAIN secret
    When release-rc.yml calls _reusable-sync-repo.yml
    Then RELEASETRAIN is passed as an explicit secret parameter
    And not via "secrets: inherit"

  Scenario: Each stage is independently triggerable
    Given the three caller workflows exist
    When Mike triggers release-dev.yml alone
    Then only Stage 1 steps execute
    And Stage 2 and Stage 3 are not triggered
    When Mike triggers release-rc.yml alone
    Then only Stage 2 steps execute
    And the source dev tag is validated as input
