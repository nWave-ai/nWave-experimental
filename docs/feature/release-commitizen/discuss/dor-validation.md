# Definition of Ready Validation: release-commitizen Epic

**Date**: 2026-02-25
**Validator**: Luna (nw-product-owner)

---

## US-CZ-01: Dev Release Version Reflects Conventional Commit Types

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "4 feat: commits produce v1.1.23.dev2 instead of v1.2.0.dev1" -- specific pain with real version numbers |
| 2 | User/persona with specific characteristics | PASS | Mike Brissoni (release engineer), Ale (developer pushing feat: mid-cycle). Both named with specific roles. |
| 3 | 3+ domain examples with real data | PASS | 8 examples: feat/minor, fix/patch, breaking/major, sequential counter, empty fallback, **mid-cycle patch-to-minor escalation (Mike+Ale scenario)**, reverted feat (no de-escalation), RC promotion after escalation |
| 4 | UAT in Given/When/Then (3-7 scenarios) | PASS | 7 scenarios: 5 original + 2 new (mid-cycle escalation resets counter, multiple base versions coexist). Feature file has 6 additional detailed Gherkin scenarios in US-CZ-01b section. |
| 5 | AC derived from UAT | PASS | 9 AC items. New items: counter reset on base change, tag coexistence safety. Each traceable to UAT. |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | 7 UAT scenarios in the story. Mid-cycle escalation requires no new code (existing `_highest_counter` base-filtering handles it naturally). ~1-2 days effort. |
| 7 | Technical notes: constraints/dependencies | PASS | Original notes + 3 new: mid-cycle escalation mechanism (CZ re-scan + counter filtering), de-escalation impossibility, tag coexistence safety. |
| 8 | Dependencies resolved or tracked | PASS | commitizen already a dev dependency; pyproject.toml config is Step 1 of this story |

**Result: PASS (8/8)**

### Change Log (2026-02-26)
Added mid-cycle bump escalation coverage per Mike's review:
- 3 new domain examples (6, 7, 8) covering patch-to-minor escalation, revert non-de-escalation, RC promotion path
- 2 new UAT scenarios (6, 7) covering counter reset on base change and multi-base tag coexistence
- 2 new AC items covering counter reset and tag coexistence
- 6 new Gherkin scenarios in feature file (US-CZ-01b section) covering all escalation permutations
- Technical notes expanded with escalation mechanism details

---

## US-CZ-02: Version Floor Override from pyproject.toml

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "no way to override the dev release base version when the team decides a higher version is strategically needed" |
| 2 | User/persona with specific characteristics | PASS | Mike (release engineer), nwave-ai automation (floor consumer), team leads (set public_version) |
| 3 | 3+ domain examples with real data | PASS | 4 examples: floor overrides CZ, floor ignored, floor overrides fallback, floor with counter |
| 4 | UAT in Given/When/Then (3-7 scenarios) | PASS | 5 scenarios covering override, ignore, fallback override, counter, empty floor |
| 5 | AC derived from UAT | PASS | 7 AC items covering floor comparison logic, empty handling, PEP 440 ordering |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | 5 scenarios, ~1 day effort (add CLI arg + comparison logic + workflow step) |
| 7 | Technical notes: constraints/dependencies | PASS | Reuses existing field, read_toml_field.py exists, dev-stage only, validation behavior |
| 8 | Dependencies resolved or tracked | PASS | Depends on US-CZ-01 (--base-version arg must exist first); tracked in Technical Notes |

**Result: PASS (8/8)**

---

## US-CZ-03: Graceful Fallback When Commitizen Fails

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "pipeline must not fail when CZ has a transient issue" -- clear safety net requirement |
| 2 | User/persona with specific characteristics | PASS | Mike (expects releases to succeed), CI environment (may lack CZ), future contributors (may misconfigure) |
| 3 | 3+ domain examples with real data | PASS | 4 examples: CZ not installed, config missing, invalid base-version, invalid floor |
| 4 | UAT in Given/When/Then (3-7 scenarios) | PASS | 5 scenarios covering not installed, config missing, invalid base, invalid floor, no-bump commits |
| 5 | AC derived from UAT | PASS | 6 AC items covering error absorption, fallback path, validation errors |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | 5 scenarios, ~1 day effort (error handling + validation in existing code) |
| 7 | Technical notes: constraints/dependencies | PASS | Shell error pattern, validation via packaging.version, empty vs invalid distinction, --no-bump interaction |
| 8 | Dependencies resolved or tracked | PASS | Depends on US-CZ-01 and US-CZ-02 (both args must exist); tracked in Technical Notes |

**Result: PASS (8/8)**

---

## US-CZ-04: Full Promotion Chain Validates Correctly After Mid-Cycle Escalation

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "No explicit scenarios proving the full promotion chain works correctly after mid-cycle escalation." Pain: one wrong promotion ships wrong version to PyPI. |
| 2 | User/persona with specific characteristics | PASS | Mike Brissoni (release engineer clicking "Promote to RC/Stable"), CI/CD system (auto-discovering tags via discover_tag.py), downstream consumers (nWave-beta, nwave-ai/nwave). |
| 3 | 3+ domain examples with real data | PASS | 6 examples: dev-to-RC after escalation (v1.2.0.dev2 -> 1.2.0rc1), sequential RC counter (rc1 -> rc2), RC-to-stable (v1.2.0rc2 -> 1.2.0), accidental wrong-tag self-healing, floor dev-only scope, full chain trace with one-click UX. All with real version numbers. |
| 4 | UAT in Given/When/Then (3-7 scenarios) | PASS | 7 scenarios: discover_tag picks highest dev, calculate_rc strips suffix, sequential RC counter, discover_tag picks highest RC, calculate_stable strips suffix, self-healing wrong promotion, floor not applied at RC/stable. 7 matching Gherkin scenarios in feature file US-CZ-04 section. |
| 5 | AC derived from UAT | PASS | 9 AC items, each traceable to a UAT scenario: discover_tag sorting, orphaned tag handling, RC suffix stripping, RC counter, stable suffix stripping, self-healing, floor scope, one-click UX. |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | 7 scenarios. No code changes needed (validation/documentation story). Effort is writing test cases against existing functions. ~1 day. |
| 7 | Technical notes: constraints/dependencies | PASS | Explicit notes on: no code changes needed, discover_tag.py sorting mechanism (packaging.Version), calculate_rc/calculate_stable stripping logic with line numbers, floor scope limited to release-dev.yml, test approach (unit tests with --tag-list). |
| 8 | Dependencies resolved or tracked | PASS | Depends on US-CZ-01 (dev tags must exist for RC promotion). discover_tag.py already built in tag-auto-discovery feature. calculate_rc/calculate_stable already implemented. |

**Result: PASS (8/8)**

---

## US-CZ-05: Consolidate Versioning by Replacing PSR with Commitizen

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "Two version management tools create confusion; PSR does not support PEP 440" -- specific pain with real tool names and format incompatibility |
| 2 | User/persona with specific characteristics | PASS | Mike Brissoni (release engineer reasoning about two tools), Ale (contributor confused by dual configs), CI/CD pipelines (installing unused PSR), repo maintainers (two configs to sync) |
| 3 | 3+ domain examples with real data | PASS | 5 examples: stable release with CZ file updates, legacy release.yml with CZ, contributor adding version-tracked file (single config vs dual), dev dependency cleanup (PSR 10.5.3 removed), CI drift message update |
| 4 | UAT in Given/When/Then (3-7 scenarios) | PASS | 7 scenarios: CZ version_files config, .releaserc deletion, [tool.semantic_release] removal, PSR dependency removal, release.yml CZ migration, changelog generation, CI/docs reference updates. 7 matching Gherkin scenarios in feature file US-CZ-05 section. |
| 5 | AC derived from UAT | PASS | 11 AC items, each traceable to a UAT scenario: version_files, changelog_file, .releaserc deletion, PSR config removal, PSR dep removal, lock regeneration, release.yml migration, rsync cleanup, CI message update, pipeline unaffected, sync-public regex update |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | 7 scenarios. Config changes + file deletion + workflow edits. ~2 days effort (mostly workflow YAML changes and testing). |
| 7 | Technical notes: constraints/dependencies | PASS | Notes on: release-prod.yml unaffected, CZ version_files mechanism, changelog in .gitignore, sync-public regex change, rsync excludes, backward compatibility |
| 8 | Dependencies resolved or tracked | PASS | Depends on US-CZ-01 (CZ config must exist before expanding with version_files). No external blockers. |

**Result: PASS (8/8)**

---

## Epic Summary

| Story | DoR | Scenarios | Effort Est. | Priority |
|-------|-----|-----------|-------------|----------|
| US-CZ-01 | 8/8 PASS | 7 (+6 in feature) | 1-2 days | P1 (foundation: CZ config + --base-version) |
| US-CZ-02 | 8/8 PASS | 5 | 1 day | P2 (extends CZ-01 with floor override) |
| US-CZ-03 | 8/8 PASS | 5 | 1 day | P2 (error handling, depends on both) |
| US-CZ-04 | 8/8 PASS | 7 | 1 day | P2 (validation: full promotion chain) |
| US-CZ-05 | 8/8 PASS | 7 | 2 days | P2 (cleanup: replace PSR with CZ) |

**Recommended implementation order**: US-CZ-01 (CZ config + base-version) -> US-CZ-02 (floor override) -> US-CZ-03 (validation + fallback hardening) -> US-CZ-04 (promotion chain validation, can run in parallel with CZ-03) -> US-CZ-05 (PSR removal, after CZ is fully wired)

**Total estimated effort**: 6-7 days
**Total scenarios**: 31 (US-CZ-01: 7, US-CZ-02: 5, US-CZ-03: 5, US-CZ-04: 7, US-CZ-05: 7) + 6 detailed Gherkin in feature file US-CZ-01b + 7 Gherkin in feature file US-CZ-04 + 7 Gherkin in feature file US-CZ-05

## Peer Review: Self-Validation

### Coherence Check

| Dimension | Status | Notes |
|-----------|--------|-------|
| Vocabulary consistency | PASS | "base-version", "version-floor", "fallback", "version_files", "changelog_file" used consistently across all 5 stories |
| Emotional arc coherence | PASS | Frustrated (problem) -> Trusting (CZ analysis) -> Confident (correct version) |
| Shared artifact tracking | PASS | `cz_base_version`, `version_floor`, `dev_version`, `cz_version_files`, `cz_changelog_file` documented in shared-artifacts-registry.md |
| Integration checkpoints | PASS | 3 checkpoints defined between CZ analysis, floor read, and version-calc |
| CLI vocabulary | PASS | `--base-version` and `--version-floor` follow existing `--current-version` pattern |
| Solution neutrality | PASS | Stories describe observable outcomes, not implementation details |
| Real data in examples | PASS | Version numbers (1.1.22, 1.2.0, 2.0.0), commit types (feat:, fix:, feat!:), personas (Mike Brissoni) |

### Anti-Pattern Check

| Anti-Pattern | Status | Notes |
|---|---|---|
| Implement-X | PASS | All stories start from user pain, not "implement CZ integration" or "remove PSR" |
| Generic data | PASS | Real version numbers (1.2.0, 10.5.3), real persona names (Mike, Ale), real file paths (.releaserc, nWave/VERSION), real commit types |
| Technical AC | PASS | AC describe observable outcomes ("python-semantic-release does not appear in pyproject.toml"), not internals |
| Oversized story | PASS | Each story has 5-7 scenarios, 1-2 days effort |
| Abstract requirements | PASS | Every requirement has 4-5 concrete domain examples with real data |

### Open Questions from Design Plan (Resolution)

| Question | Resolution |
|----------|------------|
| Should floor also apply to RC stage? | No. RC inherits base from dev tags. Floor applies at dev stage only. Explicitly validated in US-CZ-04 scenario 7. |
| Should we remove `[tool.semantic_release]` config? | **Yes** (updated 2026-02-26). Mike decided to fully replace PSR with CZ. US-CZ-05 covers removing `.releaserc`, `[tool.semantic_release]`, and the PSR dev dependency. CZ's `version_files` and `changelog_file` take over PSR's side effects. |
| Do we need `--increment MAJOR/MINOR/PATCH` manual override? | Not in this epic. CZ handles commit analysis; floor handles manual override. |
| Should nwave-ai stage also use CZ? | Not in this epic. nwave-ai already has its own floor logic. |
| What happens with accidental wrong-tag promotions? | System self-heals. discover_tag.py always picks the highest version by packaging.Version sort. Explicitly validated in US-CZ-04 scenario 6. |
