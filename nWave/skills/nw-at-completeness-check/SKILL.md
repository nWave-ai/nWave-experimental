---
name: nw-at-completeness-check
description: Verify that one minimal oracle falsifies every declared delivery obligation without checklist ceremony or duplicate tests.
user-invocable: false
disable-model-invocation: true
---

# Acceptance completeness: obligation-to-observation closure

**Kind**: KNOWLEDGE. Apply to acceptance completeness during DISTILL; the
caller orchestrates, ATD authors the oracle, and its existing reviewer judges.
When the crafter reviewer applies it at AT-density review, its closure checks are
criteria only: that role's typed outcome governs, a declared behavior absent from
the oracle is a rejection owned by `oracle`, and INDETERMINATE stays reserved for
absent evidence.

Review one candidate oracle against runner-derived facts from durable authority.
Completeness is a total
relation, not a score:

```text
every declared obligation -> one or more falsifiable observations
every oracle observation  -> exactly one declared obligation or boundary law
```

PASS only when both directions hold. Never invent coverage from a fixed
checklist, scenario count, percentage, test pyramid or framework convention.

## Before-code alignment

First compare the original agreed value and its authorized exclusions/amendments
with the selected criteria, retaining provenance. A human-authorized exclusion
is not a missing requirement; a producer-only scope reduction is a defect.
Preserve every promised outcome, including already satisfied behavior that
requires no new production. Record a concrete selection/authority finding
before ATD or oracle agreement; this is adequacy, not a new requirement.

When the original value, selected-contract identity, and prior adequate
alignment are unchanged with no new finding, reuse that alignment. Do not repeat
the preimplementation assessment or existing ATD review. Human scope authority
is unchanged.

Only for new, changed, or unresolved semantic input, supply the same selected
revision, original value to preserve, and inherited criteria to ATD and the
independent source-blind examiner. Include their outputs in the existing
acceptance-designer review. Preserve behavioral specificity; summarizing criteria
away or weakening them to make the oracle pass is not alignment.


| Participant | Evidence and responsibility |
|---|---|
| ATD | Derive executable tests/properties from the original value preserved by the selected contract and its declared public observations. |
| Examiner, preimplementation | Receive only Request, original value, and selected behavioral contract bytes; assess required public stimuli, observations, falsifiers and ambiguity independently of test/source choices. Working implementation and runtime proof are not inputs to this assessment. |
| Existing ATD reviewer | First check value-to-criteria adequacy, then compare selected obligations, executable tests/properties and examiner expectations for coverage, feasibility and consistency. This is the existing oracle review, not an additional review role or approval ceremony. |

The host supplies this preimplementation reviewer packet explicitly: original
Request and authorized scope amendments, selected behavioral contract and
revision, architectural facts/native substrate needed by ATD, proposed oracle/
supports and examiner expectations. Candidate `prepare-role` reviewer packets
require a verified implementation and are not this packet. The examiner receives
only the permitted behavioral subset, never code, tests, native selectors or
producer classifications.

Check timing and public constructibility: required ATD helpers/fixtures must be
available before craft, while future production may be absent. A constructible
future capability is not impossible solely because it is unimplemented. Batch
known consumer questions/counterexamples for the same upstream owner; do not
create an architect-plus-ATD review phase for every layer.

Resolve each mismatch in that review:

- **Grounded expectation missing from tests**: ATD strengthens the executable
  oracle for the selected criterion before craft.
- **Overrestrictive expectation**: refine it to the selected criterion; retain
  every required behavior and permit equivalent valid observations.
- **Ambiguous contract or new requirement**: return the concrete question to
  the owning upstream authority explicitly; neither side silently expands scope.

The caller supplies the crafter one coherent selected revision after these
dispositions. DES constructs durable acceptance documents from selected semantic
facts; alignment introduces no parallel document, ledger or handoff. Missing
observation evidence calls for evidence collection, not a production edit merely
to create a new candidate. A genuine oracle or authority defect returns to its
owner before craft proceeds against a revised contract.

Final EXAMINE remains a separate independent, source-blind assessment using the
original value, the same selected contract, and actual public observations.
Earlier alignment neither pre-approves implementation nor limits counterexample
discovery. An observed loss of original value rejects even when tests and
selected criteria agree. Missing observation is `INDETERMINATE` for the evidence
capture owner, not a product defect. Distinguish that state from a suspected
oracle defect, an observed contract violation, and a new expectation; the
examiner reports the semantic gap, while the existing oracle owner/reviewer
establishes a test defect from test evidence.

## Required closure

For every applicable obligation, verify that the oracle observes:

- the promised outcome and every materially distinguishable result;
- declared state, composition and preservation laws, using PBT for broad
  domains and examples only for genuinely finite or singular observations;
- declared failure and recovery modes across domain, application/port,
  adapter/integration and infrastructure boundaries;
- the real boundary type or protocol when a lookalike could pass falsely;
- one assembled installed journey when the user consumes that surface;
- the exact semantic checkpoint, so a dependency, fixture, import or setup
  failure cannot masquerade as intentional RED.

An iterative or empty case is required only when the declared law induces it.
An additional test is required only when it adds a distinct observation.
Collapse equivalent examples, parameterize finite variants and keep one
property per independent universal law.

## Environment closure

The oracle's runner and dependencies must be reproducible from the repository's
actual manifest/build/test stanzas and runtime, not an ambient interpreter.
Follow native discovery in `nw-test-design-mandates`, including Dune/opam where
present. No closed manifest list, Python bridge or nWave adapter is required.
Missing runtime/dependency or build/setup evidence is BROKEN, not semantic RED.

## Boundary and reuse closure

Drive the nearest honest port that preserves the promised observation. A
cheaper seam is valid only with an explicit preservation map to the real
surface. Reuse existing helpers and oracles when they already own the same
law; do not duplicate them. New seams require an observation through the real
entry point, and the oracle must not create an architectural dependency that
the permanent design forbids.

For every broad-input/state/failure law projected below the real port, require
an explicit preservation map to the same promised observation. Without it,
return `EVIDENCE_GAP`; never downgrade the law to example-only coverage.

## Verdict

- `APPROVE`: both relation directions close, the intended route state is
  observed, and no duplicate or undeclared test remains.
- `NEEDS_REVISION`: a declared obligation lacks an observation, an observation
  lacks authority, or RED is ambiguous with BROKEN.
- `INDETERMINATE`: required source, runner or execution evidence is absent.

Route specification ambiguity to its owning upstream authority. Correct a
delivery-scope oracle gap inside DISTILL. Reviewer findings are ephemeral;
never create a checklist, gap ledger, receipt or parallel progress artifact.
