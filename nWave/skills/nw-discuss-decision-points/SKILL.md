---
name: nw-discuss-decision-points
description: "DISCUSS interactive decision catalog — Decisions 1-4 (feature type, walking skeleton, UX research depth, JTBD inclusion) with options, defaults, and rationale. Consult when presenting or resolving the wave-entry decisions."
user-invocable: false
disable-model-invocation: true
---

# DISCUSS Interactive Decision Points (KNOWLEDGE)

**Kind**: KNOWLEDGE (reference). No forced sequence — consulted on its trigger.

**Trigger**: you are presenting or resolving the wave-entry Decisions 1-4 (feature type, walking skeleton, UX research depth, JTBD inclusion). Composed by `nw-discuss`.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Interactive Decision Points

### Decision 1: Feature Type
**Question**: What type of feature is this?
**Options**:
1. User-facing -- UI/UX functionality visible to end users
2. Backend -- APIs, services, data processing
3. Infrastructure -- DevOps, CI/CD, tooling
4. Cross-cutting -- Spans multiple layers (auth, logging, etc.)
5. Other -- user provides custom input

### Decision 2: Walking Skeleton
**Question**: Should we start with a walking skeleton?
**Options**:
1. Yes -- recommended for greenfield projects
2. Depends -- brownfield; Luna evaluates existing structure first
3. No -- feature is isolated enough to skip

### Decision 3: UX Research Depth
**Question**: Priority for UX research depth?
**Options**:
1. Lightweight -- quick journey map, focus on happy path
2. Comprehensive -- full experience mapping with emotional arcs
3. Deep-dive -- extensive user research, multiple personas, edge cases

### Decision 4: JTBD Analysis
**Question**: Include Jobs-to-be-Done analysis?
**Options**:
1. Yes -- mandatory by default. Every user-facing story must trace to a `job_id` in `docs/product/jobs.yaml`. Stories without job traceability fail Definition of Ready.
2. No (infrastructure-only escape valve) -- only permitted when the feature is a pure internal change (e.g. rename internal module, refactor build script) with no user-visible behavior. Requires `job_id: infrastructure-only` AND a `infrastructure_rationale` field on every story explaining why no user job applies. Reviewer will reject this option for any feature that touches user-facing surfaces.

Default: 1 (Yes). Rationale: STANDING rule "Tech-surface vs value-outcome backlog anti-pattern" (2026-04-24) — epics with tech-surface children but no JTBD framing fail to converge on done-state. Default-on JTBD enforces value-outcome framing at PO level.
