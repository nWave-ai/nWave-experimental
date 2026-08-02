---
name: nw-code-design-oo
description: OO code-design SSOT — the WHAT-to-design anti-smell catalog (Object Calisthenics, RPP smell taxonomy, effect isolation) shared by the solution architect (design-time) and the crafter (execution-time).
---

# OO Code Design

Design-time anti-smell catalog for object-oriented work. The architect loads this
to design smell-free domain types and module boundaries BEFORE DISTILL authors
ATs; the crafter loads the same SSOT for the execution mechanics that enforce it.
This file is the WHAT-to-design subset — execution mechanics (batch-then-verify,
commit gates, build/test protocol, RPP dispatch) stay in `nw-quality-framework`
and `nw-refactor`.

## Object Calisthenics

9 design constraints for clean OO in the hexagonal core (Jeff Bay). Design domain
and application types to satisfy these; enforced at GREEN+COMMIT by the crafter.

| # | Rule | Design intent | Layer |
|---|------|---------------|-------|
| 1 | One indentation level per method | Forces decomposition | Domain, Application |
| 2 | No `else` keyword | Guard clauses, early returns | Domain, Application |
| 3 | Wrap all primitives and strings | Value objects at boundaries | Domain |
| 4 | First-class collections | Domain collection types | Domain |
| 5 | One dot per line | Law of Demeter | Domain, Application |
| 6 | No abbreviations | Intention-revealing names | All |
| 7 | Small entities (<50 LOC classes, <10 LOC methods) | SRP | Domain, Application |
| 8 | Max 2 instance variables per class | Promotes decomposition | Domain |
| 9 | No getters/setters | Tell, don't ask | Domain, Application |

**Rule 9 relaxation** — getters allowed for: DTOs/response objects at port
boundaries, CQRS read models, value objects with computed properties
(`Money.amount`), framework/ORM mapping. Rule 9 applies strictly to domain
entities and application services.

**Scope** — applies inside the hexagon (domain + application). Does NOT apply to
adapters, infrastructure, DTOs, or configuration.

## RPP Smell Taxonomy

Smell names an architect detects in a design before code is written. Detection is
design-time; the refactor execution (cascade planning, batch-then-verify) is
crafter-only in `nw-refactor`. Levels L1 Readability | L2 Complexity |
L3 Responsibilities | L4 Abstractions | L5 Design Patterns | L6 SOLID++.

| Level | Smell | Design-time implication |
|-------|-------|-------------------------|
| L3 | Primitive Obsession | Raw int/str carrying domain meaning → introduce a value object |
| L3 | Magic Numbers | Bare literal with hidden semantics → name it (enum / constant / value object) |
| L3 | Tell-Don't-Ask | Caller queries state then decides → move the decision onto the owning object |
| L3 | Feature Envy | Method reaches into another type's data → relocate behavior to that type |
| L3 | God Object | One type owns too many responsibilities → split along bounded responsibilities |
| L3 | Large Class | Class exceeds SRP / Calisthenics size → extract collaborators |
| L4 | Shotgun Surgery | One change forces edits across many sites → consolidate the concept into one home |

Design rule: a smell named here at design time must not survive into the design
artifact — resolve it in the type/boundary decisions, not at DELIVER.

## Effect Isolation

Design components so the bug class "side-effect-free function silently writes" is
non-representable, not testable-around. Push contract enforcement up the type
hierarchy as far as the language allows. Three levers:

- **Functional Core / Imperative Shell** (Bernhardt) — business logic in pure
  functions; effects only at a thin shell. Approximates IO-monad separation in
  any language.
- **Plan-value pattern** — dry-run / preview / validate functions return a `Plan`
  data value, never silent side effects (`dry_run(cfg) -> Plan` pure; `execute(plan)`
  the only impure call). Makes "preview wrote to disk" structurally impossible.
- **Capability injection** — pass restricted interfaces (`PlanRecorder`,
  `SafeFileSystem(root=tmp)`) at boundaries, never god-objects (`os`,
  `Path.home()`). Approximates capability typing via DI.

Per component, declare a **contract shape**: pure-function (return-only),
bounded-change (declared mutation set), or unbounded-preservation (must return a
Plan, never mutate). A driving port that "only reads" must not expose write
methods — split read/write into separate ports.

## Cross-cutting invariants (load them — they are not restated here)

Paradigm- and role-independent rules live in ONE shipped home: `nw-cross-cutting-invariants`.
Load it alongside this skill and honour these clauses by id — they are NOT duplicated here:

- `data:consumer-known-before-produced` — a datum is produced only because a named consumer
  reads it, and you must name the JOIN KEY it will be related on. No reader, or no key → the
  datum is unjustified.
- `gate:self-explaining-what-why-how` — every rejection states WHAT / WHY / HOW.
- `gate:design-principles-gdp-1-9` — the canonical gate-design contract.
