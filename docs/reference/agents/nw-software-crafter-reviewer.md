# nw-software-crafter-reviewer

Use for review and critique tasks. Classic mode → code-quality + TDD-discipline review primary. ATDD-pure workflow mode → AT-density-completeness audit PRIMARY at Phase C_REVIEWER_AUDIT and Phase F_FINAL_REVIEW per ADR-027; code review secondary. Runs on Haiku for cost efficiency.

**Wave:** DELIVER
**Model:** haiku
**Max turns:** 25
**Tools:** Read, Glob, Grep, Task, mcp__tsunami__callers_of, mcp__tsunami__reads_of, mcp__tsunami__never_wired, mcp__tsunami__atoms_in_file, mcp__tsunami__adr_section

## Commands

- [`/nw-deliver`](../commands/index.md)
- [`/nw-review`](../commands/index.md)

## Skills

- [nw-adversarial-refutation](../skills/nw-adversarial-refutation.md) — The adversarial-refutation review stance — assume the artifact is WRONG and try to PROVE it, default-to-refuted, diverse lenses, and an exhibited executable counterexample. The shared SSOT every DELIVER review (per-slice C_REVIEWER_AUDIT + per-feature F_FINAL_REVIEW) applies so the expensive final swarm is needed less.
- [nw-at-completeness-check](../skills/nw-at-completeness-check.md) — Canonical AT completeness gate (lean core) — composes a Tier-1 coverage taxonomy (C1-C7 + 15-item checklist), a Tier-2 structural-invariants gate (S-family), gap routing, and taxonomy lifecycle. Paradigm-neutral. Drives the acceptance-designer reviewer verdict deterministically.
- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) THROUGH the nWave vendor-neutral CodeFactPort, preferring Tsunami, then AST, with grep as last resort and degrading LOUD. Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-sc-review-dimensions](../skills/nw-sc-review-dimensions.md) — Reviewer critique dimensions for peer review - implementation bias detection, test quality validation, completeness checks, and priority validation
- [nw-tdd-methodology](../skills/nw-tdd-methodology.md) — Deep knowledge for Outside-In TDD - double-loop architecture, ATDD integration, port-to-port testing, walking skeletons, and test doubles policy
- [nw-tdd-review-enforcement](../skills/nw-tdd-review-enforcement.md) — Test design mandate enforcement, test budget validation, TDD phase validation (3-phase canon per ADR-025), and external validity checks for the software crafter reviewer
