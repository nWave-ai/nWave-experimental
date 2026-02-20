# US-RTR-002: RC Release and Beta Distribution

## Problem (The Pain)
Mike is the nwave-dev maintainer who wants to give selected beta testers early access to a release candidate before making it public.
He finds it error-prone and fragmented to manually coordinate pre-release distribution: there is no structured way to promote a dev build to an RC, publish it where testers can install it with standard pip, and sync it to a dedicated beta repository with full traceability.

## Who (The User)
- Mike, nwave-dev maintainer, promoting a vetted dev release to RC
- Beta testers (invited guests) who install and exercise the RC via pip
- Both need standard tooling (pip, GitHub Releases) without custom workarounds

## Solution (What We Build)
A dedicated `release-rc.yml` workflow, triggered via `workflow_dispatch`, that validates a source dev tag, builds from the exact same commit, creates an RC tag (PEP 440 `rcN`), publishes to production PyPI with pre-release marker, and syncs to the nWave-beta repo with cross-repo traceability in commit messages.

## Domain Examples

### Example 1: First RC promotion from dev3
Mike has tested `v1.1.22.dev3` locally and is satisfied. He triggers release-rc.yml with `source_dev_tag: v1.1.22.dev3`. The pipeline checks out commit abc123d (the commit behind dev3), builds, creates tag `v1.1.22rc1`, publishes `nwave-ai==1.1.22rc1` to PyPI, syncs to nWave-beta, and posts to Slack: "RC v1.1.22rc1 published. Install: `pip install --pre nwave-ai==1.1.22rc1`".

### Example 2: Beta tester installs RC
Alessandro, a beta tester, sees the GitHub pre-release on nwave-ai/nWave-beta. He runs `pip install --pre nwave-ai==1.1.22rc1` and it installs from production PyPI. He runs `nwave-ai version` and sees `1.1.22rc1`. He exercises the CLI and files a bug report on the nWave-beta repo.

### Example 3: Invalid source dev tag
Mike mistypes the source tag as `v1.1.22.dev99` (does not exist). The pipeline immediately fails: "Tag v1.1.22.dev99 not found. Available dev tags for 1.1.22: v1.1.22.dev1, v1.1.22.dev2, v1.1.22.dev3." No RC tag is created, nothing is published.

## UAT Scenarios (BDD)

### Scenario: Happy path RC promotion
Given Mike triggers release-rc.yml with source_dev_tag "v1.1.22.dev3"
And tag "v1.1.22.dev3" exists on nwave-dev pointing to commit "abc123d"
When the pipeline completes
Then tag "v1.1.22rc1" exists on nwave-dev
And "nwave-ai" version "1.1.22rc1" is on production PyPI
And nWave-beta repo has tag "v1.1.22rc1"
And the nWave-beta commit message contains "Source: nwave-dev@abc123d"

### Scenario: Beta tester pip install
Given "nwave-ai" version "1.1.22rc1" is published on PyPI
When a beta tester runs "pip install --pre nwave-ai==1.1.22rc1"
Then nwave-ai 1.1.22rc1 is installed
And "pip install nwave-ai" does NOT install the RC (requires --pre)

### Scenario: Source dev tag not found
Given Mike triggers with source_dev_tag "v1.1.22.dev99"
When the pipeline validates the tag
Then the pipeline fails with available tag list
And no RC tag is created

### Scenario: Dry run validates logic without side effects
Given Mike triggers release-rc.yml with source_dev_tag "v1.1.22.dev3" and dry_run "true"
When the pipeline completes
Then source tag is validated, CI status is checked, RC version is calculated, dist packages are built, and traceability message is composed
And the summary reports "Would have: tagged v1.1.22rc1, published 1.1.22rc1 to PyPI, synced to nWave-beta"
And no RC tag is created, no PyPI upload occurs, no nWave-beta sync occurs, no Slack notification is sent

### Scenario: Sequential RC counter
Given tag "v1.1.22rc1" already exists
When Mike promotes "v1.1.22.dev5" to RC
Then the RC version is "1.1.22rc2"

### Scenario: Cross-repo traceability
Given the RC promotion from "v1.1.22.dev3" succeeded
When inspecting the nWave-beta commit for v1.1.22rc1
Then the commit message contains the source commit SHA
And the commit message contains the dev tag reference
And the commit message contains the pipeline run URL

### Scenario: PyPI publishing uses OIDC
Given Trusted Publisher is configured for the repository
When the pipeline publishes to PyPI
Then no stored API token is used
And the OIDC token is acquired and expires within 15 minutes

## Acceptance Criteria
- [ ] RC version follows PEP 440 `X.Y.ZrcN` format (no dot before rc)
- [ ] Builds from the exact commit behind the source dev tag (promotion, not rebuild)
- [ ] Published to production PyPI with pre-release marker (pip ignores by default)
- [ ] Beta testers install via `pip install --pre nwave-ai==X.Y.ZrcN`
- [ ] nWave-beta repo synced with full cross-repo traceability in commit messages
- [ ] Source dev tag validation with helpful error on missing tag
- [ ] RC counter increments sequentially from highest existing rcN
- [ ] Dry run mode executes all logic (validate, CI gate, version calc, build, traceability compose) but produces zero side effects (no tag, no release, no PyPI upload, no beta sync, no Slack)
- [ ] PyPI publishing via Trusted Publisher (OIDC), not stored API tokens

## Technical Notes
- Requires nWave-beta repo creation at https://github.com/nwave-ai/nWave-beta
- Trusted Publisher OIDC must be configured in PyPI project settings for this workflow
- RELEASETRAIN token needed for nWave-beta repo push (passed explicitly, not inherited)
- Workflow file: `.github/workflows/release-rc.yml`
- Calls reusable workflows: `_reusable-build.yml`, `_reusable-publish-pypi.yml`, `_reusable-sync-repo.yml`
- Dependency: US-RTR-001 (dev release pipeline must exist to produce source tags)
