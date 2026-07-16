# nw-solution-architect-reviewer

Architecture design and patterns review specialist - Optimized for cost-efficient review operations using Haiku model.

**Wave:** DESIGN
**Model:** haiku
**Max turns:** 25
**Tools:** Read, Glob, Grep, Task, Bash, mcp__tsunami__callers_of, mcp__tsunami__reads_of, mcp__tsunami__never_wired, mcp__tsunami__atoms_in_file, mcp__tsunami__adr_section

## Commands

- [`/nw-distill`](../commands/index.md)
- [`/nw-review`](../commands/index.md)

## Skills

- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) THROUGH the nWave vendor-neutral CodeFactPort, preferring Tsunami, then AST, with grep as last resort and degrading LOUD. Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-roadmap-review-checks](../skills/nw-roadmap-review-checks.md) — Roadmap-specific validation checks for architecture reviews. Load when reviewing roadmaps for implementation readiness.
- [nw-sar-critique-dimensions](../skills/nw-sar-critique-dimensions.md) — Architecture quality critique dimensions for peer review. Load when performing architecture document reviews.
