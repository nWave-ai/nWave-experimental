---
name: nw-type-level-design
description: Design or review evidence-preserving APIs that model invalid states, state transitions, capabilities, and trusted construction proportionately to the target language.
user-invocable: false
disable-model-invocation: true
---

# Type-Level Design and Evidence-Preserving APIs

Use this skill when an API must represent valid states, excluded states, a phase
transition, a capability, or evidence obtained at a trust boundary. Choose the
smallest representation that makes ordinary misuse difficult and keeps the
accepted call site clear.

Knowledge basis for the advanced Haskell material: Sandy Maguire, *Thinking
with Types*.

## Trigger

Use when a design or implementation needs one of these:

- an invalid call or state must be rejected or made hard to construct;
- a sum/product, opaque value, smart constructor, result type, or state/phase
  API may make the invariant clearer;
- a successful parse, validation, authorization, or transition must carry
  evidence to the next operation;
- a finite, stable state or capability changes which operations are valid; or
- a proposed generic, phantom, indexed, dependent, GADT, type-family, or
  singleton technique needs a proportionate design review.

Do not trigger merely because an invariant exists. Keep volatile policy,
user-defined schemas, external behavior, time, concurrency, I/O, migration,
and untrusted input at their owning runtime boundary.

## Core design method

1. State the proposition in one sentence: which call or state is excluded, who
   could otherwise construct it, and what harm follows. Name admitted input,
   constructor, consumer, and public observation.
2. Start with the least powerful representation: a named sum for alternatives,
   a product/record for required parts, an opaque value with a smart
   constructor, or a result carrying a reason and validated value. Do not
   replace domain names with a clever encoding.
3. For a phase or capability, name the finite stable states and each permitted
   transition. Expose operations only through the state or evidence they need:
   an operation that may only receive validated input takes the validator's
   evidence type as its parameter. Where the repository runs a checker,
   re-checking inside the operation instead keeps the rule at runtime but
   leaves the checker nothing to reject. Do not let clients forge a later
   phase through a public raw constructor.
4. Sketch one ordinary accepted call and one rejected or refused call. The
   accepted call must remain more legible than a value-level validation loop.
   When implementing, demonstrate both as `nw-certainty-by-construction`
   step 5 requires.
5. State bypasses and residual obligations: deserialization, reflection,
   casts, database writers, foreign code, process failure, and other systems
   may remain outside the representation.
6. Keep evidence through the boundary. Return a validated value, capability,
   or explicit outcome rather than a Boolean that discards what the next step
   needs. A Boolean validator left beside the evidence path returns that
   evidence instead, or is removed.

## Calibrate the guarantee

State the claim at the strength of the matching row of
`nw-certainty-by-construction`'s calibration table, chosen by the checker the
repository actually runs.

## State and evidence boundaries

Use a state/phase-indexed API only when the states are small, stable, and
central to the product contract, and when a rejected call matters before
execution. Otherwise use a closed state value plus an explicit transition or
validation result. A representation is successful when clients can see what
they possess, which operation they may call, and what failure means without
knowing its internal machinery.

For representation-preserving conversion, distinguish representational
equality from semantic equality. For normalization or transformation, state
the observation and preservation claim before optimizing. For an existential
or hidden implementation, preserve only the operations the client genuinely
needs through a named eliminator or interface.

## Advanced Haskell/GHC

Read [advanced Haskell design](references/advanced/haskell-type-level-design.md)
only when the target and its compiler range make GADTs, `DataKinds`, rank-N
types, families, roles, open rows, or singletons a concrete option. Then read
[technique selection](references/advanced/technique-selection.md) and
[ergonomics and compatibility](references/advanced/ergonomics-and-compatibility.md)
before exposing the API. These techniques are optional tools for GHC projects,
not a requirement for other languages.
