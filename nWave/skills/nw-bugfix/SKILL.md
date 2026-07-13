---
name: nw-bugfix
description: "Bug fix workflow: root cause analysis → user review → regression test + fix via TDD"
user-invocable: true
argument-hint: '[bug-description] - Describe the defect observed'
---

> **Code facts** — resolve structural facts about code (who-calls / defs-reads / never-wired / call-graph / atoms-in-file) through the `nw-code-analysis-port` skill: Tsunami-first via the `mcp__tsunami__*` tools, declared fallback (AST, then grep), degrade-LOUD. Never ad-hoc grep for a structural fact.

# NW-BUGFIX: Defect Resolution Workflow

**Wave**: CROSS_WAVE
**Agents**: Rex (nw-troubleshooter) → nw-acceptance-designer (regression test author) → selected crafter (OOP or FP per project paradigm, fix implementor only)

## Overview

End-to-end bug fix pipeline: diagnose root cause, review findings with user, then deliver regression tests that fail with the bug and pass with the fix. Ensures every defect produces a test that prevents recurrence.

**Test/fix authorship split (SLIM-crafter discipline)**: the crafter NEVER authors tests, in `/nw-bugfix` same as everywhere else in nWave. `nw-acceptance-designer` authors the regression test (it IS the bugfix's acceptance test — no DISTILL wave runs separately, but AT authorship still belongs to the acceptance-designer, not the crafter). The paradigm-selected crafter (OOP or FP) implements the fix only, against the already-authored, already-RED test — mirroring the SLIM-crafter dispatch contract every other `/nw-execute`/`/nw-deliver` A_GREEN phase already enforces (no carve-out needed).

## Flow

```
INPUT: "{bug-description}"
  │
  ├─ t=0 — TWO INDEPENDENT DERIVATIONS START IN PARALLEL (both from the raw bug, before any code is read):
  │   │
  │   ├─ Phase 1: Root Cause Analysis (@nw-troubleshooter)                 ☁️ cloud
  │   │   └─ /nw-root-why "{bug-description}"   (derives from the CODE)
  │   │   └─ Output: RCA document with root cause chain + fix proposal
  │   │
  │   └─ Phase 0-charter: Expectation Charter (FRESH @nw-product-owner)    ☁️ cloud
  │       └─ Derives from the bug's OBSERVABLE ONLY (what a user sees) + the human's verbatim bug
  │          description — NEVER the RCA chain or the fix diff (that context does not exist yet)
  │       └─ Output: docs/product/expectations/fix-{bug-summary}/{intent}.md
  │       └─ WHY t=0: the charter does NOT depend on the RCA. Authoring it here — before any
  │          contaminated context exists — makes the disqualification rule STRUCTURALLY EASY to obey
  │          instead of a virtue to remember: there is nothing yet to resist. GDP-1 (fire-early) +
  │          GDP-5 (cost on the system, not the operator). Same two-independent-derivations rule DISTILL
  │          already applies (code-side AT vs observable-side charter).
  │
  ├─ Phase 2: User Review (INTERACTIVE — STOP here; non-blocking under an
  │   │        autonomous loop with standing authorization — see Phase 2)
  │   └─ Present RCA findings to user
  │   └─ User confirms root cause + approves fix direction
  │   └─ If user rejects → refine RCA or stop
  │
  ├─ Phase 3a: Regression Test (@nw-acceptance-designer, RED)              🔒 box (RED seal)
  │   └─ Author the regression test from the RCA's root cause + proposed fix
  │   └─ Test MUST fail against current code for the diagnosed reason (not import/syntax error)
  │
  ├─ Phase 3b: Fix (branches on workflow.mode, paradigm-selected crafter, GREEN)  🔒 box <!-- mode-ref-ok -->
  │   └─ classic   → /nw-deliver "fix-{bug-id}" — roadmap-based bugfix flow
  │   └─ atdd_pure → single carpaccio slice via the /nw-execute per-slice cycle, A_GREEN <!-- mode-ref-ok -->
  │   └─ Paradigm detection determines crafter (OOP or FP)
  │   └─ Crafter implements against the already-RED test only — never authors or edits the test
  │
  └─ Phase 3c: EXAMINE (@nw-user-examiner "Vera") — BEFORE the commit      🔒 box
      └─ Vera runs the FIXED product through its real surface (CLI/HTTP/browser) — not the unit test —
         against the charter ALREADY authored at t=0 (NO charter authoring happens here anymore)
      └─ Record the verdict via `des record-examine-verdict` BEFORE COMMIT; PASS gates the commit
      └─ A_GREEN → EXAMINE → COMMIT — the same DoD as /nw-execute; examine is NEVER skipped

LANE MAP — so the orchestrator parallelizes BY CONSTRUCTION, not by deduction:
  ☁️ cloud  (fan-out over N defects, ~0 box cost): Phase 1 RCA · Phase 0-charter · Phase 3a AT authoring
  🔒 box    (ONE box, serialized — one defect at a time): RED seal (verify-red-green) · Phase 3b crafter
            GREEN · Vera EXAMINE · commit-slice
  Across N defects it is a PIPELINE, not a swarm: fan the cloud lanes out, then feed defects through the
  single box lane one at a time — almost all the speedup, zero disk, zero lock, zero merge conflicts.
  NO worktree as a parallelism mechanism (cargo does not share target/: either N×20GB + N cold builds,
  or serialize on the lock — exactly what a swarm was meant to avoid). A swarm does not multiply the box.
```

## Execution Steps

> **Phase 1 (RCA) and Phase 0-charter both start at t=0, in parallel.** They are two
> INDEPENDENT derivations of the same bug — Phase 1 from the CODE, Phase 0-charter from the
> OBSERVABLE — and neither depends on the other. Dispatch them together; do NOT serialize the
> charter after the RCA. Both are ☁️ cloud lanes (fan out over N defects at ~0 box cost).

### Phase 0-charter: Expectation Charter (t=0, parallel with RCA)

Authored at t=0 — NOT at Phase 3c — precisely so the authoring context is uncontaminated.
The bugfix orchestrator that has read the RCA + the fix diff is a DISQUALIFIED author (an
author holding the design/implementation cannot produce an uncontaminated charter); at t=0
that context does not exist yet, so the disqualification rule is satisfied BY CONSTRUCTION
rather than by remembering to resist the "I have it all in my head, I'll write it inline"
temptation. GDP-1 (fire the guard early) + GDP-5 (cost on the system, not the operator).

Dispatch a FRESH `@nw-product-owner` context (never inline by this orchestrator). Give it
ONLY value-side inputs: the bug's OBSERVABLE (what a user sees/does that is currently wrong —
the symptom) plus the human's original bug description verbatim. NEVER the RCA's causal chain
or a fix diff — at t=0 neither exists. The PO loads
`~/.claude/skills/nw-expectation-charter/SKILL.md` (Disqualification Rule + authoring steps
are SSOT'd there) and writes one short file under
`docs/product/expectations/fix-{bug-summary}/{intent-name}.md` naming how a demanding user
checks the fix from the outside (CLI/HTTP/browser, no source reading). Cheap (a paragraph),
high-value — it is the oracle Vera examines against at Phase 3c. Push hard for the NEGATIVE
oracles (the ways this cure could itself become a disease); authored before the fix exists,
they are exactly the failure modes a fix-focused mind omits.

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

**STOP and wait for user confirmation before proceeding to Phase 3a** (unless the
autonomous-loop exception below applies).

### Phase 2: User Review

Present the RCA findings and ask:
1. "Does this root cause match your understanding?"
2. "Do you approve the proposed fix direction?"
3. "Any additional constraints or context?"

If user rejects:
- Refine the RCA with additional context
- Or stop the workflow entirely

If user approves → proceed to Phase 3a.

**Autonomous-loop exception (Ale-ratified 2026-07-09).** When the bugfix runs under an
autonomous loop with the human's standing authorization, Phase 2's interactive STOP is
NON-BLOCKING — the standing authorization satisfies the human-approval intent, and Phase 3c
EXAMINE (Vera PASS, mandatory pre-commit) is the quality gate. Proceed from RCA (Phase 1)
directly to Phase 3a. This does NOT weaken quality: Vera EXAMINE still gates the commit.
Outside an autonomous loop, Phase 2 stays a hard interactive STOP.

### Phase 3a: Regression Test (@nw-acceptance-designer)

Invoke @nw-acceptance-designer via Agent tool to author the regression test from the RCA's
root cause chain and proposed fix (Phase 1 output) — the crafter dispatched in Phase 3b
does NOT write or edit this test, only implements against it. Test location + naming follow
the mode-appropriate convention below (classic: `tests/regression/{component}/` or
`tests/bugs/`, `test_bug_{description}.py`; atdd_pure: the bugfix's single-slice `.feature` + <!-- mode-ref-ok -->
step file under `tests/{feature-path}/`). The test MUST fail against current code for the
diagnosed reason (a real assertion on the defect's observable behavior, never an
import/collection error) — confirm this before proceeding to Phase 3b.

**Slice entry evidence — mechanical seal by default (evolution-plan P1.1).** Once the test
is confirmed RED, record the mechanical pair against the regression test file:

```bash
des verify-red-green --record-red --test-file {regression-test-file}
des verify-negative-at --test-file {regression-test-file} --all-critical
```

The first captures the `RedObserved` seal, bound to the file's current content — re-run it
if the test file changes afterward, a stale seal is void. The second verifies the file
carries at least one negative AT (the wrong output is NOT produced). The carpaccio slice
gate accepts this pair as the slice's AT attestation (`SliceCleared at_evidence:
mechanical-seal`) — no AT-review LLM dispatch on this pytest-regression path. If the
dispatched acceptance-designer dies before this seal lands, apply the recovery fallback in
`nw-execute` §Recovery Fallback — recover from its final message's verbatim RED confirmation.

**Optional double attestation (rigor-profile opt-in)**: dispatch an independent reviewer of
the regression test and record the verdict via `des record-at-review-verdict --verdict
APPROVED` (clears as `at_evidence: reviewer-verdict`). Use it when the rigor profile
demands double attestation; it is never mandatory on this path.

### Phase 3b: Fix (branches on workflow.mode, paradigm-selected crafter) <!-- mode-ref-ok -->

Phase 3b reads `workflow.mode` from `.nwave/config.yaml` and dispatches the fix <!-- mode-ref-ok -->
along one of two paths, against the already-authored, already-RED regression test from Phase
3a. Per-mode descriptor + DELIVER phase shape, projected from the mode registry (never
hand-written here):

<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice carpaccio loop; no roadmap.json / execution-log.json; AT-completion ledger + commit trailers are the audit.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
- `classic` — Roadmap-driven 3-phase TDD canon (ADR-025); roadmap.json + execution-log.json are the audit. DEPRECATED per ADR-028 D6 — fallback under explicit per-instance authorization only.
  Deliver phase shape: `RED -> GREEN -> COMMIT`
<!-- GENERATED:mode-descriptor END -->

Both paths share paradigm detection (reads project
CLAUDE.md for `## Development Paradigm`), crafter selection (@nw-software-crafter
for OOP, @nw-functional-software-crafter for FP), DES enforcement, and the rigor
profile from `.nwave/des-config.json`. Neither path's crafter authors or edits the
regression test — it was authored in Phase 3a by @nw-acceptance-designer.

**Preparation (both modes):**

1. Derive feature-id: `fix-{kebab-case-bug-summary}` (max 5 words)
2. Create `docs/feature/{feature-id}/deliver/` directory
3. Prepare RCA context from Phase 1 output (root cause, files affected, proposed fix)
4. Confirm Phase 3a's regression test exists and is RED for the right reason before dispatching the crafter

#### Mode `classic` — roadmap-based bugfix flow

Under `workflow.mode: classic`, delegate to `/nw-deliver`: <!-- mode-ref-ok -->

```
/nw-deliver "fix-{bug-summary}"
```

The deliver orchestrator builds a minimal one-step roadmap (the regression test
already exists from Phase 3a):

**Step 01-01: Fix implementation (GREEN)**
- Implement the minimal fix identified in RCA against the Phase 3a regression test
- Run ALL tests — regression test must now PASS
- Existing tests must not regress
- The crafter does NOT write, edit, or weaken the regression test — if it seems
  wrong or insufficient, escalate back to @nw-acceptance-designer, do not touch it directly

#### Mode `atdd_pure` — single carpaccio slice, no roadmap <!-- mode-ref-ok -->

Under `workflow.mode: atdd_pure` the bugfix is the canonical single carpaccio <!-- mode-ref-ok -->
slice: there is no roadmap and no roadmap-step extraction. The defect's
regression test (authored in Phase 3a) IS the slice's acceptance test. The
slice enters the carpaccio gate in pytest-regression mode, where the Phase 3a
mechanical pair is its default entry evidence (`at_evidence: mechanical-seal`)
— no AT-reviewer dispatch and no verdict record needed unless the rigor
profile opts into double attestation. Run the
fix through the slice-04 roadmap-free spine via the per-slice `/nw-execute` lean
cycle, starting at `A_GREEN` (the AT already exists — same SLIM-crafter contract
as any other atdd_pure slice, no carve-out): <!-- mode-ref-ok -->

```
/nw-execute "fix-{bug-summary}"
```

The per-slice cycle drives the `A_GREEN → EXAMINE → COMMIT` shape (light
single-slice bugfix cycle) against the already-authored, already-RED regression
AT. EXAMINE (Phase 3c, `@nw-user-examiner`) is part of the light cycle — it is the
DoD, never skipped. What the light cycle drops are the FEATURE-scope passes (deep
`E_BATCH_REFACTOR`/`F_FINAL_REVIEW` code-reading + whole-feature refactor), which
belong to a full feature's feature-end cycle, not to a single-slice bugfix.

The crafter handles the TDD cycle (3-phase canon RED → GREEN → COMMIT per
ADR-025, or legacy 5-phase PREPARE → RED_ACCEPTANCE → RED_UNIT → GREEN → COMMIT
for pre-2026-05-07 audit-log replay) with DES monitoring in either mode — RED
here means activating/running the already-authored test, never authoring it.

**The light single-slice bugfix cycle is `A_GREEN → EXAMINE → COMMIT`** — the SAME
DoD as `/nw-execute`. What the light cycle drops are the FEATURE-scope passes
(deep `C_REVIEWER_AUDIT` code-reading, `E_BATCH_REFACTOR`, `F_FINAL_REVIEW` — those
belong to a full feature's feature-end cycle). It does NOT drop **EXAMINE**: the
green regression test proves the CODE, EXAMINE (Vera) proves the running SYSTEM
through the real surface, and the two diverge (isolated-green ≠ assembled-green).
Examine is the Definition of DONE and is NEVER skipped for a bugfix — see Phase 3c.

### Phase 3c: EXAMINE (@nw-user-examiner "Vera") — runs BEFORE the commit

The fix is not done when the regression test is green — it is done when a demanding
user, running the FIXED product through its real surface, observes the bug gone.
Phase 3c runs after Phase 3b's GREEN and BEFORE the commit:

1. **The charter ALREADY EXISTS — it was authored at t=0 (Phase 0-charter), in parallel
   with the RCA, NOT here.** By Phase 3c this orchestrator has read the RCA + the fix diff
   (Phase 1-3b) and is a DISQUALIFIED author (the charter-governance rule: an author holding
   the design/implementation cannot produce an uncontaminated charter). That is exactly WHY
   the charter is not authored at this point: it was written at t=0, before any contaminated
   context existed, by a FRESH `@nw-product-owner` given ONLY the bug's OBSERVABLE + the
   human's verbatim description (see §Phase 0-charter). Here, simply LOCATE the existing
   charter under `docs/product/expectations/fix-{bug-summary}/{intent-name}.md`. If it is
   somehow missing (the parallel t=0 dispatch failed), dispatch the FRESH PO to author it NOW
   from the OBSERVABLE ONLY — never inline, never from the RCA/fix diff — then continue.
2. **Dispatch @nw-user-examiner (Vera)** on the charter against the REAL fixed
   product (the installed `des` / the running surface), Haiku model. Build a
   concrete repro first and verify it yourself, then hand Vera the exact commands.
   Vera cannot read source — the verdict is PASS/FAIL/INDETERMINATE from observed
   behaviour only.
3. **Record the verdict** via `des record-examine-verdict --feature-id fix-{...}
   --slice slice-01 --charter <path> --verdict PASS --examiner nw-user-examiner`
   BEFORE the commit. The examine gate arms on charter presence: `des commit-slice`
   refuses the commit without a fresh Vera PASS. If Vera dies before self-recording,
   apply the recovery fallback in `nw-execute` §Recovery Fallback — recover from her
   final message's verbatim `VERDICT:` line, never re-guess it.

**Verdict strictness (never gamed, never a silent ship):**
- Vera flags EVERYTHING — there is no "out-of-charter" category. A defect, a
  degradation, an INDETERMINATE, or a nitpick are all flags.
- **PASS = ZERO flags**, computed MECHANICALLY: `des record-examine-verdict`
  REFUSES a PASS carrying ≥1 flag of any kind. The orchestrator does not decide
  it.
- **Every flag → an explicit, RECORDED disposition**, never silent-ship: either
  fix-now (re-loop `acceptance-designer → crafter → re-examine`, BOUNDED to N
  attempts) OR a named-owned residue (backlog entry, gate-or-residue).
- **Never deadlock — always escalate.** If the bounded re-loop does not converge,
  or a disposition is contested, ESCALATE to the human with the flag + options
  (asymmetric authority: controls VETO, the human decides). The strictness holds
  (the flag stays tracked, nothing silent-ships); the valve is escalation, not
  a spin.

Only after a recorded Vera PASS does the bugfix proceed to COMMIT.

## Success Criteria

- [ ] Root cause identified with evidence at each causal level
- [ ] User reviewed and approved fix direction
- [ ] Regression test authored by @nw-acceptance-designer, fails with the bug
- [ ] Fix implemented by the paradigm-selected crafter that makes the regression test pass, without the crafter touching the test itself
- [ ] All existing tests still pass (no regressions)
- [ ] **Charter (Phase 0-charter) authored at t=0, in PARALLEL with the RCA, by a FRESH `nw-product-owner` from the OBSERVABLE only (never inline by the bugfix orchestrator, never from the RCA/fix diff)**
- [ ] **EXAMINE (Phase 3c): @nw-user-examiner (Vera) PASS recorded via `des record-examine-verdict` against the t=0 charter, BEFORE the commit — examine is the DoD, never skipped**
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
- **Phase 0-charter and Phase 1 (RCA) both start at t=0, in parallel** — two independent derivations of the same bug (charter from the OBSERVABLE, RCA from the CODE). The charter does not depend on the RCA, so authoring it at t=0 keeps its context uncontaminated BY CONSTRUCTION. Phase 3a (@nw-acceptance-designer, regression test) runs next, regardless of mode. Phase 3b branches on `workflow.mode`: `classic` delegates to `/nw-deliver` (one-step roadmap, GREEN only); `atdd_pure` runs a single carpaccio slice via the `/nw-execute` per-slice cycle starting at `A_GREEN`. <!-- mode-ref-ok --> Both modes handle paradigm detection, DES enforcement, and rigor profile automatically for the fix implementor; neither touches the test.
- **The charter is authored at t=0 (Phase 0-charter), NOT at Phase 3c.** By Phase 3c the bugfix orchestrator, holding the RCA + fix diff, is disqualified from authoring it — so the charter is authored earlier, at t=0, by a FRESH `nw-product-owner` from the OBSERVABLE only (before any contaminated context exists — see `nw-expectation-charter` skill + §Phase 0-charter). This makes the disqualification rule structurally easy to obey rather than a virtue to remember (GDP-1 fire-early + GDP-5 cost-on-system).
- **Phase 3c (EXAMINE) always runs before the commit, in BOTH modes.** The `A_GREEN → EXAMINE → COMMIT` DoD is not waived for a bugfix: @nw-user-examiner (Vera) records a PASS via `des record-examine-verdict` against the t=0 charter before `des commit-slice` will commit. Green regression tests prove the code; EXAMINE proves the running system through the real surface. Skipping examine on the "light" bugfix cycle is the spec-drift this closes — examine is high-value and low-cost, never skipped.
