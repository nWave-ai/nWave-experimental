# nw-software-crafter-reviewer

Use for review and critique tasks. The AT-density-completeness audit is primary whenever the active workflow requests it; code-quality and TDD-discipline review are secondary. Runs on Haiku for cost efficiency.

**Wave:** DELIVER
**Model:** sonnet
**Max turns:** 25
**Tools:** Read, Glob, Grep, Task, Bash

## Skills

- [nw-adversarial-refutation](../skills/nw-adversarial-refutation.md) — The adversarial-refutation review stance — assume the artifact is WRONG and try to PROVE it, default-to-refuted, diverse lenses, and an exhibited executable counterexample. The shared SSOT every DELIVER review (per-slice C_REVIEWER_AUDIT + per-feature F_FINAL_REVIEW) applies so the expensive final swarm is needed less.
- [nw-algebraic-design-protocol](../skills/nw-algebraic-design-protocol.md) — The METHOD for finding a design — name observations and equality before constructors, then follow any contradiction to the type or observation that causes it. Use when a design decision is contested, a law has exceptions, a census or model keeps producing wrong answers, or a representation change must preserve meaning. Complements nw-fp-algebra-driven-design, which catalogues the structures; this says how to arrive at one and what to do when it breaks.
- [nw-at-completeness-check](../skills/nw-at-completeness-check.md) — Canonical AT completeness gate (lean core) — composes a Tier-1 coverage taxonomy (C1-C7 + 15-item checklist), a Tier-2 structural-invariants gate (S-family), gap routing, and taxonomy lifecycle. Paradigm-neutral. Drives the acceptance-designer reviewer verdict deterministically.
- [nw-certainty-by-construction](../skills/nw-certainty-by-construction.md) — Turn a stable domain claim into a construction boundary so the invalid state cannot be built, and state honestly what remains unguarded. Use when a requirement says an invalid state or transition must not occur, when values need a canonical form, or when a rewrite/cache/optimisation must preserve meaning. Complements nw-fp-domain-modeling, which shows the encodings; this decides whether to encode, how strong the claim really is, and what obligation is left over.
- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) THROUGH the nWave vendor-neutral CodeFactPort, preferring graphify (Tsunami temporarily disabled), then AST, with grep as last resort and degrading LOUD. Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-sc-review-dimensions](../skills/nw-sc-review-dimensions.md) — Reviewer critique dimensions for peer review - implementation bias detection, test quality validation, completeness checks, and priority validation
- [nw-tdd-methodology](../skills/nw-tdd-methodology.md) — Deep knowledge for Outside-In TDD - double-loop architecture, ATDD integration, port-to-port testing, walking skeletons, and test doubles policy
- [nw-tdd-review-enforcement](../skills/nw-tdd-review-enforcement.md) — Test design mandate enforcement, test budget validation, active-workflow slice-evidence validation, and external validity checks for the software crafter reviewer
