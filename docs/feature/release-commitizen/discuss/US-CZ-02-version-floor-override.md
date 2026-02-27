# US-CZ-02: Version Floor Override from pyproject.toml

## Problem (The Pain)
Mike Brissoni and the nwave-ai team need to force a version jump for the public package (e.g., from 1.x to 2.0.0 for a rebranding or major API change) regardless of what conventional commits suggest. Today, the `[tool.nwave].public_version` floor only applies to the nwave-ai stage. There is no way to override the dev release base version when the team decides a higher version is strategically needed. The workaround is waiting until stable release to manually set the version, which means the entire dev/RC cycle carries the wrong version number.

## Who (The User)
- Release engineer (Mike) who needs dev tags to reflect a planned major version jump
- nwave-ai stage automation that uses the floor to control public package versioning
- Team leads who set `public_version` in pyproject.toml to signal version strategy

## Solution (What We Build)
Add `--version-floor` CLI argument to `next_version.py` for the dev stage. When the floor is higher than the CZ-computed (or fallback) base version, the floor becomes the base. This reuses the existing `[tool.nwave].public_version` field, extending its reach from nwave-ai-only to also cover dev releases.

## Domain Examples

### Example 1: Floor overrides CZ when higher (happy path)
The team sets `public_version = "1.3.0"` in pyproject.toml to signal a planned minor bump beyond what commits suggest. Commitizen outputs `1.2.0` (feat commits). The pipeline passes `--base-version 1.2.0 --version-floor 1.3.0`. Since `1.3.0 > 1.2.0`, the floor wins. Dev version: `1.3.0.dev1`.

### Example 2: Floor is ignored when lower than CZ base
The floor is set to `1.1.0` (old value, never updated). Commitizen outputs `1.2.0`. The pipeline passes both. Since `1.1.0 < 1.2.0`, the floor is ignored. Dev version: `1.2.0.dev1`. CZ analysis drives the version as expected.

### Example 3: Floor overrides fallback when CZ fails
Commitizen fails and returns empty. The fallback produces `1.1.23`. The floor is `2.0.0`. Since `2.0.0 > 1.1.23`, the floor wins. Dev version: `2.0.0.dev1`. The team's strategic version intent is preserved even when CZ is unavailable.

### Example 4: Floor and sequential counter
The floor is `1.3.0`, overriding CZ's `1.2.0`. A tag `v1.3.0.dev1` already exists from a previous run. The counter increments: `1.3.0.dev2`.

## UAT Scenarios (BDD)

### Scenario 1: Floor overrides CZ base when higher
Given --base-version is "1.2.0" (from Commitizen)
And --version-floor is "1.3.0" (from pyproject.toml)
And no existing dev tags for version "1.3.0"
When the pipeline runs next_version.py
Then the floor "1.3.0" is selected because it is higher than "1.2.0"
And the dev version is "1.3.0.dev1"

### Scenario 2: Floor is ignored when lower
Given --base-version is "1.2.0"
And --version-floor is "1.1.0"
And no existing dev tags for version "1.2.0"
When the pipeline runs next_version.py
Then the CZ base "1.2.0" is used because the floor "1.1.0" is lower
And the dev version is "1.2.0.dev1"

### Scenario 3: Floor overrides fallback when CZ fails
Given --base-version is "" (CZ failed)
And --version-floor is "2.0.0"
And the current version is "1.1.22"
And no existing dev tags for version "2.0.0"
When the pipeline runs next_version.py
Then the fallback is "1.1.23" but the floor "2.0.0" overrides it
And the dev version is "2.0.0.dev1"

### Scenario 4: Floor and base with existing tags
Given --base-version is "1.2.0"
And --version-floor is "1.3.0"
And a dev tag "v1.3.0.dev1" already exists
When the pipeline runs next_version.py
Then the floor wins with base "1.3.0"
And the dev version is "1.3.0.dev2"

### Scenario 5: Empty floor is treated as no override
Given --base-version is "1.2.0"
And --version-floor is "" (empty)
When the pipeline runs next_version.py
Then the CZ base "1.2.0" is used unchanged
And the dev version is "1.2.0.dev1"

## Acceptance Criteria
- [ ] `--version-floor` CLI argument accepted by next_version.py (optional, default empty)
- [ ] When floor is non-empty and higher than the resolved base, floor becomes the new base
- [ ] When floor is non-empty but lower or equal to the resolved base, floor is ignored
- [ ] When floor is empty, no override is applied (base unchanged)
- [ ] Floor comparison uses `packaging.version.Version` for correct PEP 440 ordering
- [ ] Sequential `.devN` counter works correctly with the floor-resolved base
- [ ] release-dev.yml reads `[tool.nwave].public_version` and passes it as `--version-floor`

## Technical Notes
- Reuses existing `[tool.nwave].public_version` field; no new config needed
- Floor comparison happens after CZ/fallback resolution (step 2 in the priority chain)
- `read_toml_field.py` already exists and can read `tool.nwave.public_version`
- Invalid floor value (not PEP 440) causes exit code 2 with descriptive error
- No changes to `calculate_rc()` or `calculate_stable()`; floor applies to dev stage only
- Dependency: US-CZ-01 must be implemented first (--base-version arg must exist)

## Traceability
- **Journey**: `docs/ux/release-commitizen/journey-dev-release.feature` scenarios 6-9
- **Design**: `docs/release/plan-commitizen-version-calculation.md` (Step 2, version resolution priority)
- **Shared artifacts**: `docs/ux/release-commitizen/shared-artifacts-registry.md` (version_floor artifact)
