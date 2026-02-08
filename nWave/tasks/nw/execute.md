# NW-EXECUTE: Atomic Task Execution

**Wave**: EXECUTION_WAVE
**Agent**: Dispatched agent (specified by caller)

## Overview

Dispatch a single roadmap step to an agent for execution. The orchestrator extracts step context from the roadmap and passes it to the agent so the agent never loads the full roadmap (saves ~97k tokens per step).

## Syntax

```
/nw:execute @{agent} "{project-id}" "{step-id}"
```

## Context Files Required

- `docs/feature/{project-id}/roadmap.yaml` - Orchestrator reads once, extracts step context
- `docs/feature/{project-id}/execution-log.yaml` - Agent appends only (never reads)

## Dispatcher Workflow

1. Parse parameters: agent name, project ID, step ID
2. Validate roadmap and execution-log exist for the project
3. Grep roadmap for `step_id: "{step-id}"` with surrounding context (~50 lines)
4. Extract: name, description, acceptance_criteria, test_file, scenario_line, acceptance_test_scenario, quality_gates, implementation_notes, dependencies, estimated_hours, deliverables
5. Invoke Task tool with extracted context (see Agent Invocation below)

## Agent Invocation

@{agent}

Pass extracted step context as a self-contained prompt. The agent receives everything needed to execute without loading the roadmap.

**DES markers are MANDATORY.** The orchestrator MUST include all 4 DES HTML markers, all 8 mandatory sections, and all 7 TDD phases in the Task prompt. Without these markers, the DES hooks cannot validate the task.

**DES Prompt Template (MANDATORY):**

The orchestrator MUST use this template when building the Task prompt. Fill in all `{placeholders}` with actual values extracted from the roadmap.

```
<!-- DES-VALIDATION : required -->
<!-- DES-PROJECT-ID : {project-id} -->
<!-- DES-STEP-ID : {step-id} -->

# DES_METADATA
Step: {step-id}
Project: {project-id}
Command: /nw:execute

# AGENT_IDENTITY
Agent: {agent-name}

# TASK_CONTEXT
{step context extracted from roadmap - name, description, acceptance_criteria, test_file, scenario_line, acceptance_test_scenario, quality_gates, implementation_notes, dependencies, estimated_hours, deliverables}

# TDD_7_PHASES
Execute these phases in order:
0. PREPARE - Load context, verify prerequisites
1. RED_ACCEPTANCE - Write failing acceptance test
2. RED_UNIT - Write failing unit test
3. GREEN - Minimal code to pass tests
4. REVIEW - Verify quality gates
5. REFACTOR_CONTINUOUS - Improve design, tests stay green
6. COMMIT - Stage and commit with conventional message

# QUALITY_GATES
- All tests pass before COMMIT
- No skipped phases without blocked_by reason
- Coverage maintained or improved

# OUTCOME_RECORDING
After each phase, append to execution-log.yaml:
  - "{step-id}|{phase}|{status}|{data}|{timestamp}"
Status: EXECUTED (data: PASS/FAIL) or SKIPPED (data: reason)

# BOUNDARY_RULES
- Only modify files listed in step's files_to_modify
- Do not load roadmap.yaml
- Do not modify execution-log.yaml structure (append only)

# TIMEOUT_INSTRUCTION
Target: 30 turns maximum. If approaching limit, COMMIT current progress.
```

**Configuration:**
- max_turns: 30
- subagent_type: extracted agent name

## Event Format

Append after each phase using Bash:
```bash
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo '  - "{step-id}|{phase}|{status}|{data}|'$timestamp'"' >> docs/feature/{project-id}/execution-log.yaml
```

Status is EXECUTED (data: PASS, FAIL, UNEXPECTED_GREEN) or SKIPPED (data: NOT_APPLICABLE/APPROVED_SKIP/BLOCKED_BY_DEPENDENCY + reason).

## Error Handling

- Invalid agent: report available agents (nw-researcher, nw-software-crafter, nw-solution-architect, nw-product-owner, nw-acceptance-designer, nw-devop)
- Missing roadmap/execution-log: report path not found
- Step not in roadmap: report available step IDs
- Agent reports dependency failure: explain blocking tasks to user

## Examples

```bash
# Implementation step
/nw:execute @nw-software-crafter "des-us007-boundary-rules" "02-01"

# Research step
/nw:execute @nw-researcher "auth-upgrade" "01-01"

# Retry after failure (agent resumes from last completed phase)
/nw:execute @nw-software-crafter "des-us007" "03-01"
```

## TDD_7_PHASES
<!-- Schema v3.0 — canonical source: TDDPhaseValidator.MANDATORY_PHASES_V3 -->
<!-- Build system injects mandatory phases from step-tdd-cycle-schema.json -->
{{MANDATORY_PHASES}}

## Success Criteria

- [ ] Agent invoked via Task tool (dispatcher does not execute the work)
- [ ] Step context extracted from roadmap and passed in prompt
- [ ] Agent appended phase events to execution-log.yaml
- [ ] Agent did not load roadmap.yaml

## Next Wave

**Handoff To**: /nw:review for post-execution review
**Deliverables**: Updated execution-log.yaml, implementation artifacts, git commits
