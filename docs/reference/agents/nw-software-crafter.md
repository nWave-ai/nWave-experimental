# nw-software-crafter

DELIVER wave - SLIM scope (implementation + refactor expert). Crafter implements production code to satisfy ATs authored by acceptance-designer (DISTILL). Does NOT author tests. Phase protocol follows the active workflow mode, projected from the mode registry into this spec.

**Wave:** DELIVER
**Model:** inherit
**Max turns:** 45
**Tools:** Read, Write, Edit, Bash, Glob, Grep, Task, mcp__tsunami__callers_of, mcp__tsunami__reads_of, mcp__tsunami__never_wired, mcp__tsunami__atoms_in_file, mcp__tsunami__adr_section

## Commands

- [`/nw-bugfix`](../commands/index.md)
- [`/nw-deliver`](../commands/index.md)
- [`/nw-design`](../commands/index.md)
- [`/nw-distill`](../commands/index.md)
- [`/nw-execute`](../commands/index.md)
- [`/nw-finalize`](../commands/index.md)
- [`/nw-mikado`](../commands/index.md)
- [`/nw-mutation-test`](../commands/index.md)
- [`/nw-refactor`](../commands/index.md)
- [`/nw-review`](../commands/index.md)
- [`/nw-roadmap`](../commands/index.md)
- [`/nw-spike`](../commands/index.md)

## Skills

- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) THROUGH the nWave vendor-neutral CodeFactPort, preferring Tsunami, then AST, with grep as last resort and degrading LOUD. Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-code-design-oo](../skills/nw-code-design-oo.md) — OO code-design SSOT — the WHAT-to-design anti-smell catalog (Object Calisthenics, RPP smell taxonomy, effect isolation) shared by the solution architect (design-time) and the crafter (execution-time).
- [nw-collaboration-and-handoffs](../skills/nw-collaboration-and-handoffs.md) — Cross-agent collaboration protocols, workflow handoff patterns, and commit message formats for TDD/Mikado/refactoring workflows
- [nw-crafter-discipline-atdd-pure](../skills/nw-crafter-discipline-atdd-pure.md) — Crafter discipline contract for the ATDD-pure workflow — what the slim crafter does in Phase A (GREEN-the-ATs with AT-driven minimalism), Phase B (coverage-driven dead-code elimination — DEPRECATED velocity-v2, absorbed into A_GREEN), and Phase E (batch L1-L6 refactor), plus hard prohibitions
- [nw-hexagonal-testing](../skills/nw-hexagonal-testing.md) — 5-layer agent output validation, I/O contract specification, vertical slice development, and test doubles policy with per-layer examples
- [nw-legacy-refactoring-ddd](../skills/nw-legacy-refactoring-ddd.md) — DDD-guided legacy refactoring patterns -- strangler fig, bubble context, ACL migration, 14 tactical/strategic/infrastructure patterns, and incremental monolith-to-microservices methodology
- [nw-mikado-method](../skills/nw-mikado-method.md) — Enhanced Mikado Method for complex architectural refactoring - systematic dependency discovery, tree-based planning, and bottom-up execution
- [nw-mutation-test](../skills/nw-mutation-test.md) — Runs feature-scoped mutation testing to validate test suite quality. Use after implementation to verify tests catch real bugs (kill rate >= 80%).
- [nw-production-safety](../skills/nw-production-safety.md) — Agent safety boundaries - input validation, output filtering, scope constraints, and document creation policy
- [nw-progressive-refactoring](../skills/nw-progressive-refactoring.md) — Progressive L1-L6 refactoring hierarchy, 22 code smell taxonomy, atomic transformations, test code smells, and Fowler refactoring catalog
- [nw-quality-framework](../skills/nw-quality-framework.md) — Quality gates - 11 commit readiness gates, build/test protocol, validation checkpoints, and quality metrics
- [nw-refactor](../skills/nw-refactor.md) — Applies the Refactoring Priority Premise (RPP) levels L1-L6 for systematic code refactoring. Use when improving code quality through structured refactoring passes.
- [nw-sc-review-dimensions](../skills/nw-sc-review-dimensions.md) — Reviewer critique dimensions for peer review - implementation bias detection, test quality validation, completeness checks, and priority validation
- [nw-tdd-methodology](../skills/nw-tdd-methodology.md) — Deep knowledge for Outside-In TDD - double-loop architecture, ATDD integration, port-to-port testing, walking skeletons, and test doubles policy
