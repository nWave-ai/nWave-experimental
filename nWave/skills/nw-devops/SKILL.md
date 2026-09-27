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

DEVOPS does not author a handover, feature workspace, rollout ledger or CI
status copy. A downstream operational contradiction returns to the platform
authority; software re-derives any needed execution facts.

## Public construction

For a machine-supplied operational brief, emit the complete closed
`OperationalDocumentInput v1` JSON and invoke `des devops --repo-root ROOT --feature FEATURE_ID
--input -`.  The provider-free command writes the configured Markdown brief and
canonical adjacent `.operational-facts.json` sidecar.  A later PO turn consumes
facts only when the orchestrator explicitly selects that sidecar with
`des po --operational-facts PATH`; never infer it from ambient documents.

## Feature evolution

Feature evolution applies to every completed feature, not only DEVOPS work.
Before creating or inheriting a lane, or finalizing/resuming its cleanup,
apply the worktree lifecycle and completed-feature evolution guidance in
`nw-throughput`. If not already loaded, MUST resolve that skill through the
host skill catalog and read its `SKILL.md`.

Document scope must be explicit for DISCUSS, PO and DEVOPS. The examples select a feature; alternatives are `--project`, `--epic EPIC_ID`, or `--slice FEATURE_ID SLICE_ID`. Select exactly one. Later steps inherit the persisted scope.
