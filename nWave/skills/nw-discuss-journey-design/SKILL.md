---
name: nw-discuss-journey-design
description: "DISCUSS Phase 2 journey design procedure — mental model discovery, happy path, emotional arc, shared artifact tracking, error paths, and Gherkin scenario generation, with artifact paths. Run when designing the UX journey informed by JTBD."
user-invocable: false
disable-model-invocation: true
---

# DISCUSS Phase 2: Journey Design (PROCEDURE)

**Kind**: PROCEDURE | **One job**: design the UX journey (visual + YAML + Gherkin) informed by JTBD | **One trigger**: Phase 2 — the UX journey is about to be designed after JTBD analysis.

Composed by `nw-discuss`.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Phase 2: Journey Design

Luna runs deep discovery (mental model|emotional arc|shared artifacts|error paths) informed by JTBD, produces visual journey + YAML schema + Gherkin scenarios. Each journey maps to one or more identified jobs.

1. **Mental Model Discovery** — Uncover user mental model: what users believe about the system, their vocabulary, and assumptions. Gate: mental model documented with no vague steps.
2. **Happy Path Definition** — Define all steps start-to-goal with expected outputs at each step. Gate: complete happy path with explicit outputs per step.
3. **Emotional Arc Design** — Map emotional state at each step. Confidence must build progressively toward goal. Gate: emotional arc coherent with upward trajectory.
4. **Shared Artifact Tracking** — Identify every `${variable}` or artifact passed between steps. Document single source of truth for each. Gate: every shared artifact has one documented source.
5. **Error Path Mapping** — Identify failure modes and recovery paths for critical steps. Gate: error paths documented for each high-risk step.
6. **Gherkin Scenario Generation** — Produce Gherkin scenarios covering happy path and key error paths. Gate: scenarios cover all journey steps.

| Artifact | Path |
|----------|------|
| Visual Journey | `docs/feature/{feature-id}/discuss/journey-{name}-visual.md` |
| Journey Schema | `docs/feature/{feature-id}/discuss/journey-{name}.yaml` |
| Gherkin Scenarios | `docs/feature/{feature-id}/discuss/journey-{name}.feature` |
| Artifact Registry | `docs/feature/{feature-id}/discuss/shared-artifacts-registry.md` |
