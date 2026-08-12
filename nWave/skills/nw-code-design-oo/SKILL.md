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

### Declared inputs at the boundary

The OO reading of `contract:declared-inputs-not-ambient-reads` (SSOT:
`nw-cross-cutting-invariants` — the gate list and the anchor live there, not
here). It is `Capability injection` above restated as a review question, because
that pattern is easy to agree with and easy not to apply.

> **What does this component read that nobody passed it?** For every gate the
> clause lists, decide at the boundary: a constructor parameter, an injected
> capability, or an explicit override — with the ambient lookup kept as a default
> the caller may state.

Resolve it **where the caller can see it**. A gate resolved lazily, at first use
deep inside a method, is read outside the window in which the caller — or a test
— controls the environment, so even a caller that wanted to declare it cannot.

Test-side mirror: the Algebraic Analysis Before the Scenario mandate
(`nw-test-design-mandates`), its declared-inputs question.

### Enumerate the outcomes before choosing the return type

> **How many outcomes does this operation have — and does its signature carry
> every one of them?** "It returns the value and raises on the bad case" is the
> wrong answer: that is N-1 outcomes in the type and one in the control flow.
> **If any outcome is not in the return type, put it there** — a value the caller
> branches on, with the illegal combinations unconstructible (enforce in the
> constructor: only the outcome that carries a payload may carry one, and it
> always does).

Why this is a design rule, not a style preference: `except` matches on class
**identity**, so a raised outcome couples the caller to the exact module object
the raiser was loaded from. Where the same package is reachable by more than one
path — a source tree plus an installed runtime, a harness that adjusts
`sys.path`, a plugin cache — that identity is not guaranteed. The `except` then
fails to match and a *handled* outcome escapes as a crash, in an environment
nobody was testing.

Keep `raise` for what it is good at: a **programming error** (a broken
precondition, an import-time drift guard) where crashing is the correct outcome
and no `except` is meant to cross a module boundary to catch it.

FP states the canonical form of the same rule — a total function into a sum type
(`nw-code-design-fp` § Railway, "Count the outcomes before you choose the return
type"). This is its OO translation.

Empirical anchor, 2026-08-06 (`des.cli.phases`): CI reported `UnknownPhaseName`
propagating out of `_resolve` from the line INSIDE its own `try`, with the
matching `except` on the next line. `resolve_phase` documented three outcomes,
returned two, threw the third. Returning all three closed the failure class
*without* establishing why the module loaded twice — a fix that does not depend
on that answer is a design fix rather than a patch.

## Cross-cutting invariants (load them — they are not restated here)

Paradigm- and role-independent rules live in ONE shipped home: `nw-cross-cutting-invariants`.
Load it alongside this skill and honour these clauses by id — they are NOT duplicated here:

- `data:consumer-known-before-produced` — a datum is produced only because a named consumer
  reads it, and you must name the JOIN KEY it will be related on. No reader, or no key → the
  datum is unjustified.
- `gate:self-explaining-what-why-how` — every rejection states WHAT / WHY / HOW.
- `gate:design-principles-gdp-1-9` — the canonical gate-design contract.
