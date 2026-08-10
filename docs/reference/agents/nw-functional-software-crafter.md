# nw-functional-software-crafter

DELIVER wave — SLIM functional crafter. GREEN-the-ATs + L1-L6 refactor for FP paradigm (F#/Haskell/Scala/Clojure/Elixir/FP-heavy TS/Py/Kotlin). Pure functions, pipeline composition, types-as-documentation. Test authoring (ATs + paired PBT) is owned by `nw-acceptance-designer`; this agent implements pure functions and refactors. Use when the project follows functional-first. Accepts exactly either the current DES `atdd_pure` envelope or a validated two-header thin DeliveryContract authority; bare Agent/Task dispatch is refused. For current `atdd_pure`, prefer `des dispatch` and pass its envelope VERBATIM; `/nw-deliver` and `/nw-bugfix` also drive it. For analysis, measurement or investigation pick a different agent — this one is for implementation only.

**Wave:** DELIVER
**Model:** sonnet
**Max turns:** 45
**Tools:** Read, Write, Edit, Bash, Glob, Grep, Task

## Commands

- [`/nw-bugfix`](../commands/index.md)
- [`/nw-deliver`](../commands/index.md)
- [`/nw-design`](../commands/index.md)

## Preloaded skills

- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) through the vendor-neutral CLI `des code-fact`, degrading LOUD through bundled adapters (AST, TextSearch). Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-collaboration-and-handoffs](../skills/nw-collaboration-and-handoffs.md) — Cross-agent collaboration protocols, workflow handoff patterns, and commit message formats for TDD/Mikado/refactoring workflows
- [nw-crafter-discipline-atdd-pure](../skills/nw-crafter-discipline-atdd-pure.md) — Crafter discipline contract for the ATDD-pure workflow — what the slim crafter does in Phase A (GREEN-the-ATs with AT-driven minimalism), Phase B (coverage-driven dead-code elimination — DEPRECATED velocity-v2, absorbed into A_GREEN), and Phase E (batch L1-L6 refactor), plus hard prohibitions
- [nw-cross-cutting-invariants](../skills/nw-cross-cutting-invariants.md) — Cross-cutting normative invariants — paradigm-independent and role-independent rules that bind every architect and crafter (data justification, gate design GDP-1..9, self-explaining surfaces). SHIPPED home of these definitions; cite by clause id, never re-declare.
- [nw-fp-clojure](../skills/nw-fp-clojure.md) — Clojure language-specific patterns, data-first modeling, REPL-driven development, and spec
- [nw-fp-domain-modeling](../skills/nw-fp-domain-modeling.md) — Domain modeling with algebraic data types, smart constructors, and type-level error handling
- [nw-fp-fsharp](../skills/nw-fp-fsharp.md) — F# language-specific patterns, Railway-Oriented Programming, and Computation Expressions
- [nw-fp-haskell](../skills/nw-fp-haskell.md) — Haskell language-specific patterns, GADTs, type classes, and effect systems
- [nw-fp-hexagonal-architecture](../skills/nw-fp-hexagonal-architecture.md) — Hexagonal architecture patterns with pure core and side-effect shell for functional codebases
- [nw-fp-kotlin](../skills/nw-fp-kotlin.md) — Kotlin language-specific patterns with Arrow, Raise DSL, and coroutine-based effects
- [nw-fp-scala](../skills/nw-fp-scala.md) — Scala 3 language-specific patterns with ZIO, Cats Effect, and opaque types
- [nw-fp-usable-design](../skills/nw-fp-usable-design.md) — Naming conventions, API ergonomics, and usability patterns for functional code
- [nw-hexagonal-testing](../skills/nw-hexagonal-testing.md) — 5-layer agent output validation, I/O contract specification, vertical slice development, and test doubles policy with per-layer examples
- [nw-legacy-refactoring-ddd](../skills/nw-legacy-refactoring-ddd.md) — DDD-guided legacy refactoring patterns -- strangler fig, bubble context, ACL migration, 14 tactical/strategic/infrastructure patterns, and incremental monolith-to-microservices methodology
- [nw-mutation-test](../skills/nw-mutation-test.md) — Runs feature-scoped mutation testing to validate test suite quality. Use after implementation to verify tests catch real bugs (kill rate >= 80%).
- [nw-quality-framework](../skills/nw-quality-framework.md) — Quality gates - 11 commit readiness gates, build/test protocol, validation checkpoints, and quality metrics
- [nw-refactor](../skills/nw-refactor.md) — Applies the Refactoring Priority Premise (RPP) levels L1-L6 for systematic code refactoring. Use when improving code quality through structured refactoring passes.
- [nw-tdd-methodology](../skills/nw-tdd-methodology.md) — Deep knowledge for Outside-In TDD - double-loop architecture, ATDD integration, port-to-port testing, walking skeletons, and test doubles policy
- [nw-tlaplus-verification](../skills/nw-tlaplus-verification.md) — TLA+ formal verification for design correctness and PBT pipeline integration
