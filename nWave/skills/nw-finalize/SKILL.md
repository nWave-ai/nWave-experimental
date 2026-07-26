---
name: nw-finalize
description: "Archives a completed feature to docs/evolution/, migrates lasting artifacts to permanent directories, and cleans up the temporary workspace. Use after all implementation steps pass."
user-invocable: false
argument-hint: '[agent] [feature-id] - Example: @platform-architect "auth-upgrade"'
---

# NW-FINALIZE: Feature Completion and Archive

**Wave**: CROSS_WAVE
**Agent**: @nw-platform-architect (default) or specified agent

## Overview

Finalize a completed feature: verify all steps done|create evolution document|migrate lasting artifacts to permanent directories|clean up temporary workspace. Agent gathers project data|analyzes execution history|writes summaries|migrates|cleans up.

`docs/feature/{feature-id}/` is a **temporary workspace** — it exists during active nWave waves (DISCUSS through DELIVER). At finalize, artifacts with lasting value migrate to permanent directories; the rest is discarded.

## Usage

```
/nw-finalize @{agent} "{feature-id}"
```

## Context Files Required

The completion-evidence files depend on `workflow.mode` — per-mode descriptor + audit substrate projected from the mode registry: <!-- mode-ref-ok -->

<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice carpaccio loop; no roadmap.json / execution-log.json; AT-completion ledger + commit trailers are the audit.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
<!-- GENERATED:mode-descriptor END -->

- **atdd_pure mode** — the AT-completion ledger: it records each slice's `at_ids`, their pass transitions, and the phase-boundary timestamps. <!-- mode-ref-ok -->

## Pre-Dispatch Gate: All Work Complete

Before dispatching, verify all work is done — prevents archiving incomplete features. The completeness signal is `workflow.mode`-specific. <!-- mode-ref-ok -->


2. **Verify completeness** — Check every step has status `DONE`. Gate: all steps DONE.
3. **Block or proceed** — If any step is not DONE, list incomplete steps with current status and halt. If all DONE, proceed to dispatch. Gate: zero incomplete steps before dispatch.

### atdd_pure mode <!-- mode-ref-ok -->

Completion is read from the **AT-completion ledger**: every slice in the slice plan must show all its `at_ids` GREEN, and the Phase 6 verification — ledger + slice plan + commit-trailer chain (ADR-028 D4.3) — must reconcile. Gate: ledger shows every slice-plan slice complete, trailer chain unbroken.

## Phases

### Phase A — Evolution Document

2. **Extract key decisions** — Pull decisions, issues, and lessons from wave-decisions files. Gate: decisions list assembled.

### Phase B — Migrate Lasting Artifacts

1. **Scan workspace** — List all files under `docs/feature/{feature-id}/`. Gate: file list produced.
2. **Match against destination map** — For each file, apply the destination map below. Gate: migration plan assembled.
3. **Create destination directories** — Create any missing permanent directories. Gate: directories exist.
4. **Copy files** — Copy each matched file to its permanent destination. Gate: all copies verified.
5. **Log skipped files** — Note any files from the discard list (not migrated). Gate: discard list documented.

#### Destination Map

| Source (temporary workspace) | Destination (permanent) | Condition |
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

#### What NOT to Migrate (Discard)

These are process scaffolding — valuable during delivery, disposable after:

| File pattern | Why discard |
|---|---|
| `deliver/.develop-progress.json` | Resume state — temporary |
| `design/review-*.md` | Review findings captured in evolution doc |
| `discuss/dor-checklist.md` | Process gate, not lasting value |
| `discuss/shared-artifacts-registry.md` | Process scaffolding |
| `discuss/prioritization.md` | Superseded by roadmap execution |
| `*/wave-decisions.md` | Key decisions extracted into evolution doc |

### Phase C — Cleanup Workspace

1. **List remaining files** — List all files still in `docs/feature/{feature-id}/` after migration. Gate: list produced.
2. **Present for approval** — Show the exact list to the user and request approval. Gate: user explicitly approves.
3. **Preserve workspace** — `docs/feature/{feature-id}/` is NOT deleted. The wave matrix derives status from this directory. Removing it would make finalized features disappear from the matrix. The evolution doc in `docs/evolution/` is the summary; the feature directory is the history. Gate: directory preserved, session markers removed.
4. **Clean session artifacts only** — Remove `.nwave/des/deliver-session.json`, `.develop-progress.json`, and any temp files. Do NOT remove wave artifacts (discuss/, design/, distill/, deliver/). Gate: session markers removed, wave artifacts intact.

**NEVER delete without user approval.** Show exactly what will be removed.

### Phase D — Post-Cleanup Verification

1. **Verify migrated files** — Confirm every file copied in Phase B exists at its destination. Gate: all destinations present.
2. **Update architecture doc statuses** — Change any "FUTURE DESIGN" labels to "IMPLEMENTED" in migrated architecture docs. Gate: no stale FUTURE DESIGN labels.
3. **Optionally generate reference docs** — Invoke /nw-document unless `--skip-docs` flag provided. Gate: docs generated or skipped.
4. **Commit evolution doc and artifacts** — Commit 1: evolution doc + migrated artifacts. Gate: commit created.
5. **Commit workspace cleanup** — Commit 2: workspace removal. Gate: commit created and pushed.

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

- [ ] All steps verified DONE before dispatch
- [ ] Evolution document created in docs/evolution/
- [ ] Architecture docs migrated to docs/architecture/{feature}/
- [ ] ADRs migrated to docs/adrs/ (if any)
- [ ] Scenario docs migrated to docs/scenarios/{feature}/ (if any)
- [ ] UX journeys migrated to docs/ux/{feature}/ (if any)
- [ ] User approved cleanup before workspace removal
- [ ] Workspace directory removed: docs/feature/{feature-id}/
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
| Incomplete steps | Block finalization, list incomplete steps |
| No files to migrate | Log "No lasting artifacts found — skipping Phase B" and proceed to cleanup |

## Examples

### Example 1: Standard finalization
```
/nw-finalize @nw-platform-architect "auth-upgrade"
```
Verifies all steps done. Creates evolution doc. Migrates `design/architecture-design.md` → `docs/architecture/auth-upgrade/`, ADRs → `docs/adrs/`, test-scenarios → `docs/scenarios/auth-upgrade/`. Shows remaining files, user approves, removes workspace. Commits.

### Example 2: Blocked by incomplete steps
```
/nw-finalize @nw-platform-architect "data-pipeline"
```
Pre-dispatch gate finds step 02-03 status IN_PROGRESS. Returns: "BLOCKED: 1 incomplete step - 02-03: IN_PROGRESS. Complete all steps before finalizing."

## Next Wave

**Handoff To**: Feature complete - no next wave
**Deliverables**: docs/evolution/YYYY-MM-DD-{feature-id}.md, migrated artifacts, cleaned workspace

## Expected Outputs

```
docs/evolution/YYYY-MM-DD-{feature-id}.md
docs/architecture/{feature}/ (migrated design docs)
docs/adrs/ADR-*.md (migrated ADRs)
docs/scenarios/{feature}/ (migrated test scenarios)
docs/ux/{feature}/ (migrated UX journeys, if any)
Removed: docs/feature/{feature-id}/
```
