---
name: nw-deliver
description: Routes one strict Request into the DES steps that deliver it.
user-invocable: true
argument-hint: '<request>'
---
# NW-DELIVER

Before creating or inheriting a lane, or finalizing/resuming its cleanup,
apply the worktree lifecycle in `nw-throughput`. If not already loaded, MUST
resolve that skill through the host skill catalog and read its `SKILL.md`.

Interactive, one step at a time:
```bash
printf '%s' "$REQUEST" | des po --repo-root ROOT --feature FEATURE_ID
```
For this feature Request, the LLM evaluates and revises an evidence-based S/M/L assessment, decides applicable waves or an upstream authority correction, and chooses each supported operation. `NEXT` is advisory and may be ignored; DES never maps size to a route or invokes it. Each step owns one thing — the Product Owner decomposition, design facts, public oracle, change, candidate/native evidence, separately selected reviewer and source-blind examiner, and integration — and returns. The sequence is yours; no command composes it. Role outcomes are observations, never admission. `nw-auto` owns that guidance. Public results are `Success`, `Refusal`, `Retry`, and `Indeterminate`.

Read `~/.claude/skills/nw-role-invocation/SKILL.md` for role forms: `des po`,
`des design --value N`, `des oracle --value N`, `des craft --value N`, and
`des prepare-role` then `des invoke-role` for reviewer/examiner only. Native
delegation selects the exact installed role; never a generic fallback.

Where an uncertain boundary remains, use those existing operations to exercise
an early concrete producer-to-consumer connection: semantic input, DES
constructor, executable public-port oracle and its RED observation, then the
implementation and observation it enables. The LLM chooses whether and when to
take that path; it does not turn `NEXT` into a mandatory order. If a consumer
cannot proceed, route its specific missing semantic question and counterexample
to the owning author before expanding the affected design or solution. Do not
introduce a cycle for an internal technical fragment.

Document scope must be explicit for DISCUSS, PO and DEVOPS. The examples select a feature; alternatives are `--project`, `--epic EPIC_ID`, or `--slice FEATURE_ID SLICE_ID`. Select exactly one. Later steps inherit the persisted scope.

## Wave-end expansion offer — resolved at entry, said at the end

At the START of this wave, before any deliver work, run once:

```
des wave-entry --repo-root <repository top level> --wave deliver
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
