# Definition of Ready Validation: Release Train Revamp

**Feature**: release-train-revamp
**Validated**: 2026-02-20
**Validator**: Luna (product-owner agent)

---

## US-RTR-001: Dev Release on Demand

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "tag spam that buries meaningful releases", "manual version string editing" |
| 2 | User/persona identified | PASS | Mike, nwave-dev maintainer, trunk-based model |
| 3 | At least 3 domain examples with real data | PASS | 3 examples: first dev release (v2.18.0.dev1), third sequential (dev3), test failure |
| 4 | UAT scenarios in Given/When/Then (3-7) | PASS | 5 scenarios: happy path, sequential, dry run, failure, no commits |
| 5 | Acceptance criteria from UAT | PASS | 7 checkable items derived from scenarios |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | ~2 days; 5 scenarios |
| 7 | Technical notes: constraints/dependencies | PASS | PSR limitation, custom version script, workflow file name |
| 8 | Dependencies resolved or tracked | PASS | Depends on US-RTR-004 (tracked) |

**Result: PASS (8/8)**

---

## US-RTR-002: RC Release and Beta Distribution

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "error-prone and fragmented to manually coordinate pre-release distribution" |
| 2 | User/persona identified | PASS | Mike (promoter) + beta testers (consumers, e.g. Alessandro) |
| 3 | At least 3 domain examples with real data | PASS | 3 examples: RC promotion, beta tester install, invalid tag |
| 4 | UAT scenarios in Given/When/Then (3-7) | PASS | 6 scenarios: happy path, pip install, missing tag, counter, traceability, OIDC |
| 5 | Acceptance criteria from UAT | PASS | 8 checkable items derived from scenarios |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | ~3 days; 6 scenarios |
| 7 | Technical notes: constraints/dependencies | PASS | nWave-beta repo creation, OIDC setup, RELEASETRAIN token, workflow files |
| 8 | Dependencies resolved or tracked | PASS | Depends on US-RTR-001 (dev tags), US-RTR-004 (modular workflows) |

**Result: PASS (8/8)**

---

## US-RTR-003: Stable Release and Public Distribution

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "monolithic pipeline fragile and hard to debug", "incomplete traceability" |
| 2 | User/persona identified | PASS | Mike (releaser), end users (pip install), Mike (debugger) |
| 3 | At least 3 domain examples with real data | PASS | 3 examples: happy path (v2.18.0 -> v1.1.6), floor override (2.0.0), tracing bug |
| 4 | UAT scenarios in Given/When/Then (3-7) | PASS | 7 scenarios: happy path, floor, auto-bump, missing RC, traceability, reverse, end user |
| 5 | Acceptance criteria from UAT | PASS | 9 checkable items derived from scenarios |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | ~3 days; 7 scenarios |
| 7 | Technical notes: constraints/dependencies | PASS | RELEASETRAIN token, pyproject.toml patching, workflow files, reusable workflows |
| 8 | Dependencies resolved or tracked | PASS | Depends on US-RTR-002 (RC tags), US-RTR-004 (modular workflows) |

**Result: PASS (8/8)**

---

## US-RTR-004: Pipeline Modularization

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "1075-line monolithic release.yml painful to maintain", "shared logic duplicated" |
| 2 | User/persona identified | PASS | Mike (maintainer/debugger), CI/CD system, future contributors |
| 3 | At least 3 domain examples with real data | PASS | 3 examples: debugging PyPI failure (120 vs 1075 lines), Python upgrade, new stage |
| 4 | UAT scenarios in Given/When/Then (3-7) | PASS | 5 scenarios: modular structure, composite actions, independent trigger, secrets, inputs/outputs |
| 5 | Acceptance criteria from UAT | PASS | 8 checkable items derived from scenarios |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | ~3 days; 5 scenarios |
| 7 | Technical notes: constraints/dependencies | PASS | GitHub limits (10 inputs, 10 nesting), env propagation, naming conventions |
| 8 | Dependencies resolved or tracked | PASS | Prerequisite for US-RTR-001/002/003 (tracked) |

**Result: PASS (8/8)**

---

## US-RTR-005: Migrate PyPI Publishing to Trusted Publishers (OIDC)

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "API token has no expiration date", "indefinite upload access if compromised" |
| 2 | User/persona identified | PASS | Mike (security), CI/CD system (authentication), PyPI (validation) |
| 3 | At least 3 domain examples with real data | PASS | 3 examples: OIDC RC publish, unauthorized workflow blocked, stable publish with audit |
| 4 | UAT scenarios in Given/When/Then (3-7) | PASS | 4 scenarios: OIDC success, separate jobs, environment gate, fallback |
| 5 | Acceptance criteria from UAT | PASS | 7 checkable items derived from scenarios |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | ~1 day; 4 scenarios |
| 7 | Technical notes: constraints/dependencies | PASS | PyPI project settings, per-workflow configuration, TestPyPI separate config |
| 8 | Dependencies resolved or tracked | PASS | Depends on US-RTR-004 (workflow filenames must be final for OIDC claims) |

**Result: PASS (8/8)**

---

## US-RTR-006: Cross-Repo Traceability

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "time-consuming to trace a public release back to its source" |
| 2 | User/persona identified | PASS | Mike (debugger), Mike (auditor), future maintainers |
| 3 | At least 3 domain examples with real data | PASS | 3 examples: forward trace, backward trace (nWave_v1.1.6), beta trace |
| 4 | UAT scenarios in Given/When/Then (3-7) | PASS | 4 scenarios: public commit, beta commit, reverse lookup, forward lookup |
| 5 | Acceptance criteria from UAT | PASS | 5 checkable items derived from scenarios |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | ~1 day; 4 scenarios |
| 7 | Technical notes: constraints/dependencies | PASS | Workflow output chaining, commit message template, reusable sync workflow |
| 8 | Dependencies resolved or tracked | PASS | Depends on US-RTR-004 (reusable sync workflow) |

**Result: PASS (8/8)**

---

## US-RTR-007: Tag Cleanup and PEP 440 Normalization

| # | DoR Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | Problem statement clear, domain language | PASS | "tags in inconsistent formats", "will conflict with new naming convention" |
| 2 | User/persona identified | PASS | Mike (cleanup), CI/CD system (counter calculation), git tag output (human scan) |
| 3 | At least 3 domain examples with real data | PASS | 3 examples: audit (47 tags), dry run cleanup, convention doc |
| 4 | UAT scenarios in Given/When/Then (3-7) | PASS | 4 scenarios: audit, dry run, cleanup, convention doc |
| 5 | Acceptance criteria from UAT | PASS | 6 checkable items derived from scenarios |
| 6 | Right-sized (1-3 days, 3-7 scenarios) | PASS | ~1 day; 4 scenarios (one-time task) |
| 7 | Technical notes: constraints/dependencies | PASS | Local + remote tag deletion, preserve valid tags, one-time script |
| 8 | Dependencies resolved or tracked | PASS | Must run before US-RTR-001 (tracked) |

**Result: PASS (8/8)**

---

## Summary

| Story | DoR Result | Scenarios | Est. Days | Dependencies |
|-------|-----------|-----------|-----------|--------------|
| US-RTR-001: Dev Release | PASS (8/8) | 5 | ~2 | RTR-004 |
| US-RTR-002: RC Release | PASS (8/8) | 6 | ~3 | RTR-001, RTR-004 |
| US-RTR-003: Stable Release | PASS (8/8) | 7 | ~3 | RTR-002, RTR-004 |
| US-RTR-004: Modularization | PASS (8/8) | 5 | ~3 | None (prerequisite) |
| US-RTR-005: OIDC Migration | PASS (8/8) | 4 | ~1 | RTR-004 |
| US-RTR-006: Traceability | PASS (8/8) | 4 | ~1 | RTR-004 |
| US-RTR-007: Tag Cleanup | PASS (8/8) | 4 | ~1 | None (run first) |

**All 7 stories PASS Definition of Ready.**

## Recommended Implementation Order

```
Phase 0 (prep):     US-RTR-007 (tag cleanup)
Phase 1 (infra):    US-RTR-004 (modularization)
Phase 2 (security): US-RTR-005 (OIDC) + US-RTR-006 (traceability)
Phase 3 (stages):   US-RTR-001 (dev) -> US-RTR-002 (RC) -> US-RTR-003 (stable)
```
