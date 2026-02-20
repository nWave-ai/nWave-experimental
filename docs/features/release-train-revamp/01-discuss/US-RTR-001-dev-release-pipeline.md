# US-RTR-001: Dev Release on Demand

## Problem (The Pain)
Mike is the sole maintainer of the nwave-dev repository who regularly develops features on master.
He finds it wasteful and noisy that every approach to creating dev snapshots either tags every single commit (creating tag spam that buries meaningful releases) or requires manual version string editing across multiple files.

## Who (The User)
- Mike, nwave-dev maintainer, releasing from a private repository
- Works on master branch in a trunk-based development model
- Wants intentional release points, not automatic noise

## Solution (What We Build)
A dedicated `release-dev.yml` workflow, triggered via `workflow_dispatch`, that calculates the next PEP 440 `.devN` version, runs the full CI suite, and creates a git tag plus GitHub pre-release only when tests pass. Optionally publishes to TestPyPI for upload smoke testing.

## Domain Examples

### Example 1: First dev release after v2.17.6
Mike has merged 4 commits since v2.17.6 including `feat(cli): add verbose flag`. He triggers a dev release. The pipeline reads pyproject.toml (version "2.17.6"), determines next version is "2.18.0" based on conventional commits, appends ".dev1", runs tests, and creates tag `v2.18.0.dev1` with a GitHub pre-release.

### Example 2: Third dev release for the same version
Tags `v2.18.0.dev1` and `v2.18.0.dev2` already exist. Mike triggers another dev release. The pipeline finds the highest existing dev tag (dev2), increments to "2.18.0.dev3", runs tests, and creates `v2.18.0.dev3`.

### Example 3: Tests fail, no tag created
Mike triggers a dev release but a regression in the CLI parser causes `test_verbose_flag` to fail. The pipeline stops after the build-test step. No git tag is created, no GitHub pre-release appears, and Slack sends a failure notification: "Dev release FAILED at Build + test."

## UAT Scenarios (BDD)

### Scenario: Happy path dev release
Given Mike triggers workflow_dispatch on release-dev.yml with target_version "auto" and dry_run "false"
And the current pyproject.toml version is "2.17.6"
And there are feat commits since the last tag
When the pipeline completes
Then tag "v2.18.0.dev1" exists on nwave-dev
And a GitHub pre-release is created
And Slack receives a success notification

### Scenario: Sequential dev counter
Given dev tags "v2.18.0.dev1" and "v2.18.0.dev2" exist
When Mike triggers a dev release
Then the created tag is "v2.18.0.dev3"

### Scenario: Dry run
Given Mike triggers with dry_run "true"
When the pipeline completes
Then no git tag is created
And the summary shows "Would bump to: 2.18.0.dev1"

### Scenario: Build failure blocks tag
Given a test failure occurs during CI
When the pipeline reaches the tag step
Then no tag is created
And Slack receives a failure notification

### Scenario: No version-worthy commits
Given all commits since v2.17.6 are "chore" or "ci" type
When Mike triggers a dev release with auto version
Then the pipeline reports "No version bump needed"
And no tag is created

## Acceptance Criteria
- [ ] PEP 440 `.devN` version format with sequential integer counter
- [ ] Dev tag created only after full CI suite passes
- [ ] GitHub pre-release (not full release) created with build artifacts
- [ ] Dry run mode produces no side effects (no tag, no release, no publish)
- [ ] Slack notification on success and failure
- [ ] Dev counter increments correctly from highest existing devN
- [ ] Graceful handling when no version-bump commits exist

## Technical Notes
- Requires custom version calculation script (python-semantic-release does not natively support PEP 440 `.devN`)
- Must read existing dev tags to determine next N
- TestPyPI publish is optional; failure should not block the dev tag creation
- Workflow file: `.github/workflows/release-dev.yml`
- Calls reusable workflows: `_reusable-build.yml`
