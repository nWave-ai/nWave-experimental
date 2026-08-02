---
name: nw-code-design-fp
description: FP code-design SSOT — the WHAT-to-design catalog (algebra-driven design, domain modelling with types, railway/error-track isolation) shared by the solution architect (design-time) and the functional crafter (execution-time).
---

# FP Code Design

Design-time catalog for functional work. The architect loads this to design the
domain algebra, the type-level model, and the error/effect tracks BEFORE DISTILL
authors ATs; the functional crafter loads the same SSOT for execution. This is
the WHAT-to-design subset — execution mechanics (naive/discover/freeze testing,
ORM/persistence mapping, language idioms) stay in `nw-fp-algebra-driven-design`,
`nw-fp-domain-modeling`, and the language skills.

## Algebra-Driven Design

Discover the API before implementing by specifying the rules (equations)
operations must satisfy. Rules generate property tests, reveal missing features,
and catch contradictions at design time (minutes) not production (days).

### Design process (5 steps)

1. **Start with scope, not implementation** — do not fix data structures upfront.
2. **Define observations first** — how users extract information; observations
   define equality (two values equal if no observation distinguishes them).
3. **Add operations incrementally** — for each, write rules connecting it to
   existing ones. The web of rules IS the design.
4. **Let messy rules signal problems** — complex rules mean coarse building
   blocks; decompose until each rule is near-trivial.
5. **Generalize aggressively** — remove unnecessary type constraints; if
   operations ignore contained values, parameterize over them.

### Algebraic structures (recognize → reuse known rules)

| Structure | Defining rule | Design signal / use |
|-----------|---------------|---------------------|
| Semigroup | `(a·b)·c = a·(b·c)` (associative) | Combining where parenthesization is irrelevant (concat, min/max, config merge) |
| Monoid | Associative + identity `e·x = x = x·e` | Safe defaults, fold/reduce over collections (`(+,0)`, `(concat,[])`) |
| Semilattice | Associative + commutative + idempotent | Conflict resolution, CRDTs, eventually-consistent merges (`max`) |
| Functor | Preserves identity + composition under `map` | Operations agnostic to the contained type |
| Applicative | Element-wise combine + uniform fill | Combining containers of differing content |
| Group | Monoid + inverse `x·x⁻¹ = e` | Undo, reversible spatial transforms |

Heuristic: associative? look for an identity → monoid. Have identity? check
commutativity/inverse → semilattice/group. Each upgrade unlocks new rules.

### API design properties (8, three categories)

| Category | Properties |
|----------|-----------|
| Clarity | Compositional · Task-relevant · Interrelated (rules link every operation) |
| Economy | Parsimonious · Orthogonal · Generalized (no needless type constraints) |
| Safety | Closed (valid construction ⇒ valid semantics) · Complete (max structure discovered) |

### Decision tree — is algebraic thinking worth it?

- Domain about COMBINING → rules (order/defaults/inverses) map to a known structure.
- Domain about TRANSFORMING → look for Functor / structure-preserving patterns.
- Small, well-understood surface → conventional design (algebra adds overhead).
- Otherwise → rules still clarify, even without standard structures.

## Domain Modelling with Types

Make illegal states unrepresentable; model workflows as pipelines; push errors to
the type level. Every rule encoded in a type needs no unit test.

### Building blocks and wrappers

1. **AND (record types)** — value has ALL fields (Order = CustomerInfo AND
   Address AND OrderLines).
2. **OR (choice types)** — value is ONE OF alternatives (ProductCode = Widget OR
   Gizmo). Compose recursively to express any domain structure.
3. **Domain wrappers** — never use raw primitives in the domain; wrap each
   concept so the compiler distinguishes `CustomerId` from `OrderId`. The type
   name is the documentation.
4. **Smart constructors** — private raw constructor; a `create` validates and
   returns a `Result`. Once constructed, a value is guaranteed valid — no
   defensive checks downstream.

### Make illegal states unrepresentable

| Smell | Fix |
|-------|-----|
| `{ Email; IsVerified: bool }` flag | Distinct `VerifiedEmail` / `UnverifiedEmail` types; verification-requiring functions take `VerifiedEmail` |
| `{ Email: option; Address: option }` (both could be None) | Choice type `EmailOnly \| AddressOnly \| EmailAndAddress` — "at least one" enforced structurally |
| List that must be non-empty | `NonEmptyList<T>` — zero-element state cannot be constructed |

### Workflow as pipeline

Every workflow is one function: command in, events out. Decompose into stateless,
pure, single-input/output steps, each transforming one document type to the next:

```
UnvalidatedOrder → ValidatedOrder → PricedOrder → Events
```

Each step name is a domain concept; each step is independently testable.

### State machine with types

Model each lifecycle stage / state as a separate type; a top-level choice type
unifies them (`Cart = Empty | Active of ActiveData | Paid of PaidData`).
Transition functions pattern-match the current state and return the next.
Benefits: all states explicit, per-state data, invalid transitions rejected by
types, exhaustiveness warnings reveal unhandled cases. New states (e.g.
`Refunded`) add without breaking existing code.

### Dependencies and naming

- Declare each step's dependencies as leading parameters, primary input last
  (enables partial application = functional DI). Top-level workflow hides
  dependencies; internal steps make them explicit.
- Types as nouns · workflows as verbs · events past-tense · commands imperative ·
  lifecycle prefixes (`Unvalidated…`/`Validated…`/`Priced…`).

### Decision tree — how to model a concept?

```
Simple value with validation?        → Domain Wrapper + Smart Constructor
One of several alternatives?         → Choice Type (sum)
Groups several values?               → Record Type (product)
Distinct lifecycle stages?           → State Machine with Types
Transforms data through stages?      → Workflow Pipeline
```

## Railway

Each step returns a `Result`; the pipeline runs on two tracks (success/failure)
and short-circuits on the first failure. Design the error track up front.

```
rawInput
  |> validateOrder        -- Result<ValidOrder, Error>
  |> bind calculateTotal  -- Result<PricedOrder, Error>
  |> bind checkInventory  -- Result<ConfirmedOrder, Error>
  |> map  generateReceipt -- Result<Receipt, Error>
```

### Combinators

| Combinator | Role |
|------------|------|
| `map` | Transform the success value (one-track → two-track) |
| `bind` | Chain a function that itself returns `Result` |
| `mapError` | Transform the error value (lift a step error into the common type) |
| `tee` | Side effect without changing the value (logging) |

### Error classification (design decision per category)

| Category | Examples | Strategy |
|----------|----------|----------|
| Domain errors | Validation failure, out of stock | Model as types, return via `Result` |
| Panics | Out of memory, null reference | Throw; catch at top level |
| Infrastructure errors | Network timeout, auth failure | Case-by-case |

### Design rules

1. **Unify error types** — define one common error choice type; `mapError` to
   lift each step's error before composing.
2. **Accumulate when the user needs all errors** — use Applicative validation
   (runs all checks, collects errors into a list) for forms / batch input;
   standard `bind` short-circuits on the first.
3. **Document effects in signatures** — `Result` for errors, `Async` for I/O,
   `Option` for missing data; the signature is the contract.

## Cross-cutting invariants (load them — they are not restated here)

Paradigm- and role-independent rules live in ONE shipped home: `nw-cross-cutting-invariants`.
Load it alongside this skill and honour these clauses by id — they are NOT duplicated here:

- `data:consumer-known-before-produced` — a datum is produced only because a named consumer
  reads it, and you must name the JOIN KEY it will be related on. No reader, or no key → the
  datum is unjustified.
- `gate:self-explaining-what-why-how` — every rejection states WHAT / WHY / HOW.
- `gate:design-principles-gdp-1-9` — the canonical gate-design contract.
