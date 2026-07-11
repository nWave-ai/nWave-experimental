---
name: nw-execute
description: "Dispatches one unit of DELIVER work to a specialized agent for TDD execution. Use to run a step (classic workflow mode, a roadmap.json plan) or one carpaccio slice (ATDD-pure workflow mode)."
user-invocable: true
argument-hint: '[agent] [feature-id] [step-id] - Example: @nw-software-crafter "auth-upgrade" "01-01"'
---

> **Code facts** — resolve structural facts about code (who-calls / defs-reads / never-wired / call-graph / atoms-in-file) through the `nw-code-analysis-port` skill: Tsunami-first via the `mcp__tsunami__*` tools, declared fallback (AST, then grep), degrade-LOUD. Never ad-hoc grep for a structural fact.

# NW-EXECUTE: Atomic Task Execution

**Wave**: EXECUTION_WAVE | **Agent**: Dispatched agent (specified by caller)

## Overview

Dispatch one unit of DELIVER work to an agent. The unit depends on `workflow.mode` (read from `.nwave/config.yaml`): under `classic` it is a single roadmap step; under `atdd_pure` it is one carpaccio slice run through the per-slice lean cycle. <!-- mode-ref-ok -->

## Workflow Mode

`/nw-execute` reads `workflow.mode` from `.nwave/config.yaml` and branches on it before doing anything else. <!-- mode-ref-ok -->
Per-mode descriptor + DELIVER phase shape, projected from the mode registry (never hand-written here):

<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice carpaccio loop; no roadmap.json / execution-log.json; AT-completion ledger + commit trailers are the audit.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
- `classic` — Roadmap-driven 3-phase TDD canon (ADR-025); roadmap.json + execution-log.json are the audit. DEPRECATED per ADR-028 D6 — fallback under explicit per-instance authorization only.
  Deliver phase shape: `RED -> GREEN -> COMMIT`
<!-- GENERATED:mode-descriptor END -->

- **`classic`** — `/nw-execute` extracts a single step from `roadmap.json` and dispatches it; the agent appends phase events to `execution-log.json`. This is the default and everything below under "Context Files", "Dispatcher Workflow", and "TDD_PHASES" describes the `classic` path.
- **`atdd_pure`** — `/nw-execute` IS the **per-slice lean cycle**: it executes ONE carpaccio slice. See "ATDD-Pure Per-Slice Lean Cycle" below. <!-- mode-ref-ok -->

### ATDD-Pure Per-Slice Lean Cycle

Under `workflow.mode: atdd_pure`, `/nw-execute` runs one carpaccio slice through the per-slice lean cycle (ADR-028 D6). It does NOT extract roadmap steps and does NOT emit an execution-log — the unit of work is a carpaccio slice, not a roadmap step. The cycle, in order: <!-- mode-ref-ok -->

1. **Carpaccio entry gate** — confirm the slice's acceptance tests exist and are correctly skip-scaffolded; reject the slice if the carpaccio gate fails. Entry evidence for the gate's AT-attestation leg (assertion 5): a pytest-regression slice (`at_kind: pytest-regression`, the `/nw-bugfix` mode — the regression test IS the slice's AT) clears by DEFAULT on the mechanical pair — fresh `RedObserved` seal (`des verify-red-green --record-red --test-file <f>`) + negative-AT pass (`des verify-negative-at --test-file <f> --all-critical`) — recorded as `SliceCleared at_evidence: mechanical-seal`, no AT-review LLM dispatch (evolution-plan P1.1). A recorded `ATReviewVerdict` (reviewer dispatch + `des record-at-review-verdict`) is the optional rigor-profile alternative on that path. Gherkin slices keep the reviewer-verdict route unchanged — the seal path is not yet wired for Gherkin (tracked follow-up).
2. **`A_GREEN_ATS`** — activate the slice's acceptance tests and implement until they are GREEN. This replaces `classic`-mode roadmap-step extraction: under `atdd_pure` the slice's ATs ARE the work unit. <!-- mode-ref-ok -->
3. **`B_COVERAGE_CLEANUP`** — coverage-driven dead-code elimination for the slice. **DEPRECATED (FR-2/FR-3, velocity-v2)**: absorbed into A_GREEN as AT-driven minimalism (no `pytest --cov` gate, no ≥90% target) — see the Phase B DEPRECATED banner in `nw-crafter-discipline-atdd-pure`.
4. **Light slice review** — confirm the implementation satisfies the slice's ATs. This is a light pass, not the deep adversarial review (the deep `C`+`F` review belongs to `/nw-deliver`'s feature-end cycle, not here).
5. **Terminating slice-scoped run** — run the slice's own AT suite (`pytest tests/{feature-path}/`, covering every shipped + entering slice). The whole-tree contract suite is NOT run per slice; it is run once at the feature-end cycle. The `Gate-Scope:` digest (E2 `--verify-gate-scope`) stays a whole-tree `--collect-only` digest — unchanged.
6. **EXAMINE — the Definition of DONE (hard-gated, ADR P1.2).** For a VALUE slice, dispatch `nw-user-examiner` (Vera) against the slice's charter (`docs/product/expectations/{feature-id}/*.md` — the one whose `Spec rows: slice-NN` names this slice), have her observe the outcome end-to-end through the REAL user surface, then record the verdict: `des record-examine-verdict --repo . --feature-id {feature-id} --slice {slice-NN} --charter <path> --verdict PASS --observations <text> --examiner nw-user-examiner`. **EXAMINE is the true DoD** — green tests verify the CODE, EXAMINE verifies the running SYSTEM (isolated-green ≠ assembled-green; a stale process can serve old code while tests pass on fresh source). This is NOT optional: G_COMMIT's `des verify-slice-commit` runs **E3 (`check_examine_verdict`)** and refuses `SliceCommitVerified` fail-closed for an ARMED feature (a charter dir exists) that lacks a fresh PASS verdict whose `charter_seal` matches the charter's current bytes. **EXEMPTION** — a behaviour-preserving **prefactoring/refactoring** slice changes no behaviour, carries no charter → the gate is UNARMED → green-to-green (tests pass before AND after) suffices; prefactorings run through a SEPARATE path (Mikado / the prefactoring-lane), not this cycle. **Slicing test**: if a value slice cannot be EXAMINE'd (no observable surface), that is a horizontal-slicing smell — re-slice it VERTICAL; the gate records `ExamineVerdictIndeterminate` = "an unexaminable slice carries no observable value — it was not a slice", never a silent pass.
7. **`G_COMMIT`** — stage and conventional-commit, then run the exit gate EXPLICITLY: `des verify-slice-commit --repo . --commit HEAD --feature-id {feature-id}` (the verify-then-record path — E1 completeness + E2 feature-scoped contract gate + E3 examine-verdict — which RECORDS `SliceCommitVerified` to the AT-completion ledger IFF all three clear). This is MANDATORY, not optional: the successor slice's carpaccio entry gate BLOCKS until that record exists. Do NOT rely on the `SubagentStop` hook to emit it — the hook fires only on a distinct `G_COMMIT`-phase return, which a folded lean-cycle commit may not produce; it is a backstop, never the sole emitter. Confirm the `SliceCommitVerified` record landed before phase exit (empirical 2026-05-29: a slice committed but left no record, blocking its successor until backfilled).

`E_BATCH_REFACTOR` and the deep review are explicitly NOT part of `/nw-execute` under `atdd_pure` — they belong to `/nw-deliver`'s feature-end cycle. <!-- mode-ref-ok -->

## Recovery Fallback — Subagent Died Before Its Final Mechanical Record

Empirically recurring failure mode (gap-3, cross-instance): a dispatched subagent — the examiner (Vera), the acceptance-designer sealing RED, a reviewer recording an AT-review verdict, an ad-hoc reviewer (e.g. `nw-agent-builder-reviewer`) recording a general review verdict — completes its investigation and DECIDES its verdict, then the process dies exactly before its LAST mechanical step: the `des record-examine-verdict` / `des verify-red-green --record-red` / `des record-at-review-verdict` / `des record-review-verdict` call that persists it. The ledger then lacks the record even though the subagent knew the verdict. This is additive, not a replacement: the subagent still self-records on the happy path — self-recording is tamper-evident (the examiner signs HER OWN verdict, the reviewer signs HER OWN AT-review or general review) and that property is preserved.

Two-part contract:

1. **Dispatch contract (produces recovery data)** — every dispatch whose final step is a `des record-*` / `des verify-red-green --record-red` call MUST instruct the subagent to end its final message with the verdict/seal + observations stated VERBATIM (e.g. `VERDICT: PASS` plus the observation text, or `RED CONFIRMED: <reason>`). Without this line, recovery has nothing to record from.
2. **Orchestrator contract (recovers when the record is missing)** — after a dispatched subagent (examiner / acceptance-designer / reviewer) returns or goes idle, the orchestrator VERIFIES the record actually landed in the relevant ledger (e.g. grep `.nwave/telemetry/examine/{feature-id}.jsonl` for `ExamineVerdictRecorded`, the AT-completion ledger for `RedObserved` / `ATReviewVerdict`, or `.nwave/telemetry/review/{feature-id}.jsonl` for `ReviewVerdictRecorded` — the ledger for ad-hoc reviewers that lack a wave-specific recorder, #45). If the record is ABSENT — the subagent died before its last step — the orchestrator runs the SAME `des record-*` command the subagent would have run, using the subagent's verbatim reported verdict from its final message. This is a fallback: the orchestrator only records when the ledger shows the subagent died before doing so; it never overrides a self-recorded verdict.

**Per-slice pipelining (throughput).** While the crafter greens the current slice (`A_GREEN`), dispatch `@nw-acceptance-designer` for the NEXT slice's AT — and, for an observable slice, a fresh `@nw-product-owner` for its charter — in PARALLEL cloud lanes. The box-seal lane (carpaccio `entry_gate` → commit-slice) stays strictly serialized: N LLM lanes, ONE box lane, never two heavy box gates concurrently. Canonical prose + empirical anchor: `nw-deliver` §Per-slice pipelining.

The long-lived orchestrator always survives to persist a decided verdict — a subagent's death can never silently lose it. This discipline is the canonical locus for the recovery fallback (the per-slice cycle owner); `/nw-deliver` and `/nw-bugfix` point here rather than restating it.

## Syntax

```
/nw-execute @{agent} "{feature-id}" "{step-id}"
```

## Context Files Required (classic mode)

These context files apply only when `workflow.mode` is `classic`; under `atdd_pure` there is no roadmap or execution-log (see "ATDD-Pure Per-Slice Lean Cycle"). <!-- mode-ref-ok -->

- `classic` mode: `docs/feature/{feature-id}/deliver/roadmap.json` — Orchestrator reads once, extracts step context
- `classic` mode: `docs/feature/{feature-id}/deliver/execution-log.json` — Agent appends only (never reads)

## Rigor Profile Integration

Before dispatching the agent, read rigor config from `.nwave/des-config.json` (key: `rigor`). If absent, use standard defaults.

- **`agent_model`**: Pass as `model` parameter to Agent tool. If `"inherit"`, omit `model` (inherits from session).
- **`tdd_phases`**: Modify the TDD_PHASES section in the DES template to match the configured phases. The 3-phase canon (ADR-025) is `[RED, GREEN, COMMIT]`; the lean variant is `[RED, GREEN]`. Legacy 5-phase contract (`[PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT]`) and its lean variant (`[RED_UNIT, GREEN]`) remain supported for audit-log replay of pre-2026-05-07 commits. Remove omitted phases' instructions from the template.
- **`refactor_pass`**: If `false`, skip COMMIT phase refactoring instructions.

## Dispatcher Workflow

This workflow is the `classic`-mode path (roadmap.json step extraction, execution-log emission). Under `atdd_pure`, follow "ATDD-Pure Per-Slice Lean Cycle" above instead. <!-- mode-ref-ok -->

1. **Parse Parameters** — Extract agent name, feature ID, and step ID from invocation. Gate: all three parameters present and non-empty.
2. **Load Rigor Profile** — Read `.nwave/des-config.json` key `rigor` (default: standard if absent). Gate: config loaded or default applied.
3. **Validate Context Files** — `classic` mode only: confirm `roadmap.json` and `execution-log.json` exist under `docs/feature/{feature-id}/deliver/`. Gate: both files present; report path-not-found if missing. Skip this step entirely under `atdd_pure` (no roadmap.json / execution-log). <!-- mode-ref-ok -->
4. **Extract Step Context** — Grep roadmap for `step_id: "{step-id}"` with ~50 lines context. Gate: step found; report available step IDs if missing.
5. **Invoke Agent** — Call Agent tool with DES template below, applying rigor model and phases from step 2. Gate: Agent tool called, not executed inline.

## Agent Invocation

@{agent}

**Template selection — branch on `workflow.mode`.** Before rendering the dispatch prompt, the dispatcher MUST select the dispatch template by the `workflow.mode` read from `.nwave/config.yaml` (see "Workflow Mode" above): <!-- mode-ref-ok -->

- **`workflow.mode = classic`** — use the **Classic DES Dispatch Template** immediately below (`DES-STEP-ID`, `TDD_PHASES`, execution-log `OUTCOME_RECORDING` / `RECORDING_INTEGRITY`, roadmap `BOUNDARY_RULES`). <!-- mode-ref-ok -->
- **`workflow.mode = atdd_pure`** — use the **ATDD-Pure DES Dispatch Template** in the section further below (`DES-MODE:atdd_pure` + `DES-PHASE` + `DES-SLICE`, the A→G phase block, the AT-completion-ledger contract, slice-scoped boundary rules; NO `DES-STEP-ID`, NO classic `TDD_PHASES`, NO `execution-log.json`). <!-- mode-ref-ok -->

Both templates are copy-fill-verbatim: fill `{placeholders}` and emit the block unchanged. Without DES markers, hooks cannot validate.

### Classic DES Dispatch Template

Use this DES template verbatim when `workflow.mode = classic`. Fill `{placeholders}` from roadmap. <!-- mode-ref-ok -->

```
<!-- DES-VALIDATION : required -->
<!-- DES-PROJECT-ID : {feature-id} -->
<!-- DES-STEP-ID : {step-id} -->
<!-- DES-WAVE: deliver -->

# DES_METADATA
Step: {step-id}
Feature: {feature-id}
Command: /nw-execute

# AGENT_IDENTITY
Agent: {agent-name}

# SKILL_LOADING
Before starting TDD phases, read your skill files for methodology guidance.
Skills path: ~/.claude/skills/nw-{skill-name}/SKILL.md
Always load before RED: tdd-methodology.md, quality-framework.md (3-phase canon, ADR-025) — legacy 5-phase logs reference loading at PREPARE.
Load on-demand per phase as specified in your Skill Loading Strategy table.

# TASK_CONTEXT
{step context from roadmap - name|criteria|test_file|scenario_name|implementation_notes|deps|files_to_modify (per nWave/templates/roadmap-schema.json)}

# DESIGN_CONTEXT
{Summary of architectural decisions relevant to this step, extracted by the orchestrator from docs/product/architecture/brief.md and wave-decisions.md. Include: component structure, dependency boundaries, technology choices, and any design constraints that affect implementation. If no design artifacts exist, write "No design artifacts available — use project conventions."}

# TDD_PHASES
3-phase canon (ADR-025, 2026-05-07). Execute in order:

1. RED - Activate the pre-authored acceptance test (PRIMARY TBU DEFENSE); write PBT unit tests ONLY if the AT cannot reach GREEN without them.
   AT activation: If TASK_CONTEXT includes test_file, locate it and remove the @skip/@ignore/@pending/xit/.skip/[Ignore] marker from the target scenario (the AT scaffold was authored by DISTILL — DELIVER does NOT re-author ATs). Run it — must fail for business logic reason (not import/syntax error). Fail-for-right-reason gate: collected ≥ 1, failures ≥ 1, no collection errors, semantic AssertionError / expected-exception-not-thrown.
   PORT-TO-PORT PRINCIPLE: The acceptance test exercises the scenario through
   the driving port (application service, orchestrator, CLI handler, API controller),
   not a decomposed helper or internal class. A correctly-written port-to-port test
   makes TBU structurally impossible — if a new function were missing or unwired,
   THIS test stays RED. That is the entire point: GREEN is unreachable without wiring.
   Litmus test: "If I delete the call-site that wires the new code, does this test fail?"
   If no → the test is at the wrong level. Stop and flag to orchestrator (DISTILL re-author needed).
   SLIM-crafter escalation contract: the crafter does NOT author unit tests, integration tests, or any other test under any condition. If the AT cannot reach GREEN via direct minimal implementation — for example the AT requires decomposition into a port-and-adapter pair the AT cannot itself observe — escalate `{ESCALATION_NEEDED: true, reason: "AT_INSUFFICIENT_FOR_GREEN", at: "<path>", route: "nw-acceptance-designer"}` and halt. DISTILL re-enters to author the paired unit test (or adapter integration test); the slice then re-dispatches. Test authorship of every kind — ATs, paired PBT unit tests, adapter integration tests — belongs to `nw-acceptance-designer`.

2. GREEN - Minimal code to pass AT + any unit tests authored in RED.
   After GREEN: run FULL test suite. If all pass, proceed to COMMIT immediately.
   Smell test: if any new function is only called from test code, your acceptance
   test is at the wrong abstraction level — stop and flag.
   Never move to new task or stop without committing green code.

3. COMMIT - Stage and commit with conventional message.
   Include git trailer: `Step-Id: {step-id}` (required for DES verification)
   Example:
   ```
   feat(feature-id): implement feature X

   Step-Id: 02-01
   ```

LEGACY 5-PHASE CONTRACT (ADR-024 era, pre-2026-05-07): PREPARE → RED_ACCEPTANCE → RED_UNIT → GREEN → COMMIT. Preserved for audit-log replay only — new work uses the 3-phase canon above. Audit-log entries referencing RED_ACCEPTANCE/RED_UNIT/PREPARE represent merged sub-steps now folded into RED.

# QUALITY_GATES
- All tests pass before COMMIT
- No skipped phases without blocked_by reason
- Coverage maintained or improved

# OUTCOME_RECORDING
After ACTUALLY EXECUTING each phase, record via DES CLI:

    des log-phase \
      --project-dir docs/feature/{feature-id}/deliver \
      --step-id {step-id} \
      --phase {PHASE_NAME} \
      --status EXECUTED \
      --data PASS

For SKIPPED phases (genuinely not applicable):

    des log-phase \
      --project-dir docs/feature/{feature-id}/deliver \
      --step-id {step-id} \
      --phase {PHASE_NAME} \
      --status SKIPPED \
      --data "NOT_APPLICABLE: reason"

CLI enforces real UTC timestamps and validates phase names.
In `classic` mode, do NOT manually edit execution-log.json.
Use the DES CLI to record phase outcomes and create log files.
Python resolution: `$(command -v python3 || command -v python)` — works on macOS (python3 only), Linux, and Windows.

CRITICAL: Only the executing agent calls the CLI.
Orchestrator MUST NEVER write phase entries — only the agent that performed the work. A log entry without actual execution is a **violation that DES detects and that will cause integrity verification to fail**, blocking finalize.

# RECORDING_INTEGRITY
Valid Skip Prefixes: NOT_APPLICABLE, BLOCKED_BY_DEPENDENCY, APPROVED_SKIP, CHECKPOINT_PENDING
Anti-Fraud Rules:
- NEVER write EXECUTED for phases you did not actually perform
- NEVER invent timestamps — DES CLI generates real UTC timestamps
- DES audits all entries; integrity violations block finalize

# BOUNDARY_RULES
- Only modify files listed in step's files_to_modify
- `classic` mode: do not load roadmap.json
- `classic` mode: do not modify execution-log.json structure (append only)
- `classic` mode: NEVER write execution-log entries for phases you did not execute

# TIMEOUT_INSTRUCTION
Target: 30 turns max. If approaching limit, COMMIT current progress.
If GREEN complete (all tests pass), MUST commit before returning — even at turn limit.
```

### ATDD-Pure DES Dispatch Template

Use this DES template verbatim when `workflow.mode = atdd_pure`. It dispatches ONE carpaccio slice into ONE ATDD-pure phase. Fill `{placeholders}` from the slice plan in `feature-delta.md` — `{feature-id}`, `{slice-NN}` (the bare carpaccio slice id, anchored `slice-\d+` shape), `{phase}` (one of the seven `ATDDPurePhase` members), and `{agent}`. <!-- mode-ref-ok -->

This template carries the three U0 dispatch markers (`DES-MODE:atdd_pure`, `DES-PHASE`, `DES-SLICE`) the `PreToolUse` / `SubagentStop` hooks key on. It carries NO `DES-STEP-ID`, NO classic `TDD_PHASES` RED/GREEN/COMMIT block, and NO `execution-log.json` recording — `atdd_pure` is roadmap-free (ADR-028 D6) and records via the AT-completion ledger, not the execution-log. <!-- mode-ref-ok -->

The block between the `ATDD-PURE-DISPATCH-TEMPLATE:BEGIN` / `:END` anchor comments is the copy-fill-verbatim dispatch prompt.

<!-- ATDD-PURE-DISPATCH-TEMPLATE:BEGIN -->
```
<!-- DES-VALIDATION : required -->
<!-- DES-PROJECT-ID : {feature-id} -->
<!-- DES-MODE : atdd_pure --> <!-- mode-ref-ok -->
<!-- DES-PHASE : {phase} -->
<!-- DES-SLICE : {slice-NN} -->
<!-- DES-WAVE: deliver -->

# DES_METADATA
Slice: {slice-NN}
Feature: {feature-id}
Phase: {phase}
Command: /nw-execute — atdd_pure workflow.mode, per-slice lean cycle (ADR-028 D6) <!-- mode-ref-ok -->

# AGENT_IDENTITY
Agent: {agent}

# SKILL_LOADING
Before starting, read your skill files for methodology guidance.
Skills path: ~/.claude/skills/nw-{skill-name}/SKILL.md
Always load at phase entry: nw-tdd-methodology, nw-quality-framework.
In atdd_pure mode also load nw-crafter-discipline-atdd-pure at phase entry. <!-- mode-ref-ok -->
Load on-demand per phase as specified in your Skill Loading Strategy table.

# TASK_CONTEXT
{slice context from feature-delta.md slice plan — slice value statement |
acceptance tests for the slice | files_to_modify | the DISTILL-authored ATs
this slice must turn GREEN. The slice's ATs ARE the work unit — atdd_pure does <!-- mode-ref-ok -->
NOT extract roadmap steps.}

# DESIGN_CONTEXT
{Summary of architectural decisions relevant to this slice, extracted from
docs/feature/{feature-id}/feature-delta.md DESIGN section. Include component
structure, dependency boundaries, technology choices, design constraints. If
no design artifacts exist, write "No design artifacts available — use project
conventions."}

# ATDD_PURE_PHASES
ATDD-pure per-slice cycle (ADR-027 / ADR-028 D6). The seven canonical phases,
in order: A → B → C → D → (E | reloop A | reroute | exit) → E → F → G.
This dispatch executes the phase named in the DES-PHASE marker.

1. A_GREEN_ATS — crafter. Activate the slice's DISTILL-authored acceptance
   tests and implement the minimum production code that turns them all GREEN.
   Do NOT author new tests. Do NOT add defensive code beyond AT-driven need.
   Gate: all the slice's ATs green; wiring check passes.
2. B_COVERAGE_CLEANUP — same crafter instance. Coverage-driven dead-code
   elimination for the slice. Gate: ≥90% line+branch coverage on new code OR
   justified misses recorded in the commit body.
3. C_REVIEWER_AUDIT — reviewer. 15-item AT-completeness audit.
   Gate: PhaseCReviewerVerdict emitted.
4. D_GAP_ROUTING — orchestrator. Route per ATGapKind.
   Gate: one routing decision recorded.
5. E_BATCH_REFACTOR — separate crafter instance. L1-L6 batch refactor:
   plan in cascade order, apply as one batch, run the suite ONCE at the end.
   Gate: tests stay green post-batch.
6. F_FINAL_REVIEW — reviewer. Code review + refactor green check.
   Gate: PhaseFReviewerVerdict with mandatory verdict_hash.
7. G_COMMIT — crafter. Conventional commit with Slice-Id: + Gate-Scope: +
   Reviewed-by: (verdict_hash) trailers. Gate: G_COMMIT exit gate exit 0.

# QUALITY_GATES
- All the slice's ATs pass before G_COMMIT
- No new tests authored by the crafter (DISTILL owns AT authorship)
- Coverage maintained or improved; dead code eliminated in B_COVERAGE_CLEANUP
- Wiring check: every production file in files_to_modify appears in git diff

# AT_COMPLETION_LEDGER
atdd_pure records phase outcomes to the AT-completion ledger only. The ledger <!-- mode-ref-ok -->
lives at `.nwave/telemetry/atdd-pure/{feature-id}.jsonl`. Each slice records the
at_ids it satisfied and the implementation files those ATs drove.
- The C_REVIEWER_AUDIT / F_FINAL_REVIEW verdicts and the G_COMMIT trailers are
  the records of truth for the slice.
- The DES sequencer appends FeatureEndCheckpoint records to the AT-completion
  ledger at feature-end-cycle boundaries — the crafter does not write these.
- atdd_pure produces no classic step-log artifact; do not create one. <!-- mode-ref-ok -->

# RECORDING_INTEGRITY
Do not fake green. Every AT reaches its assertion and passes for the right
reason. State explicitly whether all the slice's ATs are genuinely green.
- NEVER report a phase outcome you did not actually perform.
- NEVER weaken, skip, or rewrite a DISTILL-authored AT to make it pass — if an
  AT cannot be satisfied, escalate to nw-acceptance-designer, do not edit it.

# BOUNDARY_RULES (slice-scoped)
- Only modify files within this slice's files_to_modify.
- Stay within the slice's value statement — do NOT implement adjacent slices.
- atdd_pure mode: there is no roadmap and no classic step-log — do not read or <!-- mode-ref-ok -->
  create either; the slice's ATs are the work unit.
- Do NOT author acceptance tests — AT authorship belongs to nw-acceptance-designer.
- Do NOT run E_BATCH_REFACTOR or the deep review here — they belong to
  /nw-deliver's feature-end cycle, not the per-slice /nw-execute cycle.

# TERMINATING_RUN
After any code modification, end with a terminating run of the slice's own AT
suite (`pytest tests/{feature-path}/`, covering every shipped + entering slice).
Do NOT run the whole-tree contract suite per slice — it is run once at the
feature-end cycle. The `Gate-Scope:` digest (E2 `--verify-gate-scope`) stays a
whole-tree `--collect-only` digest. Report exact pass/fail counts.

# TIMEOUT_INSTRUCTION
Target: 30 turns max. If approaching the limit, commit current green progress.
If A_GREEN_ATS is complete (all slice ATs pass), MUST commit before returning.
```
<!-- ATDD-PURE-DISPATCH-TEMPLATE:END -->

**Configuration:**
- subagent_type: extracted agent name
- Turn limits are defined in each agent's `maxTurns` frontmatter field (not as a tool parameter)

## Error Handling

1. **Invalid Agent** — Report available agents from the agent registry. Gate: error message returned, no invocation attempted.
2. **Missing Context Files** (`classic` mode) — Report exact path not found for roadmap or execution-log. Gate: clear path reported.
3. **Step Not in Roadmap** — Report available step IDs from roadmap. Gate: list of valid IDs returned.
4. **Dependency Failure** — Explain which blocking tasks are incomplete. Gate: blocking step IDs named explicitly.

## Resume vs Restart

When subagent times out:

| Last Completed Phase (3-phase canon) | Legacy phase (5-phase) | Action | Rationale |
|--------------------------------------|------------------------|--------|-----------|
| GREEN (or later) | GREEN | Resume | Only COMMIT remains (~5 turns) |
| RED with partial GREEN | RED_UNIT with partial GREEN | Resume | Preserves implementation progress |
| RED only (pre-GREEN) | PREPARE or RED_ACCEPTANCE | Restart | Little context worth replaying |

Resume costs ~50% more tokens/call due to context replay (measured: 3.7K vs 2.5K tokens/call). For <5 remaining turns, resume is efficient. For 15+ turns, restart is cheaper.

## Examples

```bash
/nw-execute @nw-software-crafter "des-us007-boundary-rules" "02-01"
/nw-execute @nw-researcher "auth-upgrade" "01-01"
/nw-execute @nw-software-crafter "des-us007" "03-01"  # retry after failure
```

## TDD_PHASES
<!-- Schema v4.0 — canonical source: TDDPhaseValidator.MANDATORY_PHASES -->
<!-- Build system injects mandatory phases from step-tdd-cycle-schema.json -->
{{MANDATORY_PHASES}}

## Success Criteria

- [ ] Agent invoked via Agent tool (dispatcher does not execute the work)
- [ ] `classic` mode: step context extracted from roadmap and passed in prompt; `atdd_pure` mode: one carpaccio slice run through the per-slice lean cycle <!-- mode-ref-ok -->
- [ ] `classic` mode: agent appended phase events to execution-log.json
- [ ] `classic` mode: agent did not load roadmap.json (under `atdd_pure` there is no roadmap.json) <!-- mode-ref-ok -->

## Next Wave

**Handoff To**: /nw-review for post-execution review
**Deliverables**: `classic` mode — updated execution-log.json; `atdd_pure` mode — committed carpaccio slice; both — implementation artifacts and git commits <!-- mode-ref-ok -->
