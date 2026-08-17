---
name: nw-at-completeness-check
description: Verify that one minimal oracle falsifies every declared delivery obligation without checklist ceremony or duplicate tests.
user-invocable: false
disable-model-invocation: true
---

# Acceptance completeness: obligation-to-observation closure

Review one candidate oracle against the schema-valid `DeliveryContract` and
the permanent architecture authority it names. Completeness is a total
relation, not a score:

```text
every declared obligation -> one or more falsifiable observations
every oracle observation  -> exactly one declared obligation or boundary law
```

PASS only when both directions hold. Never invent coverage from a fixed
checklist, scenario count, percentage, test pyramid or framework convention.

## Required closure

For every applicable contract obligation, verify that the oracle observes:

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

The oracle's runner and dependencies must be reproducible from the repository
dependency manifest, never from an ambient interpreter. Check the applicable
cross-language manifests explicitly: `requirements`, `pyproject.toml`,
`package.json`, `Cargo.toml`, and `go.mod`. Missing runtime or test dependency
evidence is BROKEN, not RED.

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
