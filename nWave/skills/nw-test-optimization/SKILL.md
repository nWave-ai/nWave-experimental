---
name: nw-test-optimization
description: Methodology for minimizing test count while maximizing behavioral coverage - lean core composing behavior-counting, anti-patterns, consolidation, budget-gate, paradigm-match, coverage-validation, scope-selection modules
user-invocable: false
disable-model-invocation: true
---

# Test Optimization Methodology (core)

## Mission

> Minimize tests, maximize value, reduce feedback time, maintain quality.
> (Ale, 2026-04-28: "Bisogna minimizzare i test, massimizzare il valore per ridurre il tempo di feedback, mantenendo la qualità.")

This skill operationalizes that mission. Apply during DELIVER COMMIT, scheduled audits, or `/nw-optimize-tests` invocations.

This is a lean core. The methodology lives in 7 one-job modules. Load the module whose trigger matches the situation; never re-inline its content here.

## Module loading table (module → trigger)

| Module | Kind | Trigger — load when |
|--------|------|---------------------|
| `nw-test-optimization-behavior-counting` | KNOWLEDGE | "what counts as a behavior here / how many distinct behaviors does this scope expose" |
| `nw-test-optimization-anti-patterns` | KNOWLEDGE | "is this test an anti-pattern — block at review" |
| `nw-test-optimization-consolidation` | KNOWLEDGE | "I have redundant tests — how do I collapse them without losing coverage" |
| `nw-test-optimization-budget-gate` | PROCEDURE | "should I author more tests / is this scope's count above budget" |
| `nw-test-optimization-paradigm-match` | KNOWLEDGE | "which test paradigm fits this test shape — before authoring/migrating" |
| `nw-test-optimization-coverage-validation` | PROCEDURE | "before declaring an optimization done, prove no coverage was lost" |
| `nw-test-optimization-scope-selection` | KNOWLEDGE | "invoked without a specific scope — what do I attack first" |

Path form: `~/.claude/skills/{module}/SKILL.md`.

## Composition

- COMPOSES (KNOWLEDGE): `nw-test-optimization-behavior-counting`, `nw-test-optimization-anti-patterns`, `nw-test-optimization-consolidation`, `nw-test-optimization-paradigm-match`, `nw-test-optimization-scope-selection`.
- COMPOSES (PROCEDURE): `nw-test-optimization-budget-gate`, `nw-test-optimization-coverage-validation`.

## What This Methodology Does NOT Cover

- Test infrastructure (fixtures, conftest, plugins) — that is platform-architect or troubleshooter scope
- Production code refactoring — `/nw-refactor` and the crafter scope
- New test authoring — crafter scope (DELIVER wave)
- Adapter integration tests — different rules apply (real I/O, no parametrize-collapse there); see `nw-hexagonal-testing` skill

## Cross-References

- `nw-tdd-methodology` — Mandate 1 (Observable Behavioral Outcomes), Mandate 5 (Parametrize Input Variations)
- `nw-tdd-review-enforcement` — reviewer block conditions
- `nw-mutation-test` — coverage-preserving validation via mutation kill rate
- `nw-property-based-testing` — PBT paradigm, falsifier-gate for closed-world domains
- `nw-test-design-mandates` — universe-per-layer, state-delta + Universe matrix (§263-270)
- `nw-test-refactoring-catalog` — refactoring patterns for test code structure
- `docs/analysis/investigation-overtesting-hypothesis-2026-04-28.md` — empirical evidence (~580 removable tests, 18% of unit suite, the gap is enforcement decay + loose behavior definition)
- Empirical speedup commits 2026-05-18: `c2637f6c8` (parametrize-collapse 8.9×), `defc07f0d` (single-lifecycle 2.4×), `e97c94663`+`a90606d6b` (CVE+timeout+tiktoken)
