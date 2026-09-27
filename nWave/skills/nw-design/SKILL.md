---
name: nw-design
description: "Establishes durable architecture, reuse, boundaries, cross-layer algebra, residual stress behavior, paradigm, and prefactoring decisions for deterministic minimal handover construction."
user-invocable: true
argument-hint: '[bounded design question] --paradigm=[auto|oop|fp] [--residuality]'
---

> **Code facts** — resolve structural facts through `des code-fact`; degrade
> LOUD when its provider-neutral adapters cannot answer.

# NW-DESIGN

Read `~/.claude/skills/nw-human-collaboration/SKILL.md` to offer and conduct
interactive refinement with the human. Honor an already selected final-review
or full-delegation mode; the LLM manages the dialogue and progression.


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

**Requested scope, designed scope and unresolved shared decisions are distinct.**
For a feature with several values, first establish or confirm existing common contracts,
dependencies and observation of the whole requested result, then design
per-slice deltas; a slice is not ready until the shared decisions it depends on
are resolved. Inherit epic/project decisions when present; never invent them. A
one-value or local change reuses adequate existing architecture: no full upfront
local implementation design, repeated boilerplate or universal gate. Resolve a
shared contract the slice needs first; an independent slice proceeds when
inherited architecture suffices, and that does not make the feature design
complete. Honor an explicit human instruction to design shared decisions first.
A single-value Request needs no shared section. A value oracle covers the slice
delta and still carries inherited common constraints and feature
walking-skeleton obligations; it does not attest feature completeness. This paragraph is the sole owner
of this rule; other roles and skills reference it.

When an uncertain boundary needs exercise, orient the existing delegation toward
one concrete producer-to-consumer connection: semantic input through the DES
constructor to an executable oracle on the real public port. Let that consumer's
specific missing semantic question and counterexample return to its decision
owner before expanding the affected design or solution. This tests one
uncertainty in an existing value-level connection; it neither shrinks the
requested architecture scope nor attests that feature DESIGN is complete, and it
creates no technical-fragment cycle or additional delivery phase.

Read `~/.claude/skills/nw-role-invocation/SKILL.md` before delegating. Use the
exact installed role, natively or via `des design --repo-root ROOT --value N`
(buys the solution architect); `--input -` constructs and buys no turn.
The outer `/nw-design` caller invokes the relevant installed specialist per
that skill; the Required Design Pass, self-falsification and Handoff below are
that architect's duties, and its returned facts feed `--input -`.

Route application/component to `nw-solution-architect`, domain boundaries to
`nw-ddd-architect`, scale/distribution to `nw-system-designer`, deployment to
`nw-platform-architect`. Invoke only risk-required lenses. Algebra, certainty
and formal verification are owner-scoped lenses, never replacement routes.
Code-level structure stays downstream unless a public contract needs a boundary.

**Consultation policy (short).** The application/component architect owns
coherent design decisions by default — no fanout for routine work. Involve the
system designer only for a genuinely consequential distribution, capacity,
scaling, or availability trade-off. Involve the DDD architect only when
language, bounded context, aggregate, or invariant boundaries are actually
contested. Pattern/style selection (e.g. hexagonal, CQRS, event-driven)
applies only when system structure is actually in scope for the change at
hand — not by default on every design pass. The LLM chooses which consult(s)
to make and integrates their input into one coherent decision; DES never
dispatches or governs which specialist is consulted — that choice stays
semantic and upstream of the constructor boundary below.

## Required Design Pass

Performed by the invoked architect, not the outer host.

1. **Intent and constraints** — bind product identities/observations; name
   uncertainty, never invent a requirement.
2. **Code facts and reuse** — map responsibilities/callers/ports/dependencies;
   choose evidence-backed `REUSE`, `EXTEND`, `REPLACE` or `CREATE_NEW` for each.
   Check specifically for a SEMANTIC duplicate authority or a parallel
   implementation independently deciding the same business rule/fact under a
   different name or shape — not only a textual/symbol match (see
   `nw-code-craftsmanship`). Gate: `CREATE_NEW` explains why no candidate
   safely owns it.
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
10. **Agreement analysis** — reuse asks "does something already own this?";
    agreement analysis asks the question reuse cannot: "who else must agree
    with the contract I am changing?" For every shared contract the change
    touches (a schema, a wire format, a config shape read by more than one
    producer/consumer), name every producer and every consumer with a locator
    and a closed decision (`MIGRATED`, `UNCHANGED_COMPATIBLE`, or
    `INCOMPATIBLE`) and a reason. Gate: a change touching no shared contract
    must say so explicitly; it is never inferred from silence.

## Result and constructor boundary

DESIGN supplies semantic decisions; it does not edit a durable brief or ADR and
never authors Markdown for a DESIGN document. The LLM supplies typed semantic
inputs as a closed, complete JSON manifest (schema_version 1). The same field
grammar applies to `--shared`: fill targets, obligations, primary observable
oracle and verification from the common feature-level contract, without a slice ID. DES is the sole writer: for a feature with missing or
human-requested common decisions, invoke
`des design --repo-root ROOT --shared [--feature ID] --input -` once, with
explicit or inherited scope, for the common section; then send each slice delta
to `des design --repo-root ROOT --value N --input -`. Pass exactly one of
`--value` or `--shared`; there is no automatic project fallback.
`--replace-current` is only a deliberate same-identity replacement. DES
validates the input, constructs the human authority, and binds downstream typed
facts from the same normalized input.

The generated contract below is the sole field grammar for the manifest. Do
not supply completed Markdown or an ADR draft. Resolve the semantic decisions
from code facts, preserve the reuse, prefactoring, native-evidence, and
uncertainty duties above, and use at most one bounded Bash probe for a
load-bearing unknown.

A provider-enforced output schema remains authoritative. When a caller requires
existing typed `design_facts`, obey that schema exactly and do not substitute a
manifest for it. When no schema is enforced and the normal DESIGN host asks
for constructor input, return the semantic manifest only. In either case,
do not write authority, handover, production, or oracle bytes. `NEXT` is
advisory; the producer does not select or invoke another delivery step.

Plain `--input -` intentionally refuses different already-bound facts before a
write. For a rework of the same configured destination and section heading, use
the explicit `--replace-current --input -` constructor; do not imply replacement
without that flag.

<!-- GENERATED:design-document-input START — source of truth: des.domain.design_document.DesignDocument.input_description(); do not hand-edit (docgen renders this region) -->
DESIGN constructor input is one strict UTF-8 JSON manifest:
object with exactly:
- `schema_version`: integer `1`.
- `authority`: object with exactly:
  - `heading`: plain non-empty text, not a Markdown heading.
- `purpose`: non-empty text.
- `constraints`: non-empty unique list of non-empty text.
- `targets`: non-empty unique list with distinct paths of object with exactly:
    - `path`: repository-relative file path.
    - `decision`: `EXTEND` or `CREATE_NEW`
    - `reason`: non-empty text.
- `paradigm`: `object_oriented` or `functional`
- `decisions`: non-empty unique list of non-empty text.
- `reuse_analysis`: object with exactly:
  - `candidates`: unique list of object with exactly:
      - `symbol`: non-empty text.
      - `locator`: repository-relative path and positive line.
      - `decision`: `REUSE` or `EXTEND` or `REPLACE` or `CREATE_NEW`
      - `reason`: non-empty text.
- `prefactoring`: tagged object on `applicability`:
  - `applicable`:
    object with exactly:
    - `applicability`: `applicable`
    - `existing_oracle`: a repository-relative DESIGN oracle locator: the whole file (`tests/verify_order.py`) or the file with an optional `::selector` (`tests/verify_order.py::Class::case`); a `:line` suffix is not accepted.
    - `move`: non-empty text.
    - `preserved_observation`: non-empty text.
  - `not_applicable`:
    object with exactly:
    - `applicability`: `not_applicable`
    - `reason`: non-empty text.
- `agreement_analysis`: tagged object on `applicability`:
  - `applicable`:
    object with exactly:
    - `applicability`: `applicable`
    - `parties`: non-empty unique list of object with exactly:
        - `contract`: non-empty text.
        - `role`: `producer` or `consumer`
        - `locator`: repository-relative path and positive line.
        - `decision`: `MIGRATED` or `UNCHANGED_COMPATIBLE` or `INCOMPATIBLE`
        - `reason`: non-empty text.
  - `not_applicable`:
    object with exactly:
    - `applicability`: `not_applicable`
    - `reason`: non-empty text.
- `boundaries`: tagged object on `applicability`:
  - `applicable`:
    object with exactly:
    - `applicability`: `applicable`
    - `driving_port`: non-empty text.
    - `driven_ports`: non-empty unique list of non-empty text.
    - `dependency_direction`: non-empty text.
    - `failures`: non-empty unique list of object with exactly:
        - `condition`: non-empty text.
        - `outcome`: `Refusal` or `Retry` or `Indeterminate`
        - `observation`: non-empty text.
  - `not_applicable`:
    object with exactly:
    - `applicability`: `not_applicable`
    - `reason`: non-empty text.
- `public_oracle`: object with exactly:
  - `observation`: non-empty text.
  - `stimulus`: non-empty text.
  - `expected`: non-empty text.
  - `falsifier`: non-empty text.
- `oracle`: a repository-relative DESIGN oracle locator: the whole file (`tests/verify_order.py`) or the file with an optional `::selector` (`tests/verify_order.py::Class::case`); a `:line` suffix is not accepted.
- `acceptance_supports`: unique list of repository-relative file path.
- `verification`: non-empty unique list of non-empty argv list of non-empty text without NUL.
- `oracle_verification_index`: non-negative integer.
<!-- GENERATED:design-document-input END -->

The Request's ordered value graph is decomposed once. Every independently
observable, shippable value slice retains its value-level oracle,
acceptance-test review, whole-slice implementation review, conditional
source-blind EXAMINE, and integration/finalization. Internal technical shards
receive no separate contract, review, EXAMINE, or finalization.

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
the host, not assumed Linux/tooling. For a new selected temporal or modelable
non-functional claim, use Quint as the standard readable notation with
Apalache/TLC as the selected verifier. Preserve useful existing TLA+ models;
choose direct TLA+ for a new model only with a recorded capability or tooling
reason. Agda complements these for applicable local
proofs. Use `nw-solution-architect-formal-verification` for tool selection,
installation offers and explicit model-versus-runtime evidence. When an applicable claim's
tool is available, execute it; otherwise use explicit algebraic fallback and
mark only that proof `INDETERMINATE`. Offer installation only on a known,
bounded, user-consented path. Tool absence never blocks DESIGN or becomes proof.

Use applicable `nw-review` questions as DESIGN self-checks only (S1-S4
structure; selected T5-T7 time; three values); do not dispatch an independent
DESIGN review. They find "structural incoherence", never temporal holes; a
temporal gap needs the model checker.

## Handoff

After self-falsification, return semantic input or the caller-enforced typed
facts; never edit a brief, ADR, handover, or DESIGN document. An acceptance
finding that needs upstream rework remains with the owner of the bound
architecture decision. The caller may route that rework with
`--replace-current --input -` when it deliberately replaces the same configured
destination and section heading; plain `--input -` continues to refuse a
conflicting already-bound fact set.

The semantic input records the decision evidence, public validation, and
executable support. DES alone projects those facts into the authority and
handover. Use an opaque diagnostic only to summarize a refusal or remaining
uncertainty for a human; it is never a machine-readable terminal grammar.
