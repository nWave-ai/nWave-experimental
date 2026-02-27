# Acceptance Test Specifications: release-commitizen

**Feature**: CZ-Driven Dev Release Version Calculation
**Author**: Quinn (nw-acceptance-designer)
**Date**: 2026-02-26
**Source**: `docs/ux/release-commitizen/journey-dev-release.feature` (33 Gherkin scenarios)

---

## Test Infrastructure

### Driving Ports

All tests invoke production scripts via subprocess (the existing test pattern). No internal function imports; no mocking.

| Script | Pattern | Args |
|--------|---------|------|
| `next_version.py` | `run_next_version(*args)` | `--stage`, `--current-version`, `--existing-tags`, `--base-version`, `--version-floor`, `--no-bump` |
| `discover_tag.py` | `run_discover_tag(*args)` | `--pattern`, `--tag-list`, `--validate` |

### Helpers (reuse existing)

```python
SCRIPT_NV = "scripts/release/next_version.py"
SCRIPT_DT = "scripts/release/discover_tag.py"

def run_next_version(*args) -> subprocess.CompletedProcess
def run_discover_tag(*args) -> subprocess.CompletedProcess
def parse_output(result) -> dict
```

### Output Contract

`next_version.py` returns JSON:
```json
{"version": "1.2.0.dev1", "tag": "v1.2.0.dev1", "base_version": "1.2.0", "pep440_valid": true}
```

`discover_tag.py` returns JSON:
```json
{"tag": "v1.2.0.dev2", "version": "1.2.0.dev2", "found": true, "commits_behind": null}
```

Error responses: `{"error": "message"}` with exit code 1 or 2.

---

## Test File: `tests/release/test_cz_version_calculation.py`

All 33 Gherkin scenarios mapped below. Organized by user story, grouped by roadmap step.

---

## US-CZ-01: CZ-Driven Version Bump (Roadmap Steps 01, 03)

### Class: `TestCZBaseVersionOverride` (Step 01)

Tests that `--base-version` replaces the hardcoded patch bump when provided.

---

**Test 01** `test_feat_commits_produce_minor_bump_via_base_version`
Gherkin: Scenario 1 "feat commits produce minor bump via Commitizen"

```
Given:
  --stage dev
  --current-version "1.1.22"
  --base-version "1.2.0"
  --existing-tags (empty)

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.2.0.dev1"
  output["tag"] == "v1.2.0.dev1"
  output["base_version"] == "1.2.0"
  output["pep440_valid"] is True
  Version(output["version"]).dev == 1
```

**Status**: RED (--base-version arg does not exist yet)

---

**Test 02** `test_fix_commits_produce_patch_bump_via_base_version`
Gherkin: Scenario 2 "fix-only commits produce patch bump via Commitizen"

```
Given:
  --stage dev
  --current-version "1.1.22"
  --base-version "1.1.23"
  --existing-tags (empty)

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.1.23.dev1"
  output["base_version"] == "1.1.23"
```

**Status**: RED

---

**Test 03** `test_breaking_change_produces_major_bump_via_base_version`
Gherkin: Scenario 3 "breaking change produces major bump via Commitizen"

```
Given:
  --stage dev
  --current-version "1.1.22"
  --base-version "2.0.0"
  --existing-tags (empty)

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "2.0.0.dev1"
  output["base_version"] == "2.0.0"
```

**Status**: RED

---

**Test 04** `test_sequential_counter_with_cz_base_version`
Gherkin: Scenario 4 "Sequential counter with CZ base version"

```
Given:
  --stage dev
  --current-version "1.1.22"
  --base-version "1.2.0"
  --existing-tags "v1.2.0.dev1"

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.2.0.dev2"
```

**Status**: RED

---

**Test 05** `test_empty_base_version_falls_back_to_patch_bump`
Gherkin: Scenario 5 "Empty base-version falls back to patch bump"

```
Given:
  --stage dev
  --current-version "1.1.22"
  --base-version ""
  --existing-tags (empty)

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.1.23.dev1"
  output["base_version"] == "1.1.23"
```

Note: Empty --base-version means the fallback _bump_patch is used. This preserves backward compatibility.

**Status**: RED (--base-version arg does not exist; but the fallback behavior matches current code)

---

### Class: `TestMidCycleEscalation` (Step 03)

Tests that when the base version changes mid-cycle (e.g., patch to minor), the dev counter resets because `_highest_counter` filters by base version string.

---

**Test 06** `test_patch_to_minor_escalation_resets_counter`
Gherkin: Scenario 6 "Patch-to-minor escalation resets dev counter mid-cycle"

```
Given:
  --stage dev
  --current-version "1.1.25"
  --base-version "1.2.0"
  --existing-tags "v1.1.26.dev1,v1.1.26.dev2,v1.1.26.dev3,v1.1.26.dev4,v1.1.26.dev5,v1.1.26.dev6,v1.1.26.dev7,v1.1.26.dev8"

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.2.0.dev1"
  output["base_version"] == "1.2.0"
```

Rationale: No v1.2.0.dev* tags exist, so counter starts at 1. The 8 v1.1.26.dev* tags are invisible because `_highest_counter` filters by base "1.2.0".

**Status**: RED

---

**Test 07** `test_patch_to_major_escalation_resets_counter`
Gherkin: Scenario 7 "Patch-to-major escalation resets dev counter mid-cycle"

```
Given:
  --stage dev
  --current-version "1.1.25"
  --base-version "2.0.0"
  --existing-tags "v1.1.26.dev1,v1.1.26.dev2,v1.1.26.dev3"

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "2.0.0.dev1"
  output["base_version"] == "2.0.0"
```

**Status**: RED

---

**Test 08** `test_minor_to_major_escalation_resets_counter`
Gherkin: Scenario 8 "Minor-to-major escalation resets dev counter mid-cycle"

```
Given:
  --stage dev
  --current-version "1.1.25"
  --base-version "2.0.0"
  --existing-tags "v1.2.0.dev1,v1.2.0.dev2,v1.2.0.dev3,v1.2.0.dev4"

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "2.0.0.dev1"
  output["base_version"] == "2.0.0"
```

**Status**: RED

---

**Test 09** `test_reverted_feat_does_not_deescalate`
Gherkin: Scenario 9 "Reverted feat commit does not de-escalate"

This test validates that CZ outputs "1.2.0" even after a revert. Since CZ is external and we test `next_version.py` (not CZ itself), this test proves that passing --base-version "1.2.0" still works correctly after a revert scenario. The Gherkin's "CZ scans ALL commits" is CZ's responsibility; we test the pipeline side.

```
Given:
  --stage dev
  --current-version "1.1.25"
  --base-version "1.2.0"
  --existing-tags "v1.2.0.dev1"

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.2.0.dev2"
```

Note: The key insight is that CZ will still output "1.2.0" because the original feat: is in history. The test validates that next_version.py correctly handles the sequential counter, trusting the CZ-provided base.

**Status**: RED

---

**Test 10** `test_multiple_base_versions_coexist_after_escalation`
Gherkin: Scenario 10 "Multiple base versions coexist in tags after escalation"

```
Given:
  --stage dev
  --current-version "1.1.25"
  --base-version "1.2.0"
  --existing-tags "v1.1.26.dev1,v1.1.26.dev2,v1.1.26.dev3,v1.1.26.dev4,v1.1.26.dev5,v1.1.26.dev6,v1.1.26.dev7,v1.1.26.dev8,v1.2.0.dev1"

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.2.0.dev2"
  output["base_version"] == "1.2.0"
```

Rationale: `_highest_counter` matches only v1.2.0.dev* (one tag, counter=1). Next is dev2. The 8 v1.1.26.dev* tags are ignored.

**Status**: RED

---

**Test 11** `test_rc_promotion_after_escalation_uses_highest_base`
Gherkin: Scenario 11 "RC promotion after mid-cycle escalation uses highest base"

This scenario spans discover_tag + calculate_rc. Split into two sub-assertions.

```
Sub-test A (discover_tag):
  --pattern dev
  --tag-list "v1.1.26.dev1,v1.1.26.dev2,v1.1.26.dev3,v1.1.26.dev4,v1.1.26.dev5,v1.1.26.dev6,v1.1.26.dev7,v1.1.26.dev8,v1.2.0.dev1,v1.2.0.dev2"

  Then:
    output["tag"] == "v1.2.0.dev2"

Sub-test B (calculate_rc):
  --stage rc
  --current-version "v1.2.0.dev2"
  --existing-tags (empty)

  Then:
    output["version"] == "1.2.0rc1"
    output["base_version"] == "1.2.0"
```

**Status**: RED (discover_tag part already works; calculate_rc part already works; but the combined scenario needs explicit coverage)

---

## US-CZ-02: Version Floor Override (Roadmap Step 02)

### Class: `TestVersionFloorOverride`

Tests the `--version-floor` CLI argument and its interaction with `--base-version`.

---

**Test 12** `test_floor_overrides_cz_base_when_higher`
Gherkin: Scenario 12 "Floor overrides CZ when floor is higher"

```
Given:
  --stage dev
  --current-version "1.1.22"
  --base-version "1.2.0"
  --version-floor "1.3.0"
  --existing-tags (empty)

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.3.0.dev1"
  output["base_version"] == "1.3.0"
```

Rationale: Floor "1.3.0" > CZ base "1.2.0", so floor wins.

**Status**: RED

---

**Test 13** `test_floor_ignored_when_lower_than_cz_base`
Gherkin: Scenario 13 "Floor is ignored when lower than CZ base"

```
Given:
  --stage dev
  --current-version "1.1.22"
  --base-version "1.2.0"
  --version-floor "1.1.0"
  --existing-tags (empty)

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.2.0.dev1"
  output["base_version"] == "1.2.0"
```

**Status**: RED

---

**Test 14** `test_floor_overrides_fallback_when_cz_fails`
Gherkin: Scenario 14 "Floor overrides fallback when CZ fails"

```
Given:
  --stage dev
  --current-version "1.1.22"
  --base-version ""
  --version-floor "2.0.0"
  --existing-tags (empty)

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "2.0.0.dev1"
  output["base_version"] == "2.0.0"
```

Rationale: Empty base triggers fallback to _bump_patch("1.1.22") = "1.1.23". Floor "2.0.0" > "1.1.23", so floor wins.

**Status**: RED

---

**Test 15** `test_floor_and_cz_base_with_existing_tags`
Gherkin: Scenario 15 "Floor and CZ base with existing tags combine correctly"

```
Given:
  --stage dev
  --current-version "1.1.22"
  --base-version "1.2.0"
  --version-floor "1.3.0"
  --existing-tags "v1.3.0.dev1"

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.3.0.dev2"
  output["base_version"] == "1.3.0"
```

Rationale: Floor wins (1.3.0 > 1.2.0). Existing tag v1.3.0.dev1 means counter is 2.

**Status**: RED

---

## US-CZ-03: Graceful Fallback (Roadmap Steps 01, 02)

### Class: `TestGracefulFallback`

Tests error handling and fallback paths. These tests validate input validation within `next_version.py`.

---

**Test 16** `test_cz_not_installed_empty_base_falls_back`
Gherkin: Scenario 16 "CZ not installed falls back gracefully"

This scenario is a pipeline-level integration test. The next_version.py part is: empty --base-version triggers fallback. Same as Test 05, but framed from the "CZ failure" perspective.

```
Given:
  --stage dev
  --current-version "1.1.22"
  --base-version ""
  --existing-tags (empty)

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.1.23.dev1"
```

Note: The CZ step failure and `|| BASE=""` absorption is a workflow concern (Step 04). This test validates the next_version.py fallback path.

**Status**: RED (shares implementation with Test 05)

---

**Test 17** `test_cz_config_missing_empty_base_falls_back`
Gherkin: Scenario 17 "CZ config missing falls back gracefully"

```
Given:
  --stage dev
  --current-version "1.1.22"
  --base-version ""
  --existing-tags (empty)

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.1.23.dev1"
```

Note: Identical to Test 16 from next_version.py's perspective. The difference is the CZ failure reason (config missing vs not installed), which is a workflow concern. This test confirms the fallback path is consistent regardless of why CZ produced an empty string.

**Status**: RED (shares implementation with Test 05)

---

**Test 18** `test_invalid_base_version_rejected_with_exit_code_2`
Gherkin: Scenario 18 "Invalid base-version is rejected"

```
Given:
  --stage dev
  --current-version "1.1.22"
  --base-version "not-a-version"

When: run next_version.py with above args

Then:
  exit code == 2
  output["error"] contains "Invalid base-version"
  output["error"] contains "not PEP 440 compliant" OR "PEP 440"
```

**Status**: RED

---

**Test 19** `test_invalid_version_floor_rejected_with_exit_code_2`
Gherkin: Scenario 19 "Invalid version-floor is rejected"

```
Given:
  --stage dev
  --current-version "1.1.22"
  --base-version "1.2.0"
  --version-floor "abc"

When: run next_version.py with above args

Then:
  exit code == 2
  output["error"] contains "Invalid version-floor"
```

**Status**: RED

---

## US-CZ-04: Full Promotion Chain (Roadmap Step 05)

### Class: `TestPromotionChainDevToRC`

Tests discover_tag.py and calculate_rc behavior after mid-cycle escalation.

---

**Test 20** `test_discover_tag_picks_highest_dev_after_escalation`
Gherkin: Scenario 20 "Dev to RC promotion after mid-cycle escalation uses highest dev tag"

```
Given:
  --pattern dev
  --tag-list "v1.1.26.dev1,v1.1.26.dev2,v1.1.26.dev3,v1.1.26.dev4,v1.1.26.dev5,v1.1.26.dev6,v1.1.26.dev7,v1.1.26.dev8,v1.2.0.dev1,v1.2.0.dev2"

When: run discover_tag.py with above args

Then:
  exit code == 0
  output["found"] is True
  output["tag"] == "v1.2.0.dev2"
  output["version"] == "1.2.0.dev2"
```

Rationale: packaging.Version("1.2.0.dev2") > packaging.Version("1.1.26.dev8"). String sort would incorrectly pick v1.1.26.dev8.

**Status**: GREEN (discover_tag.py already uses packaging.Version sort)

---

**Test 21** `test_orphaned_dev_tags_ignored_by_discover_tag`
Gherkin: Scenario 21 "Orphaned dev tags from pre-escalation base are ignored by discover_tag"

```
Given:
  --pattern dev
  --tag-list "v1.1.26.dev1,v1.1.26.dev2,v1.1.26.dev3,v1.1.26.dev4,v1.1.26.dev5,v1.1.26.dev6,v1.1.26.dev7,v1.1.26.dev8,v1.2.0.dev1,v1.2.0.dev2"

When: run discover_tag.py with above args

Then:
  output["tag"] == "v1.2.0.dev2"
  # v1.1.26.dev* are present in the list but never selected as the highest
```

Note: discover_tag returns the single highest tag; it does not "ignore" tags, it just sorts correctly. This test is behaviorally identical to Test 20 but the Gherkin framing emphasizes the orphaned tags.

**Status**: GREEN (can be parametrized with Test 20)

---

**Test 22** `test_sequential_rc_counter_increments`
Gherkin: Scenario 22 "Sequential RC counter increments on repeated promotion"

```
Given:
  --stage rc
  --current-version "v1.2.0.dev3"
  --existing-tags "v1.2.0rc1"

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.2.0rc2"
  output["base_version"] == "1.2.0"
```

**Status**: GREEN (calculate_rc already handles this; existing test `test_rc_version_sequential_counter` covers the pattern)

---

**Test 23** `test_rc_to_stable_strips_rc_suffix`
Gherkin: Scenario 23 "RC to stable promotion strips RC suffix"

```
Sub-test A (discover_tag):
  --pattern rc
  --tag-list "v1.2.0rc1,v1.2.0rc2"

  Then:
    output["tag"] == "v1.2.0rc2"

Sub-test B (calculate_stable):
  --stage stable
  --current-version "v1.2.0rc2"

  Then:
    output["version"] == "1.2.0"
    output["tag"] == "v1.2.0"
```

**Status**: GREEN (both discover_tag and calculate_stable already handle this)

---

**Test 24** `test_wrong_tag_promotion_self_heals_at_stable`
Gherkin: Scenario 24 "Accidental wrong-tag RC promotion self-heals at stable stage"

```
Given:
  --pattern rc
  --tag-list "v1.1.26rc1,v1.2.0rc1"

When: run discover_tag.py with above args

Then:
  output["tag"] == "v1.2.0rc1"
  # v1.1.26rc1 (from accidental promotion) is not selected

Follow-up:
  --stage stable
  --current-version "v1.2.0rc1"

  Then:
    output["version"] == "1.2.0"
```

Rationale: packaging.Version("1.2.0rc1") > packaging.Version("1.1.26rc1"). The accidental promotion to v1.1.26rc1 is harmless because discover_tag always picks the highest.

**Status**: GREEN

---

**Test 25** `test_floor_not_consulted_at_rc_stage`
Gherkin: Scenario 25 "Floor override does not affect RC or stable stages"

```
Given:
  --stage rc
  --current-version "v1.2.0.dev2"
  --existing-tags (empty)

When: run next_version.py with above args
  (Note: --version-floor is NOT passed to RC stage at all;
   the test verifies that calculate_rc produces "1.2.0rc1"
   regardless of any floor value that might exist in pyproject.toml)

Then:
  exit code == 0
  output["version"] == "1.2.0rc1"
  output["base_version"] == "1.2.0"
```

Note: This is a "negative" test: we verify that RC calculation derives its base from the dev tag suffix, not from any floor. The floor arg is not accepted by `--stage rc`.

**Status**: GREEN (calculate_rc already ignores floor; it strips the dev suffix)

---

**Test 26** `test_floor_not_consulted_at_stable_stage`
Gherkin: Scenario 25 (continued) "Floor override does not affect stable stages"

```
Given:
  --stage stable
  --current-version "v1.2.0rc1"

When: run next_version.py with above args

Then:
  exit code == 0
  output["version"] == "1.2.0"
```

**Status**: GREEN

---

**Test 27** `test_full_three_stage_promotion_chain`
Gherkin: Scenario 26 "Full three-stage promotion chain with one-click UX"

This is the **walking skeleton** for the promotion chain. It exercises all three stages sequentially with the same version lineage.

```
Stage 1 (Dev):
  --stage dev
  --current-version "1.1.25"
  --base-version "1.2.0"
  --existing-tags "v1.2.0.dev1"

  Then: output["version"] == "1.2.0.dev2"

Stage 2 (discover + RC):
  discover_tag.py --pattern dev --tag-list "v1.2.0.dev1,v1.2.0.dev2"
  Then: output["tag"] == "v1.2.0.dev2"

  next_version.py --stage rc --current-version "v1.2.0.dev2"
  Then: output["version"] == "1.2.0rc1"

Stage 3 (discover + Stable):
  discover_tag.py --pattern rc --tag-list "v1.2.0rc1"
  Then: output["tag"] == "v1.2.0rc1"

  next_version.py --stage stable --current-version "v1.2.0rc1"
  Then: output["version"] == "1.2.0"
  Then: output["tag"] == "v1.2.0"
```

This test validates the complete chain: dev -> RC -> stable, proving that version lineage is preserved across all three stages.

**Status**: RED (Stage 1 requires --base-version; Stages 2-3 already work)

---

## US-CZ-05: PSR-to-CZ Migration (Roadmap Steps 06, 07, 08)

### Class: `TestCZConfigExpansion` (Step 06)

These are **config verification tests**, not functional tests. They read files and assert content.

---

**Test 28** `test_cz_config_includes_version_files`
Gherkin: Scenario 27 "CZ config includes version_files for all PSR-managed files"

```
Given: pyproject.toml exists at the repo root

When: parse pyproject.toml with tomllib

Then:
  config = toml["tool"]["commitizen"]
  "nWave/VERSION" in config["version_files"]
  "nWave/framework-catalog.yaml:version" in config["version_files"]
  config["changelog_file"] == "CHANGELOG.md"
```

**Status**: RED

---

**Test 29** `test_releaserc_file_removed`
Gherkin: Scenario 28 ".releaserc file is removed from the repository"

```
Given: repo root path

When: check file existence

Then:
  Path(".releaserc").exists() is False
```

**Status**: RED (file currently exists)

---

**Test 30** `test_psr_config_sections_removed_from_pyproject`
Gherkin: Scenario 29 "PSR config sections removed from pyproject.toml"

```
Given: pyproject.toml exists at the repo root

When: parse pyproject.toml with tomllib

Then:
  "semantic_release" not in toml.get("tool", {})
  "commitizen" in toml["tool"]
```

**Status**: RED

---

**Test 31** `test_psr_removed_from_dev_dependencies`
Gherkin: Scenario 30 "python-semantic-release removed from dev dependencies"

```
Given: pyproject.toml exists at the repo root

When: read the [project.optional-dependencies].dev list

Then:
  no entry contains "python-semantic-release"
  at least one entry contains "commitizen"
```

**Status**: RED

---

### Class: `TestLegacyWorkflowMigration` (Step 07)

These tests verify workflow YAML content after PSR-to-CZ migration.

---

**Test 32** `test_release_yml_uses_cz_bump_instead_of_psr`
Gherkin: Scenario 31 "Legacy release.yml uses CZ instead of PSR for version bump"

```
Given: .github/workflows/release.yml exists

When: read file content as string

Then:
  "cz bump" in content
  "semantic-release version" not in content
  "cz bump --dry-run" in content
  "python-semantic-release" not in content
```

Note: Also verify force-bump uses `cz bump --increment`.

**Status**: RED

---

**Test 33** `test_cz_changelog_generation_configured`
Gherkin: Scenario 32 "CZ generates changelog during stable release"

```
Given: pyproject.toml [tool.commitizen] section exists

When: parse config

Then:
  config["changelog_file"] == "CHANGELOG.md"

Given: .gitignore exists

When: read file content

Then:
  "CHANGELOG.md" in content
```

**Status**: RED (changelog_file not yet in config)

---

### Class: `TestCIDocumentationCleanup` (Step 08)

---

**Test 34** `test_ci_yml_references_commitizen_not_psr`
Gherkin: Scenario 33 "CI and documentation references updated from PSR to CZ"

```
Given: .github/workflows/ci.yml exists

When: read file content as string

Then:
  "python-semantic-release" not in content
  "commitizen" in content (in the version-drift context)
```

**Status**: RED

---

## Additional Parametrized Tests

Some Gherkin scenarios can be efficiently combined via `pytest.mark.parametrize`.

### Parametrized: `test_base_version_produces_correct_dev_version`

Combines Tests 01-03 into a single parametrized test.

```python
@pytest.mark.parametrize(
    "base_version, expected_dev",
    [
        pytest.param("1.2.0", "1.2.0.dev1", id="feat-minor-bump"),
        pytest.param("1.1.23", "1.1.23.dev1", id="fix-patch-bump"),
        pytest.param("2.0.0", "2.0.0.dev1", id="breaking-major-bump"),
    ],
)
```

### Parametrized: `test_escalation_resets_counter`

Combines Tests 06-08 into a single parametrized test.

```python
@pytest.mark.parametrize(
    "base_version, existing_tags, expected_dev",
    [
        pytest.param(
            "1.2.0",
            "v1.1.26.dev1,...,v1.1.26.dev8",
            "1.2.0.dev1",
            id="patch-to-minor",
        ),
        pytest.param(
            "2.0.0",
            "v1.1.26.dev1,v1.1.26.dev2,v1.1.26.dev3",
            "2.0.0.dev1",
            id="patch-to-major",
        ),
        pytest.param(
            "2.0.0",
            "v1.2.0.dev1,...,v1.2.0.dev4",
            "2.0.0.dev1",
            id="minor-to-major",
        ),
    ],
)
```

---

## Walking Skeletons

Three walking skeletons that prove observable user value end-to-end:

| # | Skeleton | Tests | User Goal |
|---|----------|-------|-----------|
| 1 | CZ base version override | Test 01 | "My feat: commits produce a minor bump dev release" |
| 2 | Version floor override | Test 12 | "My strategic version floor controls the dev release" |
| 3 | Full promotion chain | Test 27 | "I can promote dev to RC to stable with correct versions" |

These three skeletons should be enabled first, in order. Each proves a distinct user journey is working.

---

## Error Path Summary

| Test | Error Scenario |
|------|---------------|
| 05, 16, 17 | Empty base-version fallback (CZ failure modes) |
| 18 | Invalid base-version rejected |
| 19 | Invalid version-floor rejected |
| 24 | Wrong-tag promotion self-heals |
| 14 | Floor overrides fallback (CZ empty + floor present) |

**Error path ratio**: 7 of 34 test specs = 20.6% at the test level. However, the Gherkin scenarios include 4 error scenarios (16, 17, 18, 19) out of 33 = 12.1%. The additional error coverage comes from the escalation tests (06-10) which test boundary behavior, and the self-healing test (24) which tests recovery. Counting boundary and recovery scenarios, the effective error/edge ratio is 13/34 = 38.2%.

---

## Implementation Sequence

The Crafter should enable tests in this order (one at a time):

1. **Test 01** (walking skeleton 1): feat base-version produces minor dev
2. **Test 05**: empty base-version fallback
3. **Test 04**: sequential counter with CZ base
4. **Test 02, 03**: parametrized bump levels
5. **Test 18**: invalid base-version rejection
6. **Test 12** (walking skeleton 2): floor override
7. **Test 13**: floor ignored when lower
8. **Test 14**: floor overrides fallback
9. **Test 15**: floor + existing tags
10. **Test 19**: invalid floor rejection
11. **Test 06-08**: mid-cycle escalation (parametrized)
12. **Test 09-10**: revert non-de-escalation + tag coexistence
13. **Test 11**: RC promotion after escalation
14. **Test 20-21**: discover_tag picks highest after escalation
15. **Test 22-23**: RC counter + stable stripping
16. **Test 24**: self-healing
17. **Test 25-26**: floor not consulted at RC/stable
18. **Test 27** (walking skeleton 3): full three-stage chain
19. **Tests 28-34**: config/migration verification (Steps 06-08)

---

## Fixture Additions for `conftest.py`

```python
@pytest.fixture()
def escalation_tags_patch_to_minor() -> list[str]:
    """8 patch-base dev tags + 0 minor-base dev tags.
    Simulates mid-cycle escalation from fix-only to feat:.
    """
    return [f"v1.1.26.dev{n}" for n in range(1, 9)]


@pytest.fixture()
def escalation_tags_mixed_bases() -> list[str]:
    """8 patch-base + 1 minor-base dev tags.
    Simulates state after first minor-base dev release post-escalation.
    """
    return [f"v1.1.26.dev{n}" for n in range(1, 9)] + ["v1.2.0.dev1"]


@pytest.fixture()
def promotion_chain_dev_tags() -> list[str]:
    """Dev tags for full promotion chain test.
    Includes both orphaned patch-base and active minor-base tags.
    """
    return [f"v1.1.26.dev{n}" for n in range(1, 9)] + [
        "v1.2.0.dev1",
        "v1.2.0.dev2",
    ]
```
