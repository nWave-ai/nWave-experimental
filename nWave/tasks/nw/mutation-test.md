---
description: Runs feature-scoped mutation testing (kill rate >= 80%) on explicit invocation. Unspecified project default is disabled; a project may declare its own strategy in CLAUDE.md.
argument-hint: "[feature-id] - Optional: --threshold=[75|80|85] --language=[auto|python|java|javascript]"
---

# NW-MUTATION-TEST: Feature-Scoped Mutation Testing

> **Not a default step.** Unspecified project default is `disabled` — mutation is never run as part of
> per-feature DELIVER. This command remains available for an **explicit, on-demand** run regardless of a
> project's declared strategy; green ATs + EXAMINE are the methodology's default correctness truth.

**Wave**: QUALITY_GATE
**Agent**: Crafter (nw-software-crafter)

## Overview

Run mutation testing against implementation files from the current feature. Derives
targets from the selected Slice Plan and changed production paths, generates
feature-scoped configs, and delegates to software-crafter. Uses cosmic-ray
(Python), PIT (Java), or Stryker (JS/TS/C#).

## Mutation Testing Strategy

Projects declare a strategy via `## Mutation Testing Strategy` in `CLAUDE.md`: `per-feature` | `nightly-delta` | `pre-release` | `disabled`. **Default (when unspecified): `disabled`** — mutation is NOT a default step. A project that declares `nightly-delta` runs mutmut nightly in CI against changed modules; that CI run is project-level, not a per-feature DELIVER gate. `/nw-mutation-test` runs on-demand independent of strategy.

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
- [ ] Mutation testing executed only inside a dedicated disposable worktree/copy, never in the user's working worktree
- [ ] Per-file breakdown in mutation-report.md
- [ ] Kill rate meets threshold (>= 80% PASS, 70-80% WARN, < 70% FAIL)
- [ ] User's working worktree verified unchanged after the mutation run (status snapshot matches pre-run snapshot)

## Post-Mutation Safety (mandatory)

Mutation tools apply mutations directly to source files. Agent MUST run mutation tooling only against a
dedicated disposable worktree or copy — never against the user's working worktree. `git checkout`,
`git reset`, or any equivalent restoration command against the user's worktree is FORBIDDEN: the user's
worktree is never mutated in the first place, so there is nothing in it to restore, and running these
commands risks discarding the user's own uncommitted work.

After EVERY mutation run (success, failure, or interruption):

1. Snapshot `git status` of the user's working worktree before creating the disposable target.
2. Run mutation tooling only inside the disposable worktree/copy.
3. Snapshot `git status` of the user's working worktree again; fail loud if it differs from the pre-run snapshot.
4. Discard only the disposable target the agent owns.

## Quality Gate

Kill rate thresholds: >= 80% PASS (proceed)|70-80% WARN (review surviving mutants)|< 70% FAIL (add tests first).

Skip conditions: no mutation tool for language|project opts out via `.mutation-config.yaml`|test suite broken. Mutation testing is SKIPPED BY DEFAULT for every project unless the project's `CLAUDE.md` declares a strategy other than `disabled`; it is never a required per-feature gate.

## Next Wave

This command is invoked standalone, on explicit invocation — it is not a numbered step in `nWave/tasks/nw/deliver.md`'s DELIVER phase sequence.
**Deliverables**: `docs/feature/{feature-id}/deliver/mutation/mutation-report.md`

## Expected Outputs

```
docs/feature/{feature-id}/deliver/mutation/
  mutation-report.md
  cosmic-ray-*.toml                (ephemeral)
```
