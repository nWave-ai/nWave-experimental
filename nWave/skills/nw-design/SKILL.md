---
name: nw-design
description: "Establishes durable architecture, reuse, boundaries, cross-layer algebra, residual stress behavior, paradigm, and prefactoring decisions for later DeliveryContract compilation."
user-invocable: true
argument-hint: '[bounded design question] --paradigm=[auto|oop|fp] [--residuality]'
---

> **Code facts** — resolve structural facts through `des code-fact`; degrade
> LOUD when its provider-neutral adapters cannot answer.

# NW-DESIGN

## Authority

DESIGN updates the durable architecture brief and permanent ADRs. It never
writes a per-delivery narrative, plan or duplicate contract. DISTILL later
projects the executable subset into one immutable `DeliveryContract`.

Route application/component questions to `nw-solution-architect`, domain
boundaries to `nw-ddd-architect`, scale/distribution to `nw-system-designer`
and deployment architecture to `nw-platform-architect`. Invoke only the lenses
the risk requires.

## Required Design Pass

1. **Intent and constraints** — bind stable product identities and observations;
   name uncertainty rather than inventing a requirement.
2. **Code facts and reuse** — map existing responsibilities, callers, ports and
   dependencies. For every proposed responsibility choose `REUSE`, `EXTEND`,
   `REPLACE` or `CREATE_NEW` with evidence. `CREATE_NEW` must explain why an
   existing candidate cannot safely own it.
3. **Prefactoring** — when the desired behavior is blocked by structure, define
   a smallest observationally preserving `GREEN_TO_GREEN` move before new
   behavior. Name its existing green oracle. Do not hide behavior change in it.
4. **Ports and boundaries** — define driving/driven ports, dependency direction,
   authority ownership and failure translation. A downstream diff that changes
   these without an amended durable decision is architectural drift.
5. **Paradigm** — select `functional` or `object_oriented` from the repository's
   actual conventions and the problem, not taste. Both consume the same
   behavioral laws and boundary obligations.
6. **Cross-layer algebra** — for every affected layer name states, operations,
   observations and laws:
   - domain: legal states and transitions;
   - application/ports: explicit success, refusal and retry outcomes;
   - adapter/integration: protocol, decoding, concurrency and dependency
     failures that callers must handle;
   - infrastructure/recovery: timeout, partial failure, replay, recovery and
     resource-loss observations.
   Use the target language's native types and patterns; do not impose FP syntax
   on every implementation.
7. **Residuality** — enumerate relevant stressors and the architectural residues
   that remain viable. State which observations/laws are preserved when moving
   between residues and which intentionally change. A newly discovered residue
   amends the durable architecture; it is not disguised as refactoring.
8. **Test substrate** — name the real driving port, canonical helper/import,
   fixture construction, executor/lifecycle boundary, dependency owner,
   declaration-vs-runtime state and literal verification argv. This prevents
   DISTILL from inventing an ambient interpreter or fake boundary.
9. **Human projection** — explain the selected laws, failure handling and
   trade-offs in ordinary domain language alongside the rigorous design. The
   projection is a view of the same decision, not a second authority.

## Counterexample discipline

A refuted invariant, a failing property, a model-check violation, or a
scenario the design cannot classify is first a ROOT-CAUSE question about the
representation, never a patch site:

1. Ask which type made the violating state representable. Route the
   diagnosis through `nw-algebraic-design-protocol` (follow the contradiction
   to the type or observation that causes it) and the cure through
   `nw-certainty-by-construction` (encode the missing distinction so the
   state is unrepresentable). Never add a law, guard, or ceremony on top of
   the unchanged representation as the first move.
2. A theorem that only holds conditionally is the same signal: its hypothesis
   names the constraint the representation should enforce by construction.
3. An added law over an unchanged representation is a symptom patch. It may
   ship only with an explicit recorded justification of why the representation
   cannot change, in the amended durable authority.

## Independent statement review

Proof artifacts (mechanized proofs, model-check runs, exhaustive surrogates)
derived from one reading of the design verify the PROOFS, not the STATEMENTS.
Two verification lanes translating the same reading agree on the same
misreading — that is a coherence check, never corroboration. Before a
formally-verified design decision is ratified, dispatch one adversarial
statement-level review to a reader who receives ONLY the mandate and the
binding constraints — never the algebra, the proofs, or their conclusions —
and tries to break the statements. Findings amend the durable authority
before the proofs are re-run against the amended statements.

This discipline requires no proof assistant or model checker: property tests
in the project's own language, exhaustive finite checks, or a model checker
when one is available all qualify — a prover is never a prerequisite.

## Handoff

Update the brief/ADRs once. Return stable decision ids plus the minimum facts
DISTILL needs to compile route, paradigm, targets, boundaries, obligations,
oracle choice, applicability and command vectors. Do not author the
`DeliveryContract` here and do not copy full rationale into it.

```text
DESIGN-RESULT
verdict: PASS | NEEDS_INPUT | CONFLICT
authorities: <changed brief/ADR paths>
decisions: <stable ids>
route: RED_TO_GREEN | GREEN_TO_GREEN
oracle: <existing locator for GREEN_TO_GREEN, otherwise ATD_REQUIRED>
boundaries: <named ports and dependency directions>
obligations: <cross-layer laws and residual stress properties>
```
