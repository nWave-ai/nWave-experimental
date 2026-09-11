---
name: nw-devops
description: "Establishes durable deployment, environment, observability, recovery, and CI constraints when platform risk requires the DEVOPS lens."
user-invocable: true
argument-hint: '[platform risk or deployment target]'
---

# NW-DEVOPS

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
6. Send the same constraints to `des devops --authority <doc.md> --section
   <heading>`, which constructs the platform brief/ADR/environment authority
   update and returns stable ids plus the executable obligations DISTILL must
   project.

DEVOPS does not author a handover, feature workspace, rollout ledger or CI
status copy. A downstream operational contradiction returns to the platform
authority; software re-derives any needed execution facts.

## Public construction

For a machine-supplied operational brief, emit the complete closed
`OperationalDocumentInput v1` JSON and invoke `des devops --repo-root ROOT
--input -`.  The provider-free command writes the configured Markdown brief and
canonical adjacent `.operational-facts.json` sidecar.  A later PO turn consumes
facts only when the orchestrator explicitly selects that sidecar with
`des po --operational-facts PATH`; never infer it from ambient documents.

## Feature evolution

Feature evolution applies to every completed feature, not only DEVOPS work.
Follow the canonical whole-feature invocation and cleanup guidance in
`nWave/skills/nw-throughput/SKILL.md#feature-evolution-before-cleanup`.
