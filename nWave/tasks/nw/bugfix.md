---
description: "Bug fix workflow: root cause analysis → user review → regression test + fix via TDD"
argument-hint: "[bug-description] - Describe the defect observed"
---


# NW-BUGFIX: Defect Resolution Workflow

**Wave**: CROSS_WAVE
**Agents**: Rex (nw-troubleshooter) → nw-acceptance-designer (regression test author) → selected crafter (OOP or FP per project paradigm, fix implementor only)

## Overview

End-to-end bug fix pipeline: diagnose root cause, review findings with user, then deliver regression tests that fail with the bug and pass with the fix. Ensures every defect produces a test that prevents recurrence.

**Test/fix authorship split (SLIM-crafter discipline)**: the crafter NEVER authors tests, in `/nw-bugfix` same as everywhere else in nWave. `nw-acceptance-designer` authors the regression test (Phase 3a). The paradigm-selected crafter (OOP or FP) implements the fix only (Phase 3b), against the already-authored, already-RED test.

## Flow

```
INPUT: "{bug-description}"
  │
  ├─ Phase 1: Root Cause Analysis (@nw-troubleshooter)
  │   └─ /nw-root-why "{bug-description}"
  │   └─ Output: RCA document with root cause chain + fix proposal
  │
  ├─ Phase 2: User Review (INTERACTIVE — STOP here)
  │   └─ Present RCA findings to user
  │   └─ User confirms root cause + approves fix direction
  │   └─ If user rejects → refine RCA or stop
  │
  ├─ Phase 3a: Regression Test (@nw-acceptance-designer, RED)
  │   └─ Author the regression test from the RCA's root cause + proposed fix
  │   └─ Test MUST fail against current code for the diagnosed reason (not import/syntax error)
  │
  ├─ Phase 3b: Fix (branches on workflow.mode, paradigm-selected crafter, GREEN) <!-- mode-ref-ok -->
  │   └─ atdd_pure → single carpaccio slice via the /nw-execute per-slice cycle, A_GREEN <!-- mode-ref-ok -->
  │   └─ Paradigm detection determines crafter (OOP or FP)
  │   └─ Crafter implements against the already-RED test only — never authors or edits the test
  │
  └─ Phase 3c: EXAMINE (@nw-user-examiner "Vera") — BEFORE the commit
      └─ A FRESH @nw-product-owner dispatch authors a light expectation charter from the
         bug's observable only (never the RCA/fix diff) → Vera runs the FIXED product
      └─ `des record-examine-verdict` PASS BEFORE COMMIT (the commit gate arms on the charter)
      └─ A_GREEN → EXAMINE → COMMIT — examine is the DoD, never skipped for a bugfix
```

## Execution Steps

### Phase 1: Root Cause Analysis

**Skill loading**: The troubleshooter loads its skills from `~/.claude/skills/nw-{skill}/SKILL.md`:
- `nw-five-whys-methodology` — core investigation methodology
- `nw-investigation-techniques` — systematic debugging patterns
- `nw-post-mortem-framework` — structured incident analysis

Invoke @nw-troubleshooter via Agent tool:

```
Execute *investigate-root-cause for the following defect:

{bug-description}

Configuration:
- investigation_depth: 5
- multi_causal: true
- evidence_required: true

Produce:
1. Root cause chain (5 Whys with evidence at each level)
2. Contributing factors
3. Proposed fix with specific code changes
4. Files affected
5. Risk assessment of the fix
```

After the troubleshooter returns, present findings to the user. Include:
- Root cause summary (1-2 sentences)
- Evidence chain
- Proposed fix
- Files to modify
- Risk level

**STOP and wait for user confirmation before proceeding to Phase 3a.**

### Phase 2: User Review

Present the RCA findings and ask:
1. "Does this root cause match your understanding?"
2. "Do you approve the proposed fix direction?"
3. "Any additional constraints or context?"

If user rejects:
- Refine the RCA with additional context
- Or stop the workflow entirely

If user approves → proceed to Phase 3a.

### Phase 3a: Regression Test (@nw-acceptance-designer)

Invoke @nw-acceptance-designer via Agent tool to author the regression test from the RCA's
root cause chain and proposed fix (Phase 1 output) — the crafter dispatched in Phase 3b does
NOT write or edit this test, only implements against it. Test location + naming follow the
mode-appropriate convention (retired workflow: `tests/regression/{component}/` or `tests/bugs/`,
`test_bug_{description}.py`; atdd_pure: the bugfix's single-slice `.feature` + step file <!-- mode-ref-ok -->
under `tests/{feature-path}/`). The test MUST fail against current code for the diagnosed
reason (a real assertion on the defect's observable behavior, never an import/collection
error) — confirm this before proceeding to Phase 3b.

### Phase 3b: Fix (branches on workflow.mode, paradigm-selected crafter) <!-- mode-ref-ok -->

Phase 3b reads `workflow.mode` from `.nwave/config.yaml` and dispatches the fix along one <!-- mode-ref-ok -->
of two paths, against the already-authored, already-RED regression test from Phase 3a.
Per-mode descriptor + DELIVER phase shape, projected from the mode registry (never
hand-written here):

<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice carpaccio loop; no roadmap.json / execution-log.json; AT-completion ledger + commit trailers are the audit.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
<!-- GENERATED:mode-descriptor END -->

Both paths share paradigm detection (reads project CLAUDE.md for `## Development
Paradigm`), crafter selection (@nw-software-crafter for OOP, @nw-functional-software-crafter
for FP), DES enforcement, and the rigor profile from `.nwave/des-config.json`. Neither
path's crafter authors or edits the regression test — it was authored in Phase 3a by
@nw-acceptance-designer.

**Preparation (both modes):**

1. Derive feature-id: `fix-{kebab-case-bug-summary}` (max 5 words)
2. Create `docs/feature/{feature-id}/deliver/` directory
3. Prepare RCA context from Phase 1 output (root cause, files affected, proposed fix)
4. Confirm Phase 3a's regression test exists and is RED for the right reason before dispatching the crafter



```
/nw-deliver "fix-{bug-summary}"
```

The deliver orchestrator builds a minimal one-step roadmap (the regression test already
exists from Phase 3a):

**Step 01-01: Fix implementation (GREEN)**
- Implement the minimal fix identified in RCA against the Phase 3a regression test
- Run ALL tests — regression test must now PASS
- Existing tests must not regress
- The crafter does NOT write, edit, or weaken the regression test — if it seems wrong or
  insufficient, escalate back to @nw-acceptance-designer, do not touch it directly

#### Mode `atdd_pure` — single carpaccio slice, no roadmap <!-- mode-ref-ok -->

Under `workflow.mode: atdd_pure` the bugfix is the canonical single carpaccio slice: there <!-- mode-ref-ok -->
is no roadmap and no roadmap-step extraction. The defect's regression test (authored in
Phase 3a) IS the slice's acceptance test. Run the fix through the slice-04 roadmap-free
spine via the per-slice `/nw-execute` lean cycle, starting at `A_GREEN` (the AT already
exists — same SLIM-crafter contract as any other atdd_pure slice, no carve-out): <!-- mode-ref-ok -->

```
/nw-execute "fix-{bug-summary}"
```

The per-slice cycle drives the `A_GREEN → EXAMINE → COMMIT` shape against the
already-authored, already-RED regression AT. EXAMINE (Phase 3c, @nw-user-examiner) is
part of this cycle — it is the DoD, never skipped.

The crafter handles the TDD cycle (3-phase canon RED → GREEN → COMMIT per ADR-025, or
legacy 5-phase PREPARE → RED_ACCEPTANCE → RED_UNIT → GREEN → COMMIT for pre-2026-05-07
audit-log replay) with DES monitoring in either mode — RED here means activating/running
the already-authored test, never authoring it.

## Progress Tracking

The invoked agent MUST create a task list from its workflow phases at the start of execution using TaskCreate. Each phase becomes a task with the gate condition as completion criterion. Mark tasks in_progress when starting each phase and completed when the gate passes. This gives the user real-time visibility into progress.

## Success Criteria

- [ ] Root cause identified with evidence at each causal level
- [ ] User reviewed and approved fix direction
- [ ] Regression test authored by @nw-acceptance-designer, fails with the bug
- [ ] Fix implemented by the paradigm-selected crafter that makes the regression test pass, without the crafter touching the test itself
- [ ] All existing tests still pass (no regressions)
- [ ] EXAMINE (Phase 3c): light charter authored by a FRESH `nw-product-owner` dispatch (never inline) + @nw-user-examiner (Vera) PASS recorded via `des record-examine-verdict` BEFORE the commit — examine is the DoD, never skipped
- [ ] Commit with conventional message: `fix(scope): description`

## Examples

### Example 1: Runtime crash
```
/nw-bugfix "DES hook crashes with FileNotFoundError when template schema is missing"
```
Phase 1: Rex traces to missing `step-tdd-cycle-schema.json` in plugin cache.
Phase 2: User confirms.
Phase 3a: @nw-acceptance-designer writes `test_bug_missing_template_schema.py` (RED).
Phase 3b: `/nw-deliver "fix-missing-template-schema"` → crafter adds fallback path resolution (GREEN), commits.

### Example 2: Silent failure
```
/nw-bugfix "Skills plugin reports success but installs zero files when source has nw-prefixed layout"
```
Phase 1: Rex traces to `is_public_skill()` returning False for all nw-prefixed names due to ownership map key mismatch.
Phase 2: User confirms.
Phase 3a: @nw-acceptance-designer writes a regression test with an nw-prefixed fixture (RED).
Phase 3b: `/nw-deliver "fix-ownership-map-keys"` → crafter fixes the ownership map keys (GREEN), commits.

### Example 3: Functional project bug
```
/nw-bugfix "Pipeline composition breaks when filter predicate returns None"
```
Phase 1: Rex traces to missing None guard in compose() function.
Phase 2: User confirms.
Phase 3a: @nw-acceptance-designer writes a property-based test covering the None-predicate case (RED).
Phase 3b: `/nw-deliver "fix-compose-none-guard"` → paradigm detected as FP → @nw-functional-software-crafter adds the None guard (GREEN), commits.

## Notes

- This command is for **known defects** (something is broken). For new features, use `/nw-deliver`.
- The regression test is the primary deliverable — it prevents the bug from recurring. It is authored by @nw-acceptance-designer (Phase 3a), never by the crafter — the SLIM-crafter no-test-authorship discipline applies to `/nw-bugfix` exactly as it does everywhere else in nWave.
- Keep the fix minimal. Refactoring belongs in `/nw-refactor`, not here.
- If the RCA reveals a design flaw (not just a code bug), escalate to `/nw-design` before fixing.
