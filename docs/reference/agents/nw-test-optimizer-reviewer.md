# nw-test-optimizer-reviewer

Use to validate test-optimizer outputs - hard-blocks if coverage dropped, production code touched, or anti-patterns went unmarked. Runs on Haiku for cost efficiency. Read-only.

**Wave:** Other
**Model:** haiku
**Max turns:** 25
**Tools:** Read, Glob, Grep, Bash

## Commands

- [`/nw-optimize-tests`](../commands/index.md)

## Preloaded skills

- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) through the vendor-neutral CLI `des code-fact`, degrading LOUD through bundled adapters (AST, TextSearch). Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-tdd-methodology](../skills/nw-tdd-methodology.md) — Deep knowledge for Outside-In TDD - double-loop architecture, ATDD integration, port-to-port testing, walking skeletons, and test doubles policy
- [nw-test-optimization](../skills/nw-test-optimization.md) — Methodology for minimizing test count while maximizing behavioral coverage - lean core composing behavior-counting, anti-patterns, consolidation, budget-gate, paradigm-match, coverage-validation, scope-selection modules
