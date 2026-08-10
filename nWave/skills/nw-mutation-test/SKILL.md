---
name: nw-mutation-test
description: "Runs feature-scoped mutation testing to validate test suite quality. Use after implementation to verify tests catch real bugs (kill rate >= 80%)."
user-invocable: true
argument-hint: '[feature-id] - Optional: --threshold=[75|80|85] --language=[auto|python|java|javascript]'
---

# NW-MUTATION-TEST: Feature-Scoped Mutation Testing

**Wave**: QUALITY_GATE
**Agent**: Crafter (nw-software-crafter)

## Overview


## Mutation Testing Strategy

Projects declare a strategy via `## Mutation Testing Strategy` in `CLAUDE.md`: `per-feature` | `nightly-delta` | `pre-release` | `disabled`.

**Default (when unspecified): `disabled`** — fail-safe; no mutation gate runs unless a project opts in. A project may declare `nightly-delta` in its own `CLAUDE.md` to run mutmut nightly in CI against modules changed since the last run (the delta); that CI run is project-level, not a per-feature DELIVER gate. `/nw-mutation-test` remains usable as an explicit, on-demand feature-scoped run regardless of strategy.

### Target extraction by `workflow.mode` <!-- mode-ref-ok -->

How implementation files are selected depends on `workflow.mode` — per-mode audit substrate projected from the mode registry: <!-- mode-ref-ok -->

<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice AT-first loop; AT-completion ledger + commit trailers are the authority.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
<!-- GENERATED:mode-descriptor END -->

- **atdd_pure mode** — scope mutants by the slice's `at_ids` read from the **AT-completion ledger**: each ledger slice records the `at_ids` it satisfied and the implementation files those ATs drove, and only those files are mutated for the slice. <!-- mode-ref-ok -->

## Context Files Required

- `scripts/mutation/generate_scoped_configs.py` - Automated config generation (if available)

## Pre-Invocation

Orchestrator performs before delegating:

2. **Verify on disk** — Check all extracted files exist on disk. Gate: zero missing files.
3. **Detect language** — Scan config files (pyproject.toml, pom.xml, package.json, etc.) to select tool. Gate: language identified.
4. **Confirm tests pass** — Run `pytest -x {test_scope}` (or equivalent). Gate: exit code 0, no failures.
5. **Ensure mutation venv** — For Python, verify `.venv-mutation/` exists with cosmic-ray installed. Gate: `cosmic-ray --version` succeeds.

## Agent Invocation

@nw-software-crafter

Execute mutation testing for project {feature-id}.

**Context to pass inline (agent has no Skill access):**
- Project ID
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

### Example 2: Python project without config generator
```bash
/nw-mutation-test auth-upgrade tests/auth/
```

### Example 3: Non-Python project
```bash
/nw-mutation-test payment-gateway tests/payment/
```
Detects `package.json`, selects Stryker, delegates with Stryker-specific instructions.

## Success Criteria

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

1. **Snapshot before** — Record `git status` of the user's working worktree before creating the disposable target. Gate: snapshot captured.
2. **Run in isolation** — Execute mutation tooling only inside the disposable worktree/copy. Gate: user's working worktree untouched during the run.
3. **Snapshot after and compare** — Record `git status` of the user's working worktree again. Gate: identical to the pre-run snapshot; fail loud if it differs.
4. **Discard only the disposable target** — Remove the dedicated worktree/copy the agent owns. Gate: user's working worktree was never a deletion/restoration target.

## Quality Gate

Kill rate thresholds:

1. **>= 80% PASS** — Proceed to next wave.
2. **70-80% WARN** — Review surviving mutants, document findings, proceed with caution.
3. **< 70% FAIL** — Add tests targeting surviving mutants before proceeding.

Skip conditions (each requires documented justification in mutation-report.md):

1. **No tool for language** — No mutation framework available for detected language.
2. **Project opt-out** — `.mutation-config.yaml` has `skip: true` with justification.
3. **Broken test suite** — Pre-invocation step 4 fails; fix tests before mutation testing.

Note: Mutation testing is disabled by default for every project. All skips need documented justification.

## Next Wave

This command is invoked standalone, on explicit invocation — it is not a numbered step in any develop.md workflow phase.
**Deliverables**: `docs/feature/{feature-id}/deliver/mutation/mutation-report.md`

## Expected Outputs

```
docs/feature/{feature-id}/deliver/mutation/
  mutation-report.md
  cosmic-ray-*.toml                (ephemeral)
```
