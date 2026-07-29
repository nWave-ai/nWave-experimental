# nw-ddd-architect-reviewer

Use for reviewing DDD domain models. Validates bounded context boundaries, aggregate design, context mapping, ES/CQRS recommendations, and ubiquitous language consistency.

**Wave:** DESIGN
**Model:** sonnet
**Max turns:** 25
**Tools:** Read, Glob, Grep, Task, Bash, mcp__tsunami__callers_of, mcp__tsunami__reads_of, mcp__tsunami__never_wired, mcp__tsunami__atoms_in_file, mcp__tsunami__adr_section

## Skills

- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) THROUGH the nWave vendor-neutral CodeFactPort, preferring Tsunami, then AST, with grep as last resort and degrading LOUD. Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-ddd-architect](../skills/nw-ddd-architect.md) — DDD architect design-time mandates — the Fixture-Fanout Enumeration Mandate for shared-substrate per-caller migration (enumerate production callers plus fixture sites plus atomic bundle scope, mechanically enforced) that both the ddd-architect and its reviewer load by name
- [nw-ddd-strategic](../skills/nw-ddd-strategic.md) — Strategic DDD — bounded context discovery, context mapping patterns, subdomain classification, ubiquitous language, and organizational alignment
- [nw-ddd-tactical](../skills/nw-ddd-tactical.md) — Tactical DDD — aggregate design rules, entities, value objects, domain events, repositories, domain services, and anti-pattern detection
