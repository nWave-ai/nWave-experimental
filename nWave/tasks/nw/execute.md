---
description: Dispatches one unit of DELIVER work to a specialized agent for executable-AT delivery. Active execution is one atdd-pure carpaccio slice.
argument-hint: '[agent] [feature-id] [step-id] - Example: @nw-software-crafter "auth-upgrade" "01-01"'
---


# NW-EXECUTE: Atomic Task Execution

**Wave**: EXECUTION_WAVE | **Agent**: Dispatched agent (specified by caller)

## Overview


## Workflow Mode

`/nw-execute` reads `workflow.mode` from `.nwave/config.yaml` and branches on it before doing anything else. <!-- mode-ref-ok -->
Per-mode descriptor + DELIVER phase shape, projected from the mode registry (never hand-written here):

<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice AT-first loop; AT-completion ledger + commit trailers are the authority.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
<!-- GENERATED:mode-descriptor END -->

- **`atdd_pure`** — `/nw-execute` IS the **per-slice lean cycle**: it executes ONE carpaccio slice. See "ATDD-Pure Per-Slice Lean Cycle" below. <!-- mode-ref-ok -->

### ATDD-Pure Per-Slice Lean Cycle

Under `workflow.mode: atdd_pure`, `/nw-execute` runs one carpaccio slice through the per-slice lean cycle (ADR-028 D6). It reads the feature delta and its `[REF] Slice Plan` row; the unit of work is a carpaccio slice. The cycle, in order: <!-- mode-ref-ok -->

1. **Carpaccio entry gate** — confirm the slice's acceptance tests exist and are active-RED (run + raise AssertionError — no @skip/@pending, per ADR-GV-001 D6); reject the slice if the carpaccio gate fails.
2. **`A_GREEN`** — dispatch the selected crafter with the feature-delta Slice Plan target paths, the pre-authored AT, and the design context; implementation remains AT-first and no test edits are authorized.
3. **EXAMINE** — confirm the implementation satisfies the slice's ATs through the user surface.
4. **Terminating contract-gate run** — run the whole-tree contract suite (`run_contract_gate.py`); a slice that breaks an earlier slice fails its own terminating run.
5. **COMMIT** — stage and conventional-commit, then enforce the commit exit gate.

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
- **`refactor_pass`**: If `false`, omit a separate refactoring dispatch; the fixed delivery floor still requires proportionate cleanup.

## Dispatcher Workflow


1. **Parse** — parse agent name, feature ID, and slice ID. Gate: parameters valid.
2. **Read rigor** — read `.nwave/des-config.json` (default: standard). Gate: active profile resolved.
3. **Dispatch slice** — read the feature delta, select the requested `[REF] Slice Plan` row, and invoke Agent with its declared target paths plus the slice AT and design context. Gate: DES envelope carries one current slice.

## Agent Invocation

@{agent}

Use this DES template verbatim. Fill `{placeholders}` from the feature delta and the selected `[REF] Slice Plan` row. Without DES markers, hooks cannot validate.

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
Before starting, read your skill files for methodology guidance.
Skills path: ~/.claude/skills/nw/{agent-name}/
Always load the test methodology and quality framework appropriate to the target language and paradigm.
Load on demand as the target language and architecture require.

# TASK_CONTEXT
{slice context from feature-delta + selected Slice Plan row - slice-id|value_statement|acceptance_test_file|scenario_name|quality_gates|implementation_notes|dependencies|declared_target_paths}

# DESIGN_CONTEXT
{Summary of architectural decisions relevant to this step, extracted by the orchestrator from design wave artifacts (architecture-design.md, component-boundaries.md, wave-decisions.md). Include: component structure, dependency boundaries, technology choices, and any design constraints that affect implementation. If no design artifacts exist, write "No design artifacts available — use project conventions."}

# DELIVERY_INVARIANTS
- Start from the DISTILL-authored, executable acceptance test. It must fail for the missing behaviour, not for collection, syntax, or fixture errors. If it is not executable, stop and return it to the acceptance designer.
- Implement the smallest design-conformant production change that makes the acceptance test pass through the real driving port. Do not author, weaken, skip, or rewrite its test contract.
- Add focused lower-level tests only where the acceptance contract cannot otherwise drive the behaviour; adapt test style to the target language and paradigm.
- Refactor proportionately after the behaviour is passing. A configured separate refactoring pass changes scheduling, never the requirement for readable, maintainable code.
- Independently review the change and EXAMINE it through the observable user surface when one exists. A non-observable vertical slice is a slicing concern, not an excuse to invent phase evidence.
- Preserve only outcome evidence: executable test results, review or EXAMINE observations, the clean commit, and the declared slice/design boundaries. Do not create a roadmap, execution log, or manual phase history.

# QUALITY_GATES
- The executable acceptance test and the relevant project checks pass before integration.
- The public surface conforms to the declared design and the changed production paths remain inside the declared slice boundary.
- Independent review or EXAMINE supplies observations where the user surface is observable.

# EVIDENCE_INTEGRITY
- Never claim work that was not performed or invent timestamps, verdicts, or phase history.
- Keep evidence tied to the executed test, review or EXAMINE observation, and clean commit; do not manufacture retrospective records.

# BOUNDARY_RULES
- Only modify the selected Slice Plan row's declared target paths

# TIMEOUT_INSTRUCTION
Target: 30 turns max. If approaching the limit, stop at a truthful, recoverable boundary.
Commit only a validated change; do not create a commit solely to mark a workflow stage.
```

**Configuration:**
- subagent_type: extracted agent name
- Turn limits are defined in each agent's `maxTurns` frontmatter field (not as a tool parameter)

## Error Handling

- Invalid agent: report available agents
- Dependency failure: explain blocking tasks

## Resume vs Restart

When subagent times out:

| Observable work state | Action | Rationale |
|-----------------------|--------|-----------|
| Executable AT passes and the change is ready to integrate | Resume | Preserve validated implementation progress. |
| Implementation is partly complete with a clear next change | Resume | Preserve useful context. |
| No validated implementation exists | Restart | Little context is worth replaying. |

Resume costs ~50% more tokens/call due to context replay (measured: 3.7K vs 2.5K tokens/call). For <5 remaining turns, resume is efficient. For 15+ turns, restart is cheaper.

## Examples

```bash
/nw-execute @nw-software-crafter "des-us007-boundary-rules" "02-01"
/nw-execute @nw-researcher "auth-upgrade" "01-01"
/nw-execute @nw-software-crafter "des-us007" "03-01"  # retry after failure
```

## Progress Tracking

The invoked agent MUST create a task list from its workflow phases at the start of execution using TaskCreate. Each phase becomes a task with the gate condition as completion criterion. Mark tasks in_progress when starting each phase and completed when the gate passes. This gives the user real-time visibility into progress.

## Success Criteria

- [ ] Agent invoked via Agent tool (dispatcher does not execute the work)

## Next Wave

**Handoff To**: /nw-review for post-execution review
