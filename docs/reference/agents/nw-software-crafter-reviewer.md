# nw-software-crafter-reviewer

Use for review and critique tasks. The AT-density-completeness audit is primary whenever the active workflow requests it; code-quality and TDD-discipline review are secondary. Runs on Haiku for cost efficiency.

**Wave:** DELIVER
**Model:** sonnet
**Max turns:** 25
**Tools:** Read, Glob, Grep, Task, Bash

## Preloaded skills

- [nw-adversarial-refutation](../skills/nw-adversarial-refutation.md) — The adversarial-refutation review stance — assume the artifact is WRONG and try to PROVE it, default-to-refuted, diverse lenses, and an exhibited executable counterexample. The shared SSOT every DELIVER review (per-slice C_REVIEWER_AUDIT + per-feature F_FINAL_REVIEW) applies so the expensive final swarm is needed less.
- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) through the vendor-neutral CLI `des code-fact`, degrading LOUD through bundled adapters (AST, TextSearch). Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-tdd-methodology](../skills/nw-tdd-methodology.md) — Deep knowledge for Outside-In TDD - double-loop architecture, ATDD integration, port-to-port testing, walking skeletons, and test doubles policy
- [nw-tdd-review-enforcement](../skills/nw-tdd-review-enforcement.md) — Test design mandate enforcement, test budget validation, active-workflow slice-evidence validation, and external validity checks for the software crafter reviewer
