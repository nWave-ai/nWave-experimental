# US-CZ-03: Graceful Fallback When Commitizen Fails

## Problem (The Pain)
Mike Brissoni is a release engineer who cannot afford dev releases to break when a new dependency (Commitizen) has a transient issue. If CZ is not installed, misconfigured, or returns unparseable output, the pipeline must not fail. Today's `_bump_patch()` logic always works because it has no external dependency. Adding CZ as the primary version calculator introduces a new failure mode that must be absorbed gracefully.

## Who (The User)
- Release engineer (Mike) who triggers dev releases and expects them to succeed even when CZ has issues
- CI environment where commitizen may not be installed (e.g., minimal runner image)
- Future contributors who may misconfigure `[tool.commitizen]` in pyproject.toml

## Solution (What We Build)
The CZ analysis step in release-dev.yml uses `|| BASE=""` to absorb any CZ failure into an empty string. When `--base-version` is empty, `next_version.py` falls back to `_bump_patch()`, preserving today's behavior as a safety net. Invalid `--base-version` or `--version-floor` values are rejected with descriptive errors (exit code 2).

## Domain Examples

### Example 1: CZ not installed (happy fallback)
A minimal CI runner does not have commitizen installed. The CZ step runs `cz bump --get-next`, which fails with "command not found". The `|| BASE=""` fallback catches it. The pipeline passes `--base-version ""` to next_version.py, which uses `_bump_patch(1.1.22)` = `1.1.23`. Dev version: `1.1.23.dev1`. The release completes successfully.

### Example 2: CZ config missing from pyproject.toml
Someone accidentally deleted the `[tool.commitizen]` section from pyproject.toml. CZ runs but exits with "No commitizen configuration found". The `|| BASE=""` fallback catches it. Fallback produces `1.1.23.dev1`. Mike sees the patch bump, checks the CZ config, and fixes it for the next release.

### Example 3: Invalid base-version rejected
A corrupted CZ output produces `--base-version "not-a-version"`. next_version.py validates the input, finds it is not PEP 440 compliant, and exits with code 2 and error message "Invalid base-version 'not-a-version': not PEP 440 compliant." The pipeline fails explicitly rather than producing a bad version.

### Example 4: Invalid floor rejected
Someone sets `public_version = "abc"` in pyproject.toml. next_version.py receives `--version-floor "abc"`, validates it, and exits with code 2: "Invalid version-floor 'abc': not PEP 440 compliant."

## UAT Scenarios (BDD)

### Scenario 1: CZ not installed, graceful fallback
Given commitizen is not installed in the CI environment
When the pipeline runs the CZ analysis step
Then the step outputs an empty string (not a pipeline failure)
When --base-version "" is passed to next_version.py
Then the fallback _bump_patch produces base "1.1.23"
And the dev version is "1.1.23.dev1"
And the pipeline completes with exit code 0

### Scenario 2: CZ config missing, graceful fallback
Given pyproject.toml does not contain a [tool.commitizen] section
When the pipeline runs "cz bump --get-next"
Then CZ exits with a non-zero code
And the step outputs an empty string
When --base-version "" is passed to next_version.py
Then the dev version is "1.1.23.dev1"

### Scenario 3: Invalid base-version is rejected
Given --base-version is "not-a-version"
When next_version.py validates the input
Then it exits with code 2
And the error JSON contains "Invalid base-version"
And the error JSON contains "not PEP 440 compliant"

### Scenario 4: Invalid version-floor is rejected
Given --version-floor is "abc"
When next_version.py validates the input
Then it exits with code 2
And the error JSON contains "Invalid version-floor"
And the error JSON contains "not PEP 440 compliant"

### Scenario 5: CZ returns empty due to no bump-worthy commits
Given all commits since v1.1.22 are "chore:" and "ci:" type
When the pipeline runs "cz bump --get-next"
Then CZ outputs an empty string (no version bump needed)
When --base-version "" and --no-bump are passed to next_version.py
Then next_version.py exits with code 1: "No version bump needed"

## Acceptance Criteria
- [ ] CZ step in release-dev.yml uses `|| BASE=""` to absorb any CZ failure
- [ ] Empty `--base-version` triggers `_bump_patch()` fallback (preserving current behavior)
- [ ] Non-empty invalid `--base-version` exits code 2 with "Invalid base-version" error
- [ ] Non-empty invalid `--version-floor` exits code 2 with "Invalid version-floor" error
- [ ] Pipeline completes successfully when CZ is not installed (fallback path)
- [ ] Pipeline completes successfully when CZ config is missing (fallback path)

## Technical Notes
- CZ step must use `BASE=$(cz bump --get-next 2>/dev/null) || BASE=""` pattern
- Validation of `--base-version` uses `packaging.version.Version` (same as existing validation)
- Validation happens early in `calculate_dev()`, before counter calculation
- Empty string is explicitly allowed; only non-empty invalid strings are rejected
- The `--no-bump` flag from US-CZ-01 interacts: if CZ says "no bump" AND no-bump is set, exit code 1
- Dependency: US-CZ-01 must be implemented first (--base-version arg must exist)
- Dependency: US-CZ-02 must be implemented first (--version-floor arg must exist)

## Traceability
- **Journey**: `docs/ux/release-commitizen/journey-dev-release.feature` scenarios 10-13
- **Design**: `docs/release/plan-commitizen-version-calculation.md` (priority chain level 3)
- **Research**: `docs/research/cicd/psr-version-calculation-for-release-trains.md` (Gap 3: CZ --get-next behavior)
