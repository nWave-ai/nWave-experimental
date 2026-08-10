# nw-ddd-architect-reviewer

Use for reviewing DDD domain models. Validates bounded context boundaries, aggregate design, context mapping, ES/CQRS recommendations, and ubiquitous language consistency.

**Wave:** DESIGN
**Model:** sonnet
**Max turns:** 25
**Tools:** Read, Glob, Grep, Task, Bash

## Preloaded skills

- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) through the vendor-neutral CLI `des code-fact`, degrading LOUD through bundled adapters (AST, TextSearch). Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
