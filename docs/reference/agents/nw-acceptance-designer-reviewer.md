# nw-acceptance-designer-reviewer

Use for review and critique tasks - Acceptance criteria and BDD review specialist. Runs on Haiku for cost efficiency.

**Wave:** DISTILL
**Model:** sonnet
**Max turns:** 25
**Tools:** Read, Glob, Grep, Task, Bash, mcp__tsunami__callers_of, mcp__tsunami__reads_of, mcp__tsunami__never_wired, mcp__tsunami__atoms_in_file, mcp__tsunami__adr_section

## Commands

- [`/nw-distill`](../commands/index.md)

## Skills

- [nw-ad-critique-dimensions](../skills/nw-ad-critique-dimensions.md) — Review dimensions for acceptance test quality - happy path bias, GWT compliance, business language purity, coverage completeness, walking skeleton user-centricity, priority validation, observable behavior assertions, traceability coverage, and walking skeleton boundary proof
- [nw-adversarial-refutation](../skills/nw-adversarial-refutation.md) — The adversarial-refutation review stance — assume the artifact is WRONG and try to PROVE it, default-to-refuted, diverse lenses, and an exhibited executable counterexample. The shared SSOT every DELIVER review (per-slice C_REVIEWER_AUDIT + per-feature F_FINAL_REVIEW) applies so the expensive final swarm is needed less.
- [nw-bdd-methodology](../skills/nw-bdd-methodology.md) — BDD patterns for acceptance test design - Given-When-Then structure, scenario writing rules, pytest-bdd implementation, anti-patterns, and living documentation
- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) THROUGH the nWave vendor-neutral CodeFactPort, preferring Tsunami, then AST, with grep as last resort and degrading LOUD. Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-test-design-mandates](../skills/nw-test-design-mandates.md) — Design mandates for acceptance tests - hexagonal boundary, business language abstraction, user journey completeness, pure function extraction, 3 Pillars (domain language / chained narrative / production composition), and the layered ATD discipline (Universe-bound assertion, layer-dependent PBT mode, two-tier acceptance, example-based sad paths). Lean recomposing core - routes to three narrow mandate modules.
