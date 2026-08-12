---
name: nw-certainty-by-construction
description: Turn a stable domain claim into a construction boundary so the invalid state cannot be built, and state honestly what remains unguarded. Use when a requirement says an invalid state or transition must not occur, when values need a canonical form, or when a rewrite/cache/optimisation must preserve meaning. Complements nw-fp-domain-modeling, which shows the encodings; this decides whether to encode, how strong the claim really is, and what obligation is left over.
---

# Certainty by Construction

`nw-fp-domain-modeling` shows the encodings — wrappers, smart constructors,
choice types. This decides **whether a claim belongs in construction at all**,
how strong the resulting guarantee honestly is, and what obligation remains
outside it.

Knowledge basis: certainty by construction — encoding invariants so the
invalid state cannot be built.

## Work from the claim outward

1. **State the proposition precisely.** "A `ConfirmedBooking` has an approved
   payment." Name its owner and its semantic equality.
2. **Draw the trust boundary.** Which inputs and writers are untrusted, where
   effects and persistence enter, and **who can bypass the constructor**.
3. **Choose the strongest proportionate encoding.** A guarantee is only real if
   its constructors and eliminators make the prohibited state hard to express.
4. **State the residual obligation.** Do not quietly convert an external,
   temporal or cross-system rule into a local type claim.

Before refining, ask: is the invariant stable, local and high-value; can all
legitimate construction pass through this boundary; will the representation
survive the API, serialization and interop edges? If not, keep it **extrinsic** —
and carry it deliberately rather than pretending it is intrinsic.

## Make propositions carry evidence

Treat `P(x)` as a type of evidence for `P(x)`.

- Prefer a validated constructor, opaque value object, non-empty wrapper or
  state-specific type over a primitive plus a convention.
- Make construction the only ordinary route in. A public raw constructor that
  recreates the invalid state cancels the guarantee.
- **Return the evidence, not a Boolean.** A decision's success branch carries a
  witness; its failure branch carries a reason. `true`/`false` throws away what
  the caller needs next.
- Keep operations total over their stated input types; where the language cannot
  make an alternative unrepresentable, put it in the **result type** instead.

## Prefer canonical meaning

Decide first whether semantically equal values should have ONE representation. If
yes, design the canonical form into the constructors and the later normalization
and equality burden disappears.

If several representations are intentionally valid, specify all four: the
denotation map, the equivalence relation, the normalization, and the
**preservation claim** — that normalization has the same denotation as its input.
Never hide a lossy conversion behind the word "normalization".

## Preserve meaning before optimising

| Change | The argument you owe |
|---|---|
| Same information, different representation | Isomorphism: both round trips preserve the intended equality |
| Mapping computations across an operation | Homomorphism: identity and composition preserved |
| Rewrite, cache, memoize, compile | A relation to the specification, plus that every operation preserves it |

An equivalence argument establishes meaning. It says nothing about speed, memory
or availability — those are separate claims and must be measured separately.

## Calibrate the claim to the language — say what you actually have

| Environment | Honest claim |
|---|---|
| Proof assistant | The property follows from checked definitions and admitted axioms |
| Strong static language | Invalid states blocked on typed paths; casts, reflection, deserialization and foreign writers remain boundaries |
| Mainstream OO/FP | Construction is centralised and misuse reduced; the compiler does **not** prove the predicate |
| Dynamic / boundary-heavy | Checked at controlled runtime boundaries, and every writer must preserve it |

Do not call all type safety "proof", and do not simulate proof strength with
nominal wrappers. Name the bypass routes and keep their checks visible.

## What construction never establishes

Stakeholder intent, authorization, time-dependent policy, cross-aggregate
consistency under concurrency, external API behaviour, persistence integrity
after a bypass, cryptographic soundness, availability. Validate those at their
owning boundary and say so.

A false proposition is not a missing implementation detail. Revisit the
statement or the representation.

## Cross-cutting invariants

Load `nw-cross-cutting-invariants` alongside this — especially
`gate:self-explaining-what-why-how`: a constructor that refuses must say WHAT was
invalid, WHY it cannot be built, and HOW to build a valid one.
