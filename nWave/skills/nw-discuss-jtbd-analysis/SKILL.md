---
name: nw-discuss-jtbd-analysis
description: "DISCUSS Phase 1 JTBD analysis procedure — job discovery, job dimensions, four forces, opportunity scoring, and the JTBD-to-story bridge, with artifact paths. Run when Decision 4 = Yes and JTBD analysis is about to start."
user-invocable: false
disable-model-invocation: true
---

# DISCUSS Phase 1: Jobs-to-be-Done Analysis (PROCEDURE)

**Kind**: PROCEDURE | **One job**: ground the wave in real user motivations via JTBD analysis | **One trigger**: Phase 1 — Decision 4 = Yes and JTBD analysis is about to run.

Composed by `nw-discuss`.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Phase 1: Jobs-to-be-Done Analysis (DEFAULT — when Decision 4 = Yes; SKIPPED only for infrastructure-only escape valve)

Grounds all subsequent artifacts in real user motivations. Mandatory unless Decision 4 = No (infrastructure-only); reviewer enforces job traceability as a hard-blocking DoR check.

1. **Job Discovery** — Ask user what users are trying to accomplish. Capture in job story format: "When [situation], I want to [motivation], so I can [outcome]." Gate: all primary jobs documented in job story format.
2. **Job Dimensions** — For each job, identify functional (practical task), emotional (desired feeling), and social (desired perception) dimensions. Gate: three dimensions documented per job.
3. **Four Forces Analysis** — For each primary job, document Push (current frustration), Pull (desired future), Anxiety (adoption concerns), Habit (current behavior must change). Extract forces from interview transcripts, support tickets, or analytics when available rather than relying solely on user description. Gate: all four forces documented per job.
4. **Opportunity Scoring** — Rank jobs by importance vs. satisfaction gap. High importance + low satisfaction = strongest opportunities. Produce scored table. Gate: scored table produced when multiple jobs exist.
5. **JTBD-to-Story Bridge** — Map each job story to the user stories and acceptance criteria it will feed in Phase 3. Gate: every user story traces to at least one job.

| Artifact | Path |
|----------|------|
| Job Stories | `docs/feature/{feature-id}/discuss/jtbd-job-stories.md` |
| Four Forces | `docs/feature/{feature-id}/discuss/jtbd-four-forces.md` |
| Opportunity Scores | `docs/feature/{feature-id}/discuss/jtbd-opportunity-scores.md` (when multiple jobs) |
