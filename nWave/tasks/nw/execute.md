---
description: Dispatches one unit of DELIVER work to a specialized agent for TDD execution. Active execution is one atdd-pure carpaccio slice.
argument-hint: '[agent] [feature-id] [step-id] - Example: @nw-software-crafter "auth-upgrade" "01-01"'
---


# NW-EXECUTE: Atomic Task Execution

**Wave**: EXECUTION_WAVE | **Agent**: Dispatched agent (specified by caller)

## Overview


## Workflow Mode

`/nw-execute` reads `workflow.mode` from `.nwave/config.yaml` and branches on it before doing anything else. <!-- mode-ref-ok -->
Per-mode descriptor + DELIVER phase shape, projected from the mode registry (never hand-written here):

<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice carpaccio loop; no roadmap.json / execution-log.json; AT-completion ledger + commit trailers are the audit.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
<!-- GENERATED:mode-descriptor END -->

- **`atdd_pure`** — `/nw-execute` IS the **per-slice lean cycle**: it executes ONE carpaccio slice. See "ATDD-Pure Per-Slice Lean Cycle" below. <!-- mode-ref-ok -->

### ATDD-Pure Per-Slice Lean Cycle

Under `workflow.mode: atdd_pure`, `/nw-execute` runs one carpaccio slice through the per-slice lean cycle (ADR-028 D6). It does NOT extract roadmap steps and does NOT emit an execution-log — the unit of work is a carpaccio slice, not a roadmap step. The cycle, in order: <!-- mode-ref-ok -->

1. **Carpaccio entry gate** — confirm the slice's acceptance tests exist and are active-RED (run + raise AssertionError — no @skip/@pending, per ADR-GV-001 D6); reject the slice if the carpaccio gate fails.
3. **`B_COVERAGE_CLEANUP`** — coverage-driven dead-code elimination for the slice.
4. **Light slice review** — confirm the implementation satisfies the slice's ATs (a light pass, not the deep adversarial review, which belongs to `/nw-deliver`'s feature-end cycle).
5. **Terminating contract-gate run** — run the whole-tree contract suite (`run_contract_gate.py`); a slice that breaks an earlier slice fails its own terminating run.
6. **`G_COMMIT`** — stage and conventional-commit, then enforce the `G_COMMIT` exit gate.

`E_BATCH_REFACTOR` and the deep review are explicitly NOT part of `/nw-execute` under `atdd_pure`. <!-- mode-ref-ok -->

#### AT-kind dispatch markers (pytest-regression slices)

A carpaccio slice whose acceptance tests are a plain-pytest regression file (`at_kind: pytest-regression`, the mode `/nw-bugfix` slices use — the regression test IS the slice's AT) MUST render two extra markers into the crafter dispatch prompt, so the PreToolUse carpaccio intercept spawns the carpaccio slice gate in pytest-regression mode instead of globbing for `.feature` scenarios:

```
<!-- DES-AT-KIND : pytest-regression -->
<!-- DES-REGRESSION-TEST-FILE : <repo-relative-path-to-the-regression-test> -->
```

A default (Gherkin) slice renders NEITHER marker — its dispatch prompt stays byte-identical to today, and the intercept runs the gate in default Gherkin mode. The intercept parses these via `_parse_at_kind_from_prompt`; absent DES-AT-KIND ⇒ `("gherkin", None)`. A marker-vs-reality mismatch fails LOUD through the carpaccio CLI's existing `.feature`-presence mixed-mode guard. <!-- mode-ref-ok -->

In pytest-regression mode the gate's AT attestation (assertion 5) clears by DEFAULT on the mechanical pair recorded at test-authoring time — `des verify-red-green --record-red --test-file <f>` (fresh `RedObserved` seal, voided by content drift) + `des verify-negative-at --test-file <f> --all-critical` — yielding `SliceCleared at_evidence: mechanical-seal`, no AT-review LLM dispatch (evolution-plan P1.1). A recorded `ATReviewVerdict` (reviewer dispatch + `des record-at-review-verdict`) remains the optional, rigor-profile alternative on this path — and stays the route for Gherkin slices, where the seal path is not yet wired (tracked follow-up).

## Syntax

```
/nw-execute @{agent} "{feature-id}" "{step-id}"
```




## Rigor Profile Integration

Before dispatching the agent, read rigor config from `.nwave/des-config.json` (key: `rigor`). If absent, use standard defaults.

- **`agent_model`**: Pass as `model` parameter to Agent tool. If `"inherit"`, omit `model` (inherits from session).
- **`tdd_phases`**: Modify the TDD_PHASES section in the DES template to match the configured phases. The 3-phase canon (ADR-025) is `[RED, GREEN, COMMIT]`; the lean variant is `[RED, GREEN]`. Legacy 5-phase contract (`[PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT]`) and its lean variant (`[RED_UNIT, GREEN]`) remain supported for audit-log replay of pre-2026-05-07 commits. Remove omitted phases' instructions from the template.
- **`refactor_pass`**: If `false`, skip COMMIT phase refactoring instructions.

## Dispatcher Workflow


1. Parse parameters: agent name|feature ID|step ID
2. Read rigor profile from `.nwave/des-config.json` (default: standard)
5. Extract step fields and invoke Agent tool with DES template below, applying rigor model and phases

## Agent Invocation

@{agent}

Use this DES template verbatim. Fill `{placeholders}` from roadmap. Without DES markers, hooks cannot validate.

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
Skills path: ~/.claude/skills/nw/{agent-name}/
Always load before RED: tdd-methodology.md, quality-framework.md (3-phase canon, ADR-025) — legacy 5-phase logs reference loading at PREPARE.
Load on-demand per phase as specified in your Skill Loading Strategy table.

# TASK_CONTEXT
{step context from roadmap - name|description|acceptance_criteria|test_file|scenario_name|quality_gates|implementation_notes|dependencies|estimated_hours|deliverables|files_to_modify}

# DESIGN_CONTEXT
{Summary of architectural decisions relevant to this step, extracted by the orchestrator from design wave artifacts (architecture-design.md, component-boundaries.md, wave-decisions.md). Include: component structure, dependency boundaries, technology choices, and any design constraints that affect implementation. If no design artifacts exist, write "No design artifacts available — use project conventions."}

# TDD_PHASES
3-phase canon (ADR-025, 2026-05-07). Execute in order:

1. RED - Activate the pre-authored acceptance test (PRIMARY TBU DEFENSE); write PBT unit tests ONLY if the AT cannot reach GREEN without them.
   AT activation: If TASK_CONTEXT includes test_file, locate the active-RED scenario authored by DISTILL (the scaffold already runs and raises AssertionError — DELIVER does NOT re-author ATs, and in atdd_pure there is no @skip marker to remove). Run it — must fail for business logic reason (not import/syntax error). Fail-for-right-reason gate: collected ≥ 1, failures ≥ 1, no collection errors, semantic AssertionError / expected-exception-not-thrown. If the scenario is SKIPPED instead of FAIL → BLOCK (silent dormant seam — see ADR-GV-001 D7; remediation: DISTILL must convert to active-RED). <!-- mode-ref-ok -->
   PORT-TO-PORT PRINCIPLE: The acceptance test exercises the scenario through
   the driving port (application service, orchestrator, CLI handler, API controller),
   not a decomposed helper or internal class. A correctly-written port-to-port test
   makes TBU structurally impossible — if a new function were missing or unwired,
   THIS test stays RED. That is the entire point: GREEN is unreachable without wiring.
   Litmus test: "If I delete the call-site that wires the new code, does this test fail?"
   If no → the test is at the wrong level. Stop and flag to orchestrator (DISTILL re-author needed).
   Conditional unit-test authoring: write PBT unit tests (or integration tests for adapter/infrastructure code — adapters use real infrastructure, never mocked unit tests) ONLY when the AT requires them to reach GREEN. If the AT can pass via direct minimal implementation, skip unit-test authoring inside RED.

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

# TIMEOUT_INSTRUCTION
Target: 30 turns max. If approaching limit, COMMIT current progress.
If GREEN complete (all tests pass), MUST commit before returning — even at turn limit.
```

**Configuration:**
- subagent_type: extracted agent name
- Turn limits are defined in each agent's `maxTurns` frontmatter field (not as a tool parameter)

## Error Handling

- Invalid agent: report available agents
- Dependency failure: explain blocking tasks

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

## Progress Tracking

The invoked agent MUST create a task list from its workflow phases at the start of execution using TaskCreate. Each phase becomes a task with the gate condition as completion criterion. Mark tasks in_progress when starting each phase and completed when the gate passes. This gives the user real-time visibility into progress.

## Success Criteria

- [ ] Agent invoked via Agent tool (dispatcher does not execute the work)

## Next Wave

**Handoff To**: /nw-review for post-execution review
