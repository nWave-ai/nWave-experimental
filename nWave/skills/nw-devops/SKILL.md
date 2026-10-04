---
name: nw-devops
description: "Establishes durable deployment, environment, observability, recovery, and CI constraints when platform risk requires the DEVOPS lens."
user-invocable: true
argument-hint: '[platform risk or deployment target]'
---

# NW-DEVOPS

Read `~/.claude/skills/nw-human-collaboration/SKILL.md` to offer and conduct
interactive refinement with the human. Honor an already selected final-review
or full-delegation mode; the LLM manages the dialogue and progression.


Read `~/.claude/skills/nw-role-invocation/SKILL.md` before delegating. Invoke
the installed `nw-platform-architect` role natively to supply semantic facts;
`des devops --input -` constructs the document and buys no role turn.

These invocation, wave-entry, expansion and rendering steps bind the outer wave caller only. When the `nw-platform-architect` role itself reads this skill, it applies only the semantic workflow and returns the OperationalDocumentInput facts and human questions to its caller; it never invokes itself, runs `des wave-entry` or `des devops`, or keeps an expansion offer hidden from its caller.

## Purpose

Apply the platform lens only when infrastructure, deployment, recovery,
observability or environment risk is material. Update existing durable platform
architecture, environment inventory and ADRs; do not create a per-delivery
narrative.

## Workflow

1. Read stable product KPI identities and durable architecture decisions.
2. Inventory actual environments, toolchains, trust boundaries and ownership.
3. Define deployment and rollback observations, health signals, SLOs and alert
   ownership.
4. Model infrastructure/recovery outcomes explicitly: timeout, unavailable,
   partial success, retryable, permanent refusal, replay and operator action.
   Ensure the application/port contract cannot silently ignore a required
   failure mode.
5. Define literal environment-native verification commands and dependency
   ownership. Never substitute an ambient `.venv` or assume a language.
6. Supply one closed `OperationalDocumentInput v1` to `des devops
   --repo-root ROOT --feature FEATURE_ID --input -`. DES constructs the
   operational authority and adjacent facts; cite the returned facts to PO.
7. When independent operational review is selected, follow `nw-role-invocation`'s selected-review branch: the native caller invokes `nw-platform-architect-reviewer` on the current constructed authority, bound facts, scope and observations, then consumes its actual result. Keep review outside the closed constructor JSON. Required revisions return to the platform authority owner; construction alone is not completion of an enabled selected review. No unselected review turn or live rollout is implied.

DEVOPS does not author a handover, feature workspace, rollout ledger or CI
status copy. A downstream operational contradiction returns to the platform
authority; software re-derives any needed execution facts.

## Public construction

For a machine-supplied operational brief, emit the complete closed
`OperationalDocumentInput v1` JSON and invoke `des devops --repo-root ROOT --feature FEATURE_ID
--input -`.  The provider-free command writes the configured Markdown brief and
canonical adjacent `.operational-facts.json` sidecar. A later native PO turn
consumes only explicitly selected facts; include them through the DISCUSS
manifest contract, never infer them from ambient documents.

## Feature evolution

Feature evolution applies to every completed feature, not only DEVOPS work.
Before creating or inheriting a lane, or finalizing/resuming its cleanup,
apply the worktree lifecycle and completed-feature evolution guidance in
`nw-throughput`. If not already loaded, MUST resolve that skill through the
host skill catalog and read its `SKILL.md`.

Document scope must be explicit for DISCUSS, PO and DEVOPS. The examples select a feature; alternatives are `--project`, `--epic EPIC_ID`, or `--slice FEATURE_ID SLICE_ID`. Select exactly one. Later steps inherit the persisted scope.

## Wave-end expansion offer — resolved at entry, said at the end

At the START of this wave, before any devops work, run once:

```
des wave-entry --repo-root <repository top level> --wave devops
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
For full density, the port renders the successful DES `DOCUMENT:` Markdown
authority after its path checks and reports the local HTML path. Lean retains the document and
handoff. A single successful DES step or partial/stopped wave does not trigger
rendering. Density does not alter optional explanation, provider/model
selection or required checks.
