---
name: nw-tdd-methodology-walking-skeleton
description: Building and validating a walking skeleton - the WS protocol, per-slice JIT E2E management, Mandate 5 adapter-strategy decision tree (A/B/C/D + resource table), and Mandate 6 adapter-integration real-I/O requirement
user-invocable: false
disable-model-invocation: true
---

# Walking Skeleton — Protocol, Adapter Strategy, Real-I/O Mandates

**Trigger**: building or validating a walking skeleton — choosing the WS adapter strategy (A/B/C/D), managing per-slice E2E scenarios, or deciding adapter-integration real-I/O coverage.

## Walking Skeleton Protocol

At most one walking skeleton per new feature. When `is_walking_skeleton: true` in roadmap:
- Write exactly ONE E2E/acceptance test proving end-to-end wiring with REAL adapters
- Implement thinnest possible slice — hardcoded values, minimal branching
- Unit tests are written ONLY if needed to decompose complex GREEN implementation
- Do NOT add error handling, edge cases, or validation beyond what the AT requires
- No code without a test that requires it — the AT drives ALL implementation

The WS is an acceptance test on steroids: it proves wiring AND drives implementation of adapters, domain logic, and application services. If the WS AT requires 5 functions to pass, those 5 functions are justified. Subsequent steps that find "already implemented, AT goes GREEN" confirm the WS was well-designed.

Integration tests for adapters (real filesystem, real subprocess) are naturally created during WS — the WS REQUIRES real adapters, which drives their implementation and testing.

## E2E Test Management

**atdd_pure (the path)**: per-slice JIT — only the current slice's scenarios exist on disk (active-RED). Future-slice scenarios are absent. No @skip. Implement the current slice's active-RED scenarios to GREEN, commit, then DISTILL authors the next slice's scenarios. <!-- mode-ref-ok -->

**Test-pyramid default (Ale-ratified 2026-07-18): ONE `@walking_skeleton` subprocess-E2E per FEATURE — never per slice, never per command.** The feature's single WS lands with the first slice and proves the installed wiring once; every other scenario (all slices) drives IN-PROCESS/in-memory through the driving port. Wiring coverage beyond the single WS is a declared triple, not scenario multiplication: (a) the feature's WS; (b) Vera's EXAMINE exercising every charter observable through the REAL surface (the user-perspective manual test); (c) the feature-end cycle (env-e2e + full-suite + deep-review) backstopping paths no observable reaches. An additional subprocess-E2E requires an explicit written justification (e.g. the slice's value IS an integration boundary).


## Mandate 5: Walking Skeleton E2E Strategy

The DISTILL acceptance designer determines the WS adapter strategy for each feature. This is auto-detected with user confirmation, not a question to the user.

### Decision Tree

```
Feature is pure domain (no driven ports with I/O)? → Strategy A (InMemory)
Feature has only local resources (filesystem, git, in-process)? → Strategy C (Real local)
Feature has costly external dependencies (paid APIs, LLM calls)? → Strategy B (Real local + fake costly)
Team needs CI flexibility? → Strategy D (Configurable via env var)
```

### Resource Classification Table

| Resource Type | WS Local | WS CI | Adapter Integration Test |
|--------------|----------|-------|------------------------|
| Filesystem | real (tmp_path) | real (tmp_path) | real (tmp_path) — ALWAYS |
| Git repo | real (tmp_path + git init) | real | real — ALWAYS |
| Local subprocess (pytest, ruff, grep) | real | real | real — ALWAYS |
| Costly subprocess (claude -p, LLM) | fake (mock Popen) | fake | contract smoke (@requires_external) |
| Paid external API (Stripe, Blumberg) | fake server | fake server | contract test with recorded fixtures |
| Database | real (SQLite/testcontainers) | real (testcontainers) | real — ALWAYS |
| Container services | optional (docker-compose) | testcontainers | real if available |

### Walking Skeleton Adapter Rule

Under strategies B/C/D, the WS uses real adapters for local resources. InMemory is ONLY for costly external resources that have a separate contract test.

### Determinism Contract

Real-adapter WS tests accept non-determinism as a trade-off for environmental realism. InMemory acceptance tests remain the fast deterministic inner loop. The WS is the slow truth-checking outer loop. Both are necessary. If WS fails, triage: logic failure (fix code) or environment failure (retry, investigate infra).

### Rollback Policy

If WS with Strategy C fails due to infrastructure issues (not code bugs), downgrade to Strategy B for that step. Document the downgrade in wave-decisions.md with justification.

## Mandate 6: Adapter Integration Tests Are Real I/O

Every driven adapter has at least ONE integration test with real I/O. This is not optional regardless of WS strategy.

### Adapter Type Minimum Real I/O Test

| Adapter Type | Minimum Real I/O Test |
|-------------|----------------------|
| Filesystem adapter | tmp_path fixture, real read/write/delete |
| Subprocess adapter (local) | real subprocess call, real exit codes |
| Subprocess adapter (costly) | contract smoke test with @requires_external marker |
| Config/env adapter | real env vars or real config file on tmp_path |
| Git adapter | real temp git repo (tmp_path + git init + git commit) |
| Database adapter | real DB (SQLite in-memory or testcontainers) |
| Network/HTTP adapter | contract test against recorded fixture or fake server |

"Real" means: the test would FAIL if the adapter's actual system dependency is absent or broken.

### Tagging Convention for Enforcement

- Scenarios using real adapters: `@real-io`
- Scenarios using InMemory: `@in-memory`
- Walking skeleton: `@walking_skeleton` + `@real-io` (for strategies B/C/D)

## Adapter Integration Slice RED-Phase Semantics

The RED-phase `fail-for-right-reason` gate (Mandate-7) carries different semantics for an acceptance slice vs an adapter-integration slice. Conflating the two produces false-positive convergence — an AT that "fails" because the adapter contract is not yet authored is NOT the same shape of failure as an AT that "fails" because the feature behavior is missing.

Reference: design spike v2 `docs/analysis/adapter-integration-slice-design-2026-05-27.md` §6 surface #10.

### Two RED-phase modes — distinguished by the failure source

- **acceptance RED**: the AT fails because the feature behavior is not implemented. The driving port returns the unimplemented-default response; the assertion against expected end-state fails. Implementing the feature inside the hexagon (domain + application + new wiring through existing adapters) turns the AT GREEN. Fail-for-right-reason token: `AssertionError` against expected feature outcome.
- **adapter-integration RED**: the AT fails because a property-matrix row contract is not satisfied against the (still-stub-or-partial) adapter implementation. The SUT is the adapter itself, not the feature; the assertion is about the property declared in the slice plan (error-class taxonomy / concurrency / atomicity / idempotency / recovery / edge case / observability / fail-mode / resource-leak / driving-port purity). Implementing the adapter contract row turns the AT GREEN. Fail-for-right-reason token: `AssertionError` (or expected-exception-not-raised) against the declared property — NOT against feature behavior.

The distinguishing token between the two modes is **property-matrix row contract**: an adapter-integration AT names the property it exercises (one row of the 10-property matrix), and the assertion shape verifies that the adapter satisfies the named row. The acceptance AT does NOT cite a property-matrix row — it asserts feature outcome through the driving port.

### Mandate-7 applies in both modes

The fail-for-right-reason gate is mandatory in both modes. Crafters MUST verify the RED failure is a semantic `AssertionError` (or expected-exception-not-raised), NOT a collection error, NOT an import error, NOT a skip marker, NOT a timeout. The mode distinction does NOT relax the gate; it only changes the assertion subject (feature behavior vs property-matrix row contract).

### Practical implication for DELIVER crafters

When the slice plan declares an adapter-integration slice, the crafter knows the GREEN target is the adapter contract row, not the feature behavior. A crafter who tries to GREEN an adapter-integration AT by changing the feature workflow violates the mode — they are answering an acceptance question with an adapter answer, or vice versa. Surface to the Phase C reviewer if the slice plan does not declare which mode applies.
