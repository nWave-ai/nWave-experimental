# nw-solution-architect-reviewer

Architecture design and patterns review specialist - Optimized for cost-efficient review operations using Haiku model.

**Wave:** DESIGN
**Model:** sonnet
**Max turns:** 25
**Tools:** Read, Glob, Grep, Task, Bash

## Commands

- [`/nw-distill`](../commands/index.md)

## Skills

- [nw-algebraic-design-protocol](../skills/nw-algebraic-design-protocol.md) — The METHOD for finding a design — name observations and equality before constructors, then follow any contradiction to the type or observation that causes it. Use when a design decision is contested, a law has exceptions, a census or model keeps producing wrong answers, or a representation change must preserve meaning. Complements nw-fp-algebra-driven-design, which catalogues the structures; this says how to arrive at one and what to do when it breaks.
- [nw-certainty-by-construction](../skills/nw-certainty-by-construction.md) — Turn a stable domain claim into a construction boundary so the invalid state cannot be built, and state honestly what remains unguarded. Use when a requirement says an invalid state or transition must not occur, when values need a canonical form, or when a rewrite/cache/optimisation must preserve meaning. Complements nw-fp-domain-modeling, which shows the encodings; this decides whether to encode, how strong the claim really is, and what obligation is left over.
- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) through the vendor-neutral CLI `des code-fact`, degrading LOUD through bundled adapters (AST, TextSearch). Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-sar-critique-dimensions](../skills/nw-sar-critique-dimensions.md) — Architecture quality critique dimensions for peer review. Load when performing architecture document reviews.
