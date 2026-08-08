# nw-test-optimizer

Use to minimize test count while preserving coverage. Invoke after a feature lands, when a suite feels slow or noisy, on a scheduled audit, or whenever the maintainer suspects overtesting. Detects byte-identical pairs, parametrize-inflation, language-guarantee tests, AST-shape tests, and migration-collapse opportunities. Never modifies production code.

**Wave:** Other
**Model:** sonnet
**Max turns:** 45
**Tools:** Read, Edit, Write, Bash, Glob, Grep, Task, mcp__tsunami__callers_of, mcp__tsunami__reads_of, mcp__tsunami__never_wired, mcp__tsunami__atoms_in_file, mcp__tsunami__adr_section

## Commands

- [`/nw-optimize-tests`](../commands/index.md)

## Skills

- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) THROUGH the nWave vendor-neutral CodeFactPort, preferring graphify (Tsunami temporarily disabled), then AST, with grep as last resort and degrading LOUD. Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-tdd-methodology](../skills/nw-tdd-methodology.md) — Deep knowledge for Outside-In TDD - double-loop architecture, ATDD integration, port-to-port testing, walking skeletons, and test doubles policy
- [nw-test-optimization](../skills/nw-test-optimization.md) — Methodology for minimizing test count while maximizing behavioral coverage - lean core composing behavior-counting, anti-patterns, consolidation, budget-gate, paradigm-match, coverage-validation, scope-selection modules
