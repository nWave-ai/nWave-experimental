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
Before authoring tests or changing code, load `nw-auto` and report the
existing test baseline for the affected work to the user as required by its
visible-baseline rule. A broken setup is not an intentional feature RED.


Interactive, one step at a time:
First invoke the native installed Product Owner with the Request; use its
complete DISCUSS v2 manifest below, not raw Request prose.

```bash
printf '%s' "$DISCUSS_MANIFEST" | des po --repo-root ROOT --feature FEATURE_ID --input -
```
For this feature Request, the LLM evaluates and revises an evidence-based S/M/L assessment, decides applicable waves or an upstream authority correction, and chooses each supported operation. `NEXT` is advisory and may be ignored; DES never maps size to a route or invokes it. Each step owns one thing — the Product Owner decomposition, design facts, public oracle, change, candidate/native evidence, separately selected reviewer and source-blind examiner, and integration — and returns. The sequence is yours; no command composes it. Role outcomes are observations, never admission. `nw-auto` owns that guidance. Public results are `Success`, `Refusal`, `Retry`, and `Indeterminate`.

Read `~/.claude/skills/nw-role-invocation/SKILL.md` for exact native role
invocation, mandatory skills, source-blind packets and recording contracts.
The native host runs specialists; `des po|design ... --input -` constructs their
manifests, `des oracle|craft ... --input -` measures and records their work, and
`des prepare-role` / `des record-role-result` bind independent assessments.

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
outcome among them. Invoke no wave-end expansion step; the local view has a
separate completion port.

If `des wave-entry` refuses or returns `Indeterminate`, make no offer and do not
invent one; report its WHAT/WHY/HOW to the human.

## Completed-wave local view

Read `nw-doc-as-artifact` and retain `WAVE-DOCUMENTATION-DENSITY` from wave
entry. After this whole wave succeeds, invoke `des wave-entry --complete` with
the captured entry and successful constructor terminals as that skill directs.
For full density, the port renders each distinct successful DES Markdown
`DOCUMENT:` authority after its path checks and reports the local HTML path. DELIVER
does not create a separate wave document; if no such DES authority was produced,
there is no applicable HTML view to claim. Lean retains the authority and
handoff. Never render for a lone DES step, stopped wave or partial outcome.
This choice does not alter optional explanation, provider/model selection or
required checks.

## Feature evolution and closing

For lane work, use the user's project `ROOT/lanes/NAME` reported by `des lane
open`, not a framework checkout or `TMPDIR`. Integrate with `--keep-worktree`
so the lane survives until evolution and evidence preservation are complete.

Only after the whole feature is integrated, never per slice, follow
`nw-throughput` "Feature evolution before cleanup": invoke `des evolution
--repo-root ROOT --input -` once on destination `ROOT`, filling the JSON from
the delivery's own records (accepted documents, verify evidence) with
`not_applicable` plus a reason instead of invented content. Preserve the
generated document and its evidence on `ROOT`; commit them when authorized.
DES never commits or publishes automatically.
If the work ran in a lane the LLM opened, run `des lane finalize --repo-root
ROOT --worktree PATH` after reconciliation. This is advisory: no DES gate, no
automatic NEXT execution. Omit evolution only when the human declined or the
request is a trivial non-feature change, with the reason stated.
