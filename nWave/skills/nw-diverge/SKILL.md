---
name: nw-diverge
description: "Generates 3-5 divergent design directions through JTBD analysis, competitive research, structured brainstorming, and taste evaluation before convergence. Use when the team has a validated problem but hasn't chosen a solution approach."
user-invocable: true
argument-hint: '[feature-id] --work-type=[new-product|brownfield|pivot]'
---

# NW-DIVERGE

## Authority

DIVERGE updates the durable `docs/product/jobs.yaml` (the validated job,
opportunity scores, changelog). It never writes a per-delivery decision
ledger. `recommendation.md` and its supporting artifacts are the ephemeral
workspace read while this delivery is open, not a second authority.

## Required Pass

1. **Job (JTBD)** -- extract and elevate the job from the request or
   `docs/product/vision.md`/DISCOVER evidence, at strategic or physical
   level, not tactical. Produce functional/emotional/social statements and
   minimum 3 ODI outcome statements.
2. **Competitive research** -- invoke `nw-researcher` for evidence-grounded
   mapping of how existing products serve the job, including at least one
   non-obvious alternative.
3. **Brainstorming** -- frame the HMW question, apply SCAMPER, generate 6
   structurally diverse options (mechanism, assumption and cost differ).
4. **Taste evaluation** -- apply the DVF filter, score surviving options on
   the 4 locked-weight taste criteria, produce a traceable ranking with a
   dissenting case for the second-place option.
5. **Peer review** -- `nw-diverger-reviewer` validates all 5 dimensions,
   maximum 2 revision iterations.

## Handoff

Update `docs/product/jobs.yaml` once with the validated job and a changelog
entry referencing this feature-id. Return the recommendation and decision
statement; do not author a `wave-decisions.md` or any other per-wave ledger.

```text
DIVERGE-RESULT
verdict: PASS | NEEDS_INPUT
job: <JOB-id, statement>
options: <count generated, count survived>
recommended: <option> -- <one-line rationale>
dissent: <second-place option> -- <why it might win under different assumptions>
ssot: <docs/product/jobs.yaml updated>
```

## Wave-end expansion offer — resolved at entry, said at the end

At the START of this wave, before any diverge work, run once:

```
des wave-entry --repo-root <repository top level> --wave diverge
```

It is read-only. Retain its output for the rest of the wave and obey the
`WAVE-END-OFFER-INTERNAL-*` rows; they are addressed to you alone and are never
shown to the user. Do not reread the configuration later: the preference was
already resolved at this entry.

Say nothing about expansion before your final response for this wave, and only
after the whole wave has really completed. The `WAVE-END-OFFER-INTERNAL-NOT-NOW`
rows decide which situations carry no offer — a single DES step terminal of any
outcome among them. Invoke no wave-end step: none exists.

If `des wave-entry` refuses or returns `Indeterminate`, make no offer and do not
invent one; report its WHAT/WHY/HOW to the human.
