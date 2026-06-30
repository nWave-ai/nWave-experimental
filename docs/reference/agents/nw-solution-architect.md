# nw-solution-architect

Use for DESIGN wave - collaborates with user to define system architecture, component boundaries, technology selection, and creates architecture documents with business value focus. Hands off to acceptance-designer.

**Wave:** DESIGN
**Model:** inherit
**Max turns:** 45
**Tools:** Read, Write, Edit, Glob, Grep, Bash, Task, mcp__tsunami__callers_of, mcp__tsunami__reads_of, mcp__tsunami__never_wired, mcp__tsunami__atoms_in_file, mcp__tsunami__adr_section

## Commands

- [`/nw-deliver`](../commands/index.md)
- [`/nw-design`](../commands/index.md)
- [`/nw-diagram`](../commands/index.md)
- [`/nw-discuss`](../commands/index.md)
- [`/nw-finalize`](../commands/index.md)
- [`/nw-review`](../commands/index.md)
- [`/nw-roadmap`](../commands/index.md)
- [`/nw-spike`](../commands/index.md)

## Skills

- [nw-architectural-styles-tradeoffs](../skills/nw-architectural-styles-tradeoffs.md) — Architectural style selection decision matrices, trade-off analysis, structural enforcement rules, and combination patterns. Load when choosing or evaluating architecture styles.
- [nw-architecture-patterns](../skills/nw-architecture-patterns.md) — Comprehensive architecture patterns, methodologies, quality frameworks, and evaluation methods for solution architects. Load when designing system architecture or selecting patterns.
- [nw-code-analysis-port](../skills/nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) THROUGH the nWave vendor-neutral CodeFactPort, preferring Tsunami, then AST, with grep as last resort and degrading LOUD. Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.
- [nw-domain-driven-design](../skills/nw-domain-driven-design.md) — Strategic and tactical DDD patterns, bounded context discovery, context mapping, aggregate design rules, and decision frameworks for when to apply DDD
- [nw-formal-verification-tlaplus](../skills/nw-formal-verification-tlaplus.md) — TLA+ and PlusCal for specifying distributed system invariants. Decision heuristics for when formal verification adds value, key patterns, state explosion management, and alternatives comparison.
- [nw-sa-critique-dimensions](../skills/nw-sa-critique-dimensions.md) — Architecture quality critique dimensions for peer review. Load when invoking solution-architect-reviewer or performing self-review of architecture documents.
- [nw-security-by-design](../skills/nw-security-by-design.md) — Security design principles, STRIDE threat modeling, OWASP Top 10 architectural mitigations, and secure patterns. Load when designing systems or reviewing architecture for security.
- [nw-stress-analysis](../skills/nw-stress-analysis.md) — Advanced architecture stress analysis methodology for designing systems that survive unknown stresses. Load when --residuality flag is used or when designing high-uncertainty, mission-critical systems.
