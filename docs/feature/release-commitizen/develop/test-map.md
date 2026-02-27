# Traceability Matrix: release-commitizen

**Author**: Quinn (nw-acceptance-designer)
**Date**: 2026-02-26

Maps every Gherkin scenario to its test specification, roadmap step, and user story.

---

## Full Matrix

| # | Gherkin Scenario | Test Function | Test Class | Roadmap Step | US | Status |
|---|-----------------|---------------|------------|-------------|-----|--------|
| 01 | feat commits produce minor bump via Commitizen | `test_feat_commits_produce_minor_bump_via_base_version` | `TestCZBaseVersionOverride` | step_01 | CZ-01 | RED |
| 02 | fix-only commits produce patch bump via Commitizen | `test_fix_commits_produce_patch_bump_via_base_version` | `TestCZBaseVersionOverride` | step_01 | CZ-01 | RED |
| 03 | breaking change produces major bump via Commitizen | `test_breaking_change_produces_major_bump_via_base_version` | `TestCZBaseVersionOverride` | step_01 | CZ-01 | RED |
| 04 | Sequential counter with CZ base version | `test_sequential_counter_with_cz_base_version` | `TestCZBaseVersionOverride` | step_01 | CZ-01 | RED |
| 05 | Empty base-version falls back to patch bump | `test_empty_base_version_falls_back_to_patch_bump` | `TestCZBaseVersionOverride` | step_01 | CZ-01 | RED |
| 06 | Patch-to-minor escalation resets dev counter mid-cycle | `test_patch_to_minor_escalation_resets_counter` | `TestMidCycleEscalation` | step_03 | CZ-01 | RED |
| 07 | Patch-to-major escalation resets dev counter mid-cycle | `test_patch_to_major_escalation_resets_counter` | `TestMidCycleEscalation` | step_03 | CZ-01 | RED |
| 08 | Minor-to-major escalation resets dev counter mid-cycle | `test_minor_to_major_escalation_resets_counter` | `TestMidCycleEscalation` | step_03 | CZ-01 | RED |
| 09 | Reverted feat commit does not de-escalate | `test_reverted_feat_does_not_deescalate` | `TestMidCycleEscalation` | step_03 | CZ-01 | RED |
| 10 | Multiple base versions coexist in tags after escalation | `test_multiple_base_versions_coexist_after_escalation` | `TestMidCycleEscalation` | step_03 | CZ-01 | RED |
| 11 | RC promotion after mid-cycle escalation uses highest base | `test_rc_promotion_after_escalation_uses_highest_base` | `TestMidCycleEscalation` | step_03 | CZ-01 | RED |
| 12 | Floor overrides CZ when floor is higher | `test_floor_overrides_cz_base_when_higher` | `TestVersionFloorOverride` | step_02 | CZ-02 | RED |
| 13 | Floor is ignored when lower than CZ base | `test_floor_ignored_when_lower_than_cz_base` | `TestVersionFloorOverride` | step_02 | CZ-02 | RED |
| 14 | Floor overrides fallback when CZ fails | `test_floor_overrides_fallback_when_cz_fails` | `TestVersionFloorOverride` | step_02 | CZ-02 | RED |
| 15 | Floor and CZ base with existing tags combine correctly | `test_floor_and_cz_base_with_existing_tags` | `TestVersionFloorOverride` | step_02 | CZ-02 | RED |
| 16 | CZ not installed falls back gracefully | `test_cz_not_installed_empty_base_falls_back` | `TestGracefulFallback` | step_01 | CZ-03 | RED |
| 17 | CZ config missing falls back gracefully | `test_cz_config_missing_empty_base_falls_back` | `TestGracefulFallback` | step_01 | CZ-03 | RED |
| 18 | Invalid base-version is rejected | `test_invalid_base_version_rejected_with_exit_code_2` | `TestGracefulFallback` | step_01 | CZ-03 | RED |
| 19 | Invalid version-floor is rejected | `test_invalid_version_floor_rejected_with_exit_code_2` | `TestGracefulFallback` | step_02 | CZ-03 | RED |
| 20 | Dev to RC promotion after mid-cycle escalation | `test_discover_tag_picks_highest_dev_after_escalation` | `TestPromotionChainDevToRC` | step_05 | CZ-04 | GREEN |
| 21 | Orphaned dev tags from pre-escalation base ignored | `test_orphaned_dev_tags_ignored_by_discover_tag` | `TestPromotionChainDevToRC` | step_05 | CZ-04 | GREEN |
| 22 | Sequential RC counter increments on repeated promotion | `test_sequential_rc_counter_increments` | `TestPromotionChainDevToRC` | step_05 | CZ-04 | GREEN |
| 23 | RC to stable promotion strips RC suffix | `test_rc_to_stable_strips_rc_suffix` | `TestPromotionChainDevToRC` | step_05 | CZ-04 | GREEN |
| 24 | Accidental wrong-tag RC promotion self-heals | `test_wrong_tag_promotion_self_heals_at_stable` | `TestPromotionChainDevToRC` | step_05 | CZ-04 | GREEN |
| 25 | Floor override does not affect RC stage | `test_floor_not_consulted_at_rc_stage` | `TestPromotionChainDevToRC` | step_05 | CZ-04 | GREEN |
| 26 | Floor override does not affect stable stage | `test_floor_not_consulted_at_stable_stage` | `TestPromotionChainDevToRC` | step_05 | CZ-04 | GREEN |
| 27 | Full three-stage promotion chain with one-click UX | `test_full_three_stage_promotion_chain` | `TestPromotionChainDevToRC` | step_05 | CZ-04 | RED |
| 28 | CZ config includes version_files | `test_cz_config_includes_version_files` | `TestCZConfigExpansion` | step_06 | CZ-05 | RED |
| 29 | .releaserc file is removed | `test_releaserc_file_removed` | `TestCZConfigExpansion` | step_06 | CZ-05 | RED |
| 30 | PSR config sections removed from pyproject.toml | `test_psr_config_sections_removed_from_pyproject` | `TestCZConfigExpansion` | step_06 | CZ-05 | RED |
| 31 | python-semantic-release removed from dev deps | `test_psr_removed_from_dev_dependencies` | `TestCZConfigExpansion` | step_06 | CZ-05 | RED |
| 32 | Legacy release.yml uses CZ instead of PSR | `test_release_yml_uses_cz_bump_instead_of_psr` | `TestLegacyWorkflowMigration` | step_07 | CZ-05 | RED |
| 33 | CZ generates changelog during stable release | `test_cz_changelog_generation_configured` | `TestLegacyWorkflowMigration` | step_07 | CZ-05 | RED |
| 34 | CI and documentation references updated | `test_ci_yml_references_commitizen_not_psr` | `TestCIDocumentationCleanup` | step_08 | CZ-05 | RED |

---

## Coverage by User Story

| User Story | Gherkin Scenarios | Test Count | GREEN | RED |
|-----------|-------------------|------------|-------|-----|
| US-CZ-01 | 1-11 | 11 | 0 | 11 |
| US-CZ-02 | 12-15 | 4 | 0 | 4 |
| US-CZ-03 | 16-19 | 4 | 0 | 4 |
| US-CZ-04 | 20-27 | 8 | 7 | 1 |
| US-CZ-05 | 28-34 | 7 | 0 | 7 |
| **Total** | | **34** | **7** | **27** |

---

## Coverage by Roadmap Step

| Roadmap Step | Tests | Status |
|-------------|-------|--------|
| step_01: CZ config + --base-version | 01-05, 16-18 | RED (all require --base-version arg) |
| step_02: Version floor override | 12-15, 19 | RED (all require --version-floor arg) |
| step_03: Mid-cycle escalation validation | 06-11 | RED (require --base-version arg) |
| step_04: Workflow wiring (release-dev.yml) | (no script-level tests; workflow YAML changes) | N/A |
| step_05: Full promotion chain | 20-27 | 7 GREEN, 1 RED |
| step_06: CZ config expansion + PSR removal | 28-31 | RED (config changes pending) |
| step_07: Legacy release.yml migration | 32-33 | RED (workflow changes pending) |
| step_08: CI/docs reference cleanup | 34 | RED (message changes pending) |

---

## Walking Skeletons

| # | Test | Description | Validates |
|---|------|-------------|-----------|
| 1 | Test 01 | CZ base version produces correct dev release | "My feat: commits produce 1.2.0.dev1, not 1.1.23.dev1" |
| 2 | Test 12 | Floor overrides CZ base when higher | "My strategic version floor controls the dev release" |
| 3 | Test 27 | Full dev -> RC -> stable chain | "I promote through all stages with correct version lineage" |

---

## Dependency Graph (Test Enable Order)

```
Test 01 (walking skeleton 1)
  |
  +-- Test 05 (empty fallback)
  +-- Test 04 (sequential counter)
  +-- Test 02, 03 (bump levels)
  +-- Test 18 (invalid base-version)
  |
  +-- Test 12 (walking skeleton 2, requires --version-floor)
  |     +-- Test 13 (floor ignored)
  |     +-- Test 14 (floor overrides fallback)
  |     +-- Test 15 (floor + tags)
  |     +-- Test 19 (invalid floor)
  |
  +-- Tests 06-11 (escalation, requires --base-version)
  |
  +-- Tests 20-26 (promotion chain, most already GREEN)
  |
  +-- Test 27 (walking skeleton 3, requires --base-version)
  |
  +-- Tests 28-34 (config/migration, independent of script changes)
```

---

## Mandate Compliance Evidence

### CM-A: Driving Port Usage

All tests invoke scripts via subprocess (the project's established driving port pattern):

- `run_next_version("--stage", "dev", "--base-version", "1.2.0", ...)`
- `run_discover_tag("--pattern", "dev", "--tag-list", "v1.2.0.dev1,...")`

No internal function imports. No mock objects. Production code executed through its CLI interface.

### CM-B: Zero Technical Terms in Gherkin

The feature file (`journey-dev-release.feature`) uses exclusively business language:

- "pipeline runs next_version.py" (not "subprocess.run calls Python")
- "dev version is 1.2.0.dev1" (not "JSON output contains key version")
- "Commitizen outputs 1.2.0" (not "cz returns exit code 0 with stdout")
- "floor wins" (not "Version comparison returns True")

One borderline term: "PEP 440 format" appears in Scenario 1; this is domain language for the release engineering context (like saying "ISO 8601" for dates).

### CM-C: Walking Skeleton + Focused Scenario Count

- Walking skeletons: **3** (Tests 01, 12, 27)
- Focused scenarios: **31** (Tests 02-11, 13-26, 28-34)
- Total: **34 test specifications** covering **33 Gherkin scenarios** (scenario 25 maps to 2 tests: RC and stable)
