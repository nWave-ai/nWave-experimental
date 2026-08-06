---
description: "Detects current wave progress for a feature and resumes at the next step. Scans docs/feature/ for artifacts."
argument-hint: "[feature-id] - Optional: omit to auto-detect from docs/feature/"
disable-model-invocation: true
---

# NW-CONTINUE: Resume a Feature

**Wave**: CROSS_WAVE (entry point) | **Agent**: Main Instance (self — wizard) | **Command**: `/nw-continue`

## Overview

Scans `docs/feature/` for active projects, detects wave artifacts, displays progress summary, launches next wave command. Eliminates manual artifact inspection when returning after hours/days.

You (main Claude instance) run this wizard directly. No subagent delegation.

## Behavior Flow

### Step 1: Scan for Projects

If project ID provided as argument, use it directly.

Otherwise scan `docs/feature/` for project directories:
```bash
ls -d docs/feature/*/
```

**No directories found:** Display "No active projects found under `docs/feature/`." Suggest `/nw-new`. Stop.

### Step 2: Project Selection (Multiple Projects)

If multiple directories exist, list by most recent file modification:
```bash
find docs/feature/{feature-id}/ -type f -printf '%T@ %p\n' | sort -rn | head -1
```

Present via AskUserQuestion: project name|last modified date|most recent first. Ask user to select.

### Step 3: Wave Progress Detection

Check each wave's artifacts using Wave Detection Rules in `~/.claude/skills/nw-wizard-shared-rules/SKILL.md`.

### Step 4: Anomaly Detection

Check before showing progress:

**Empty/corrupted artifacts:** Verify file size > 0 for each "complete" artifact. If empty, flag: "Warning: `user-stories.md` exists but is empty (0 bytes). Recommend re-running DISCUSS wave."

**Non-adjacent waves (skipped):** If artifacts exist for non-consecutive waves (e.g., DISCUSS + DELIVER but no DESIGN/DISTILL), warn with options:
1. Fill the gap — start from missing wave
2. Continue as-is
3. Show all artifacts for manual review

### Step 5: DELIVER Progress Detail

DELIVER progress detection branches on `workflow.mode` (read from `.nwave/config.yaml`). <!-- mode-ref-ok -->
Per-mode descriptor + DELIVER phase shape, projected from the mode registry:

<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice AT-first loop; AT-completion ledger + commit trailers are the authority.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
<!-- GENERATED:mode-descriptor END -->

- Read the feature-delta Slice Plan, AT-completion ledger, and commit trailers for current delivery evidence.
- Display the first un-shipped slice or the feature-end outcome.

**`atdd_pure` mode** — resume is driven by the AT-completion ledger using the **two-case cue** (ADR-028 D6). Read the slice plan and the ledger, then pick the case: <!-- mode-ref-ok -->

1. **Case (i): slices still `pending`.** Some slices are not yet `shipped`. Restart the `/nw-execute` per-slice lean cycle at the first **un-shipped slice** — the first slice plan row whose Status is not `shipped`.
2. **Case (ii): all slices `shipped`, feature-end cycle unfinished.** The Status column gives no signal once every row is `shipped`. There is no per-step ledger checkpoint (a `FeatureEndCheckpoint` record was named in ADR-028 D6 but never implemented — zero producers in `src/des`); instead, re-run `des feature-end run` (idempotent, safe to repeat) and read its own exit code / stdout payload (`FeatureEndCycleComplete` / `FeatureEndCycleRefused` / `FeatureEndCycleIndeterminate`) to learn the current outcome.

Display under `atdd_pure`: "DELIVER (atdd_pure) in progress: 3/5 slices shipped. Next: re-enter /nw-execute at the first un-shipped slice" or "DELIVER (atdd_pure): all slices shipped. Re-running the feature-end cycle to determine its outcome." <!-- mode-ref-ok -->

### Step 6: Progress Display

```
Feature: {feature-id}

  DISCOVER   ○ not started
  DISCUSS    ● complete
  DESIGN     ● complete
  DISTILL    ◐ in progress
  DELIVER    ○ not started

  Next: DISTILL — Create acceptance tests
```

Symbols: ● complete | ◐ in progress | ○ not started

### Step 7: Recommendation and Launch

Recommend next wave: resume in-progress wave|successor of last complete wave. Show via AskUserQuestion for confirmation. After confirmation, invoke recommended wave command by reading its task file, passing project ID as argument.

## Error Handling

| Error | Response |
|-------|----------|
| No `docs/feature/` directory | Suggest `/nw-new` |
| Empty project directory | Suggest `/nw-new` or re-run from DISCUSS |
| Corrupted artifact (0 bytes) | Flag file, recommend re-running that wave |
| Skipped waves | Warn, offer gap-fill or continue options |

## Progress Tracking

The invoked agent MUST create a task list from its workflow phases at the start of execution using TaskCreate. Each phase becomes a task with the gate condition as completion criterion. Mark tasks in_progress when starting each phase and completed when the gate passes. This gives the user real-time visibility into progress.

## Success Criteria

- [ ] Projects scanned from `docs/feature/`
- [ ] Project selected (auto or user choice)
- [ ] Wave progress detected accurately from artifact presence
- [ ] Anomalies flagged (empty files, skipped waves)
- [ ] DELIVER step-level progress shown when applicable
- [ ] Progress summary displayed
- [ ] Next wave recommended and launched after user confirmation

## Examples

### Example 1: Single project, resume at DESIGN
```
/nw-continue
```
Wizard finds one project: `notification-service`. DISCUSS artifacts exist (complete), no DESIGN artifacts. Shows progress, recommends DESIGN. User confirms, wizard launches `/nw-design notification-service`.

### Example 2: DELIVER resume
```
/nw-continue rate-limiting
```
Wizard checks `rate-limiting` project. All waves through DISTILL complete, DELIVER in progress (steps 01-01 through 02-01 done). Shows "Next: step 02-02", launches `/nw-deliver "rate-limiting"`.

### Example 3: Multiple projects
```
/nw-continue
```
Wizard finds `rate-limiting` (modified today) and `user-notifications` (modified 3 days ago). Lists them, user picks `rate-limiting`. Wizard shows progress and recommends next wave.

### Example 4: No projects
```
/nw-continue
```
Wizard finds no `docs/feature/` directories. Shows "No active projects found" and suggests `/nw-new`.
