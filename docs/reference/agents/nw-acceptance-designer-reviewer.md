# nw-acceptance-designer-reviewer

Independently falsifies the acceptance oracle bound by one DeliveryContract, with emphasis on observable value, cross-layer failure handling, PBT, and real driving-port wiring.

**Wave:** DISTILL
**Model:** sonnet
**Max turns:** 20
**Tools:** Read, Glob, Grep, Task, Bash, Skill

## Preloaded skills

- [nw-adversarial-refutation](../skills/nw-adversarial-refutation.md) — The adversarial-refutation review stance — assume the artifact is WRONG and try to PROVE it, default-to-refuted, diverse lenses, and an exhibited executable counterexample. The shared SSOT every DELIVER review (per-slice C_REVIEWER_AUDIT + per-feature F_FINAL_REVIEW) applies so the expensive final swarm is needed less.
- [nw-bdd-methodology](../skills/nw-bdd-methodology.md) — BDD patterns for acceptance test design - Given-When-Then structure, scenario writing rules, pytest-bdd implementation, anti-patterns, and living documentation
- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) through the vendor-neutral CLI `des code-fact`, degrading LOUD through bundled adapters (AST, TextSearch). Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-test-design-mandates](../skills/nw-test-design-mandates.md) — Design mandates for acceptance tests - hexagonal boundary, business language abstraction, user journey completeness, pure function extraction, 3 Pillars (domain language / chained narrative / production composition), and the layered ATD discipline (Universe-bound assertion, layer-dependent PBT mode, two-tier acceptance, example-based sad paths). Lean recomposing core - routes to three narrow mandate modules.
