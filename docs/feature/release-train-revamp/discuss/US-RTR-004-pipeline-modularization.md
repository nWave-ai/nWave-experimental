# US-RTR-004: Pipeline Modularization

## Problem (The Pain)
Mike is the nwave-dev maintainer who debugs and evolves the release pipeline.
He finds the current 1075-line monolithic `release.yml` painful to maintain: a failure in the cross-repo sync step requires reading through hundreds of lines to find the relevant section, shared logic (Python setup, version extraction, changelog generation) is duplicated across jobs, and testing a single stage requires running the entire pipeline.

## Who (The User)
- Mike, maintaining and debugging CI/CD workflows
- CI/CD system, executing modular pipeline stages
- Future contributors who need to understand the pipeline structure

## Solution (What We Build)
Split the monolithic `release.yml` into three caller workflows (one per stage), three reusable workflows (shared pipeline stages), and three composite actions (repeated step bundles). Each caller workflow is independently triggerable, each reusable workflow has defined inputs/outputs, and composite actions eliminate step duplication.

## Domain Examples

### Example 1: Debugging a PyPI publish failure
Mike's RC release fails at PyPI publishing. Instead of scrolling through 1075 lines, he opens `release-rc.yml` (the caller, ~40 lines), sees it calls `_reusable-publish-pypi.yml`, opens that file (~80 lines), and finds the OIDC configuration issue immediately. Total lines to scan: ~120 instead of 1075.

### Example 2: Updating Python setup across all stages
Mike needs to upgrade from Python 3.12 to 3.13 for CI. Instead of editing three separate job blocks in a single file, he updates `.github/actions/setup-python-env/action.yml` once. All three caller workflows automatically use the updated setup.

### Example 3: Adding a new stage (e.g., alpha)
A future contributor wants to add an alpha release stage. They create `release-alpha.yml` as a new caller workflow that composes the existing reusable workflows (`_reusable-build.yml`) with new alpha-specific logic, without touching any existing workflow file.

## UAT Scenarios (BDD)

### Scenario: Monolith replaced by modular structure
Given the modularization is complete
When listing files in .github/workflows/
Then release-dev.yml exists (Stage 1 caller)
And release-rc.yml exists (Stage 2 caller)
And release-prod.yml exists (Stage 3 caller)
And _reusable-build.yml exists (shared build + test)
And _reusable-publish-pypi.yml exists (shared PyPI publish)
And _reusable-sync-repo.yml exists (shared cross-repo sync)
And the original release.yml is removed

### Scenario: Composite actions eliminate duplication
Given the modularization is complete
When listing .github/actions/
Then setup-python-env/action.yml exists
And verify-version/action.yml exists
And generate-changelog/action.yml exists

### Scenario: Each stage independently triggerable
Given release-dev.yml is triggered via workflow_dispatch
When the workflow runs
Then only Stage 1 logic executes
And Stage 2 and Stage 3 workflows are not triggered

### Scenario: Secrets passed explicitly
Given release-rc.yml calls _reusable-sync-repo.yml
When inspecting the workflow call
Then RELEASETRAIN is passed as an explicit secret parameter
And the reusable workflow does not use "secrets: inherit"

### Scenario: Reusable workflow inputs and outputs defined
Given _reusable-build.yml is called by release-dev.yml
When inspecting the reusable workflow
Then it accepts input "python_version" with a default
And it accepts input "commit_ref" (required)
And it outputs "dist_artifact_name"
And it outputs "test_result"

## Acceptance Criteria
- [ ] Three caller workflows replace the monolith (release-dev, release-rc, release-prod)
- [ ] Three reusable workflows extracted (_reusable-build, _reusable-publish-pypi, _reusable-sync-repo)
- [ ] Three composite actions extracted (setup-python-env, verify-version, generate-changelog)
- [ ] Each caller workflow is independently triggerable via workflow_dispatch
- [ ] Reusable workflows have defined inputs and outputs
- [ ] Secrets passed explicitly to reusable workflows (not inherited)
- [ ] Original release.yml removed after migration
- [ ] No individual workflow file exceeds 300 lines

## Technical Notes
- Reusable workflows prefixed with `_` per GitHub Well-Architected convention
- Max 10 workflow_dispatch inputs per workflow (GitHub limit)
- Max 10 nesting levels for reusable workflows (keep flat)
- `env` context not propagated to called workflows; use inputs instead
- `GITHUB_ENV` does not work across workflow boundaries; use outputs
- Composite actions under `.github/actions/{name}/action.yml`
- This story is a prerequisite for US-RTR-001, US-RTR-002, US-RTR-003 (they reference the modular structure)
