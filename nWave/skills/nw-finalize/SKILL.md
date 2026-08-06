---
name: nw-finalize
description: "Archives a completed feature to docs/evolution/, migrates lasting artifacts to permanent directories, preserves the feature workspace, and cleans session artifacts. Use after completion evidence passes."
user-invocable: false
argument-hint: '[agent] [feature-id] - Example: @nw-platform-architect "auth-upgrade"'
---

# NW-FINALIZE: Feature Completion and Archive

**Wave**: CROSS_WAVE
**Agent**: @nw-platform-architect (default) or specified agent

## Overview

Finalize a completed feature: verify current completion evidence|create evolution document|migrate lasting artifacts to permanent directories|preserve the feature workspace|clean session artifacts. The agent gathers project data, writes a concise summary, migrates lasting artifacts, and preserves the source history.

`docs/feature/{feature-id}/` is the active feature workspace and remains the feature's living history after finalization. Lasting artifacts are copied to permanent directories for discoverability; only explicitly approved session artifacts are removed.

## Usage

```
/nw-finalize @{agent} "{feature-id}"
```

## Context Files Required

The completion-evidence files depend on `workflow.mode` — per-mode descriptor + audit substrate projected from the mode registry: <!-- mode-ref-ok -->

<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice AT-first loop; AT-completion ledger + commit trailers are the authority.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
<!-- GENERATED:mode-descriptor END -->

- **atdd_pure mode** — the feature delta, executable acceptance-test results, EXAMINE/review evidence, and clean slice/feature completion attestations. <!-- mode-ref-ok -->

## Pre-Dispatch Gate: All Work Complete

Before dispatching, verify that the feature's current completion evidence is internally consistent. Do not infer completion from the presence or contents of a planning or execution-history carrier. <!-- mode-ref-ok -->

1. **Verify completion evidence** — Confirm every declared slice is shipped, its executable acceptance tests pass, observable value has independent EXAMINE evidence, and feature-level review/completion evidence is current. Gate: no declared outcome lacks evidence.
2. **Block or proceed** — If evidence is missing or contradictory, list the exact slice or outcome and halt. Otherwise proceed to dispatch. Gate: completion evidence reconciled before dispatch.

### atdd_pure mode <!-- mode-ref-ok -->

Completion is established from the feature delta plus current executable-test, EXAMINE/review, and clean-commit evidence. Every declared slice must be shipped and every observable outcome independently examined. Gate: the evidence set reconciles without missing slices or stale observations.

## Phases

### Phase A — Evolution Document

1. **Create evolution document** — Write `docs/evolution/YYYY-MM-DD-{feature-id}.md` from the feature outcome, decisions, executable-test results, EXAMINE/review observations, and relevant git history. Gate: concise current-state summary created.
2. **Extract key decisions** — Pull lasting decisions, issues, and lessons from the feature workspace. Gate: decisions list assembled.

### Phase B — Migrate Lasting Artifacts

1. **Scan workspace** — List all files under `docs/feature/{feature-id}/`. Gate: file list produced.
2. **Match against destination map** — For each file, apply the destination map below. Gate: migration plan assembled.
3. **Create destination directories** — Create any missing permanent directories. Gate: directories exist.
4. **Copy files** — Copy each matched file to its permanent destination. Gate: all copies verified.
5. **Log files not copied** — Note the workspace files retained in living history rather than copied to a permanent discovery location. Gate: retention list documented.

#### Destination Map

| Source (feature workspace) | Destination (permanent) | Condition |
|---|---|---|
| `design/architecture-design.md` | `docs/architecture/{feature}/` | If exists |
| `design/component-boundaries.md` | `docs/architecture/{feature}/` | If exists |
| `design/technology-stack.md` | `docs/architecture/{feature}/` | If exists |
| `design/data-models.md` | `docs/architecture/{feature}/` | If exists |
| `design/adrs/ADR-*.md` | `docs/adrs/` | Flat namespace, cross-feature |
| `distill/walking-skeleton.md` | `docs/scenarios/{feature}/` | Walking skeleton specification |
| `discuss/journey-*.yaml` | `docs/ux/{feature}/` | If UX journeys exist |
| `discuss/journey-*-visual.md` | `docs/ux/{feature}/` | If UX visuals exist |

Research docs (`docs/research/`) are already in a permanent location — no migration needed.

#### Workspace Artifacts Not Copied

These artifacts remain in `docs/feature/{feature-id}/` as living history. They are not copied to a second permanent location:

| File pattern | Why retain only in the feature workspace |
|---|---|
| `design/review-*.md` | Review findings captured in evolution doc |
| `discuss/dor-checklist.md` | Process gate, not lasting value |
| `discuss/shared-artifacts-registry.md` | Process scaffolding |
| `discuss/prioritization.md` | Superseded by the delivered outcome and evolution summary |
| `*/wave-decisions.md` | Key decisions extracted into evolution doc |

### Phase C — Preserve Workspace and Clean Session Artifacts

1. **List removable session artifacts** — Enumerate only session markers and temporary files; exclude every wave artifact. Gate: bounded cleanup list produced.
2. **Present for approval** — Show the exact bounded cleanup list to the user and request approval. Gate: user explicitly approves.
3. **Preserve workspace** — `docs/feature/{feature-id}/` is NOT deleted. The evolution document is the concise summary; the feature directory remains the living history. Gate: workspace intact.
4. **Clean session artifacts only** — Remove `.nwave/des/deliver-session.json` and any temp files. Do NOT remove wave artifacts (discuss/, design/, distill/, deliver/). Gate: session markers removed, wave artifacts intact.

**NEVER delete without user approval.** Show exactly what will be removed.

### Phase D — Post-Cleanup Verification

1. **Verify migrated files** — Confirm every file copied in Phase B exists at its destination. Gate: all destinations present.
2. **Update architecture doc statuses** — Change any "FUTURE DESIGN" labels to "IMPLEMENTED" in migrated architecture docs. Gate: no stale FUTURE DESIGN labels.
3. **Optionally generate reference docs** — Invoke /nw-document unless `--skip-docs` flag provided. Gate: docs generated or skipped.
4. **Commit evolution doc and artifacts** — Commit 1: evolution doc + migrated artifacts. Gate: commit created.
5. **Commit session-artifact cleanup** — Commit 2: the session markers removed in Phase C step 4 (the feature workspace directory itself is preserved, per Phase C step 3 — never deleted). Gate: commit created and pushed.

## Agent Invocation

@{agent}

<!-- DES-WAVE: feature-end -->

Include the `<!-- DES-WAVE: feature-end -->` marker line above verbatim in the Agent dispatch prompt — it declares the wave so the PreToolUse hook can arm enforcement even on runtimes whose prompt-submission anchor never fired (INFERRED fallback; the marker can only ADD gating, never remove it).

Finalize: {feature-id}

**Key constraints:**

1. Follow the 4-phase process (A → B → C → D) in order.
2. Create evolution document BEFORE migration (needs source files).
3. Migrate BEFORE cleanup (preserves artifacts).
4. Show cleanup list and wait for user approval before removing anything.
5. Commit and push after approval.

## Success Criteria

- [ ] Current feature completion evidence reconciled before dispatch
- [ ] Evolution document created in docs/evolution/
- [ ] Architecture docs migrated to docs/architecture/{feature}/
- [ ] ADRs migrated to docs/adrs/ (if any)
- [ ] Scenario docs migrated to docs/scenarios/{feature}/ (if any)
- [ ] UX journeys migrated to docs/ux/{feature}/ (if any)
- [ ] User approved the exact session-artifact cleanup list
- [ ] Feature workspace preserved: docs/feature/{feature-id}/
- [ ] Session artifacts removed without deleting wave artifacts
- [ ] Architecture docs updated to "IMPLEMENTED" status
- [ ] Committed and pushed

## Permanent Directory Structure

```
docs/
  adrs/                  # ADR-NNN-{slug}.md (flat, cross-feature)
  architecture/          # Design docs by feature
    {feature}/
      architecture-design.md
      component-boundaries.md
      data-models.md
      technology-stack.md
  decisions/             # Product decisions by feature (optional)
    {feature}/
  evolution/             # Post-mortem summaries
    YYYY-MM-DD-{feature-id}.md
  research/              # Research docs (flat, cross-feature)
  scenarios/             # Acceptance test documentation by feature
    {feature}/
      walking-skeleton.md
  ux/                    # UX specs and journeys by feature
    {feature}/
      journey-*.yaml
      journey-*-visual.md
```

## Error Handling

| Error | Response |
|-------|----------|
| Invalid agent name | "Invalid agent. Available: nw-researcher, nw-software-crafter, nw-solution-architect, nw-product-owner, nw-acceptance-designer, nw-platform-architect" |
| Missing feature ID | "Usage: /nw-finalize @agent 'feature-id'" |
| Project directory not found | "Project not found: docs/feature/{feature-id}/" |
| Incomplete or contradictory evidence | Block finalization and list the exact missing or stale outcome evidence |
| No files to migrate | Log "No lasting artifacts found — skipping Phase B" and proceed to cleanup |

## Examples

### Example 1: Standard finalization
```
/nw-finalize @nw-platform-architect "auth-upgrade"
```
Reconciles completion evidence. Creates the evolution document. Migrates `design/architecture-design.md` → `docs/architecture/auth-upgrade/`, ADRs → `docs/adrs/`, and walking-skeleton material → `docs/scenarios/auth-upgrade/`. Shows session artifacts, obtains approval, removes only those artifacts, preserves the feature workspace, and commits.

### Example 2: Blocked by incomplete steps
```
/nw-finalize @nw-platform-architect "data-pipeline"
```
Pre-dispatch validation finds a declared slice without current EXAMINE evidence. It returns the exact slice and missing evidence and does not finalize.

## Next Wave

**Handoff To**: Feature complete - no next wave
**Deliverables**: docs/evolution/YYYY-MM-DD-{feature-id}.md, migrated artifacts, preserved feature workspace, cleaned session artifacts

## Expected Outputs

```
docs/evolution/YYYY-MM-DD-{feature-id}.md
docs/architecture/{feature}/ (migrated design docs)
docs/adrs/ADR-*.md (migrated ADRs)
docs/scenarios/{feature}/ (migrated test scenarios)
docs/ux/{feature}/ (migrated UX journeys, if any)
Preserved: docs/feature/{feature-id}/
Removed: session artifacts explicitly approved by the user
```
