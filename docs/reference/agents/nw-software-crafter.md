# nw-software-crafter

Implements the OO change for one ready ordered batch.

**Wave:** Other
**Model:** claude-opus-5
**Max turns:** 40
**Tools:** Read, Edit, Glob, Bash, StructuredOutput

## Commands

- [`/nw-mikado`](../commands/index.md)
- [`/nw-refactor`](../commands/index.md)
- [`/nw-spike`](../commands/index.md)

## Preloaded skills

- [nw-certainty-by-construction](../skills/nw-certainty-by-construction.md) — Turn a stable layer claim (domain, application, adapter, or infrastructure) into a construction boundary so the invalid state cannot be built, and state honestly what remains unguarded. Use when a requirement says an invalid state or transition must not occur, when values need a canonical form, or when a rewrite/cache/optimisation must preserve meaning. Complements nw-fp-domain-modeling, which shows the encodings; this decides whether to encode, how strong the claim really is, and what obligation is left over.
- [nw-code-craftsmanship](../skills/nw-code-craftsmanship.md) — Universal OO/FP craftsmanship foundation — domain-language naming, small cohesive units, semantic DRY/SSOT, reuse-before-new, one owner per rule/config/fact, prefactoring before new behavior, ports/adapters for testability. Consult before writing or reviewing any unit of code, either paradigm.
- [nw-code-design-oo](../skills/nw-code-design-oo.md) — OO code-design SSOT — the WHAT-to-design anti-smell catalog (Object Calisthenics, RPP smell taxonomy, effect isolation) shared by the solution architect (design-time) and the crafter (execution-time).
- [nw-tdd-methodology](../skills/nw-tdd-methodology.md) — Deep knowledge for Outside-In TDD - double-loop architecture, ATDD integration, port-to-port testing, walking skeletons, and test doubles policy
- [nw-tdd-methodology-port-to-port](../skills/nw-tdd-methodology-port-to-port.md) — What a test asserts on and where it enters - port-to-port discipline at all test levels, the layer-specific Universe, refactoring-resilience, and the hexagonal per-layer testing strategy
- [nw-tdd-methodology-test-doubles](../skills/nw-tdd-methodology-test-doubles.md) — Choosing and building a test double - Meszaros taxonomy, classical-vs-mockist verification, the mock-only-at-port-boundaries policy, and the contract that every InMemory double must validate inputs like the real adapter
- [nw-type-level-design](../skills/nw-type-level-design.md) — Design or review evidence-preserving APIs that model invalid states, state transitions, capabilities, and trusted construction proportionately to the target language.
- [nw-typesafe-system-one](../skills/nw-typesafe-system-one.md) — Use Jev System One for every supported, authorized semantic judgment when available: relevance selection, handoff preflight, evidence mapping, finding clustering, and confidence-gated escalation.
