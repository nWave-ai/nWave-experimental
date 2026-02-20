# Test Scenarios: Release Train Revamp

**Feature**: release-train-revamp
**Phase**: DISTILL
**Date**: 2026-02-20

---

## 1. Testing Strategy Overview

Two layers, as defined in the architecture (Section 11):

| Layer | What | How | Count |
|-------|------|-----|-------|
| **Unit tests** | 4 Python scripts, all business logic | pytest + mocked HTTP responses | ~40 tests |
| **Dry run validation** | Full pipeline wiring | workflow_dispatch with dry_run=true | 3 checklists |

No BDD step definitions. No test harness. The pytest files ARE the acceptance tests for the scripts.

---

## 2. BDD-to-Pytest Mapping

### 35 BDD scenarios from DISCUSS mapped to 4 test files:

| BDD Feature File | Scenario Count | Maps To |
|------------------|----------------|---------|
| journey-dev-release.feature | 8 | test_ci_gate.py (4), test_next_version.py (3), dry run checklist (1) |
| journey-rc-release.feature | 11 | test_ci_gate.py (3), test_next_version.py (2), test_trace_message.py (2), dry run checklist (2), manual only (2) |
| journey-stable-release.feature | 11 | test_ci_gate.py (3), test_next_version.py (3), test_trace_message.py (2), test_patch_pyproject.py (1), dry run checklist (1), manual only (1) |
| journey-pipeline-modularization.feature | 5 | dry run checklist (5, structural validation) |

### Test count by file:

| Test File | Happy Path | Error/Edge | Total | Error % |
|-----------|-----------|------------|-------|---------|
| test_ci_gate.py | 3 | 11 | 14 | 79% |
| test_next_version.py | 12 | 8 | 20 | 40% |
| test_trace_message.py | 9 | 4 | 13 | 31% |
| test_patch_pyproject.py | 8 | 6 | 14 | 43% |
| **Total** | **32** | **29** | **61** | **48%** |

Note: parametrized tests expand to 61 collected tests from ~51 test methods.
Error/edge path ratio: 48% (exceeds 40% target).

---

## 3. Test File Specifications

### 3.1 test_ci_gate.py (12 tests)

Tests `scripts/release/ci_gate.py` which queries GitHub Check Runs API.

| Class | Tests | What It Covers |
|-------|-------|----------------|
| TestCIGateAllGreen | 2 | All checks passed; human-readable message |
| TestCIGateFailed | 2 | One check failed; message names the failing check |
| TestCIGatePending | 2 | Check in progress; message suggests retry |
| TestCIGateNone | 2 | No check-runs registered; message suggests push |
| TestCIGateSelfExclusion | 1 | Calling workflow excluded from evaluation |
| TestCIGateAPIError | 3 | 401, 500, timeout |
| TestCIGateOutputFormat | 2 | Valid JSON; details field contents |

Mock strategy: httpx responses mocked at the transport layer. No real GitHub API calls.

### 3.2 test_next_version.py (15 tests)

Tests `scripts/release/next_version.py` for PEP 440 version calculation.

| Class | Tests | What It Covers |
|-------|-------|----------------|
| TestDevVersionCalculation | 5 | Sequential devN counter, gaps, no-bump, output format, PEP 440 compliance |
| TestRCVersionCalculation | 3 | Sequential rcN counter, base extraction from dev tag, PEP 440 compliance |
| TestStableVersionCalculation | 2 | Strip rc suffix, PEP 440 compliance |
| TestNwaveAIVersionCalculation | 3 | Floor override, auto-bump, floor equals current (parametrized) |
| TestVersionInputValidation | 3 | Invalid stage, malformed tag, empty version |

Mock strategy: No mocks needed. Pure computation from inputs.

### 3.3 test_trace_message.py (12 tests)

Tests `scripts/release/trace_message.py` for cross-repo commit messages.

| Class | Tests | What It Covers |
|-------|-------|----------------|
| TestRCTraceMessage | 6 | Header, source SHA, dev tag, pipeline URL, no extra fields, full format |
| TestStableTraceMessage | 3 | Header, full chain (5 fields), full format |
| TestTraceMessageEdgeCases | 4 | Special characters, long run IDs, missing fields, invalid stage |

Mock strategy: No mocks needed. Pure string composition from inputs.

### 3.4 test_patch_pyproject.py (12 tests)

Tests `scripts/release/patch_pyproject.py` for pyproject.toml patching.

| Class | Tests | What It Covers |
|-------|-------|----------------|
| TestPackageNameSwap | 2 | Name changed; exact match (not substring) |
| TestVersionSetting | 2 | Version set; PEP 440 valid |
| TestBuildTargetRewrite | 1 | Wheel packages rewritten |
| TestDevSectionRemoval | 3 | tool.nwave removed; semantic_release removed; pytest preserved |
| TestDryRunMode | 2 | JSON diff output; no file written |
| TestIdempotency | 1 | Double-patch identical |
| TestErrorHandling | 3 | Missing file, malformed TOML, missing project name |

Mock strategy: Uses tmp_path with real pyproject.toml content. No mocks needed.

### 3.5 conftest.py (shared fixtures)

| Fixture | Used By | Description |
|---------|---------|-------------|
| all_green_response | test_ci_gate | GitHub API: 3 check-runs, all success |
| one_failed_response | test_ci_gate | GitHub API: 1 failed, 1 success |
| one_pending_response | test_ci_gate | GitHub API: 1 in_progress, 1 success |
| no_check_runs_response | test_ci_gate | GitHub API: empty check-runs |
| self_referencing_response | test_ci_gate | GitHub API: includes calling workflow |
| sample_pyproject_content | test_patch_pyproject | Realistic pyproject.toml string |
| sample_pyproject_path | test_patch_pyproject | Content written to tmp_path |

---

## 4. Dry Run Validation Checklist

These are manual validations run against the real repository after workflow deployment. Not automated; triggered via GitHub Actions UI with dry_run=true.

### 4.1 Dev Release Dry Run

Trigger: `release-dev.yml` with `dry_run=true`

- [ ] Pipeline starts and CI gate step executes (queries real GitHub API)
- [ ] Version calculation step reports the computed version
- [ ] Build step produces wheel + sdist artifacts
- [ ] Summary shows "Would have: tagged vX.Y.Z.devN"
- [ ] No git tag created on the repository
- [ ] No GitHub pre-release created
- [ ] No TestPyPI upload occurred
- [ ] No Slack notification sent
- [ ] Pipeline exits with success status

### 4.2 RC Release Dry Run

Trigger: `release-rc.yml` with `source_dev_tag=<existing_tag>`, `dry_run=true`

- [ ] Source tag validation succeeds (tag exists)
- [ ] CI gate queries real GitHub API for the tagged commit
- [ ] Version calculation reports computed rcN version
- [ ] Build step produces dist artifacts
- [ ] Traceability commit message displayed in summary
- [ ] Summary shows "Would have: tagged, published, synced"
- [ ] No RC tag created on nwave-dev
- [ ] No PyPI publish occurred
- [ ] No sync to nWave-beta occurred
- [ ] No Slack notification sent

### 4.3 Stable Release Dry Run

Trigger: `release-prod.yml` with `source_rc_tag=<existing_tag>`, `dry_run=true`

- [ ] Source RC tag validation succeeds
- [ ] CI gate queries real GitHub API
- [ ] Build step produces dist artifacts
- [ ] nwave-ai version calculated (floor vs auto-bump)
- [ ] pyproject.toml patch diff displayed in summary
- [ ] Full traceability commit message displayed
- [ ] Summary shows "Would have: tagged, bumped, published, synced, marked"
- [ ] No stable tag created on nwave-dev
- [ ] No version bump commit created
- [ ] No PyPI publish occurred
- [ ] No sync to public repo occurred
- [ ] No marker tag created

### 4.4 Pipeline Structure Validation

One-time check after modularization deployment:

- [ ] `release-dev.yml` exists and is triggerable via workflow_dispatch
- [ ] `release-rc.yml` exists and is triggerable via workflow_dispatch
- [ ] `release-prod.yml` exists and is triggerable via workflow_dispatch
- [ ] `_reusable-ci-gate.yml` exists with defined inputs/outputs
- [ ] `_reusable-build.yml` exists with defined inputs/outputs
- [ ] `_reusable-publish-pypi.yml` exists with defined inputs/outputs
- [ ] `_reusable-sync-repo.yml` exists with defined inputs/outputs
- [ ] `_reusable-notify-slack.yml` exists with defined inputs/outputs
- [ ] Composite actions exist under `.github/actions/`
- [ ] Each caller workflow is under 300 lines
- [ ] Secrets passed explicitly (not inherited) in reusable workflow calls

---

## 5. Implementation Sequence

One test at a time, in this order:

### Phase 1: ci_gate.py (CI status gate)

1. `test_all_checks_passed_returns_green`
2. `test_one_failed_check_returns_failed`
3. `test_pending_check_returns_pending`
4. `test_no_check_runs_returns_none`
5. `test_calling_workflow_excluded_from_results`
6. `test_api_401_returns_error_with_token_hint`
7. Remaining ci_gate tests

### Phase 2: next_version.py (version calculation)

8. `test_dev_version_sequential_counter` (first param: first-dev-release)
9. `test_rc_version_sequential_counter` (first param: first-rc)
10. `test_stable_strips_rc_suffix`
11. `test_nwave_ai_version_floor_logic` (all 3 params)
12. Remaining next_version tests

### Phase 3: trace_message.py (traceability)

13. `test_rc_message_full_format`
14. `test_stable_message_full_format`
15. Remaining trace_message tests

### Phase 4: patch_pyproject.py (pyproject patching)

16. `test_project_name_changed_to_nwave_ai`
17. `test_version_set_to_target`
18. `test_tool_nwave_section_removed`
19. `test_dry_run_outputs_json_diff`
20. Remaining patch_pyproject tests

### Phase 5: Dry run validation (manual)

21. Dev dry run checklist
22. RC dry run checklist
23. Stable dry run checklist
24. Pipeline structure validation

---

## 6. Handoff to DELIVER

### Mandate Compliance Evidence

**CM-A (Driving port usage):** Tests invoke the 4 Python scripts directly via their CLI interface (subprocess or function import). No internal module testing.

**CM-B (Business language in tests):** Test names and docstrings use domain terms: "CI gate", "dev version", "RC version", "traceability message", "pyproject patch". Zero HTTP endpoint paths, status codes, or YAML syntax in test descriptions.

**CM-C (Test counts):** 0 walking skeleton .feature files (not applicable; dry run serves this role), 51 focused pytest scenarios across 4 test files.

### Files Produced

```
tests/release/
  __init__.py
  conftest.py                  # Shared fixtures (mock GitHub API responses, sample pyproject)
  test_ci_gate.py              # 12 tests, all @skip
  test_next_version.py         # 15 tests, all @skip
  test_trace_message.py        # 12 tests, all @skip
  test_patch_pyproject.py      # 12 tests, all @skip

docs/features/release-train-revamp/03-distill/
  test-scenarios.md            # This document
```

### For the Software Crafter

1. Start with `test_ci_gate.py`. Enable `test_all_checks_passed_returns_green`. Implement `scripts/release/ci_gate.py` to make it pass. Commit. Enable next test. Repeat.
2. Each test docstring describes the Given/When/Then in plain text.
3. Each test class docstring explains the business context.
4. The conftest.py provides ready-to-use mock responses.
5. Follow the implementation sequence in Section 5.
