---
name: nw-discuss
description: "Clarifies jobs, journeys, outcomes, and human-visible value in the durable product SSOT without creating a delivery workspace or executable contract."
user-invocable: true
argument-hint: '[product question or outcome]'
---

# NW-DISCUSS

## Purpose

Turn validated product evidence into durable human authorities. DISCUSS owns
product meaning; it does not plan implementation and does not author a
`DeliveryContract`.

The durable product SSOT is the smallest existing set of long-lived product
authorities, for example:

- `docs/product/vision.md` for direction and principles;
- `docs/product/jobs.yaml` for validated jobs;
- product journeys for human interactions and shared artifacts; and
- `docs/product/kpi-contracts.yaml` for observable outcomes and measures.

Extend the existing authority that owns a fact. Do not copy the same decision
into a feature workspace, wave log, delta, status document or second schema.

## Workflow

1. Read the relevant durable product authorities and the evidence that changed.
2. Resolve the job, user or operator, trigger, desired outcome, negative
   outcome, journey and measurable success. Do not fabricate a human journey
   for an internal constraint; state the operator/system outcome directly.
3. Decide which existing authority owns each new fact. Update that authority
   once, preserving identifiers consumed downstream.
4. When alternatives remain material, route to DIVERGE. When product meaning
   is stable but architecture is not, route to DESIGN. Do not settle technical
   structure here.
5. Return a concise handoff naming changed authority paths, stable identifiers,
   unresolved product questions and the observations a later expectation
   charter may derive. Do not create the charter here.

## Boundary Laws

- Product facts flow forward by stable identity, not copied prose.
- A downstream contradiction propagates backward to the authority that owns
  the contradicted fact; downstream waves never silently override it.
- DESIGN may refine technical realization but cannot rewrite the user outcome.
- DISTILL later projects stable product and design facts into one immutable
  `DeliveryContract` for one delivery. That contract is executable and
  short-lived; it is not the durable product SSOT.
- Human cadence changes interaction, not the authority graph.

## Terminal Result

```text
DISCUSS-RESULT
verdict: PASS | NEEDS_INPUT | CONFLICT
authorities: <changed repository-relative paths, or none>
identities: <jobs, journeys and KPI ids consumed downstream>
observations: <positive and negative value observations>
next-owner: DIVERGE | DESIGN | DISTILL | NONE
```

No per-delivery narrative, plan, ledger or wave-status artifact is produced.
