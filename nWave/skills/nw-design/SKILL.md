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

DESIGN updates durable architecture brief/ADRs, never a per-delivery narrative,
plan or duplicate contract; DISTILL projects its executable subset into one
immutable `DeliveryContract`.

Route application/component to `nw-solution-architect`, domain boundaries to
`nw-ddd-architect`, scale/distribution to `nw-system-designer`, deployment to
`nw-platform-architect`. Invoke only risk-required lenses. Algebra, certainty
and formal verification are owner-scoped lenses, never replacement routes.
Code-level structure stays downstream unless a public contract needs a boundary.

## Required Design Pass

1. **Intent and constraints** — bind product identities/observations; name
   uncertainty, never invent a requirement.
2. **Code facts and reuse** — map responsibilities/callers/ports/dependencies;
   choose evidence-backed `REUSE`, `EXTEND`, `REPLACE` or `CREATE_NEW` for each.
   Gate: `CREATE_NEW` explains why no candidate safely owns it.
3. **Prefactoring** — before behavior, define the smallest observationally
   preserving `GREEN_TO_GREEN` move and existing green oracle. Gate: no hidden
   behavior change.
4. **Ports and boundaries** — define driving/driven ports, dependency direction,
   ownership and failure translation. Gate: change requires durable amendment.
5. **Paradigm** — select `functional` or `object_oriented` from repository and
   problem, not taste; both consume the same laws/boundaries.
6. **Cross-layer algebra** — for every affected layer name states, operations,
   observations and laws:
   - domain: legal states and transitions;
   - application/ports: explicit success, refusal and retry outcomes;
   - adapter/integration: protocol, decoding, concurrency and dependency failures;
   - infrastructure/recovery: timeout, partial failure, replay, recovery and loss.
   Use native types/patterns; do not impose FP syntax.
7. **Residuality** — enumerate stressors and viable residues; state
   preserved/changed observations and laws. Record stable/local admitted,
   excluded and unknown states with risk owner; use `nw-stress-analysis` for
   triggered stressors. A removed-hypothesis counterexample is triage evidence,
   not automatically a missing type. A new residue amends architecture, never
   refactoring.
8. **Test substrate** — name real driving port, helper/import, fixture,
   executor/lifecycle, dependency owner, declared/runtime state and literal argv.
   Gate: DISTILL cannot invent ambient interpreter or boundary.
9. **Human projection** — state observations/equality, examples/counterexamples,
   alternatives/provenance, laws, consequences/trade-offs, failure handling and
   guarantee ceiling/exclusions in ordinary language. Ask only where an answer
   changes equality, carrier, law or irreducible trade-off; otherwise proceed.
   It projects the same model, never a second authority or changed metaphor.

## Constructive closure and refinement

For every public value, distinguish **safety** excludes an invalid state;
**inhabitation** proves an intended valid value can be constructed from admitted
input; **public reachability** proves its producer-to-consumer path reaches a
public driving/observation port; **liveness** proves eventual progress under
explicit temporal/fairness assumptions. Record each in the brief/ADR on axes: DESIGN
`PASS|BLOCKED`, runtime `OBSERVED|DESIGNED_NOT_BUILT|INDETERMINATE`. Liveness is
`NOT_APPLICABLE` only when irrelevant; bounded/synchronous execution justifies
that only for liveness, never safety/refinement/reachability. Omission is BLOCKED.

Record `input -> constructor/producer -> consumer -> public port`, with exact
owner/invocation/existing symbol or concrete repo-relative DNB site/symbol.
Generic “planned site” is not buildable DESIGN evidence. `PASS +
DESIGNED_NOT_BUILT` is acyclic/buildable/unobserved. Reject an unseeded cycle or
name its bootstrap.

A formal model closes only its claim: map atoms to runtime symbols, exclusions
and refinement. For `RED_TO_GREEN`, unimplemented runtime is allowed only with
mapping/refinement obligation and declared limits. A verified mapped model may
close DESIGN, never runtime; without mapping it is unrefined **model-only**.

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
2. A theorem that only holds conditionally is the same signal: triage its
   hypothesis as missing type/carrier distinction, law scope or external boundary.
3. An added law over an unchanged representation is a symptom patch. It may
   ship only with an explicit recorded justification of why the representation
   cannot change, in the amended durable authority.

## Independent statement review

Proof/model/exhaustive artifacts verify the PROOFS, not the STATEMENTS;
two lanes may agree on the same misreading — that is a coherence check, never
corroboration. Required DESIGN review is one two-phase conversation: before solution, reviewer gets ONLY
mandate/binding constraints, never authority/algebra/proofs/conclusions, and
returns precommitted counterexamples/questions; after authoring, it evaluates the
authority against that challenge and normal criteria. Challenge stays ephemeral,
never an artifact/schema/gate/lane. Findings amend authority before proof re-run.

For each unknown load-bearing system fact, run at most one bounded empirical
probe (three per authority), recording fact and result. Model only a separately
selected formal-proof obligation; a probe never prototypes a desired answer or
becomes a wave.

This discipline requires no proof assistant or model checker: property tests
in the project's own language, exhaustive finite checks, or a model checker
when one is available all qualify — a prover is never a prerequisite. Probe
the host, not assumed Linux/tooling. When an applicable Agda/TLA+/TLC claim's
tool is available, execute it; otherwise use explicit algebraic fallback and
mark only that proof `INDETERMINATE`. Offer installation only on a known,
bounded, user-consented path. Tool absence never blocks DESIGN or becomes proof.

Use applicable `nw-review` questions only (S1-S4 structure; selected T5-T7
time; three values); `nw-review` owns universal routing. They find "structural incoherence", never temporal holes; a temporal gap needs the model checker.

## Handoff

After phase-two review, update the brief/ADRs once. Return stable decision ids
plus the minimum facts DISTILL needs to compile route, paradigm, targets,
boundaries, obligations, oracle choice, applicability and command vectors. Do
not author the `DeliveryContract` here and do not copy full rationale into it.
Apply `construction:design-paradigm-projection` from the shared cross-cutting
core; root never retypes or defaults that decision.

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
