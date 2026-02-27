# US-CZ-04: Full Promotion Chain Validates Correctly After Mid-Cycle Escalation

## Problem (The Pain)
Mike Brissoni is a release engineer who promotes dev releases through RC to stable using a three-stage pipeline. He finds it risky that there are no explicit scenarios proving the full promotion chain works correctly after a mid-cycle bump escalation. The dev stage has thorough scenarios (US-CZ-01), but the RC and stable stages have zero dedicated validation. After a patch-to-minor escalation (v1.1.26.dev8 orphaned, v1.2.0.dev2 is the real candidate), Mike has to trust that `discover_tag.py` picks the right tag and that `calculate_rc` / `calculate_stable` strip suffixes correctly. The code works, but there is no acceptance test proving it. One wrong promotion (e.g., promoting v1.1.26.dev8 instead of v1.2.0.dev2) would ship the wrong version to PyPI.

## Who (The User)
- Release engineer (Mike) clicking "Promote to RC" and "Promote to Stable" via workflow_dispatch
- CI/CD system auto-discovering the highest tag at each stage via `discover_tag.py`
- Downstream consumers (nWave-beta, nwave-ai/nwave public repo) who receive the promoted version

## Solution (What We Build)
Explicit Gherkin scenarios covering the full dev-to-RC-to-stable promotion chain, with focus on tag auto-discovery after mid-cycle escalation, orphaned tag handling, sequential RC counters, self-healing from accidental wrong promotions, and the one-click UX at each stage. No code changes are needed; the existing `discover_tag.py`, `calculate_rc`, and `calculate_stable` already handle these cases. This story validates and documents the behavior.

## Domain Examples

### Example 1: Dev to RC promotion after mid-cycle escalation (happy path)
Tags in repo: v1.1.26.dev1 through v1.1.26.dev8 (from fix-only period), v1.2.0.dev1, v1.2.0.dev2 (after Ale pushed feat: commit). Mike clicks "Promote to RC" in release-rc.yml, leaves the tag field empty. `discover_tag.py --pattern dev` parses all dev tags using `packaging.Version`, sorts them, and returns v1.2.0.dev2 (not v1.1.26.dev8, which would be higher in lexicographic/string sort). `calculate_rc("v1.2.0.dev2")` strips the dev suffix to base "1.2.0", finds no existing v1.2.0rc* tags, and produces "1.2.0rc1". The 8 orphaned v1.1.26.dev* tags remain as historical artifacts; they are never promoted.

### Example 2: Sequential RC counter after bug fix
First RC: v1.2.0rc1 was created from v1.2.0.dev2. During RC testing, a bug is found. The fix is merged to master. A new dev release v1.2.0.dev3 is created. Mike clicks "Promote to RC" again. `discover_tag.py --pattern dev` finds v1.2.0.dev3 (higher than dev2). `calculate_rc("v1.2.0.dev3")` strips to base "1.2.0", `_highest_counter` finds v1.2.0rc1 already exists (counter = 1), and produces "1.2.0rc2".

### Example 3: RC to stable promotion
Tags: v1.2.0rc1, v1.2.0rc2. Mike clicks "Promote to Stable" in release-prod.yml, leaves the tag field empty. `discover_tag.py --pattern rc` parses both RC tags, sorts by `packaging.Version`, returns v1.2.0rc2 (the highest). `calculate_stable("v1.2.0rc2")` strips to "1.2.0". The pipeline creates tag v1.2.0, bumps pyproject.toml to "1.2.0", and publishes to PyPI.

### Example 4: Accidental wrong-tag promotion self-heals
Someone manually types "v1.1.26.dev8" in the RC workflow tag field. `discover_tag.py --validate "v1.1.26.dev8"` confirms it exists. `calculate_rc` produces v1.1.26rc1. Later, the correct promotion creates v1.2.0rc1. When Mike promotes to stable with an empty tag field, `discover_tag.py --pattern rc` finds both v1.1.26rc1 and v1.2.0rc1. Since `packaging.Version("1.2.0rc1") > packaging.Version("1.1.26rc1")`, the stable version is "1.2.0". The accidental v1.1.26rc1 is a dead end, never reaching stable. The system self-heals because discover_tag always picks the highest.

### Example 5: Floor override is dev-stage only
`[tool.nwave].public_version = "2.0.0"` in pyproject.toml. At dev stage, the floor applies (if CZ base is lower). At RC stage, `calculate_rc` receives the dev tag directly (e.g., "v1.2.0.dev2") and strips to "1.2.0"; the floor is not consulted. At stable stage, `calculate_stable` receives the RC tag (e.g., "v1.2.0rc1") and strips to "1.2.0"; the floor is not consulted. Floor override is exclusively a dev-stage mechanism.

### Example 6: Full chain trace with one-click UX
Starting state: pyproject.toml version "1.1.25", Ale pushed feat: mid-cycle, latest dev is v1.2.0.dev2. Click 1 (RC): tag field empty, pipeline auto-discovers v1.2.0.dev2, creates v1.2.0rc1. Click 2 (Stable): tag field empty, pipeline auto-discovers v1.2.0rc1, creates v1.2.0. Total: 2 clicks, 0 manual tag entries, correct version at every stage. The chain: v1.2.0.dev2 -> v1.2.0rc1 -> v1.2.0.

## UAT Scenarios (BDD)

### Scenario 1: discover_tag picks highest dev tag after escalation
Given existing dev tags are v1.1.26.dev1 through v1.1.26.dev8 and v1.2.0.dev1 and v1.2.0.dev2
When discover_tag.py runs with --pattern dev
Then it returns v1.2.0.dev2 (highest by packaging.Version, not string sort)
And v1.1.26.dev8 is not selected despite being the most numerous series

### Scenario 2: calculate_rc strips dev suffix and creates rc1
Given discover_tag.py resolved the source tag as "v1.2.0.dev2"
And no existing v1.2.0rc* tags
When calculate_rc runs with current-version "v1.2.0.dev2"
Then the RC version is "1.2.0rc1"
And the base_version in JSON output is "1.2.0"

### Scenario 3: Sequential RC counter increments correctly
Given v1.2.0rc1 already exists
And discover_tag.py resolved the source tag as "v1.2.0.dev3"
When calculate_rc runs with current-version "v1.2.0.dev3" and existing tags including "v1.2.0rc1"
Then the RC version is "1.2.0rc2"

### Scenario 4: discover_tag picks highest RC for stable promotion
Given existing RC tags are v1.2.0rc1 and v1.2.0rc2
When discover_tag.py runs with --pattern rc
Then it returns v1.2.0rc2

### Scenario 5: calculate_stable strips RC suffix to base version
Given discover_tag.py resolved the source tag as "v1.2.0rc2"
When calculate_stable runs with current-version "v1.2.0rc2"
Then the stable version is "1.2.0"
And the tag is "v1.2.0"

### Scenario 6: Self-healing from accidental wrong-tag promotion
Given both v1.1.26rc1 (accidental) and v1.2.0rc1 (correct) exist as RC tags
When discover_tag.py runs with --pattern rc
Then it returns v1.2.0rc1 (higher by packaging.Version)
And the stable promotion produces version "1.2.0" (correct, not "1.1.26")

### Scenario 7: Floor override is not applied at RC or stable stages
Given [tool.nwave].public_version is "2.0.0"
And the dev tag being promoted to RC is "v1.2.0.dev2"
When the RC pipeline runs calculate_rc with current-version "v1.2.0.dev2"
Then the RC version is "1.2.0rc1" (floor "2.0.0" is not consulted)
When the stable pipeline runs calculate_stable with current-version "v1.2.0rc1"
Then the stable version is "1.2.0" (floor "2.0.0" is not consulted)

## Acceptance Criteria
- [ ] `discover_tag.py --pattern dev` returns the highest dev tag by `packaging.Version` sort, not lexicographic sort, correctly selecting v1.2.0.dev2 over v1.1.26.dev8
- [ ] Orphaned dev tags (v1.1.26.dev*) from pre-escalation are never selected for RC promotion when a higher-base dev tag exists
- [ ] `calculate_rc` strips the dev suffix to produce the correct RC base version (v1.2.0.dev2 -> 1.2.0rc1)
- [ ] RC counter increments sequentially (rc1, rc2) when multiple RC promotions occur for the same base
- [ ] `discover_tag.py --pattern rc` returns the highest RC tag by `packaging.Version` sort
- [ ] `calculate_stable` strips the RC suffix to produce the correct stable version (v1.2.0rc2 -> 1.2.0)
- [ ] Accidental wrong-tag promotions (e.g., v1.1.26rc1) do not affect stable promotion because discover_tag always selects the highest version
- [ ] Floor override (`[tool.nwave].public_version`) is not consulted during RC or stable calculations
- [ ] The one-click UX works at each stage: user leaves tag field empty, pipeline auto-discovers the correct tag

## Technical Notes
- **No code changes needed**: `discover_tag.py`, `calculate_rc()`, and `calculate_stable()` already handle all these cases correctly. This story adds acceptance scenarios that prove the chain works.
- **discover_tag.py sorting**: Uses `packaging.Version` comparison via `max(matched, key=lambda pair: pair[1])` (line 153). This is semantic sort, not string sort. Version("1.2.0.dev2") > Version("1.1.26.dev8") is True.
- **calculate_rc stripping**: `parsed.major`, `parsed.minor`, `parsed.micro` extracts the base from any pre-release tag (line 163 of next_version.py).
- **calculate_stable stripping**: Same base extraction logic (line 180 of next_version.py).
- **Floor scope**: Floor is read and passed as `--version-floor` only in `release-dev.yml`. The `release-rc.yml` and `release-prod.yml` workflows do not read or pass floor values.
- **Dependency**: This story depends on US-CZ-01 (the --base-version mechanism that feeds into dev tags). The RC and stable pipelines are already implemented.
- **Test approach**: These scenarios can be validated as unit tests against `discover_tag.py` (with `--tag-list` for deterministic input) and `calculate_rc`/`calculate_stable` functions directly.

## Traceability
- **Journey**: `docs/ux/release-commitizen/journey-dev-release.feature` section "US-CZ-04: Full Promotion Chain"
- **Visual**: `docs/ux/release-commitizen/journey-dev-release-visual.md` section "Full Three-Stage Promotion Chain"
- **Workflows**: `.github/workflows/release-rc.yml` (Stage 2), `.github/workflows/release-prod.yml` (Stage 3)
- **Code**: `scripts/release/discover_tag.py`, `scripts/release/next_version.py` (`calculate_rc`, `calculate_stable`)
