# DW-EXECUTE: Atomic Task Execution Engine (Schema v2.0 - Token-Minimal Architecture)

---
## ORCHESTRATOR INVOCATION PROTOCOL (MANDATORY)

**When YOU (orchestrator) delegate this command to an agent via Task tool:**

### CRITICAL: You MUST Extract Full Context from Roadmap

**The orchestrator (YOU) is responsible for:**
1. Loading roadmap.yaml ONCE (102k tokens)
2. Extracting step definition context (~5k tokens)
3. Passing complete context explicitly to sub-agent
4. Sub-agent receives context and does NOT load roadmap (saves 97k tokens per step)

### CORRECT Pattern (full context extraction):
```python
# STEP 1: Read roadmap to find step definition
roadmap_content = Read("docs/feature/{project-id}/roadmap.yaml")

# STEP 2: Extract step context (search for step_id: "{step-id}")
# Extract: name, description, acceptance_criteria, test_file, scenario_line,
#          acceptance_test_scenario, dependencies, estimated_hours,
#          implementation_notes, quality_gates

# STEP 3: Pass extracted context explicitly to agent
Task(
    subagent_type="nw-software-crafter",
    max_turns=30,
    prompt="""<!-- DES-VALIDATION: required -->
<!-- DES-STEP-FILE: docs/feature/{project-id}/steps/{step-id}.json -->
<!-- DES-ORIGIN: command:/nw:execute -->

# DES_METADATA
Step: {step-id}.json
Project: {project-id}
Command: /nw:execute
Schema: v2.0

# AGENT_IDENTITY
You are the software-crafter agent executing a single implementation step.

Task type: execute
PROJECT: {project-id}
STEP: {step-id}

# TASK_CONTEXT

**Step ID**: {step_id}
**Name**: {name}
**Description**: {description}

**Acceptance Criteria**:
{acceptance_criteria}

**Test File**: {test_file}
**Scenario Line**: {scenario_line}
**Acceptance Test Scenario**: {acceptance_test_scenario}

**Implementation Notes**:
{implementation_notes}

**Dependencies**: {dependencies}
**Estimated Hours**: {estimated_hours}

**CRITICAL**: DO NOT load roadmap.yaml (context provided above).

# TDD_7_PHASES

Execute these 7 phases in order:
(Schema v3.0 - MUST stay in sync with TDDPhaseValidator.MANDATORY_PHASES_V3)

0. PREPARE - Remove @skip decorators, verify only 1 scenario enabled
1. RED_ACCEPTANCE - Run acceptance test, expect FAIL for valid reason
2. RED_UNIT - Write failing unit tests before implementation
3. GREEN - Implement minimum code to pass all tests
4. REVIEW - Quality review: SOLID, coverage, criteria
5. REFACTOR_CONTINUOUS - L1 (naming) + L2 (complexity) + L3 (organization) [fast-path if <30 LOC]
6. COMMIT - Final validate + commit

# QUALITY_GATES

{quality_gates}

# OUTCOME_RECORDING (Schema v2.0 - Append-Only Format)

**WRITE ONLY (APPEND-ONLY)**: docs/feature/{project-id}/execution-log.yaml

**CRITICAL**: Use the new Schema v2.0 append-only format (pipe-delimited events).

After EACH phase completion, append ONE event line using Bash:
```bash
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo '  - "{step-id}|{phase}|{status}|{data}|'$timestamp'"' >> docs/feature/{project-id}/execution-log.yaml
```

**Event Format**: "step_id|phase|status|data|timestamp"
- **step_id**: Step identifier (e.g., "01-01")
- **phase**: Phase name (PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, REVIEW, REFACTOR_CONTINUOUS, COMMIT)
- **status**: EXECUTED or SKIPPED
- **data**:
  - For EXECUTED: outcome (PASS, FAIL, UNEXPECTED_GREEN)
  - For SKIPPED: reason with prefix (e.g., "NOT_APPLICABLE:Acceptance tests sufficient")
- **timestamp**: ISO 8601 UTC format (use `date -u` command above)

**Examples**:
```yaml
  - "01-01|PREPARE|EXECUTED|PASS|2026-02-05T22:00:00Z"
  - "01-01|RED_UNIT|SKIPPED|NOT_APPLICABLE:Acceptance tests provide complete coverage|2026-02-05T22:02:00Z"
  - "01-01|COMMIT|EXECUTED|PASS|2026-02-05T22:08:00Z"
```

**NEVER re-read execution-log.yaml** - pure append-only mode (orchestrator provides state in prompt)

# BOUNDARY_RULES

**Allowed modifications**: Only files within the scope of this step.
**Forbidden**: Do NOT modify files from other steps or features.
**Forbidden**: Do NOT continue to other steps after completion.

Scope defined by acceptance criteria above.

# TIMEOUT_INSTRUCTION

Target: 30 turns maximum for this step.
Checkpoints: 10, 20, 25 turns.
If stuck or blocked, exit early and report issue in execution-log.yaml."""
)
```

### Why This Works:
- ✅ Orchestrator loads roadmap.yaml ONCE (102k tokens)
- ✅ Orchestrator extracts task context (~5k tokens) and passes explicitly
- ✅ Sub-agent receives full context, does NOT load roadmap (saves 97k tokens per step)
- ✅ Agent has all information needed to execute
- ✅ No ambiguity about what to do
- ✅ Deterministic execution

### WRONG Patterns (avoid):
```python
# ❌ WRONG - Minimal prompt without context (agent forced to load roadmap)
Task(prompt="Execute: des-us007-boundary-rules step 01-01")

# ❌ WRONG - Including conversation context instead of roadmap context
Task(prompt="""Execute 01-01. As we discussed earlier, focus on parallelization.""")

# ❌ WRONG - Old step file path format (no longer used)
Task(prompt="Execute: docs/feature/auth-upgrade/steps/01-01.json")
```

### Key Principle:
**Orchestrator extracts and passes ALL context explicitly. Agent receives self-contained prompt.**

The token savings (97k per step) ONLY work if orchestrator does the extraction.
If agent has to load roadmap, we waste tokens.

---

## CRITICAL: Agent Invocation Protocol

**YOU ARE THE COORDINATOR** - Do NOT execute the task yourself. Your role is to dispatch to the appropriate agent.

### STEP 1: Extract Agent Parameter

Parse the first argument to extract the agent name:
- User provides: `/nw:execute @nw-researcher "steps/01-01.json"`
- Extract agent name: `nw-researcher` (remove @ prefix)
- Validate agent name is one of: nw-researcher, nw-software-crafter, nw-solution-architect, nw-product-owner, nw-acceptance-designer, nw-devop

### STEP 2: Verify Agent Availability

Before proceeding to Task tool invocation:
- Verify the extracted agent name matches an available agent in the system
- Check agent is not at maximum concurrency
- Confirm agent type is compatible with this command

Valid agents: nw-researcher, nw-software-crafter, nw-solution-architect, nw-product-owner, nw-acceptance-designer, nw-devop

If agent unavailable:
- Return error: "Agent '{agent-name}' is not currently available. Available agents: {list}"
- Suggest alternative agents if applicable

### STEP 3: Extract Project ID and Step ID (NEW ARCHITECTURE)

Extract the second and third arguments:
- Second argument: Project ID (e.g., `"des-us007-boundary-rules"`)
- Third argument: Step ID (e.g., `"01-01"`)

### Parameter Parsing Rules

Apply these rules to ALL extracted parameters:
1. Strip leading and trailing whitespace
2. Remove surrounding quotes (single or double) if present
3. Validate parameter is non-empty after stripping
4. Reject if extra parameters provided beyond expected count

Example for execute.md (NEW ARCHITECTURE):
- Input: `/nw:execute  @nw-software-crafter  "des-us007-boundary-rules"  "01-01"`
- After parsing:
  - agent_name = "nw-software-crafter" (whitespace trimmed)
  - project_id = "des-us007-boundary-rules" (quotes removed)
  - step_id = "01-01" (quotes removed)
- Input: `/nw:execute @nw-software-crafter "des-us007" "01-01" extra`
- Error: "Too many parameters. Expected 3, got 4"

### STEP 4: Pre-Invocation Validation Checklist (NEW ARCHITECTURE)

Before invoking Task tool, verify ALL items:
- [ ] Agent name extracted and validated (not empty)
- [ ] Agent name in valid agent list
- [ ] Agent availability confirmed
- [ ] Project ID extracted and validated (kebab-case format)
- [ ] Step ID extracted and validated (format: XX-XX)
- [ ] Roadmap file exists at `docs/feature/{project-id}/roadmap.yaml`
- [ ] Execution status file exists at `docs/feature/{project-id}/execution-log.yaml`
- [ ] Step ID exists in roadmap (orchestrator verifies via `find_step_in_roadmap()`)
- [ ] Parameters contain no secrets or credentials
- [ ] Parameters within reasonable bounds (e.g., IDs < 100 chars)
- [ ] No user input still has surrounding quotes

**ONLY proceed to Task tool invocation if ALL items above are checked.**

If any check fails, return specific error and stop.

### STEP 5: Context Extraction and Agent Invocation (NEW ARCHITECTURE)

**CRITICAL OPTIMIZATION**: Orchestrator loads roadmap ONCE, extracts task context, passes to sub-agent.
Token savings: 102k - 5k = 97k per step × 16 steps = 1.52M tokens saved.

**Orchestrator Actions BEFORE invoking Task tool**:

```python
# 1. Use Grep to find step definition location in roadmap
grep_result = Grep(
    pattern=f'step_id: "{step_id}"',
    path=f"docs/feature/{project_id}/roadmap.yaml",
    output_mode="content",
    context_lines=50  # Get surrounding context
)

# 2. Read the step section from roadmap
# Extract from grep results:
# - name: (string)
# - description: (multi-line string after >)
# - acceptance_criteria: (list of strings)
# - test_file: (string)
# - scenario_line: (number)
# - acceptance_test_scenario: (string)
# - quality_gates: (dict with acceptance_test_must_fail_first, etc.)
# - implementation_notes: (multi-line string after >)
# - dependencies: (list of step IDs)
# - estimated_hours: (number)
# - suggested_agent: (string)

# 3. Read TDD phases from roadmap header (once, reuse for all steps)
# Located in tdd_phases section at top of roadmap

# 4. Read execution config from roadmap header
# Located in execution_config section

# Result: ~5k tokens of extracted context to pass to agent
```

**Extraction Example**:

```
Step found at line 360:
  - step_id: "03-01"
    name: "Create ScopeValidator class with git diff integration"
    description: >
      Implement ScopeValidator in src/des/validation/scope_validator.py...
    acceptance_criteria:
      - "ScopeValidator executes git diff command successfully"
      - "Modified file list extracted from git output"
    test_file: "tests/des/acceptance/test_boundary_rules.py"
    scenario_line: 357
    ...

Extract these fields and format into agent prompt below.
```

**MANDATORY**: Use the Task tool to invoke the specified agent. Do NOT attempt to execute the task yourself.

Invoke the Task tool with this exact pattern:

```
Task: "You are the {agent-name} agent.

Your specific role for this command: Execute atomic tasks with complete state tracking via execution-log.yaml

Task type: execute

PROJECT: {project-id}
STEP: {step-id}

## TASK CONTEXT (EXTRACTED FROM ROADMAP - DO NOT LOAD ROADMAP)

The orchestrator has extracted the following self-contained context for you:

**Step ID**: {task_context[step_id]}
**Name**: {task_context[name]}
**Description**: {task_context[description]}

**Acceptance Criteria**:
{task_context[acceptance_criteria]}

**Test File**: {task_context[test_file]}
**Scenario Line**: {task_context[scenario_line]}
**Acceptance Test Scenario**: {task_context[acceptance_test_scenario]}

**Quality Gates**:
{task_context[quality_gates]}

**Deliverables**:
{task_context[deliverables]}

**Implementation Notes**:
{task_context[implementation_notes]}

**Dependencies** (must be complete before execution):
{task_context[dependencies]}

**Estimated Hours**: {task_context[estimated_hours]}

## MANDATORY TDD PHASES (from roadmap)

Execute these 7 phases in order:
{format_tdd_phases(task_context[tdd_phases])}

## EXECUTION CONFIGURATION

{task_context[execution_config]}

## STATE TRACKING VIA execution-log.yaml (Schema v2.0)

**CRITICAL**: DO NOT load roadmap.yaml (context provided above).
**WRITE ONLY (APPEND-ONLY)**: docs/feature/{project-id}/execution-log.yaml

Your responsibilities:
1. **DO NOT read execution-log.yaml** - orchestrator provides current state in this prompt
2. Execute each phase in order (PREPARE → RED_ACCEPTANCE → ... → COMMIT)
3. **Append ONE event line** after EACH phase (no batching, no re-reading)
4. Use correct UTC timestamp: `timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")`
5. Use correct event format: `"{step-id}|{phase}|{status}|{data}|{timestamp}"`

## CM-D: Walking Skeleton Principle

In PREPARE phase, verify: entry point exists, acceptance tests invoke entry point (not internal components), component wired into system. If tests import components directly → STOP, report wiring gap.

## INLINE REVIEW CRITERIA (Phase 4: REVIEW)

SOLID principles, coverage >80%, acceptance criteria met, no security vulnerabilities. Also validate post-refactoring quality: tests pass, quality improved, no new duplication. Record findings in execution-log.yaml.

## EXECUTION-LOG.YAML STRUCTURE (Schema v2.0 - Append-Only)

**File Format**: Simple append-only event log (pipe-delimited strings)

```yaml
# Header (written once by orchestrator)
project_id: audit-log-refactor
created_at: '2026-02-05T13:50:00Z'
total_steps: 25

# Events (APPEND-ONLY by agent - one line per phase)
events:
  - "01-01|PREPARE|EXECUTED|PASS|2026-02-05T22:00:00Z"
  - "01-01|RED_ACCEPTANCE|EXECUTED|UNEXPECTED_GREEN|2026-02-05T22:01:00Z"
  - "01-01|RED_UNIT|SKIPPED|NOT_APPLICABLE:Acceptance tests sufficient|2026-02-05T22:02:00Z"
  - "01-01|GREEN|EXECUTED|PASS|2026-02-05T22:03:00Z"
  - "01-01|REVIEW|EXECUTED|PASS|2026-02-05T22:05:00Z"
  - "01-01|REFACTOR_CONTINUOUS|SKIPPED|APPROVED_SKIP:Clean code <30 LOC|2026-02-05T22:06:00Z"
  - "01-01|COMMIT|EXECUTED|PASS|2026-02-05T22:08:00Z"
  # Next step starts here
  - "01-02|PREPARE|EXECUTED|PASS|2026-02-05T22:10:00Z"
```

**Token Efficiency**: ~15 tokens per event (vs ~500 tokens nested format)
- 7 phases × 15 tokens = 105 tokens/step (vs 3,500 tokens)
- 98% reduction in token usage

If you encounter issues:
- Append event with status=EXECUTED and data=FAIL
- Include error details in the data field (e.g., "FAIL:Tests not passing - missing import")
- Return error to orchestrator"
```

**Parameter Substitution**:
- Replace `{agent-name}` with the extracted agent name (e.g., "software-crafter")
- Replace `{project-id}` with the project ID (e.g., "des-us007-boundary-rules")
- Replace `{step-id}` with the step ID (e.g., "01-01")
- Replace `{task_context[...]}` with values from extracted context

### Agent Registry

Valid agents are: nw-researcher, nw-software-crafter, nw-solution-architect, nw-product-owner, nw-acceptance-designer, nw-devop

Note: This list is maintained in sync with the agent registry at `~/.claude/agents/nw/`. If you encounter "agent not found" errors, verify the agent is registered in that location.

Each agent has specific capabilities:
- **nw-researcher**: Information gathering, analysis, documentation
- **nw-software-crafter**: Implementation, testing, refactoring, code quality
- **nw-solution-architect**: System design, architecture decisions, planning
- **nw-product-owner**: Requirements, business analysis, stakeholder alignment
- **nw-acceptance-designer**: Test definition, acceptance criteria, BDD
- **nw-devop**: Deployment, operations, infrastructure, lifecycle management

### Example Invocations (NEW ARCHITECTURE)

**For nw-researcher agent**:
```
Task: "You are the nw-researcher agent.

Your specific role for this command: Execute atomic tasks with complete state tracking via execution-log.yaml

Task type: execute

PROJECT: auth-upgrade
STEP: 01-01

## TASK CONTEXT (EXTRACTED FROM ROADMAP - DO NOT LOAD ROADMAP)

[Orchestrator provides ~5k extracted context here]

[... rest of instructions ...]"
```

**For nw-software-crafter agent**:
```
Task: "You are the nw-software-crafter agent.

Your specific role for this command: Execute atomic tasks with complete state tracking via execution-log.yaml

Task type: execute

PROJECT: des-us007-boundary-rules
STEP: 02-01

## TASK CONTEXT (EXTRACTED FROM ROADMAP - DO NOT LOAD ROADMAP)

[Orchestrator provides ~5k extracted context here]

[... rest of instructions ...]"
```

### Error Handling (NEW ARCHITECTURE)

**Invalid Agent Name**:
- If agent name is not in the valid list, respond with error:
  "Invalid agent name: {name}. Must be one of: nw-researcher, nw-software-crafter, nw-solution-architect, nw-product-owner, nw-acceptance-designer, nw-devop"

**Missing Project Files**:
- If roadmap.yaml not found: "Roadmap not found at docs/feature/{project-id}/roadmap.yaml"
- If execution-log.yaml not found: "Execution status not found at docs/feature/{project-id}/execution-log.yaml"

**Step Not Found in Roadmap**:
- If step ID doesn't exist in roadmap: "Step {step-id} not found in roadmap. Available steps: {list_available_steps()}"

**Dependency Not Met**:
- If the invoked agent reports dependency failures, explain the blocking tasks to the user

---

## Overview

Executes a self-contained atomic task by invoking the specified agent with complete context extracted from the roadmap. Manages state transitions, tracks execution progress, and appends results to execution-log.yaml.

Designed to work with clean context, ensuring consistent quality by giving each agent a fresh start with all necessary information passed by the orchestrator in the prompt.

## Agent Instance Isolation Model (NEW ARCHITECTURE)

Each invocation of the Task tool creates a NEW, INDEPENDENT agent instance. The instance receives:
- Extracted step context from orchestrator (~5k tokens)
- Current execution state passed in prompt (orchestrator reads execution-log.yaml)
- NEVER reads execution-log.yaml itself (WRITE-ONLY for agent)

The agent executes work, APPENDS events to execution-log.yaml (append-only), and terminates. No session state is retained between invocations. State is preserved through execution-log.yaml by orchestrator, not by agent reads. The agent does NOT load the roadmap (orchestrator already extracted context). This isolation ensures clean execution without context degradation from previous instances.

## Usage Examples (NEW ARCHITECTURE - Schema v2.0)

```bash
# Execute a research task
/nw:execute @nw-researcher "auth-upgrade" "01-01"

# Execute implementation task
/nw:execute @nw-software-crafter "des-us007-boundary-rules" "02-01"

# Execute testing task
/nw:execute @nw-devop "auth-upgrade" "04-01"

# Override the suggested agent
/nw:execute @nw-solution-architect "des-us007-boundary-rules" "01-02"

# OLD SIGNATURE (DEPRECATED - DO NOT USE):
# /nw:execute @nw-software-crafter "docs/feature/auth-upgrade/steps/01-01.json"
```

## Complete Workflow Integration

roadmap → split → execute (per step) → review → finalize. See respective command documentation.

## State Transitions

```
TODO → IN_PROGRESS → DONE
         ↓      ↓
      FAILED  IN_REVIEW
         ↓      ↓
      RETRY   REWORK
```

## Context Files Required (Schema v2.0 Architecture)

- `docs/feature/{project-id}/roadmap.yaml` - Loaded by orchestrator ONCE (provides step context)
- `docs/feature/{project-id}/execution-log.yaml` - **WRITE-ONLY** by sub-agent (append-only Schema v2.0)
- Any files referenced in step's `deliverables` field

**CRITICAL**: Agent NEVER reads execution-log.yaml - orchestrator reads and passes state in prompt

---

## Coordinator Success Criteria

Verify the coordinator performed these tasks:
- [ ] Agent name extracted from parameters correctly
- [ ] Agent name validated against known agents
- [ ] File path(s) extracted and validated
- [ ] Absolute path constructed correctly
- [ ] Pre-invocation validation checklist passed
- [ ] Task tool invocation prepared with correct parameters
- [ ] Task tool returned success status
- [ ] User received confirmation of agent invocation

## Agent Execution Success Criteria

The invoked agent must accomplish (Reference Only):
- [ ] Step context received from orchestrator successfully
- [ ] Dependencies verified as complete
- [ ] Agent invoked with full context
- [ ] State transitions properly recorded
- [ ] Execution results captured
- [ ] Execution-log.yaml updated with results (append-only)
- [ ] State history maintained
- [ ] Metrics tracked for analysis

---

## Agent Invocation (Reference Documentation)

The following section documents what the invoked agent will do. **You (the coordinator) do not execute this - the agent does.**

### Primary Task Instructions

**Task**: Receive extracted context from orchestrator and execute the specified task, appending results to execution-log.yaml

**Execution Process**:

#### 1. PRE-EXECUTION PHASE

**Load and Validate**:
```python
1. Receive extracted step context from orchestrator prompt
2. Check for existing reviews
   - If reviews exist with ready_for_execution = false, BLOCK
   - Log any unresolved HIGH severity critiques
3. Verify all required fields present
4. Check dependencies are marked complete
5. Validate agent compatibility with task type
6. Load any referenced files
7. Apply any review recommendations to context
```

**State Update**:
```json
{
  "state": {
    "status": "IN_PROGRESS",
    "assigned_to": "{agent-name}",
    "started_at": "2024-01-15T10:00:00Z",
    "updated": "2024-01-15T10:00:00Z"
  }
}
```

#### 2. EXECUTION PHASE

**Agent receives complete context**:
```
Background: {self_contained_context.background}
Technical Context: {self_contained_context.technical_context}
Prerequisites Completed: {self_contained_context.prerequisites_completed}
Relevant Files: {self_contained_context.relevant_files}

TASK: {task_specification.name}
Description: {task_specification.description}
Motivation: {task_specification.motivation}

INSTRUCTIONS:
{task_specification.detailed_instructions}

ACCEPTANCE CRITERIA:
{task_specification.acceptance_criteria}

Execute this task and provide outputs as specified.
```

### State Management Across Instances (Schema v2.0 Architecture)

The executing agent does not have access to previous invocations' memory. All prior execution state is passed by orchestrator in the invocation prompt:
- **Orchestrator reads** execution-log.yaml events list to extract current state
- **Orchestrator filters** events by step_id and determines completed phases
- **Orchestrator passes** phase completion status as context in prompt
- **Agent receives** prior progress via prompt (NO file read needed)
- **Agent appends** new events to execution-log.yaml (WRITE-ONLY, append mode, never reads)

**Append-Only Format Benefits**:
- Agent never re-reads file (pure append using Bash echo)
- ~15 tokens per event (vs ~500 nested format)
- Orchestrator reads once, filters by step_id with simple grep
- 98% token reduction: 105 tokens/step vs 3,500 tokens/step

This YAML-based state management allows clean handoff between instances without context pollution. The agent receives task context from orchestrator (~5k tokens) and does NOT load roadmap.yaml (102k tokens) nor execution-log.yaml (saves token waste on rereads).

### MANDATORY: Phase Tracking Protocol (7 Phases - Schema v3.0 + v2.0 Format)

The execution-log.yaml uses append-only event format (Schema v2.0) with 7 TDD phases (Schema v3.0).
You MUST append ONE event after EACH phase. **DO NOT BATCH UPDATES** - append immediately after each phase completes.

#### The 7 TDD Phases (Execute in Order) - Schema v3.0

**Single Source of Truth**: execution-log.yaml event format (schema v3.0 phases, v2.0 format)

The phases are (0-6):
0. **PREPARE** - Remove @skip decorators, verify only 1 scenario enabled
1. **RED_ACCEPTANCE** - Run acceptance test, expect FAIL for valid reason
2. **RED_UNIT** - Write failing unit tests before implementation
3. **GREEN** - Implement minimum code to pass all tests (combines GREEN_UNIT + GREEN_ACCEPTANCE validation)
4. **REVIEW** - Quality review: SOLID, coverage, acceptance criteria, post-refactoring quality (expanded scope)
5. **REFACTOR_CONTINUOUS** - Progressive refactoring: L1 (naming) + L2 (complexity) + L3 (organization). Fast-path: if GREEN produced <30 LOC, quick scan only (2-3 min).
6. **COMMIT** - Final validate + commit (absorbs FINAL_VALIDATE metadata checks)
   - **COMMIT phase MUST also record files_modified** in execution-log.yaml (see below)

**NOTE**: L4-L6 architecture refactoring has been moved to orchestrator Phase 2.25 (runs once after all steps complete).

**For non-ATDD steps** (research, infrastructure): Phases 1-4 may be pre-set to `SKIPPED` with `blocked_by: "NOT_APPLICABLE"`.

#### COMMIT Phase: files_modified Tracking (MANDATORY - Schema v2.0)

After creating the git commit, record files modified as separate events in execution-log.yaml:

1. Run: `git diff --name-only HEAD~1`
2. For each modified file, append a FILES_MODIFIED event:
   ```bash
   timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
   # For implementation files (src/ or lib/, excluding __init__.py)
   echo '  - "{step-id}|FILES_MODIFIED|implementation|src/des/file.py|'$timestamp'"' >> execution-log.yaml
   # For test files (tests/)
   echo '  - "{step-id}|FILES_MODIFIED|tests|tests/des/test_file.py|'$timestamp'"' >> execution-log.yaml
   ```

**Example events**:
```yaml
events:
  - "01-01|COMMIT|EXECUTED|PASS|2026-02-05T22:08:00Z"
  - "01-01|FILES_MODIFIED|implementation|src/des/adapters/driven/logging/audit_events.py|2026-02-05T22:08:00Z"
  - "01-01|FILES_MODIFIED|tests|tests/des/unit/adapters/driven/logging/test_audit_events.py|2026-02-05T22:08:00Z"
```

**Format**: `"{step-id}|FILES_MODIFIED|{category}|{file-path}|{timestamp}"`
- **category**: "implementation" or "tests" or "documentation"
- **file-path**: Full path relative to project root

**Why**: This data is used by the orchestrator during mutation testing (Phase 2.5)
to discover the complete implementation scope. Without it, mutation testing may
miss implementation files, creating false confidence in test quality.

#### TDD Checkpoint Commit Strategy (Schema v3.0 - 7 Phases)

3 strategic checkpoints for rollback capability:

| Checkpoint | After Phase | Commit Prefix | Push? |
|------------|-------------|---------------|-------|
| 1. GREEN | 3 (GREEN) | `feat({step-id}): GREEN` | No |
| 2. REVIEW | 4 (REVIEW) | `review({step-id})` | No |
| 3. FINAL | 6 (COMMIT) | `feat({step-id}): DONE` | Yes |

**Each checkpoint**: Append SKIPPED events for pending phases with `CHECKPOINT_PENDING` reason, commit execution-log.yaml + implementation, verify tests pass.

**Example checkpoint events** (after GREEN phase):
```yaml
  - "01-01|GREEN|EXECUTED|PASS|2026-02-05T22:03:00Z"
  - "01-01|REVIEW|SKIPPED|CHECKPOINT_PENDING:Saving GREEN checkpoint|2026-02-05T22:03:00Z"
  - "01-01|REFACTOR_CONTINUOUS|SKIPPED|CHECKPOINT_PENDING:Saving GREEN checkpoint|2026-02-05T22:03:00Z"
  - "01-01|COMMIT|SKIPPED|CHECKPOINT_PENDING:Saving GREEN checkpoint|2026-02-05T22:03:00Z"
```

---

##### Checkpoint Rollback (Schema v2.0)

`git reset HEAD~1` then manually remove checkpoint events from execution-log.yaml (delete lines with CHECKPOINT_PENDING), re-execute from incomplete phase.

##### Checkpoint Rules (Schema v2.0)

Use CHECKPOINT_PENDING (not DEFERRED), append SKIPPED events for pending phases, push only after FINAL, commit execution-log.yaml after each checkpoint.

**Orchestrator** reads execution-log.yaml events, filters by step_id, passes prior progress to agent via prompt. **Agent** receives state, continues from incomplete phases. Agent appends ONE event per phase completion. **CRITICAL**: Agent NEVER reads execution-log.yaml - only appends using Bash echo.

#### If Phase Cannot Be Completed

If a phase cannot be completed for valid reasons:

```json
{
  "status": "SKIPPED",
  "blocked_by": "NOT_APPLICABLE: No unit tests required for documentation-only task"
}
```

**Valid SKIPPED Prefixes** (allow commit):
- `BLOCKED_BY_DEPENDENCY:` - External dependency unavailable
- `NOT_APPLICABLE:` - Phase not applicable for this task type
- `APPROVED_SKIP:` - Explicitly approved by reviewer

**Invalid SKIPPED Prefixes** (block commit):
- `DEFERRED:` - Indicates incomplete work that must be resolved

#### Phase History for Recovery

Each phase entry has a `history` array for tracking re-execution:

```json
{
  "phase_name": "GREEN_UNIT",
  "status": "EXECUTED",
  "history": [
    {
      "status": "EXECUTED",
      "outcome": "FAIL",
      "ended_at": "2024-01-15T10:20:00Z",
      "notes": "Initial attempt failed - edge case not handled"
    },
    {
      "status": "EXECUTED",
      "outcome": "PASS",
      "ended_at": "2024-01-15T10:35:00Z",
      "notes": "Fixed edge case, all tests passing"
    }
  ]
}
```

#### Phase Tracking Violations

These are CRITICAL violations that will cause the pre-commit hook to block commits:

- **Batching updates** - Appending to execution-log.yaml only at the end instead of after each phase
- **Skipping phases** - Leaving phases as NOT_EXECUTED without valid blocked_by
- **Leaving IN_PROGRESS** - Phases left in IN_PROGRESS status indicate abandoned execution
- **Missing outcome** - EXECUTED phases must have outcome (PASS/FAIL)
- **Invalid SKIPPED reason** - SKIPPED without blocked_by or with DEFERRED prefix

#### Validation Before COMMIT Phase (Schema v2.0 - 8 Phases)

Before executing the COMMIT phase (phase 7), verify:
- [ ] All 7 previous phases (0-6) have status "COMPLETED" or valid "SKIPPED"
- [ ] No phase has status "IN_PROGRESS" or "NOT_EXECUTED"
- [ ] All COMPLETED phases have outcome field set
- [ ] All SKIPPED phases have blocked_by with valid prefix
- [ ] No SKIPPED phases have DEFERRED prefix (blocks commit)

```python
# Validation pseudo-code (NEW ARCHITECTURE)
for phase in execution_status["step_checkpoint"]["phases"]:
    if phase["status"] == "NOT_EXECUTED":
        ERROR: f"Phase {phase['phase_name']} not executed"
    elif phase["status"] == "IN_PROGRESS":
        ERROR: f"Phase {phase['phase_name']} left in progress"
    elif phase["status"] == "SKIPPED":
        if not phase.get("blocked_by"):
            ERROR: "SKIPPED without reason"
        if phase["blocked_by"].startswith("DEFERRED:"):
            ERROR: "DEFERRED phases block commit"
    elif phase["status"] == "COMPLETED":
        if not phase.get("outcome"):
            ERROR: "COMPLETED without outcome"
```

#### 3. POST-EXECUTION PHASE

**Success State Update**:
```json
{
  "state": {
    "status": "DONE",
    "assigned_to": "{agent-name}",
    "started_at": "2024-01-15T10:00:00Z",
    "completed_at": "2024-01-15T11:30:00Z",
    "updated": "2024-01-15T11:30:00Z"
  },
  "execution_result": {
    "success": true,
    "outputs": [
      "docs/feature/auth-upgrade/provider-selection.md"
    ],
    "acceptance_criteria_met": [
      {
        "criterion": "Comparison matrix includes 5 providers",
        "met": true,
        "evidence": "Matrix has 6 providers"
      }
    ],
    "metrics": {
      "execution_time_hours": 1.5,
      "tokens_used": 45000
    },
    "agent_notes": "Completed successfully. Added Keycloak as 6th provider."
  }
}
```

**Failure State Update**:
```json
{
  "state": {
    "status": "FAILED",
    "assigned_to": "{agent-name}",
    "started_at": "2024-01-15T10:00:00Z",
    "failed_at": "2024-01-15T10:45:00Z",
    "updated": "2024-01-15T10:45:00Z"
  },
  "execution_result": {
    "success": false,
    "failure_reason": "Unable to access pricing information for 2 providers",
    "partial_completion": true,
    "completed_criteria": ["Comparison matrix created"],
    "blocked_criteria": ["Cost projections incomplete"],
    "recovery_suggestions": [
      "Contact vendor for pricing",
      "Use estimation based on user tiers"
    ],
    "can_retry": true
  }
}
```

**Review Required State**:
```json
{
  "state": {
    "status": "IN_REVIEW",
    "assigned_to": "{agent-name}",
    "started_at": "2024-01-15T10:00:00Z",
    "review_requested_at": "2024-01-15T11:00:00Z",
    "updated": "2024-01-15T11:00:00Z"
  },
  "execution_result": {
    "success": true,
    "outputs_require_review": true,
    "review_reason": "Significant architectural decision needs approval",
    "review_requested_from": "@nw-solution-architect"
  }
}
```

### Error Handling

**Dependency Failures**:
```json
{
  "execution_blocked": {
    "reason": "dependency_not_met",
    "blocking_tasks": ["01-02", "01-03"],
    "message": "Cannot execute until dependencies complete"
  }
}
```

**Context Issues**:
```json
{
  "execution_blocked": {
    "reason": "insufficient_context",
    "missing_information": [
      "Database connection string",
      "API endpoint URL"
    ],
    "resolution": "Update roadmap with missing context and re-extract"
  }
}
```

**Agent Errors**:
```json
{
  "execution_error": {
    "type": "agent_error",
    "error_message": "Agent encountered unexpected error",
    "stack_trace": "...",
    "retry_attempts": 1,
    "max_retries": 3
  }
}
```

### State History Tracking

All state changes are appended to history:
```json
{
  "state_history": [
    {
      "status": "TODO",
      "timestamp": "2024-01-15T09:00:00Z",
      "actor": "system"
    },
    {
      "status": "IN_PROGRESS",
      "timestamp": "2024-01-15T10:00:00Z",
      "actor": "@nw-researcher"
    },
    {
      "status": "IN_REVIEW",
      "timestamp": "2024-01-15T11:00:00Z",
      "actor": "@nw-researcher",
      "reason": "Needs architecture approval"
    },
    {
      "status": "DONE",
      "timestamp": "2024-01-15T14:00:00Z",
      "actor": "@nw-solution-architect",
      "note": "Approved with minor suggestions"
    }
  ]
}
```

### Execution Metrics

Track performance for optimization:
```json
{
  "execution_metrics": {
    "attempts": 1,
    "total_execution_time": 1.5,
    "tokens": {
      "input": 12000,
      "output": 33000,
      "total": 45000
    },
    "cost_estimate": "$0.45",
    "complexity_score": 7,
    "rework_count": 0
  }
}
```

### Integration with Other Commands (NEW ARCHITECTURE)

**Pre-execution Review** (roadmap review):
```bash
# Review roadmap before execution
/nw:review @nw-software-crafter step "docs/feature/des-us007/roadmap.yaml"
# The review validates step definitions
# Execute steps after roadmap approved
/nw:execute @nw-software-crafter "des-us007" "02-01"
```

**Post-execution Review** (implementation review):
```bash
# Execute task
/nw:execute @nw-researcher "auth-upgrade" "01-01"
# Review implementation (checks execution-log.yaml for completion)
/nw:review @nw-software-crafter implementation "docs/feature/auth-upgrade/execution-log.yaml"
```

**Retry After Failure**:
```bash
# Initial attempt fails (orchestrator detects via execution-log.yaml)
/nw:execute @nw-software-crafter "des-us007" "03-01"
# Fix issues, retry (agent resumes from last completed phase)
/nw:execute @nw-software-crafter "des-us007" "03-01"
```

**OLD INTEGRATION PATTERN (DEPRECATED)**:
```bash
# ❌ DO NOT USE - step files no longer exist
/nw:execute @nw-software-crafter "steps/02-01.json"
```

## Output Artifacts (NEW ARCHITECTURE)

- Updated execution-log.yaml with phase completion tracking
- Any outputs specified in acceptance criteria (deliverables)
- Git commits at TDD checkpoints (GREEN, REVIEW, FINAL)
- Execution logs in `docs/feature/{project-id}/logs/{timestamp}-{step-id}.log` (optional)

## Notes

### Clean Context Execution

Each execution starts with a clean context, ensuring:
1. **No contamination** from previous tasks
2. **Consistent quality** across all executions
3. **Predictable behavior** regardless of execution order
4. **Maximum LLM performance** without context degradation

### Parallel Execution Support (NEW ARCHITECTURE)

**IMPORTANT**: With execution-log.yaml as single state file, parallel execution requires careful coordination to avoid conflicts. Each step updates the same execution-log.yaml file.

**Sequential execution recommended** (safest approach):
```bash
# Execute steps in dependency order
/nw:execute @nw-researcher "auth-upgrade" "01-01"  # Wait for completion
/nw:execute @nw-researcher "auth-upgrade" "01-02"  # Then execute next
/nw:execute @nw-software-crafter "auth-upgrade" "02-01"  # Then execute next
```

**Parallel execution possible** (requires file locking):
```bash
# Only for truly independent steps with no shared dependencies
/nw:execute @nw-researcher "auth-upgrade" "01-01" &
/nw:execute @nw-researcher "auth-upgrade" "01-02" &
# WARNING: May cause execution-log.yaml write conflicts
```

**Note**: The old architecture used separate step files (parallel-safe). The new architecture uses shared execution-log.yaml (requires coordination). Trade-off accepted for 94% token reduction.

### State Machine Integrity

The execute command ensures state transitions follow valid paths:
- TODO can only go to IN_PROGRESS
- IN_PROGRESS can go to DONE, FAILED, or IN_REVIEW
- FAILED can go to RETRY
- IN_REVIEW can go to DONE or REWORK
- DONE is terminal (unless explicitly reset)

### Execution Queue Management

For complex projects, executions can be queued:
```json
{
  "execution_queue": {
    "queued_at": "2024-01-15T10:00:00Z",
    "position": 3,
    "estimated_start": "2024-01-15T11:30:00Z"
  }
}
```

This execution engine ensures each atomic task is executed with maximum efficiency and quality, maintaining the integrity of the distributed workflow system while preventing context degradation.
