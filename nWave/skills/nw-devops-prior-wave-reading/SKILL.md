---
name: nw-devops-prior-wave-reading
description: "DEVOPS prior-wave consultation + back-propagation procedure — read the DISCUSS outcome KPIs and the DESIGN artifacts with a confirmation checklist, check contradictions against the architecture, and back-propagate changed assumptions (including upstream-changes.md for the architect). Run BEFORE beginning DEVOPS work."
user-invocable: false
disable-model-invocation: true
---

# DEVOPS Prior-Wave Consultation + Back-Propagation (PROCEDURE)

**Kind**: PROCEDURE | **One job**: consume prior-wave knowledge and back-propagate changed assumptions | **One trigger**: a DEVOPS session is about to begin work and has not yet read the prior-wave artifacts.

Composed by `nw-devops`.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Prior Wave Consultation

Before beginning DEVOPS work, read targeted prior wave artifacts:

1. **DISCOVER** (skip): DESIGN already synthesizes DISCOVER+DISCUSS into architecture. Not needed for infrastructure design.
2. **DISCUSS** (KPIs only): Read `docs/feature/{feature-id}/discuss/outcome-kpis.md` — drives observability and instrumentation design.
3. **DESIGN** (primary input): Read all files in `docs/feature/{feature-id}/design/` — architecture drives infrastructure decisions.

**READING ENFORCEMENT**: Read every file listed above using the Read tool before proceeding. After reading, output a confirmation checklist (`✓ {file}` for each read, `⊘ {file} (not found)` for missing). Do NOT skip files that exist — skipping causes infrastructure decisions disconnected from architecture.

After reading, check whether any DEVOPS decisions would contradict DESIGN architecture. Flag contradictions and resolve with user before proceeding. Example: DESIGN specifies "single-region deployment" but DEVOPS discovers latency requirements from outcome-kpis.md that demand multi-region — this must be resolved.

## Document Update (Back-Propagation)

When DEVOPS decisions change assumptions from prior waves:

1. **Document change** — Add a `## Changed Assumptions` section at the end of the affected DEVOPS artifact. Gate: section present in artifact.
2. **Reference original** — Quote the original prior-wave document and the original assumption. Gate: quote included.
3. **State new assumption** — Write the new assumption and rationale for the change. Gate: rationale documented.
4. **Flag upstream changes** — If infrastructure constraints require architecture changes, write them to `docs/feature/{feature-id}/devops/upstream-changes.md` for the architect to review. Gate: file created if architecture impact exists.
