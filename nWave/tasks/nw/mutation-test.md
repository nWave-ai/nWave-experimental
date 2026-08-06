---
description: "DEPRECATED (FR-1, opt-in only, not a default step). Runs feature-scoped mutation testing (kill rate >= 80%) when a project explicitly opts in; green ATs + EXAMINE are the methodology truth."
argument-hint: "[feature-id] - Optional: --threshold=[75|80|85] --language=[auto|python|java|javascript]"
---

# NW-MUTATION-TEST: Feature-Scoped Mutation Testing

> **DEPRECATED (FR-1, 2026-07-04).** Mutation testing is a slow post-green ceremony REMOVED from the
> velocity-v2 methodology — green ATs + EXAMINE (independent end-to-end verification by Vera) are the
> truth; a coverage-after-green / mutation pass adds cost, not signal. `.nwave/des-config.json` keeps
> `mutation_enabled=false`; this command remains available for an **explicit, opt-in** run only. It is
> **NOT** part of any per-feature or nightly gate — do not run it as a default step. The strategy prose
> below is retained for that opt-in use, not as a recommended default.

**Wave**: QUALITY_GATE
**Agent**: Crafter (nw-software-crafter)

## Overview

Run mutation testing against implementation files from the current feature. Derives
targets from the selected Slice Plan and changed production paths, generates
feature-scoped configs, and delegates to software-crafter. Uses cosmic-ray
(Python), PIT (Java), or Stryker (JS/TS/C#).

## Mutation Testing Strategy

Projects declare a strategy via `## Mutation Testing Strategy` in `CLAUDE.md`: `per-feature` | `nightly-delta` | `pre-release` | `disabled`. Per FR-1 the methodology default is **`disabled`** (`mutation_enabled=false`) — mutation is NOT a default step. When a project explicitly opts in, `/nw-mutation-test` runs on-demand independent of strategy.

## Context Files Required

- `docs/feature/{feature-id}/feature-delta.md` - Selected Slice Plan and declared production targets
- `scripts/mutation/generate_scoped_configs.py` - Automated config generation (if available)

## Pre-Invocation

Orchestrator performs before delegating:

1. Read the selected Slice Plan and collect its declared production targets
2. Add changed production paths relevant to the selected slice
3. Verify all collected files exist on disk
4. Detect project language from config files (pyproject.toml, pom.xml, package.json, etc.)
5. Confirm test suite passes: run `pytest -x {test_scope}` (or equivalent)
6. Ensure mutation venv exists for Python: `.venv-mutation/` with cosmic-ray installed

## Agent Invocation

@nw-software-crafter

Execute mutation testing for project {feature-id}.

**Context to pass inline (agent has no Skill access):**
- Project ID
- Implementation file list (from the selected Slice Plan and changed production paths)
- Test scope path (e.g., `tests/des/`)
- Kill rate threshold (default: 80%)
- Language and tool selection

**Configuration:**
- threshold: 80 (percentage, minimum kill rate)
- approach: feature-scoped (one config per component, scoped test commands)
- config_generator: `scripts/mutation/generate_scoped_configs.py` (preferred over manual)

**Output file:** `docs/feature/{feature-id}/deliver/mutation/mutation-report.md`

## Examples

### Example 1: Python project with config generator
```bash
/nw-mutation-test des-hook-enforcement tests/des/
```
Reads the selected Slice Plan, runs `generate_scoped_configs.py des-hook-enforcement`, delegates to software-crafter with per-component configs. Agent runs cosmic-ray, produces mutation-report.md.

### Example 2: Python project without config generator
```bash
/nw-mutation-test auth-upgrade tests/auth/
```
Collects targets from the selected Slice Plan and changed production paths, creates a single cosmic-ray config with `module-path = [file1, file2, ...]` and `test-command = "pytest -x tests/auth/"`, then delegates to an agent.

### Example 3: Non-Python project
```bash
/nw-mutation-test payment-gateway tests/payment/
```
Detects `package.json`, selects Stryker, delegates with Stryker-specific instructions.

## Progress Tracking

The invoked agent MUST create a task list from its workflow phases at the start of execution using TaskCreate. Each phase becomes a task with the gate condition as completion criterion. Mark tasks in_progress when starting each phase and completed when the gate passes. This gives the user real-time visibility into progress.

## Success Criteria

- [ ] Implementation files derived from the selected Slice Plan and changed production paths
- [ ] All implementation files verified on disk
- [ ] Mutation testing executed without errors
- [ ] Per-file breakdown in mutation-report.md
- [ ] Kill rate meets threshold (>= 80% PASS, 70-80% WARN, < 70% FAIL)
- [ ] Source files restored to HEAD after mutation run (git checkout -- src/ tests/)

## Post-Mutation Safety (mandatory)

After EVERY mutation run (success, failure, or interruption), restore source files:

    git checkout -- src/ tests/

Mutation tools apply mutations directly to source files. An interrupted run can leave corrupted code (e.g. `is not None` -> `is  None`). Agent MUST restore source files even if the run errors out.

## Quality Gate

Kill rate thresholds: >= 80% PASS (proceed)|70-80% WARN (review surviving mutants)|< 70% FAIL (add tests first).

Skip conditions: no mutation tool for language|project opts out via `.mutation-config.yaml`|test suite broken. Per FR-1, mutation testing is SKIPPED BY DEFAULT for every project; it runs only on explicit opt-in (`rigor.mutation_enabled = true`), never as a required gate.

## Next Wave

This command is invoked standalone, on explicit opt-in — never as a numbered step in `nWave/tasks/nw/deliver.md`'s own DELIVER phase sequence (its Phase 5 is mutation testing, skip-if-disabled; Phase 7 is Finalize). There is no `develop.md` workflow in this repo to hand off to.
**Deliverables**: `docs/feature/{feature-id}/deliver/mutation/mutation-report.md`

## Expected Outputs

```
docs/feature/{feature-id}/deliver/mutation/
  mutation-report.md
  cosmic-ray-*.toml                (ephemeral)
```
