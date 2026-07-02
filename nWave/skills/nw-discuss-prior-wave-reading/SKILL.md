---
name: nw-discuss-prior-wave-reading
description: "DISCUSS prior-wave consultation + back-propagation procedure — read SSOT + DISCOVER/DIVERGE artifacts with reading enforcement, run the migration gate, check DISCOVER contradictions, and back-propagate changed assumptions. Run BEFORE beginning DISCUSS work."
user-invocable: false
disable-model-invocation: true
---

# DISCUSS Prior-Wave Consultation + Back-Propagation (PROCEDURE)

**Kind**: PROCEDURE | **One job**: consume SSOT + prior-wave knowledge and back-propagate changed assumptions | **One trigger**: a DISCUSS session is about to begin work and has not yet read the SSOT + prior-wave artifacts.

Composed by `nw-discuss`.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Prior Wave Consultation

Before beginning DISCUSS work, read SSOT and prior wave artifacts:

1. **SSOT** (if `docs/product/` exists):
   - `docs/product/journeys/{name}.yaml` — existing journey to extend (if applicable)
   - `docs/product/jobs.yaml` — validated jobs and opportunity scores
   - `docs/product/vision.md` — product vision
2. **Project context**: `docs/project-brief.md` | `docs/stakeholders.yaml`
3. **DISCOVER artifacts**: Read `docs/feature/{feature-id}/discover/` (if present)
4. **DIVERGE artifacts**: Read `docs/feature/{feature-id}/diverge/recommendation.md` and `job-analysis.md` (if present — job is already validated, do not re-run JTBD)

**Migration gate**: run the migration gate defined in the `nw-discuss` core (§Migration gate) before proceeding — it is AT-pinned to that file.

DISCUSS follows DISCOVER and optionally DIVERGE — reading SSOT first ensures continuity with prior features, then prior wave artifacts ground requirements in evidence.

**READING ENFORCEMENT**: You MUST read every file listed in Prior Wave Consultation above using the Read tool before proceeding. After reading, output a confirmation checklist (`✓ {file}` for each read, `⊘ {file} (not found)` for missing). Do NOT skip files that exist — skipping causes requirements disconnected from evidence.

After reading, check whether any DISCUSS decisions would contradict DISCOVER evidence. Flag contradictions and resolve with user before proceeding. Example: DISCOVER found "users don't want automation" but DISCUSS story assumes "automated workflow" — this must be resolved.

## Document Update (Back-Propagation)

When DISCUSS decisions change assumptions established in DISCOVER:

1. **Document change** — Add a `## Changed Assumptions` section at the end of the affected DISCUSS artifact. Gate: section exists in artifact.
2. **Reference original** — Quote the original DISCOVER document and the original assumption verbatim. Gate: source document and quote both present.
3. **State new assumption** — State the new assumption and rationale for the change. Gate: rationale is explicit.
4. **Preserve DISCOVER** — Do NOT modify DISCOVER documents directly. Gate: DISCOVER documents unchanged.
