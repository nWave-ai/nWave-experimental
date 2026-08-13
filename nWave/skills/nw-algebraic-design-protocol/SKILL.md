---
name: nw-algebraic-design-protocol
description: The METHOD for finding a design — name observations and equality before constructors, then follow any contradiction to the type or observation that causes it. Use when a design decision is contested, a law has exceptions, a census or model keeps producing wrong answers, or a representation change must preserve meaning. Complements nw-fp-algebra-driven-design, which catalogues the structures; this says how to arrive at one and what to do when it breaks.
---

# Algebraic Design Protocol

`nw-fp-algebra-driven-design` tells you which structures exist — semigroup,
monoid, functor. This tells you **how to find the design**, and what to do when a
law you believed turns out to be false. Load both when designing a compositional
core; load this one alone when something already designed keeps giving wrong
answers.

Knowledge basis: algebra-driven design — deriving an API from its laws.

**Cross-layer authority (ADR-SSOT-002 §6a).** This is the one language-agnostic
operational procedure for every layer a target's declared boundary touches —
domain, application/ports, adapter/integration, infrastructure/recovery.
Layer applicability derives from `targets` and `targets[].boundary`/
`contract-shape`; nothing here adds a persisted layer field. OO/FP structure
catalogues (`nw-code-design-oo`/`-fp`, `nw-fp-algebra-driven-design`) are thin
projections of this method, never a competing one.

## 1. Observations and equality, before anything else

State what a user can meaningfully **observe**. Then define `x ≈ y` as agreement
under that observation set — never structural equality chosen because it was easy
to implement.

Inventory each observation, its result type, and **what it cannot distinguish**.
That last column is the one that pays: a Boolean result is usually too weak the
moment composition needs the remaining input or state.

If several observations repeat the same traversal, look for one more primitive
transition the others project from.

## 2. Constructors one at a time, each with an equation

After adding a constructor, write at least one equation relating it to an
observation or an existing constructor. The web of equations IS the design.

A law with ignored arguments, many exceptions, or domain-specific flags signals a
**fused concept**. Split it before choosing a representation.

## 3. Follow a contradiction to the carrier — do not special-case it

This is the step that catches real defects, and the reason to load this skill
when something is already broken.

When a law fails, the cause is usually not the law. It is that the **carrier** —
the type you are observing through — cannot express the property. Order-insensitive
composition observed through an order-sensitive list is the textbook case.

Two honest resolutions: **replace the carrier**, or **retract the law**. Never
conceal the conflict with a special case, because a special case makes the model
agree with the data while still being wrong about the domain.

> **Worked anchor (nWave, 2026-08-06).** A census asked "is this MODULE live?"
> when liveness was a property of the VERB the module dispatched. The three verbs
> disagreed, so the answer came back for whichever one dominated the text.
> Measuring per-module was the wrong carrier, and no amount of scanning more
> surfaces would have fixed it — the fix was to change what the unit was. The
> unit comes from the SEMANTICS, not from the file system.

## 4. Keep the representation out of the public algebra

Persistence, tree shape, cache and optimisation are not part of the design.
Build a deliberately obvious reference encoding first; enforce canonical
reductions through smart constructors.

Generate values through the **public surface**, and state reachability and size
bounds explicitly. Generated counterexamples are candidate findings until a human
reviews them: an impossible minimal case is evidence to audit the generator
before blaming the implementation.

## 5. Optimise by denotation, and prove the claim observationally

Seek a homomorphic denotation the other observations derive from. State the old
and new observation sets and the equivalence claim **before** changing the
representation, and protect it with generated terms on both sides.

Passing generated checks is evidence, not proof. Say which.

## Stop conditions

The design is ready when every public constructor participates in a law or an
observation, equality has a stated scope, and tempting-but-false laws are
**recorded rather than deleted** — a future reader who rediscovers one needs to
know it was already refuted.

Escalate rather than paper over an unresolved observation, an incompatible
carrier, or a nondeterministic boundary whose effect model has not been stated.

## Cross-cutting invariants

Load `nw-cross-cutting-invariants` alongside this. In particular
`gate:design-principles-gdp-1-9` and `data:consumer-known-before-produced`: an
observation nobody consumes is not an observation, it is a field.
