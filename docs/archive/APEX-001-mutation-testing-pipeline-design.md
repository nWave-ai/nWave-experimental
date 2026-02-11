# APEX-001: Design Mutation Testing Integration for CI/CD Pipeline

**Type:** Architecture Design Request
**Priority:** HIGH
**Assigned To:** Apex (solution-architect)
**Created:** 2026-01-29
**Status:** PARKING LOT

---

## Executive Summary

During the DEVELOP wave for `versioning-release-management`, we discovered that mutation testing is NOT integrated into the CI/CD pipeline. It exists only as a manual orchestration task with limited scope.

---

## Current State Analysis

### CI/CD Pipeline Structure (`ci-cd.yml`)

| Stage | Jobs | Mutation Testing |
|-------|------|------------------|
| Stage 1 | commitlint, code-quality, file-quality, security-checks | NO |
| Stage 2 | framework-validation | NO |
| Stage 3 | pytest (3 OS x 2 Python = 6 jobs) | NO |
| Stage 4 | agent-sync | NO |
| Stage 5 | build (tags only) | NO |
| Stage 6 | release (tags only) | NO |

### Existing Mutation Testing Assets

1. **Manual Task File:** `nWave/tasks/nw/mutation-test.md`
   - Orchestration instructions for `/nw:mutation-test` skill
   - Supports multiple languages (Python, Java, JS/TS, C#, Go)
   - 75% kill rate threshold documented

2. **mutmut Configuration** in `setup.cfg`:
   ```ini
   [mutmut]
   paths_to_mutate = des
   tests_dir = tests
   test_time_multiplier = 2.0
   tests_to_run = tests/unit/des/test_validator.py tests/acceptance/test_us002_template_validation.py
   ```

### Identified Gaps

| Gap | Impact |
|-----|--------|
| No CI automation | Mutation testing only runs when manually invoked |
| Limited scope | Only `des/` module configured, not `nWave/` or new features |
| No quality gate | 75% threshold documented but not enforced |
| Single OS/Python | Config doesn't consider cross-platform matrix |
| No versioning coverage | New `versioning-release-management` feature has zero mutation test coverage |

---

## Design Requirements

### Functional Requirements

1. **Automated Execution**
   - Mutation testing runs as part of CI/CD pipeline
   - Define trigger conditions (every push? PRs only? tags only? scheduled?)

2. **Scope Configuration**
   - Which modules to mutate: `nWave/`, `src/des/`, feature code
   - Which tests to run against mutants
   - Incremental vs full mutation runs

3. **Quality Gate Enforcement**
   - 75% kill rate threshold as blocking gate
   - Configurable per-module thresholds
   - Clear pass/fail reporting

4. **Cross-Platform Considerations**
   - Which OS to run mutation tests on (Linux only? Matrix?)
   - Which Python versions (single? matrix?)
   - Performance vs coverage trade-offs

### Non-Functional Requirements

1. **Performance**
   - Mutation testing is slow (10-30 minutes for large projects)
   - Consider parallel execution strategies
   - Caching of mutation results

2. **Reporting**
   - Mutation score visible in PR/commit status
   - Surviving mutants report accessible
   - Historical tracking of mutation scores

3. **Developer Experience**
   - Local mutation testing command (`make mutation-test`?)
   - Clear documentation on running locally
   - Integration with pre-commit hooks (optional?)

---

## Questions for Apex to Address

1. **Pipeline Placement:** Where in the pipeline should mutation testing run?
   - After unit tests (Stage 3)?
   - Separate stage (Stage 3.5)?
   - Only on release branches/tags?

2. **Execution Strategy:** How to balance thoroughness vs CI time?
   - Full mutation on every commit?
   - Incremental mutation (only changed files)?
   - Scheduled nightly full runs?

3. **Failure Handling:** What happens when mutation score < 75%?
   - Block merge/release?
   - Warning only?
   - Different rules for different branches?

4. **Tool Selection:** Confirm mutmut or evaluate alternatives?
   - mutmut (current)
   - cosmic-ray
   - Other Python mutation tools?

5. **Configuration Location:** Where should mutation config live?
   - `setup.cfg` (current)
   - `pyproject.toml`
   - Dedicated `.mutation.yaml`
   - CI workflow inline?

---

## Related Files

- `.github/workflows/ci-cd.yml` - Current pipeline (no mutation testing)
- `nWave/tasks/nw/mutation-test.md` - Manual orchestration task
- `setup.cfg` - Current mutmut configuration
- `docs/guides/5-layer-testing-cicd.md` - Testing strategy documentation

---

## Acceptance Criteria for Design

- [ ] Pipeline stage definition with trigger conditions
- [ ] Module scope and test mapping configuration
- [ ] Quality gate thresholds and enforcement rules
- [ ] Cross-platform execution strategy (OS/Python matrix)
- [ ] Performance optimization approach
- [ ] Reporting and visibility solution
- [ ] Local development workflow integration
- [ ] Migration path from current manual process

---

## Discovery Context

This gap was identified during the DEVELOP wave for `versioning-release-management` feature when:
1. Phase 7.5 (Mutation Testing) was planned but found to have no CI integration
2. The devop agent incorrectly reported mutation testing passed (it doesn't exist in CI)
3. Investigation revealed mutation testing is manual-only with limited `des/` scope

**Reporter:** Vera (orchestrator)
**Discovery Date:** 2026-01-29
