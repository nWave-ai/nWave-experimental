# nw-ddd-architect

Use for DESIGN wave domain modeling. Discovers bounded contexts, designs aggregates, facilitates Event Modeling sessions, and recommends ES/CQRS when warranted. Writes to architecture SSOT.

**Wave:** DESIGN
**Model:** sonnet
**Max turns:** 45
**Tools:** Read, Write, Edit, Glob, Grep, Bash, Task

## Commands

- [`/nw-design`](../commands/index.md)

## Skills

- [nw-algebraic-design-protocol](../skills/nw-algebraic-design-protocol.md) — The METHOD for finding a design — name observations and equality before constructors, then follow any contradiction to the type or observation that causes it. Use when a design decision is contested, a law has exceptions, a census or model keeps producing wrong answers, or a representation change must preserve meaning. Complements nw-fp-algebra-driven-design, which catalogues the structures; this says how to arrive at one and what to do when it breaks.
- [nw-certainty-by-construction](../skills/nw-certainty-by-construction.md) — Turn a stable domain claim into a construction boundary so the invalid state cannot be built, and state honestly what remains unguarded. Use when a requirement says an invalid state or transition must not occur, when values need a canonical form, or when a rewrite/cache/optimisation must preserve meaning. Complements nw-fp-domain-modeling, which shows the encodings; this decides whether to encode, how strong the claim really is, and what obligation is left over.
- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) through the vendor-neutral CLI `des code-fact`, degrading LOUD through bundled adapters (AST, TextSearch). Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-code-design-fp](../skills/nw-code-design-fp.md) — FP code-design SSOT — the WHAT-to-design catalog (algebra-driven design, domain modelling with types, railway/error-track isolation) shared by the solution architect (design-time) and the functional crafter (execution-time).
- [nw-code-design-oo](../skills/nw-code-design-oo.md) — OO code-design SSOT — the WHAT-to-design anti-smell catalog (Object Calisthenics, RPP smell taxonomy, effect isolation) shared by the solution architect (design-time) and the crafter (execution-time).
- [nw-cross-cutting-invariants](../skills/nw-cross-cutting-invariants.md) — Cross-cutting normative invariants — paradigm-independent and role-independent rules that bind every architect and crafter (data justification, gate design GDP-1..9, self-explaining surfaces). SHIPPED home of these definitions; cite by clause id, never re-declare.
- [nw-ddd-architect](../skills/nw-ddd-architect.md) — DDD architect design-time mandates — the Fixture-Fanout Enumeration Mandate for shared-substrate per-caller migration (enumerate production callers plus fixture sites plus atomic bundle scope, mechanically enforced) that both the ddd-architect and its reviewer load by name
- [nw-ddd-event-modeling](../skills/nw-ddd-event-modeling.md) — Event Modeling facilitation technique — brainstorm events, identify commands and views, define aggregate boundaries, write Given-When-Then specifications
- [nw-ddd-eventsourcing](../skills/nw-ddd-eventsourcing.md) — Event Sourcing and CQRS as DDD implementation patterns — when to use, aggregate event streams, projections, snapshots, sagas, upcasting, conflict resolution
- [nw-ddd-strategic](../skills/nw-ddd-strategic.md) — Strategic DDD — bounded context discovery, context mapping patterns, subdomain classification, ubiquitous language, and organizational alignment
- [nw-ddd-tactical](../skills/nw-ddd-tactical.md) — Tactical DDD — aggregate design rules, entities, value objects, domain events, repositories, domain services, and anti-pattern detection
