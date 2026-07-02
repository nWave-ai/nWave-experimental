---
name: nw-design-prior-wave-reading
description: "DESIGN prior-wave consultation + back-propagation procedure — read SSOT architecture + DISCUSS/SPIKE artifacts with a confirmation checklist, run the migration gate, check contradictions, and back-propagate changed assumptions (including upstream-changes.md for the product owner). Run BEFORE beginning DESIGN work."
user-invocable: false
disable-model-invocation: true
---

# DESIGN Prior-Wave Consultation + Back-Propagation (PROCEDURE)

**Kind**: PROCEDURE | **One job**: consume SSOT + prior-wave knowledge and back-propagate changed assumptions | **One trigger**: a DESIGN session is about to begin work and has not yet read the SSOT + prior-wave artifacts.

Composed by `nw-design`.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Prior Wave Consultation

Before beginning DESIGN work, read SSOT and prior wave artifacts in this order:

1. **Read SSOT architecture** (if `docs/product/` exists) — read `docs/product/architecture/brief.md` (extend, not recreate), `docs/product/architecture/adr-*.md` (existing decisions), `docs/product/journeys/{name}.yaml` (journey schema for port identification). Gate: all existing files read or confirmed missing.
2. **Read DISCUSS artifacts** (primary input) — read from `docs/feature/{feature-id}/discuss/`: `wave-decisions.md` (decision summary), `user-stories.md` (scope, requirements, acceptance criteria), `story-map.md` (walking skeleton and release slicing), `outcome-kpis.md` (quality attributes). Gate: all four files read or confirmed missing.
3. **Read SPIKE findings** (if spike was run) — read from `docs/feature/{feature-id}/spike/`: `findings.md` (validated assumptions, performance measurements, what didn't work). This informs your architecture constraints. Gate: file read if present, marked as not found if absent.
4. **Output confirmation checklist** — after reading, output `✓ {file}` for each read, `⊘ {file} (not found)` for each missing. Gate: checklist produced before any architecture work begins.
5. **Check for contradictions** — identify any DESIGN decisions that would contradict DISCUSS requirements or SPIKE findings. Flag contradictions and resolve with user before proceeding. Example: DISCUSS requires "real-time updates" but DESIGN chooses batch processing; or SPIKE found performance budget can't be met. Gate: zero unresolved contradictions.
6. **Migration gate check** — if `docs/product/` does not exist but `docs/feature/` has existing features, STOP. Guide the user to `docs/guides/migrating-to-ssot-model/README.md`. If greenfield, proceed — DESIGN will bootstrap `docs/product/architecture/`. Gate: migration status confirmed.

Note: DISCOVER evidence is already synthesized into DISCUSS — read DISCOVER only if wave-decisions.md flags something architecturally significant.

## Document Update (Back-Propagation)

When DESIGN decisions change assumptions from prior waves:

1. **Document the change** — add a `## Changed Assumptions` section at the end of the affected DESIGN artifact. Gate: section present in artifact.
2. **Reference the original** — quote the original assumption from the prior-wave document, with file path. Gate: original quoted verbatim with source.
3. **State the new assumption** — write the replacement assumption and its rationale. Gate: new assumption and rationale present.
4. **Propagate upstream if needed** — if architecture constraints require changes to user stories or acceptance criteria, write them to `docs/feature/{feature-id}/design/upstream-changes.md` for the product owner to review. Gate: upstream-changes.md created if any story/criteria changes needed.
