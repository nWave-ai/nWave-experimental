# US-RTR-003: Stable Release and Public Distribution

## Problem (The Pain)
Mike is the nwave-dev maintainer who needs to promote a tested RC to a stable public release across three targets: nwave-dev tags, production PyPI, and the nWave public repo.
He finds the current monolithic pipeline (1075-line release.yml) fragile and hard to debug when any step fails, with no structured promotion path from RC to stable and incomplete traceability between the private and public repositories.

## Who (The User)
- Mike, nwave-dev maintainer, releasing a tested RC to the public
- End users installing via `pip install nwave-ai` (must get latest stable, never an RC)
- Mike debugging issues by tracing from public version back to source commit

## Solution (What We Build)
A dedicated `release-prod.yml` workflow, triggered via `workflow_dispatch`, that validates a source RC tag, verifies CI passed on the source commit via the GitHub API CI Status Gate (no re-testing), builds dist packages from the exact same commit, bumps the version on nwave-dev, publishes to PyPI as a stable release, syncs to the nWave public repo with full traceability, and creates a reverse-lookup marker tag on nwave-dev.

## Domain Examples

### Example 1: Happy path stable release from rc1
Mike's beta testers validated `v1.1.22rc1` with no blockers. He triggers release-prod.yml with `source_rc_tag: v1.1.22rc1`. The pipeline checks out commit abc123d, builds, bumps nwave-dev to v1.1.22, publishes `nwave-ai` as stable on PyPI, syncs to nwave-ai/nwave with auto-bumped version 1.1.22, and creates marker tag `v1.1.22` on nwave-dev. Slack announces: "nwave-ai v1.1.22 released! `pip install nwave-ai`"

### Example 2: Version floor override for major bump
Mike sets `public_version = "2.0.0"` in pyproject.toml's `[tool.nwave]` section because the next release has breaking changes. The current public version is 1.1.21. The pipeline sees floor (2.0.0) > current (1.1.21) and uses 2.0.0 as the nwave-ai version instead of auto-bumping to 1.1.22.

### Example 3: Tracing a bug from public to source
A user reports a bug in nwave-ai v1.1.22. Mike looks at the nwave-dev repo, finds tag `v1.1.22`, which points to the exact commit that was released. He also checks the nWave public repo's commit message for v1.1.22 and finds "Source: nwave-dev@abc123d, Dev tag: v1.1.22.dev3, RC tag: v1.1.22rc1."

## UAT Scenarios (BDD)

### Scenario: Happy path stable release
Given Mike triggers release-prod.yml with source_rc_tag "v1.1.22rc1"
And tag "v1.1.22rc1" exists pointing to commit "abc123d"
And the current nwave-ai version on the public repo is "1.1.21"
When the pipeline completes
Then nwave-dev has tag "v1.1.22" with a full GitHub Release
And "nwave-ai" stable version is on production PyPI
And nWave public repo has tag "v1.1.22" with a GitHub Release
And nwave-dev has marker tag "v1.1.22"
And Slack shows "pip install nwave-ai"

### Scenario: Version floor override
Given public_version floor is "2.0.0" in pyproject.toml
And current public version is "1.1.21"
When the pipeline calculates nwave-ai version
Then nwave-ai version is "2.0.0"

### Scenario: Auto-bump patch version
Given public_version floor is "1.1.0"
And current public version is "1.1.21"
When the pipeline calculates nwave-ai version
Then nwave-ai version is "1.1.22"

### Scenario: Dry run validates logic without side effects
Given Mike triggers release-prod.yml with source_rc_tag "v1.1.22rc1" and dry_run "true"
When the pipeline completes
Then source RC is validated, CI status is checked, stable version is calculated, dist packages are built, nwave-ai version is calculated (floor vs auto-bump), pyproject.toml patch is composed, and full traceability chain message is composed
And the summary reports "Would have: tagged v1.1.22, bumped nwave-dev to 1.1.22, published to PyPI, synced to nWave public as v1.1.22, created marker v1.1.22"
And no stable tag is created, no version bump commit, no PyPI upload, no public repo sync, no marker tag, no Slack notification

### Scenario: Source RC tag missing
Given Mike triggers with source_rc_tag "v1.1.22rc99"
When the pipeline validates
Then it fails listing available RC tags
And no stable tag is created

### Scenario: Full traceability chain
Given stable release from "v1.1.22rc1" (from "v1.1.22.dev3") completes
When inspecting the nWave public commit for "v1.1.22"
Then the commit contains: Source SHA, Dev tag, RC tag, Stable tag, Pipeline URL

### Scenario: Reverse traceability
Given marker tag "v1.1.22" exists on nwave-dev
When Mike queries that tag
Then it points to the commit that produced the public release

### Scenario: End user gets stable, not RC
Given both "1.1.22rc1" and "1.1.22" (as "1.1.22") are on PyPI
When a user runs "pip install nwave-ai"
Then version "1.1.22" is installed (stable)
And "1.1.22rc1" is not installed

## Acceptance Criteria
- [ ] Stable version on nwave-dev follows PEP 440 `X.Y.Z` format
- [ ] Builds from the exact commit behind the source RC tag
- [ ] Version bump committed on nwave-dev with `[skip ci]` tag
- [ ] Published to production PyPI as stable (pip install gets it by default)
- [ ] PyPI publishing via Trusted Publisher (OIDC)
- [ ] nWave public repo synced with pyproject.toml patched for nwave-ai identity
- [ ] nwave-ai version auto-bumped from current, or uses floor if floor > current
- [ ] Full traceability chain in target repo commit messages (SHA, dev tag, RC tag, pipeline URL)
- [ ] Reverse-lookup marker tag `vX.Y.Z` on nwave-dev
- [ ] Dry run mode executes all logic (validate, CI gate, version calc, build, version floor calc, pyproject patch compose, traceability chain compose) but produces zero side effects (no tag, no version bump commit, no release, no PyPI upload, no public sync, no marker tag, no Slack)

## Technical Notes
- Depends on: US-RTR-002 (RC pipeline must exist to produce source RC tags)
- RELEASETRAIN token for cross-repo push
- pyproject.toml patching (name, version, authors, build config) currently uses regex; consider templating
- Changelog generated from conventional commits between production marker tags
- Workflow file: `.github/workflows/release-prod.yml`
- Calls reusable workflows: `_reusable-build.yml`, `_reusable-publish-pypi.yml`, `_reusable-sync-repo.yml`
