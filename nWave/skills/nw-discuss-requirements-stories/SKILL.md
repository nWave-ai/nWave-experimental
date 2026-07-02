---
name: nw-discuss-requirements-stories
description: "DISCUSS Phase 3 requirements + user stories procedure — LeanUX stories with job traceability, the Elevator Pitch gate, the slice-composition hard gate, ACs, KPIs, DoR validation, optional peer review, handoff, and the Wave Decisions Summary. Run when crafting stories/ACs/DoR and closing the wave."
user-invocable: false
disable-model-invocation: true
---

# DISCUSS Phase 3: Requirements and User Stories (PROCEDURE)

**Kind**: PROCEDURE | **One job**: craft DoR-validated stories with ACs + KPIs and close the wave | **One trigger**: Phase 3 — journey + story map exist and requirements/stories/DoR are about to be authored.

Composed by `nw-discuss`.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Phase 3: Requirements and User Stories

Luna crafts LeanUX stories informed by JTBD + journey artifacts. Every story traces to at least one job story. Validates against DoR, prepares handoff. Per-wave peer review is OPTIONAL — the mandatory review gate is consolidated at end of DISTILL where Eclipse + Architect + Forge + Sentinel run in parallel against the full feature-delta.md (all 4 waves visible). Invoke per-wave review explicitly via `/nw-review` only when uncertainty warrants early feedback (e.g., novel domain, contested DoR, vendor-neutrality risk).

1. **Story Drafting** — Craft user stories in LeanUX format. Each story MUST trace to at least one `job_id` referencing a job in `docs/product/jobs.yaml` (Phase 1 output when Decision 4 = Yes). Infrastructure-only escape valve (Decision 4 = No): every story uses `job_id: infrastructure-only` AND includes an `infrastructure_rationale` field documenting why no user job applies — reviewer rejects this for user-facing features. Gate: every story has a job traceability reference (real `job_id` OR `infrastructure-only` with rationale).
1b. **Elevator Pitch Test (MANDATORY, per-story)** — Every user story MUST contain an `### Elevator Pitch` subsection immediately after the story narrative, with exactly these three lines:

```markdown
### Elevator Pitch
Before: {one sentence — what the user cannot do today}
After: run `{exact command / endpoint / UI action}` → sees `{exact observable output}`
Decision enabled: {one sentence — what the user decides with that output}
```

Rules:
- The "After" line MUST reference a real user-invocable entry point (CLI subcommand, HTTP endpoint path, UI action name) — not a service function or internal API
- The "sees" portion MUST describe concrete observable output (stdout text, HTTP response body, screen element) — not internal state or "tests green"
- The "Decision enabled" line is the Job-to-be-Done connection: if the user cannot make any decision with the output, the story is infrastructure, not value — merge it into the story that DOES enable a decision
- If a story legitimately has no user-visible output (pure infra migration), it MUST be labelled `@infrastructure` and BLOCK the slice — a slice containing only `@infrastructure` stories cannot be released

**Slice composition hard gate (per Decision 2)**: any slice that contains ONLY `@infrastructure` stories (zero user-visible value stories) is a structural failure. The BLOCKING verdict is MECHANICAL: the feature-delta validator (gate-id in `nWave/gates/_catalog.yaml`) run `--require-slice-plan` returns `rejected-infra-only` (cohesion-MECC, non-zero exit) on an all-`@infrastructure` slice plan. The reviewer (`nw-product-owner-reviewer`) flags slice cohesion as advisory veto feedback — it is not the blocking authority for this check. The PO must either (a) merge the slice with an adjacent value-bearing slice, or (b) split the `@infrastructure` work to land BEFORE the slice as a precursor commit (not a separately-shipped slice). This is hard-blocking: structural failure, not nit.

Gate: every non-`@infrastructure` story has a complete Elevator Pitch. Every slice contains at least one user-visible value story (slice composition hard gate).

2. **Acceptance Criteria** — Embed testable acceptance criteria in each story. Gate: every AC is verifiable without ambiguity. AC MUST verify the Elevator Pitch's "After" command produces the "sees" output end-to-end.
3. **Requirements Completeness** — Calculate requirements completeness score. Gate: score > 0.95.
4. **Outcome KPIs** — Define measurable outcome KPIs with targets. Gate: each KPI has a numeric target and measurement method.
5. **DoR Validation** — Validate all 9 DoR items with evidence. Gate: DoR passed with evidence for all 9 items.
6. **Peer Review (OPTIONAL — per-wave; mandatory at end of DISTILL)** — Per-wave Eclipse review is opt-in. Invoke explicitly via `/nw-review nw-product-owner-reviewer` only if (a) DoR validation surfaced ambiguity, (b) JTBD assumptions are unverified, (c) vendor-neutrality risk in story ACs, or (d) user explicitly requests. Default: skip. The mandatory consolidated review covering DISCUSS+DESIGN+DEVOPS+DISTILL fires at end of DISTILL. Gate: optional unless triggered. **Structural-correctness reviewer never skips**: `rigor.reviewer_model: "skip"` applies to scale-sensitive cost-driven reviewers (Eclipse / Architect / Forge) only; the structural-correctness reviewer at the end of DISTILL (Sentinel / `@nw-acceptance-designer-reviewer`) ALWAYS dispatches — silent skip masks the bug class issue #52 fixed.
7. **Handoff Preparation** — Confirm handoff acceptance by nw-solution-architect (DESIGN wave). Gate: handoff accepted.

> **ADR-022 single-narrative**: these are INLINE `## Wave: DISCUSS / [REF] <Section>` headings in `docs/feature/{feature-id}/feature-delta.md` — NOT separate `discuss/*.md` files (see the `nw-discuss` core §Outputs; legacy multi-file outputs are not produced). DoR-location is therefore `## Wave: DISCUSS / [REF] DoR Validation` inline, so the DoR gate is deterministically satisfiable.

| Artifact | Location (inline heading in `docs/feature/{feature-id}/feature-delta.md`) |
|----------|------|
| User Stories (includes requirements + embedded AC) | `## Wave: DISCUSS / [REF] User Stories` |
| DoR Validation | `## Wave: DISCUSS / [REF] DoR Validation` |
| Outcome KPIs | `## Wave: DISCUSS / [REF] Outcome KPIs` |

## Wave Decisions Summary

Before completing DISCUSS, produce `docs/feature/{feature-id}/discuss/wave-decisions.md`:

```markdown
# DISCUSS Decisions — {feature-id}

## Key Decisions
- [D1] {decision}: {rationale} (see: {source-file})

## Requirements Summary
- Primary jobs/user needs: {1-3 sentence summary}
- Walking skeleton scope: {if applicable}
- Feature type: {user-facing|backend|infrastructure|cross-cutting}

## Constraints Established
- {constraint from requirements analysis}

## Upstream Changes
- {any DISCOVER assumptions changed, with rationale}
```

This summary enables DESIGN to quickly assess DISCUSS outcomes. DESIGN reads this plus key artifacts (user-stories.md, story-map.md, outcome-kpis.md) rather than all DISCUSS files.
