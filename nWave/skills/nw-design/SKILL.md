---
name: nw-design
description: "Establishes durable architecture, reuse, boundaries, cross-layer algebra, residual stress behavior, paradigm, and prefactoring decisions for deterministic minimal handover construction."
user-invocable: true
argument-hint: '[bounded design question] --paradigm=[auto|oop|fp] [--residuality]'
---

> **Code facts** — resolve structural facts through `des code-fact`; degrade
> LOUD when its provider-neutral adapters cannot answer.

# NW-DESIGN

## Authority

DESIGN updates durable architecture brief/ADRs, never a per-delivery narrative,
plan or duplicate contract. Product value is decomposed once into an ordered
graph; no downstream competence reslices it. DISTILL asks the existing
CLI/software producer to derive one minimum executable whole-Request handover
from Git and the existing durable product/design/oracle authorities. Every
independently observable and shippable value slice represented in that graph
gets one oracle, independent acceptance-test review, whole-slice implementation
review, source-blind EXAMINE when applicable, and mechanical
integration/finalization. Internal technical shards, packages, layers and steps
get no mini-cycle. Request-wide
review or EXAMINE requires a named cross-slice observation not covered by slice
evidence.

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
   executor/lifecycle, dependency owner, resolved version and manifest/lock,
   declared/runtime state and literal argv.  If a required dependency is absent,
   include its architecture-grounded target delta; hand off only when it is both
   declared and present in the verification runtime.
   Keep one oracle and at most two examples per obligation; select a property
   test only for a broad or generated input domain, otherwise `NOT_APPLICABLE`.
   Gate: DISTILL cannot invent ambient interpreter or boundary.
9. **Human projection** — state observations/equality, examples/counterexamples,
   alternatives/provenance, laws, consequences/trade-offs, failure handling and
   guarantee ceiling/exclusions in ordinary language. Ask only where an answer
   changes equality, carrier, law or irreducible trade-off; otherwise proceed.
   It projects the same model, never a second authority or changed metaphor.
   **Explain before you formalize (owner rule, Ale 2026-09-06):** every section
   a human will read opens with one or two sentences in ordinary language that
   say what it means and why it matters, BEFORE any table, law or symbol; a
   technical term that cannot be avoided is glossed in half a line at its first
   use; a word replaces a symbol wherever a word suffices. This is a rule of the
   projection, not a style of one document: the HTML rendering
   (`nw-doc-as-artifact`) adds no content, so readability must already be in the
   markdown, or the people who decide cannot take part. Gate: a section that
   opens with a table, a formula or an undefined term fails the projection.

## Result and handover boundary

DESIGN owns semantic decisions by editing or reusing the existing durable brief
or ADR that owns them. It never authors a handover or per-delivery document. In
a managed invocation, provider-enforced structured output contains only
`accepted | rejected | indeterminate` and one opaque `diagnostic` string. It
contains no design, locator, target, authority, argv, rationale or other
semantic payload. The control plane branches only on the enum, forwards
`diagnostic` intact, parses no terminal prose, and ignores the duplicate
envelope `result`.

Before invocation, software snapshots the already allowed authority scope. An
accepted DESIGN turn may change only the existing durable authority document it
owns; a correction may change only the document named by the already bound
authority locator and must produce distinct bytes. A non-accepting turn changes
nothing. Software observes that exact owned delta, then rereads paradigm,
targets, obligations, oracle and
native verification commands through the existing durable-authority resolvers.
Zero delta is accepted only when the authority locator was already resolved
before invocation and the existing authority is complete. Missing or ambiguous
ownership is `indeterminate`; conflicting authority is `rejected`.

DISTILL asks the existing CLI/software producer to derive route, Git base,
authority locator and handover bytes from Git and the durable product/design/
oracle authorities.
The Request's ordered value graph is decomposed once; the
producer emits one minimal whole-Request handover with one fan-in. Every
independently observable, shippable value slice receives its value-level oracle,
acceptance-test review, whole-slice implementation review, source-blind EXAMINE
when applicable, and integration/finalization. Internal technical shards receive
no separate contract, review, EXAMINE or finalization.

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

## Independent statement review — retired

Proof/model/exhaustive artifacts verify the PROOFS, not the STATEMENTS; two
lanes may agree on the same misreading — that is a coherence check, never
corroboration. This limitation remains a DESIGN self-falsification duty, not an
independent delivery review. Before returning `accepted`, DESIGN attacks its own
observations, constructive public-oracle chain, reuse/prefactoring choices,
boundary/failure algebra, residual guarantees and test substrate with concrete
counterexamples. The delivery flow's independent quality points are the
acceptance-oracle review, one whole-diff implementation review, and conditional
source-blind EXAMINE.

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

Use applicable `nw-review` questions as DESIGN self-checks only (S1-S4
structure; selected T5-T7 time; three values); do not dispatch an independent
DESIGN review. They find "structural incoherence", never temporal holes; a
temporal gap needs the model checker.

## Handoff

After self-falsification and any runner-mediated initial ATD-to-DESIGN
correction, update or reuse the one existing durable brief or ADR that owns the
decision, then return the outcome ONCE. A correction changes only the already
bound authority document and the runner re-derives its facts before ATD resumes.
The authority records paradigm, targets, obligations, oracle locator and
supports, native command vectors and
the public contract; the result carries none of them. Software owns the
handover and deterministically projects only the facts downstream consumers
need. Never write the handover, create a design document or copy rationale into
the diagnostic.
Apply `construction:design-paradigm-projection` from the shared cross-cutting
core; root never retypes or defaults that decision.
Use the opaque diagnostic only to summarize a refusal or remaining uncertainty
for the human, without a machine-readable terminal grammar.
