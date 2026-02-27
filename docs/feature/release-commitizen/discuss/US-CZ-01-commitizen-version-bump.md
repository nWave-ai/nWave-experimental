# US-CZ-01: Dev Release Version Reflects Conventional Commit Types

## Problem (The Pain)
Mike Brissoni is a release engineer who triggers dev releases from master after merging features. He finds it misleading that 4 `feat:` commits produce `v1.1.23.dev2` (patch bump) instead of `v1.2.0.dev1` (minor bump), because `next_version.py` hardcodes `_bump_patch()` and ignores conventional commit semantics. His workaround is mentally tracking "the real version should be 1.2.0" and correcting it only at stable release time, which creates confusion in the dev tag sequence.

## Who (The User)
- Release engineer (Mike) triggering dev releases via workflow_dispatch on master
- CI bot executing the release-dev.yml pipeline automatically
- Downstream consumers (RC promotion) who inherit the base version from dev tags

## Solution (What We Build)
Add `--base-version` CLI argument to `next_version.py` and wire Commitizen (`cz bump --get-next`) into the release-dev.yml workflow so that the version bump level is determined by analyzing conventional commits rather than always bumping patch.

## Domain Examples

### Example 1: Mike pushes 4 feat: commits (happy path)
Mike merges 4 feature PRs into master since the last stable tag `v1.1.22`. He triggers a dev release. Commitizen scans the commits, finds `feat:` as the highest bump level, outputs `1.2.0`. The pipeline passes `--base-version 1.2.0` to next_version.py, which produces `1.2.0.dev1`. The tag `v1.2.0.dev1` is created on GitHub.

### Example 2: Only fix: commits since last tag
Mike merges 3 bug fix PRs (`fix:` prefix) into master since `v1.1.22`. He triggers a dev release. Commitizen outputs `1.1.23`. The pipeline passes `--base-version 1.1.23`, producing `1.1.23.dev1`. Behavior matches today's output but is now driven by commit analysis, not hardcoded.

### Example 3: Breaking change commit
Mike merges a commit with `feat!: redesign API surface` since `v1.1.22`. Commitizen detects the breaking change marker, outputs `2.0.0`. The pipeline produces `2.0.0.dev1`. Mike sees the major bump and knows the dev release reflects the breaking change.

### Example 4: Sequential counter with CZ base
Mike triggers a second dev release with the same commits (no new merges). Commitizen still outputs `1.2.0`. Tag `v1.2.0.dev1` already exists. next_version.py increments the counter to `1.2.0.dev2`.

### Example 5: Empty base-version falls back to patch
Commitizen returns an empty string (perhaps a transient failure or misconfiguration). The pipeline passes `--base-version ""` to next_version.py. Since base-version is empty, the script falls back to `_bump_patch(1.1.22)` = `1.1.23`, producing `1.1.23.dev1`. The pipeline does not fail.

### Example 6: Mid-cycle patch-to-minor escalation (Mike + Ale scenario)
Stable version is `v1.1.25`. Over 5 days, Mike pushes `ci:` commits and Ale pushes `fix:` commits. CZ outputs `1.1.26`; eight dev releases are tagged (`v1.1.26.dev1` through `v1.1.26.dev8`). On day 6, Ale pushes a `feat:` commit adding a new agent. CZ re-scans ALL commits since `v1.1.25`, now finds `feat:` as the highest bump type, outputs `1.2.0`. The pipeline passes `--base-version 1.2.0`. Since no `v1.2.0.dev*` tags exist (the old `v1.1.26.dev*` tags have a different base), the counter resets and produces `1.2.0.dev1`. Both sets of tags coexist in the repo.

### Example 7: Reverted feat commit does not de-escalate
After Example 6, the `feat:` commit turns out to be premature and Ale pushes a `revert:` commit. Only `fix:` commits remain as net-effective changes. However, CZ scans ALL commits since `v1.1.25` including the original `feat:` (which is still in git history). CZ still outputs `1.2.0`. The next dev release is `1.2.0.dev2`. De-escalation only happens when a new stable release resets the scan window.

### Example 8: RC promotion after mid-cycle escalation
After the escalation in Example 6, the repo has tags `v1.1.26.dev1` through `v1.1.26.dev8` and `v1.2.0.dev1`, `v1.2.0.dev2`. The team promotes to RC. The RC candidate is the highest base version's latest dev tag: `v1.2.0.dev2`. The promotion path is: `v1.2.0.dev2` -> `v1.2.0rc1` -> `v1.2.0`. One-click at each stage.

## UAT Scenarios (BDD)

### Scenario 1: feat commits produce minor bump
Given Mike has pushed 4 "feat:" commits since the last stable tag v1.1.22
And no existing dev tags for version "1.2.0"
When the pipeline passes --base-version "1.2.0" to next_version.py
Then the dev version is "1.2.0.dev1"
And the output JSON contains base_version "1.2.0"
And the version is PEP 440 compliant

### Scenario 2: fix commits produce patch bump
Given Mike has pushed 3 "fix:" commits since v1.1.22
When the pipeline passes --base-version "1.1.23" to next_version.py
Then the dev version is "1.1.23.dev1"

### Scenario 3: Breaking change produces major bump
Given Mike has pushed a "feat!:" commit since v1.1.22
When the pipeline passes --base-version "2.0.0" to next_version.py
Then the dev version is "2.0.0.dev1"

### Scenario 4: Sequential counter with CZ base
Given --base-version is "1.2.0"
And a dev tag "v1.2.0.dev1" already exists
When the pipeline runs next_version.py
Then the dev version is "1.2.0.dev2"

### Scenario 5: Empty base-version falls back to patch bump
Given --base-version is ""
And the current version is "1.1.22"
When the pipeline runs next_version.py
Then next_version.py falls back to _bump_patch
And the dev version is "1.1.23.dev1"

### Scenario 6: Mid-cycle patch-to-minor escalation resets counter
Given the current version in pyproject.toml is "1.1.25"
And dev tags v1.1.26.dev1 through v1.1.26.dev8 exist from earlier fix-only releases
And Ale has now pushed a "feat:" commit
And CZ re-scans all commits since v1.1.25 and outputs "1.2.0"
When the pipeline passes --base-version "1.2.0" to next_version.py
Then _highest_counter finds no v1.2.0.dev* tags
And the dev version is "1.2.0.dev1"
And old v1.1.26.dev* tags remain untouched in the repo

### Scenario 7: Multiple base versions coexist after escalation
Given --base-version is "1.2.0"
And existing tags include v1.1.26.dev1 through v1.1.26.dev8 and v1.2.0.dev1
When the pipeline runs next_version.py
Then _highest_counter matches only v1.2.0.dev* tags
And the dev version is "1.2.0.dev2"

## Acceptance Criteria
- [ ] `--base-version` CLI argument accepted by next_version.py (optional, default empty)
- [ ] When `--base-version` is non-empty and valid PEP 440, it replaces `_bump_patch()` as the base version
- [ ] When `--base-version` is empty, `_bump_patch()` is used as fallback (preserving current behavior)
- [ ] Sequential `.devN` counter works correctly with the CZ-provided base version
- [ ] When `--base-version` changes mid-cycle (e.g. from "1.1.26" to "1.2.0"), `_highest_counter` filters by the new base and the dev counter resets to dev1
- [ ] Multiple base version tag sets coexist safely (v1.1.26.dev8 and v1.2.0.dev1 in the same repo)
- [ ] Output JSON `base_version` field reflects the resolved base (CZ or fallback)
- [ ] `[tool.commitizen]` section added to pyproject.toml with version_scheme = "pep440"
- [ ] release-dev.yml includes a CZ analysis step that passes output to next_version.py

## Technical Notes
- Commitizen already installed as dev dependency (`commitizen>=3.12.0`)
- `[tool.commitizen]` config coexists with `[tool.semantic_release]` (different sections, no conflict)
- `cz bump --get-next` reads `[project].version` as the anchor (last stable: 1.1.22)
- **Mid-cycle escalation mechanism**: CZ always scans ALL commits since the stable anchor, not just new commits since the last dev tag. When a higher bump type appears (e.g., `feat:` after `fix:`-only), CZ output jumps (e.g., 1.1.26 to 1.2.0). The `_highest_counter` function (next_version.py lines 124-135) filters tags by base version string match, so old-base dev tags become invisible and the counter resets naturally.
- **De-escalation impossible**: A `feat:` commit remains in git history even after `revert:`. CZ still sees it. Only a new stable release resets the scan window.
- **Tag coexistence**: After escalation, both old-base and new-base dev tags exist in the repo (e.g., v1.1.26.dev8 and v1.2.0.dev1). This is correct behavior; `_highest_counter` isolates them.
- CZ step in workflow uses `|| BASE=""` to gracefully handle CZ failures
- No changes to RC or stable workflows; they inherit base version from dev tags
- Dependency: pyproject.toml `[tool.commitizen]` section must exist before CZ step runs

## Traceability
- **Journey**: `docs/ux/release-commitizen/journey-dev-release.feature` scenarios 1-5 (basic) + US-CZ-01b scenarios (mid-cycle escalation)
- **Research**: `docs/research/cicd/psr-version-calculation-for-release-trains.md` (Gap 3, Architecture Recommendation)
- **Design**: `docs/release/plan-commitizen-version-calculation.md` (Steps 1-4)
