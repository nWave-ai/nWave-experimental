---
name: nw-discover
description: "Tests whether a product problem and opportunity are real, then updates the durable product evidence authorities without creating delivery state."
user-invocable: true
argument-hint: '[product-concept]'
---

# NW-DISCOVER

## Purpose

Reduce product uncertainty before requirements or architecture investment.
Use customer evidence, assumption tests and counterexamples; never promote a
founder belief to fact by repetition.

## Workflow

1. State the opportunity, riskiest assumptions and falsification thresholds.
2. Gather evidence with source, sample size, date and confidence. Separate
   observation, inference and hypothesis.
3. Test problem severity, current workaround, triggering context and willingness
   to change. Seek disconfirming evidence.
4. Decide `VALIDATED`, `PIVOT`, `MORE_EVIDENCE` or `STOP`.
5. Update the existing durable product authority that owns the result: vision,
   jobs, journey evidence or KPI baseline. Preserve provenance and stable ids.

Return changed authority paths, evidence citations, confidence and the next
unresolved question. Do not create a feature directory, manual handover,
wave report, plan or progress artifact.

## Wave-end expansion offer — resolved at entry, said at the end

At the START of this wave, before any discover work, run once:

```
des wave-entry --repo-root <repository top level> --wave discover
```

It is read-only. Retain its output for the rest of the wave and obey the
`WAVE-END-OFFER-INTERNAL-*` rows; they are addressed to you alone and are never
shown to the user. Do not reread the configuration later: the preference was
already resolved at this entry.

Say nothing about expansion before your final response for this wave, and only
after the whole wave has really completed. The `WAVE-END-OFFER-INTERNAL-NOT-NOW`
rows decide which situations carry no offer — a single DES step terminal of any
outcome among them. Invoke no wave-end expansion step; the local view has a
separate completion port.

If `des wave-entry` refuses or returns `Indeterminate`, make no offer and do not
invent one; report its WHAT/WHY/HOW to the human.

## Completed-wave local view

Read `nw-doc-as-artifact`. Retain `WAVE-DOCUMENTATION-DENSITY` from wave entry.
After whole-wave success, invoke `des wave-entry --complete` with the captured
entry and successful constructor terminals as that skill describes.
After this whole wave succeeds, full density runs the packaged renderer on each
actual successful DES Markdown `DOCUMENT:` authority produced by this wave,
following that skill's path checks, and reports the local HTML path. DISCOVER
normally updates product evidence without a DES document; in that case there
is no applicable HTML view to claim. Lean retains the authority and handoff.
Never render for a lone DES step, stopped wave or partial outcome. This choice
does not alter optional explanation, provider/model selection or required checks.
