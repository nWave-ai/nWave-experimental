# Deterministic Execution System (DES) - Design Document

**Version:** 1.0
**Date:** 2026-01-22
**Author:** Lyra (AI Design Assistant)
**Status:** DRAFT - Updated with Empirical Findings (Q1 Resolved)
**Branch:** `determinism`

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [User Objections Analysis](#user-objections-analysis)
3. [Technical Constraints](#technical-constraints)
4. [Proposed Architecture](#proposed-architecture)
5. [Layer 1: Command-Origin Filtering](#layer-1-command-origin-filtering)
6. [Layer 2: Prompt Template Engine](#layer-2-prompt-template-engine)
7. [Layer 3: Execution Lifecycle Management](#layer-3-execution-lifecycle-management)
8. [Layer 4: Validation Gates](#layer-4-validation-gates)
9. [Failure Modes and Recovery](#failure-modes-and-recovery)
10. [Open Questions](#open-questions)
11. [Acceptance Criteria](#acceptance-criteria)
12. [Implementation Roadmap](#implementation-roadmap)

---

## Problem Statement

### The Core Issue

When Claude Code executes multi-step workflows (Outside-In TDD, step-by-step implementations, commit sequences), there is no guarantee that:

1. Each step is actually executed
2. Steps aren't accidentally skipped
3. The reason for skipping is documented
4. The workflow state is persisted reliably
5. **Critical methodology details (like 14-phase TDD) are communicated to sub-agents**

### The Context Dilution Problem

When commands delegate work via the Task tool, important details may be lost:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Command File   │────►│  Orchestrator   │────►│   Sub-Agent     │
│  (execute.md)   │     │  (main Claude)  │     │  (Task tool)    │
│                 │     │                 │     │                 │
│ 14-phase TDD ✓  │     │ May or may not  │     │ May receive     │
│ Quality gates ✓ │     │ include all     │     │ incomplete      │
│ Review criteria │     │ details in      │     │ instructions    │
│ Outcome rules   │     │ Task prompt     │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                      │                      │
         │              INFORMATION LOSS               │
         └─────────────────────────────────────────────┘
```

---

## User Objections Analysis

The following objections were raised and must be addressed:

### Objection 1: Filter Task Tool Invocations

> "We have to be able to filter out the task tool invocations that do not come from commands."

**Analysis:** Not all Task tool invocations require validation. Only those originating from nWave commands (`/nw:*`) should go through pre-invocation validation.

**Solution Required:** Command-origin tagging mechanism to distinguish:
- `/nw:execute @software-crafter "step.json"` → REQUIRES validation
- `Task(prompt="Quick research on X")` → NO validation needed

### Objection 2: Post-Execution Non-Determinism

> "Post-execution is not deterministic - what if the agent crashes, gets stuck, or goes on without returning?"

**Analysis:** Four failure modes identified:

| Failure Mode | Description | Detection Method |
|--------------|-------------|------------------|
| **Crash** | Agent terminates unexpectedly | SubagentStop hook fires with error state |
| **Stuck** | Agent loops indefinitely | Timeout mechanism needed |
| **Runaway** | Agent continues beyond scope | Boundary violation detection |
| **Silent completion** | Agent returns without updating state | Post-execution state verification |

**Solution Required:** Multi-layered protection against all four failure modes.

### Objection 3: SubagentStop Hook Availability

> "Is there a hook for when sub-agents stop?"

**Finding:** YES - `SubagentStop` hook exists in Claude Code.

```json
{
  "hooks": {
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python nWave/hooks/post_subagent_validation.py"
          }
        ]
      }
    ]
  }
}
```

**Solution:** Use SubagentStop hook for post-execution validation.

### Objection 4: Timeout Mechanism

> "Should we include a timeout?"

**Finding:** Task tool does NOT have a built-in timeout parameter.

**Solution Options:**
1. **Prompt-based timeout instruction:** "Complete within 50 turns or return with partial results"
2. **max_turns parameter:** Task tool accepts `max_turns` to limit API round-trips
3. **External timeout:** Background process monitoring (complex, not recommended)

### Objection 5: In-Flight Communication

> "Can we remind the agent while it's working?"

**Finding:** NO - Claude Code has no mechanism to inject messages into a running sub-agent.

From research document: MCP `notifications/message` is received but NOT displayed to the LLM or user.

**Implication:** All instructions MUST be complete upfront. No mid-execution correction possible.

### Objection 6: Pre-Commit Hook Granularity

> "Pre-commit hooks are good BUT not granular enough."

**Analysis:** Pre-commit hooks only fire at commit time. Many issues should be caught earlier:
- Missing phase updates
- Abandoned IN_PROGRESS phases
- Invalid skip reasons

**Trade-off Acknowledged:** More granular checks = more token usage. User decision: "For now let's not think about optimizing consumption."

**Solution:** Implement granular validation, defer optimization.

---

## Technical Constraints

### Claude Code Limitations (Empirically Verified 2026-01-22)

| Capability | Available | Notes |
|------------|-----------|-------|
| SubagentStop hook | ✅ Yes | Fires when sub-agent completes, provides transcript path |
| Task tool timeout | ❌ No | Must use prompt instructions only |
| Interrupt running agent | ❌ No | All instructions must be upfront |
| Message running agent | ❌ No | MCP notifications not displayed |
| max_turns parameter | ❌ **NO** | **CLI-only flag, NOT available in Task tool** |
| Agent transcript access | ✅ Yes | Hook receives `agent_transcript_path` with full prompt |
| Background agent monitoring | ⚠️ Limited | Can check transcript files post-hoc |

### SubagentStop Hook Schema (Empirically Verified)

The SubagentStop hook receives the following JSON input via stdin:

```json
{
  "session_id": "786ebad4-6e5b-42d3-a954-c1df6e6f25b7",
  "transcript_path": "/home/user/.claude/projects/.../session.jsonl",
  "cwd": "/path/to/project",
  "permission_mode": "bypassPermissions",
  "hook_event_name": "SubagentStop",
  "stop_hook_active": false,
  "agent_id": "ab7af5b",
  "agent_transcript_path": "/home/user/.claude/projects/.../subagents/agent-ab7af5b.jsonl"
}
```

| Field | Type | DES Usage |
|-------|------|-----------|
| `session_id` | string | Track parent session |
| `transcript_path` | string | Parent session transcript |
| `cwd` | string | Verify working directory |
| `permission_mode` | string | N/A |
| `hook_event_name` | string | Verify event type |
| `stop_hook_active` | boolean | N/A |
| **`agent_id`** | string | **Match to Task tool return value** |
| **`agent_transcript_path`** | string | **KEY: Extract prompt from here** |

**Agent Transcript Format (JSONL):**

```jsonl
{"type":"user","message":{"role":"user","content":"<FULL PROMPT HERE>"},...}
{"type":"assistant","message":{"role":"assistant","content":[...]},...}
{"type":"progress","data":{"type":"hook_progress",...},...}
```

The first line (type="user") contains the original prompt, which can be searched for DES markers.

### Design Implications

1. **Front-loaded validation:** Since we can't correct mid-execution, prompts MUST be complete
2. **Prompt-based discipline:** No max_turns available; rely on explicit timeout instructions in prompt
3. **Post-hoc verification:** SubagentStop hook + transcript parsing for validation
4. **Fail-safe defaults:** If validation fails, block further execution

---

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DETERMINISTIC EXECUTION SYSTEM                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ LAYER 1: COMMAND-ORIGIN FILTERING                                       ││
│  │ ─────────────────────────────────────────────────────────────────────── ││
│  │ • Tag Task invocations with origin (command vs ad-hoc)                  ││
│  │ • Only command-origin tasks require validation                          ││
│  │ • Pass-through for non-command Task calls                               ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ LAYER 2: PROMPT TEMPLATE ENGINE                                         ││
│  │ ─────────────────────────────────────────────────────────────────────── ││
│  │ • Mandatory templates per command type                                  ││
│  │ • Template validation BEFORE Task invocation                            ││
│  │ • Required sections: TDD_14_PHASES, QUALITY_GATES, OUTCOME_RECORDING    ││
│  │ • Machine-readable structure for validation                             ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ LAYER 3: EXECUTION LIFECYCLE MANAGEMENT                                 ││
│  │ ─────────────────────────────────────────────────────────────────────── ││
│  │ • max_turns limit on Task invocations                                   ││
│  │ • Timeout instructions in prompt                                        ││
│  │ • Boundary rules to prevent scope creep                                 ││
│  │ • State machine for valid transitions                                   ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ LAYER 4: VALIDATION GATES                                               ││
│  │ ─────────────────────────────────────────────────────────────────────── ││
│  │ GATE 1: Pre-Invocation    → Template completeness check                 ││
│  │ GATE 2: SubagentStop Hook → Post-execution state verification           ││
│  │ GATE 3: Pre-Commit Hook   → Final validation before commit (existing)   ││
│  │ GATE 4: Audit Trail       → Immutable log of all state transitions      ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### DES Wiring and Integration Architecture

The following diagram shows how DES components integrate with Claude Code infrastructure and nWave commands:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CLAUDE CODE INFRASTRUCTURE                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐           │
│  │   Session    │────────►│  Task Tool   │────────►│  Sub-Agent   │           │
│  │  Orchestrator│         │  Invocation  │         │   Execution  │           │
│  └──────────────┘         └──────┬───────┘         └──────┬───────┘           │
│         │                         │                         │                   │
│         │                         │                         │                   │
│         ▼                         ▼                         ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                      DES INTEGRATION POINTS                             │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │                                                                          │   │
│  │  [IP-1] Command Execution                                               │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │   │
│  │  │ /nw:execute @agent "step.json"                                   │  │   │
│  │  │    ↓                                                              │  │   │
│  │  │ Load Template: execute-step.template.md                          │  │   │
│  │  │    ↓                                                              │  │   │
│  │  │ Inject: DES-ORIGIN, DES-STEP-FILE, DES-VALIDATION markers        │  │   │
│  │  │    ↓                                                              │  │   │
│  │  │ GATE 1: validate_before_task_invocation()                        │  │   │
│  │  │    ├─► Check: Mandatory sections present?                        │  │   │
│  │  │    ├─► Check: 14 TDD phases listed?                              │  │   │
│  │  │    ├─► Check: TIMEOUT_INSTRUCTION exists?                        │  │   │
│  │  │    └─► Check: Step file valid JSON?                              │  │   │
│  │  │         │                                                         │  │   │
│  │  │         ├─ VALID ──► Invoke Task(prompt=...) ──────┐            │  │   │
│  │  │         │                                            │            │  │   │
│  │  │         └─ INVALID ─► BLOCK + Error Report          │            │  │   │
│  │  └─────────────────────────────────────────────────────┼────────────┘  │   │
│  │                                                         │               │   │
│  │  [IP-2] Turn Budget Monitoring (Prompt-Based)          │               │   │
│  │  ┌──────────────────────────────────────────────────────┼───────────┐  │   │
│  │  │ Agent Self-Monitors Turn Count:                      │           │  │   │
│  │  │   Turn 30: ⚠️ 60% warning                            │           │  │   │
│  │  │   Turn 40: ⚠️ 80% warning                            │           │  │   │
│  │  │   Turn 48: 🚨 95% critical warning                   │           │  │   │
│  │  │                                                       │           │  │   │
│  │  │ Agent Can Request Extension:                         │           │  │   │
│  │  │   Update step file with extension_request object     │           │  │   │
│  │  │   Continue with extended budget                      │           │  │   │
│  │  └───────────────────────────────────────────────────────┘           │  │   │
│  │                                                         │               │   │
│  │  [IP-3] Phase State Tracking                           │               │   │
│  │  ┌──────────────────────────────────────────────────────┼───────────┐  │   │
│  │  │ Agent Updates: docs/feature/X/steps/NN-MM.json      │           │  │   │
│  │  │                                                       │           │  │   │
│  │  │ phase_execution_log[N]:                              │           │  │   │
│  │  │   status: IN_PROGRESS → EXECUTED/SKIPPED/FAILED     │           │  │   │
│  │  │   started_at, ended_at, duration_minutes             │           │  │   │
│  │  │   outcome, outcome_details                           │           │  │   │
│  │  │   artifacts_created, test_results                    │           │  │   │
│  │  │                                                       │           │  │   │
│  │  │ FSM enforces valid transitions per step-execution-fsm.yaml       │  │   │
│  │  └───────────────────────────────────────────────────────┘           │  │   │
│  │                                                         │               │   │
│  └─────────────────────────────────────────────────────────┼───────────────┘   │
│                                                            │                   │
│                                                            ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    SUB-AGENT COMPLETION HANDLING                        │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │                                                                          │   │
│  │  [IP-4] SubagentStop Hook Trigger                                       │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │   │
│  │  │ Claude Code triggers: SubagentStop hook                         │  │   │
│  │  │    ↓                                                             │  │   │
│  │  │ Hook receives stdin JSON:                                        │  │   │
│  │  │   {                                                              │  │   │
│  │  │     "session_id": "...",                                         │  │   │
│  │  │     "agent_id": "...",                                           │  │   │
│  │  │     "agent_transcript_path": "/path/to/agent.jsonl"             │  │   │
│  │  │   }                                                              │  │   │
│  │  │    ↓                                                             │  │   │
│  │  │ GATE 2: post_subagent_validation.py                             │  │   │
│  │  │    ├─► Extract step file path from transcript                   │  │   │
│  │  │    ├─► Load step file JSON                                      │  │   │
│  │  │    ├─► Check: Any phases IN_PROGRESS? (abandoned)               │  │   │
│  │  │    ├─► Check: EXECUTED phases have outcome?                     │  │   │
│  │  │    ├─► Check: SKIPPED phases have valid blocked_by?             │  │   │
│  │  │    └─► Check: Task state consistent with phases?                │  │   │
│  │  │         │                                                        │  │   │
│  │  │         ├─ VALID ──► Log SUCCESS to audit trail                 │  │   │
│  │  │         └─ ERRORS ─► Log ERRORS + exit(1) (block workflow)      │  │   │
│  │  └──────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                            │                   │
│                                                            ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                       COMMIT-TIME VALIDATION                            │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │                                                                          │   │
│  │  [IP-5] Pre-Commit Hook                                                 │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │   │
│  │  │ Git triggers: pre-commit hook                                    │  │   │
│  │  │    ↓                                                             │  │   │
│  │  │ GATE 3: pre_commit_tdd_phases.py                                │  │   │
│  │  │    ├─► Scan: All step files in commit                           │  │   │
│  │  │    ├─► Check: 14 phases present?                                │  │   │
│  │  │    ├─► Check: No phases IN_PROGRESS?                            │  │   │
│  │  │    ├─► Check: No phases NOT_EXECUTED (unless SKIPPED valid)?    │  │   │
│  │  │    ├─► Check: No DEFERRED blocks?                               │  │   │
│  │  │    └─► Cross-check: audit-YYYY-MM-DD.log for SubagentStop errors│  │   │
│  │  │         │                                                        │  │   │
│  │  │         ├─ VALID ──► Allow commit                               │  │   │
│  │  │         └─ INVALID ─► BLOCK commit + detailed error report      │  │   │
│  │  └──────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                         AUDIT TRAIL LOGGING                             │   │
│  ├─────────────────────────────────────────────────────────────────────────┤   │
│  │                                                                          │   │
│  │  [IP-6] Immutable Event Log                                             │   │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │   │
│  │  │ All integration points write to:                                │  │   │
│  │  │   docs/feature/X/steps/audit-YYYY-MM-DD.log                     │  │   │
│  │  │                                                                  │  │   │
│  │  │ Event Types:                                                    │  │   │
│  │  │   TASK_INVOCATION_VALIDATED [IP-1]                             │  │   │
│  │  │   TASK_INVOCATION_REJECTED [IP-1]                              │  │   │
│  │  │   PHASE_STARTED [IP-3]                                          │  │   │
│  │  │   PHASE_COMPLETED [IP-3]                                        │  │   │
│  │  │   EXTENSION_REQUESTED [IP-2]                                    │  │   │
│  │  │   SUBAGENT_STOP_VALIDATION [IP-4]                              │  │   │
│  │  │   COMMIT_VALIDATION_PASSED [IP-5]                              │  │   │
│  │  │   COMMIT_VALIDATION_FAILED [IP-5]                              │  │   │
│  │  │                                                                  │  │   │
│  │  │ Format: JSONL (one event per line)                             │  │   │
│  │  │ Rotation: Daily (prevents unbounded growth)                    │  │   │
│  │  └──────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

Integration Point Summary:

| ID | Integration Point | Component | Timing | Action |
|----|-------------------|-----------|--------|--------|
| IP-1 | Pre-Invocation Validation | validate_before_task_invocation() | Before Task() | BLOCKS if invalid |
| IP-2 | Turn Budget Monitoring | Agent self-regulation | During execution | Warns at thresholds |
| IP-3 | Phase State Tracking | Agent updates step file | During execution | FSM enforces transitions |
| IP-4 | SubagentStop Hook | post_subagent_validation.py | After agent completes | BLOCKS workflow on errors |
| IP-5 | Pre-Commit Hook | pre_commit_tdd_phases.py | Before git commit | BLOCKS commit if invalid |
| IP-6 | Audit Trail | audit.py | All events | Immutable event log |
```

---

## Layer 1: Command-Origin Filtering

### Problem

Not all Task tool invocations should require validation. We need to distinguish:

```python
# REQUIRES VALIDATION - originated from /nw:execute command
Task(
    subagent_type="software-crafter",
    prompt="...",
    # origin: "command:/nw:execute"  ← How to tag this?
)

# NO VALIDATION - ad-hoc exploration
Task(
    subagent_type="Explore",
    prompt="Find all files related to authentication",
    # origin: "ad-hoc"
)
```

### Solution: Origin Marker in Prompt

Since we cannot modify the Task tool itself, we embed an origin marker in the prompt:

```markdown
<!-- DES-ORIGIN: command:/nw:execute -->
<!-- DES-STEP-FILE: docs/feature/auth/steps/01-01.json -->
<!-- DES-VALIDATION: required -->

You are the software-crafter agent...
```

### Validation Logic

```python
# nWave/hooks/pre_task_validation.py

def should_validate(prompt: str) -> bool:
    """Check if this Task invocation requires DES validation."""
    return "<!-- DES-VALIDATION: required -->" in prompt

def extract_origin(prompt: str) -> dict:
    """Extract DES metadata from prompt."""
    import re
    origin = re.search(r'<!-- DES-ORIGIN: (.+?) -->', prompt)
    step_file = re.search(r'<!-- DES-STEP-FILE: (.+?) -->', prompt)
    return {
        "origin": origin.group(1) if origin else "ad-hoc",
        "step_file": step_file.group(1) if step_file else None,
        "requires_validation": should_validate(prompt)
    }
```

### Command Registration

Commands that require validation:

| Command | Validation Required | Step File |
|---------|---------------------|-----------|
| `/nw:execute` | ✅ Yes | Yes |
| `/nw:develop` | ✅ Yes (for sub-tasks) | Yes |
| `/nw:baseline` | ⚠️ Partial | No |
| `/nw:roadmap` | ⚠️ Partial | No |
| `/nw:split` | ⚠️ Partial | No |
| `/nw:review` | ❌ No | No |
| `/nw:research` | ❌ No | No |

---

## Layer 2: Prompt Template Engine

### Template Structure

```
nWave/templates/prompt-templates/
├── execute-step.template.md      # For /nw:execute - FULL validation
├── develop-orchestrate.template.md
├── baseline-create.template.md
├── _validation-schema.json       # Template validation rules
└── _section-definitions.yaml     # Canonical section definitions
```

### Mandatory Sections for Step Execution

```yaml
# _section-definitions.yaml
execute_step:
  mandatory_sections:
    - DES_METADATA           # Origin, step file, validation flag
    - AGENT_IDENTITY         # Who the agent is
    - TASK_CONTEXT           # What they're working on
    - TDD_14_PHASES          # Complete phase list with criteria
    - QUALITY_GATES          # G1-G6 gate definitions
    - OUTCOME_RECORDING      # How to record results
    - BOUNDARY_RULES         # Scope limitations
    - TIMEOUT_INSTRUCTION    # Turn limit and early-exit protocol

  optional_sections:
    - REVIEW_CRITERIA        # For phases 7 and 12
    - RECOVERY_INSTRUCTIONS  # If phase fails
```

### Template Validation Script

```python
# nWave/hooks/validate_prompt_template.py

import re
from pathlib import Path
import yaml

MANDATORY_SECTIONS = [
    "DES_METADATA",
    "AGENT_IDENTITY",
    "TASK_CONTEXT",
    "TDD_14_PHASES",
    "QUALITY_GATES",
    "OUTCOME_RECORDING",
    "BOUNDARY_RULES",
    "TIMEOUT_INSTRUCTION"
]

def validate_prompt(prompt: str) -> tuple[bool, list[str]]:
    """
    Validate that a DES-tagged prompt contains all mandatory sections.

    Returns:
        (is_valid, list_of_errors)
    """
    # Skip validation for non-DES prompts
    if "<!-- DES-VALIDATION: required -->" not in prompt:
        return True, []

    errors = []

    # Check each mandatory section
    for section in MANDATORY_SECTIONS:
        # Look for section header in various formats
        patterns = [
            f"## {{{section}}}",           # Template placeholder
            f"## {section}",               # Direct header
            f"### {section}",              # Subsection
            f"<!-- SECTION: {section} -->", # Comment marker
        ]

        found = any(p in prompt for p in patterns)
        if not found:
            errors.append(f"MISSING: Mandatory section '{section}' not found")

    # Validate TDD phases are complete
    if "TDD_14_PHASES" in prompt or "## TDD" in prompt:
        required_phases = [
            "PREPARE", "RED_ACCEPTANCE", "RED_UNIT", "GREEN_UNIT",
            "CHECK_ACCEPTANCE", "GREEN_ACCEPTANCE", "REVIEW",
            "REFACTOR_L1", "REFACTOR_L2", "REFACTOR_L3", "REFACTOR_L4",
            "POST_REFACTOR_REVIEW", "FINAL_VALIDATE", "COMMIT"
        ]
        for phase in required_phases:
            if phase not in prompt:
                errors.append(f"INCOMPLETE: TDD phase '{phase}' not mentioned")

    # Validate timeout instruction exists
    timeout_patterns = ["max_turns", "turn limit", "TIMEOUT", "complete within"]
    if not any(p.lower() in prompt.lower() for p in timeout_patterns):
        errors.append("MISSING: No timeout/turn-limit instruction found")

    return len(errors) == 0, errors


def validate_before_task_invocation(prompt: str, step_file_path: str = None) -> dict:
    """
    Full pre-invocation validation.

    Returns:
        {
            "valid": bool,
            "errors": list[str],
            "warnings": list[str],
            "metadata": dict
        }
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "metadata": {}
    }

    # Extract metadata
    result["metadata"] = extract_origin(prompt)

    # Skip if not DES-tagged
    if not result["metadata"]["requires_validation"]:
        result["warnings"].append("Prompt not DES-tagged - validation skipped")
        return result

    # Validate prompt structure
    is_valid, errors = validate_prompt(prompt)
    if not is_valid:
        result["valid"] = False
        result["errors"].extend(errors)

    # Validate step file exists and is readable
    if step_file_path:
        step_path = Path(step_file_path)
        if not step_path.exists():
            result["valid"] = False
            result["errors"].append(f"Step file not found: {step_file_path}")
        else:
            # Validate step file structure
            try:
                import json
                with open(step_path) as f:
                    step_data = json.load(f)

                # Check required fields
                required_fields = ["task_id", "project_id", "tdd_cycle"]
                for field in required_fields:
                    if field not in step_data:
                        result["valid"] = False
                        result["errors"].append(f"Step file missing field: {field}")

                # Check phase_execution_log has 14 phases
                if "tdd_cycle" in step_data:
                    phases = step_data["tdd_cycle"].get("phase_execution_log", [])
                    if len(phases) != 14:
                        result["valid"] = False
                        result["errors"].append(
                            f"Step file has {len(phases)} phases, expected 14"
                        )
            except json.JSONDecodeError as e:
                result["valid"] = False
                result["errors"].append(f"Step file invalid JSON: {e}")

    return result
```

---

## Layer 3: Execution Lifecycle Management

### 4.3 Prompt Structure: TIMEOUT_INSTRUCTION Section

Since Claude Code Task tool has no built-in timeout and **max_turns is NOT available** (CLI-only parameter), we rely on prompt-based discipline with proactive warning thresholds and extension request capabilities.

> ⚠️ **CRITICAL CORRECTION:** The original design assumed `max_turns` was available for Task tool. Empirical testing confirmed this is FALSE - max_turns is a CLI flag only, not a Task tool parameter.

#### TIMEOUT_INSTRUCTION Section Specification

The TIMEOUT_INSTRUCTION section is a **mandatory component** of all DES-validated prompts for command-origin Task invocations. This section implements turn discipline through agent self-regulation.

**When Included:**
- ✅ **REQUIRED:** All Task invocations with `<!-- DES-VALIDATION: required -->` marker
- ✅ **REQUIRED:** Commands: `/nw:execute`, `/nw:develop` (for sub-tasks)
- ❌ **NOT INCLUDED:** Ad-hoc Task invocations without DES markers
- ❌ **NOT INCLUDED:** Commands: `/nw:review`, `/nw:research` (non-validated commands)

**Required Elements (AC-US-006-02):**

The TIMEOUT_INSTRUCTION section must contain exactly 4 required elements:

1. **Base Turn Budget**: Standard allocation (50 turns for step execution)
   - Clearly states the initial turn budget
   - Establishes baseline expectations for completion
   - Example: "Base Turn Budget: 50 turns (standard allocation for step execution)"

2. **Warning Thresholds**: Progressive warnings at 60%, 80%, and 95% of budget
   - Three specific checkpoints with exact turn numbers
   - Each warning escalates in severity and urgency
   - Includes recommended actions at each threshold
   - Example:
     ```
     - Turn 30 (60%): "⚠️ PROGRESS CHECK: 30/50 turns used."
     - Turn 40 (80%): "⚠️ TIME WARNING: 40/50 turns used."
     - Turn 48 (95%): "🚨 CRITICAL: 48/50 turns used."
     ```

3. **Extension Request Protocol**: Mechanism for requesting additional turns when needed
   - Structured format for extension requests
   - Required fields: requested_turns, reason, current_phase, estimated_completion_turn, critical_path
   - Documented in step file execution_result.extension_request
   - Includes at least 3 realistic examples (test debugging, complex refactoring, build issues)
   - Example structure:
     ```json
     {
       "extension_request": {
         "requested_turns": 20,
         "reason": "Specific justification",
         "current_phase": "PHASE_NAME",
         "estimated_completion_turn": 65,
         "critical_path": "Work requiring extension"
       }
     }
     ```

4. **Early Exit Protocol**: Procedure for graceful termination when completion is not feasible
   - Clear steps for saving progress
   - Setting phase to IN_PROGRESS with detailed notes
   - Setting task state to PARTIAL with recovery_suggestions
   - Explicit instruction to return immediately
   - Lists prohibited behaviors (infinite loops, ignoring warnings, etc.)

**Acceptance Criteria Reference:**

This specification satisfies the following acceptance criteria from US-006:

- **AC-US-006-01**: TIMEOUT_INSTRUCTION section included in validated prompts
- **AC-US-006-02**: Section contains 4 required elements with examples
- **AC-US-006-03**: Warning thresholds at 60%, 80%, 95% with actionable guidance
- **AC-US-006-04**: Extension request protocol with structured format and 3+ examples
- **AC-US-006-05**: Early exit protocol with step-by-step procedure

**Example TIMEOUT_INSTRUCTION Section Output:**

The following shows a complete TIMEOUT_INSTRUCTION section as it appears in a rendered prompt:

```markdown
## TIMEOUT_INSTRUCTION

**Base Turn Budget:** 50 turns (standard allocation for step execution)

**Warning Thresholds:**

You will receive internal progress warnings at:
- **Turn 30 (60% of budget)**: "⚠️ PROGRESS CHECK: 30/50 turns used. Expected completion by turn 40."
- **Turn 40 (80% of budget)**: "⚠️ TIME WARNING: 40/50 turns used. Consider extension request or early exit."
- **Turn 48 (95% of budget)**: "🚨 CRITICAL: 48/50 turns used. Complete current phase and exit OR request extension NOW."

**Extension Request Protocol:**

If you need additional turns beyond the 50-turn base budget:

1. **Assess Progress**: Determine exact work remaining
2. **Request Extension**: Include in step file update:
   ```json
   {
     "execution_result": {
       "extension_request": {
         "requested_turns": 20,
         "reason": "Complex integration test debugging requires additional investigation",
         "current_phase": "GREEN_UNIT",
         "estimated_completion_turn": 65,
         "critical_path": "Debugging async timeout in payment gateway integration"
       }
     }
   }
   ```
3. **Continue Work**: Proceed with extended budget after request

**Extension Request Examples:**

Example 1 - Test Debugging:
```json
{
  "extension_request": {
    "requested_turns": 15,
    "reason": "Unit test failures require investigating mock setup and state isolation",
    "current_phase": "GREEN_UNIT",
    "estimated_completion_turn": 60,
    "critical_path": "Fix 3 failing unit tests related to state management"
  }
}
```

Example 2 - Complex Refactoring:
```json
{
  "extension_request": {
    "requested_turns": 25,
    "reason": "Refactoring L3-L4 discovered tight coupling requiring broader architectural changes",
    "current_phase": "REFACTOR_L3",
    "estimated_completion_turn": 70,
    "critical_path": "Extract repository interface and update 5 dependent classes"
  }
}
```

Example 3 - Build/Environment Issues:
```json
{
  "extension_request": {
    "requested_turns": 10,
    "reason": "Dependency resolution conflicts in package manager require careful debugging",
    "current_phase": "PREPARE",
    "estimated_completion_turn": 58,
    "critical_path": "Resolve conflicting versions of logging framework"
  }
}
```

**Early Exit Protocol:**

If extension is not viable or you cannot complete reasonably:
1. Save all current progress to step file
2. Set current phase to IN_PROGRESS with detailed notes
3. Return with status: "PARTIAL_COMPLETION"
4. Include remaining work in execution_result.recovery_suggestions

**DO NOT:**
- Loop indefinitely trying to fix unfixable issues
- Continue past your scope without extension request
- Ignore progress warnings
- Request extension without clear justification
```

This example demonstrates all 4 required elements integrated into a complete, ready-to-use prompt section.

#### Turn Discipline Implementation

The DES implements turn discipline through three coordinated mechanisms:

#### Mechanism 1: Prompt-Based Turn Awareness (PRIMARY)

Since we cannot enforce turn limits programmatically, agents must self-regulate based on explicit instructions with progressive warnings.

Include in every DES-validated prompt:

```markdown
## TIMEOUT_INSTRUCTION

**Base Turn Budget:** 50 turns (standard allocation for step execution)

**Warning Thresholds:**

You will receive internal progress warnings at:
- **Turn 30 (60% of budget)**: "⚠️ PROGRESS CHECK: 30/50 turns used. Expected completion by turn 40."
- **Turn 40 (80% of budget)**: "⚠️ TIME WARNING: 40/50 turns used. Consider extension request or early exit."
- **Turn 48 (95% of budget)**: "🚨 CRITICAL: 48/50 turns used. Complete current phase and exit OR request extension NOW."

**Extension Request Protocol:**

If you need additional turns beyond the 50-turn base budget:

1. **Assess Progress**: Determine exact work remaining
2. **Request Extension**: Include in step file update:
   ```json
   {
     "execution_result": {
       "extension_request": {
         "requested_turns": 20,
         "reason": "Complex integration test debugging requires additional investigation",
         "current_phase": "GREEN_UNIT",
         "estimated_completion_turn": 65,
         "critical_path": "Debugging async timeout in payment gateway integration"
       }
     }
   }
   ```
3. **Continue Work**: Proceed with extended budget after request

**Extension Request Examples:**

Example 1 - Test Debugging:
```json
{
  "extension_request": {
    "requested_turns": 15,
    "reason": "Unit test failures require investigating mock setup and state isolation",
    "current_phase": "GREEN_UNIT",
    "estimated_completion_turn": 60,
    "critical_path": "Fix 3 failing unit tests related to state management"
  }
}
```

Example 2 - Complex Refactoring:
```json
{
  "extension_request": {
    "requested_turns": 25,
    "reason": "Refactoring L3-L4 discovered tight coupling requiring broader architectural changes",
    "current_phase": "REFACTOR_L3",
    "estimated_completion_turn": 70,
    "critical_path": "Extract repository interface and update 5 dependent classes"
  }
}
```

Example 3 - Build/Environment Issues:
```json
{
  "extension_request": {
    "requested_turns": 10,
    "reason": "Dependency resolution conflicts in package manager require careful debugging",
    "current_phase": "PREPARE",
    "estimated_completion_turn": 58,
    "critical_path": "Resolve conflicting versions of logging framework"
  }
}
```

**Early Exit Protocol:**

If extension is not viable or you cannot complete reasonably:
1. Save all current progress to step file
2. Set current phase to IN_PROGRESS with detailed notes
3. Return with status: "PARTIAL_COMPLETION"
4. Include remaining work in execution_result.recovery_suggestions

**DO NOT:**
- Loop indefinitely trying to fix unfixable issues
- Continue past your scope without extension request
- Ignore progress warnings
- Request extension without clear justification
```

#### Mechanism 2: Pre-Execution Stale Check (BACKUP)

Session-scoped stale detection runs **automatically before each `/nw:execute`** to catch abandoned work from previous sessions. No persistent daemon required - terminates with the session.

**Design Principles:**
- **Zero dependencies:** Pure file scanning, no databases or external services
- **Session-scoped:** Runs during work, closes when user stops
- **Blocking:** Stale work must be resolved before new execution starts

```python
# nWave/utils/stale_detection.py
from datetime import datetime, timedelta
from pathlib import Path
import json

def check_for_stale_executions(
    project_dir: str,
    threshold_minutes: int = 30
) -> list[dict]:
    """
    Pre-execution stale check - runs before /nw:execute.
    Scans step files for abandoned IN_PROGRESS phases.

    Returns list of stale executions to resolve.
    """
    stale = []
    threshold = datetime.now() - timedelta(minutes=threshold_minutes)

    for step_file in Path(project_dir).rglob("steps/*.json"):
        data = json.loads(step_file.read_text())
        for phase in data.get("tdd_cycle", {}).get("phase_execution_log", []):
            if phase.get("status") == "IN_PROGRESS":
                started = datetime.fromisoformat(phase.get("started_at", ""))
                if started < threshold:
                    stale.append({
                        "step_file": str(step_file),
                        "phase": phase.get("phase_name"),
                        "started_at": phase.get("started_at"),
                        "age_minutes": (datetime.now() - started).seconds // 60
                    })
    return stale
```

**Note:** This is a safety net. Prompt discipline should prevent most issues, but crashes happen.

#### Mechanism 3: Boundary Rules

Prevent scope creep with explicit boundaries:

```markdown
## BOUNDARY_RULES

⚠️ STRICT EXECUTION BOUNDARY

**YOUR ONLY TASK:** Execute the 14-phase TDD cycle for step {task_id}

**ALLOWED:**
✅ Read/write the step file
✅ Create/modify source files per task specification
✅ Run tests
✅ Update phase_execution_log

**FORBIDDEN:**
❌ Execute other /nw:* commands
❌ Start work on other steps
❌ Modify files outside task scope
❌ Continue workflow after step completion
❌ Make architectural decisions outside task scope

**ON COMPLETION:**
Return control immediately with execution summary.
```

### State Machine Definition

```yaml
# nWave/data/config/step-execution-fsm.yaml
name: StepExecutionFSM
version: "1.0"

states:
  TODO:
    description: Step not started
    transitions:
      - to: IN_PROGRESS
        trigger: agent_starts

  IN_PROGRESS:
    description: Agent actively working
    transitions:
      - to: DONE
        trigger: all_phases_complete
        guard: all_phases_valid
      - to: FAILED
        trigger: unrecoverable_error
      - to: PARTIAL
        trigger: timeout_or_interrupt

  DONE:
    description: Step completed successfully
    terminal: true

  FAILED:
    description: Step failed, needs intervention
    transitions:
      - to: IN_PROGRESS
        trigger: retry_with_fix

  PARTIAL:
    description: Partial completion, can resume
    transitions:
      - to: IN_PROGRESS
        trigger: resume

phase_states:
  NOT_EXECUTED:
    transitions: [IN_PROGRESS]
  IN_PROGRESS:
    transitions: [EXECUTED, SKIPPED, FAILED]
  EXECUTED:
    terminal: true
    requires: [outcome]
  SKIPPED:
    terminal: true
    requires: [blocked_by]
    validation: blocked_by_prefix_valid
  FAILED:
    transitions: [IN_PROGRESS]  # Retry allowed

commit_gate:
  blocks_on:
    - phase_status: IN_PROGRESS
    - phase_status: NOT_EXECUTED
    - phase_status: FAILED
    - blocked_by_prefix: "DEFERRED:"
```

---

## Layer 4: Validation Gates

### Gate 1: Pre-Invocation Validation

**When:** Before Task tool is invoked
**How:** Orchestrator calls validation function
**Blocks:** Task invocation if validation fails

```python
# In orchestrator logic (e.g., /nw:develop)

def invoke_step_execution(agent_name: str, step_path: str):
    # Load and render template
    template = load_template("execute-step.template.md")
    step_data = load_step_file(step_path)
    prompt = render_prompt(template, step_data, agent_name)

    # GATE 1: Pre-invocation validation
    validation = validate_before_task_invocation(prompt, step_path)

    if not validation["valid"]:
        raise PreInvocationValidationError(
            f"Cannot invoke Task - validation failed:\n" +
            "\n".join(validation["errors"])
        )

    # Proceed with invocation
    # Note: max_turns is NOT available for Task tool (CLI-only)
    return Task(
        subagent_type=agent_name,
        prompt=prompt,
        description=f"Execute step {step_data['task_id']}"
    )
```

### Gate 2: SubagentStop Hook (Post-Execution)

**When:** After sub-agent completes (success or failure)
**How:** Claude Code SubagentStop hook
**Action:** Validate step file was properly updated

```json
// .claude/settings.local.json
{
  "hooks": {
    "SubagentStop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python nWave/hooks/post_subagent_validation.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

```python
# nWave/hooks/post_subagent_validation.py

import json
import sys
import re
from pathlib import Path
from datetime import datetime

def validate_post_execution():
    """
    Validate step file state after sub-agent completion.

    This hook runs after every SubagentStop event.

    Input Schema (via stdin):
    {
        "session_id": "...",
        "agent_id": "...",
        "agent_transcript_path": "/path/to/agent.jsonl",
        ...
    }
    """
    # Read hook context from stdin
    context = json.loads(sys.stdin.read())

    # Extract step file path from agent's transcript (contains the prompt)
    step_file_path = extract_step_file_from_transcript(context)

    if not step_file_path:
        # Not a DES-managed task, skip validation
        print(json.dumps({"status": "skipped", "reason": "no_step_file"}))
        return

    # Load step file
    step_path = Path(step_file_path)
    if not step_path.exists():
        print(json.dumps({
            "status": "error",
            "error": f"Step file not found: {step_file_path}"
        }))
        sys.exit(1)

    step_data = json.load(open(step_path))

    # Validate phase states
    errors = []
    warnings = []

    phases = step_data.get("tdd_cycle", {}).get("phase_execution_log", [])

    for phase in phases:
        status = phase.get("status", "NOT_EXECUTED")
        phase_name = phase.get("phase_name", "UNKNOWN")

        if status == "IN_PROGRESS":
            errors.append(f"Phase {phase_name} left IN_PROGRESS (abandoned)")
        elif status == "NOT_EXECUTED":
            # Check if task is marked as complete
            task_status = step_data.get("state", {}).get("status")
            if task_status in ["DONE", "COMPLETED"]:
                errors.append(f"Task marked DONE but phase {phase_name} NOT_EXECUTED")
        elif status == "EXECUTED":
            if not phase.get("outcome"):
                errors.append(f"Phase {phase_name} EXECUTED without outcome")
        elif status == "SKIPPED":
            blocked_by = phase.get("blocked_by", "")
            if not blocked_by:
                errors.append(f"Phase {phase_name} SKIPPED without blocked_by")
            elif blocked_by.startswith("DEFERRED:"):
                warnings.append(f"Phase {phase_name} has DEFERRED - blocks commit")

    # Check overall task state
    task_status = step_data.get("state", {}).get("status")
    if task_status == "IN_PROGRESS":
        warnings.append("Task still IN_PROGRESS after agent stop")

    # Output validation result
    result = {
        "status": "error" if errors else ("warning" if warnings else "success"),
        "step_file": step_file_path,
        "errors": errors,
        "warnings": warnings,
        "timestamp": datetime.now().isoformat()
    }

    print(json.dumps(result, indent=2))

    # Log to daily audit trail
    from datetime import date
    today = date.today().isoformat()
    audit_log_path = Path(step_file_path).parent / f"audit-{today}.log"
    with open(audit_log_path, "a") as f:
        f.write(json.dumps({
            "event": "SUBAGENT_STOP_VALIDATION",
            **result
        }) + "\n")

    if errors:
        sys.exit(1)


def extract_step_file_from_transcript(context: dict) -> str | None:
    """
    Extract step file path from SubagentStop context via transcript.

    The prompt is NOT in the hook input directly. We must read it from
    the agent's transcript file (first line, type="user").
    """
    agent_transcript_path = context.get("agent_transcript_path")
    if not agent_transcript_path:
        return None

    transcript_path = Path(agent_transcript_path)
    if not transcript_path.exists():
        return None

    # Read first line (contains the original prompt)
    with open(transcript_path) as f:
        first_line = f.readline()

    try:
        entry = json.loads(first_line)
        # Structure: {"type":"user","message":{"role":"user","content":"..."}}
        prompt = entry.get("message", {}).get("content", "")
    except json.JSONDecodeError:
        return None

    # Search for DES marker in prompt
    match = re.search(r'<!-- DES-STEP-FILE: (.+?) -->', prompt)
    if match:
        return match.group(1)

    return None


if __name__ == "__main__":
    validate_post_execution()
```

### Gate 3: Pre-Commit Hook (Existing, Enhanced)

The existing `pre_commit_tdd_phases.py` hook remains the final gate.

**Enhancement:** Add coordination with Gate 2 results:

```python
# Check if SubagentStop validation already flagged issues in any daily log
import glob
step_dir = Path(step_file).parent
for audit_log in step_dir.glob("audit-*.log"):
    with open(audit_log) as f:
        for line in f:
            entry = json.loads(line)
            if entry.get("event") == "SUBAGENT_STOP_VALIDATION":
                if entry.get("status") == "error":
                    errors.extend(entry.get("errors", []))
```

### Gate 4: Audit Trail

Every state transition is logged to **daily rotating log files** (`audit-YYYY-MM-DD.log`) to prevent single files from growing too large:

```python
# nWave/utils/audit.py

import json
from datetime import datetime, date
from pathlib import Path

def get_daily_audit_path(step_file_path: str) -> Path:
    """Get path to today's audit log file."""
    today = date.today().isoformat()  # e.g., "2026-01-22"
    return Path(step_file_path).parent / f"audit-{today}.log"

def log_event(step_file_path: str, event_type: str, data: dict):
    """Append event to daily audit trail."""
    audit_path = get_daily_audit_path(step_file_path)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "step_file": step_file_path,
        **data
    }

    with open(audit_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

# Event types:
# - TASK_INVOCATION_STARTED
# - TASK_INVOCATION_VALIDATED
# - TASK_INVOCATION_REJECTED
# - PHASE_STARTED
# - PHASE_COMPLETED
# - PHASE_SKIPPED
# - PHASE_FAILED
# - SUBAGENT_STOP_VALIDATION
# - COMMIT_VALIDATION_PASSED
# - COMMIT_VALIDATION_FAILED
# - WATCHDOG_INTERVENTION
```

---

## Failure Modes and Recovery

### Failure Mode 1: Agent Crashes

**Detection:** SubagentStop hook fires with error context
**Symptoms:** Step file has phases stuck in IN_PROGRESS
**Recovery:**

```python
def recover_from_crash(step_file_path: str):
    step_data = load_step_file(step_file_path)

    # Find crashed phase
    for phase in step_data["tdd_cycle"]["phase_execution_log"]:
        if phase["status"] == "IN_PROGRESS":
            # Move to history and reset
            if "history" not in phase:
                phase["history"] = []
            phase["history"].append({
                "status": "CRASHED",
                "ended_at": datetime.now().isoformat(),
                "notes": "Agent crashed during execution"
            })
            phase["status"] = "NOT_EXECUTED"

    # Reset task state
    step_data["state"]["status"] = "FAILED"
    step_data["state"]["failure_reason"] = "Agent crashed"
    step_data["state"]["can_retry"] = True

    save_step_file(step_file_path, step_data)
```

### Failure Mode 2: Agent Stuck (Infinite Loop)

**Detection:** max_turns limit reached
**Symptoms:** Task tool returns after turn limit without completion
**Recovery:**

```markdown
## In prompt TIMEOUT_INSTRUCTION:

If max_turns limit is reached:
1. Immediately stop current work
2. Save partial progress to step file
3. Set execution_result.partial_completion = true
4. List remaining work in recovery_suggestions
```

### Failure Mode 3: Agent Runaway (Continues Beyond Scope)

**Detection:** SubagentStop hook finds unexpected file modifications
**Prevention:** BOUNDARY_RULES in prompt
**Recovery:**

```python
def validate_scope_compliance(step_file_path: str, git_diff: str):
    """Check if agent modified only allowed files."""
    step_data = load_step_file(step_file_path)
    allowed_patterns = step_data.get("task_specification", {}).get("allowed_file_patterns", [])

    modified_files = parse_git_diff(git_diff)
    violations = []

    for file in modified_files:
        if not matches_any_pattern(file, allowed_patterns):
            violations.append(f"Unexpected modification: {file}")

    return violations
```

### Failure Mode 4: Silent Completion (No State Update)

**Detection:** SubagentStop hook finds phases still NOT_EXECUTED
**Symptoms:** Task "completed" but step file unchanged
**Recovery:**

```python
def handle_silent_completion(step_file_path: str):
    """Handle case where agent returned without updating state."""
    step_data = load_step_file(step_file_path)

    all_not_executed = all(
        phase["status"] == "NOT_EXECUTED"
        for phase in step_data["tdd_cycle"]["phase_execution_log"]
    )

    if all_not_executed and step_data["state"]["status"] == "IN_PROGRESS":
        # Agent didn't do anything
        step_data["state"]["status"] = "FAILED"
        step_data["state"]["failure_reason"] = "Agent completed without updating step file"
        step_data["state"]["recovery_suggestions"] = [
            "Check agent transcript for errors",
            "Verify prompt contained all required instructions",
            "Retry with more explicit phase update requirements"
        ]
        save_step_file(step_file_path, step_data)

        log_event(step_file_path, "SILENT_COMPLETION_DETECTED", {
            "recovery_action": "marked_as_failed"
        })
```

---

## Open Questions

### Q1: Hook Context Access ✅ RESOLVED

**Question:** What exactly does the SubagentStop hook receive in its stdin?

**Answer (Empirically Verified 2026-01-22):**

The hook receives 8 fields via stdin JSON:
- `session_id`, `transcript_path`, `cwd`, `permission_mode`
- `hook_event_name`, `stop_hook_active`
- **`agent_id`** - Matches Task tool return value
- **`agent_transcript_path`** - Contains the full prompt in first line

**Key Finding:** The prompt is NOT included directly. Must read from `agent_transcript_path` first line (type="user").

**Impact:** Design updated to use transcript extraction instead of direct prompt access.

### Q2: Parallel Execution

**Question:** Can multiple steps execute in parallel? How to handle concurrent state updates?

**Impact:** May need file locking or optimistic concurrency.

**Proposed Answer:** For MVP, sequential execution only. Parallel execution in v2.

### Q3: Background Agent Monitoring

**Question:** If using `run_in_background: true`, how do we know when to run validation?

**Impact:** Background agents complete asynchronously.

**Proposed Answer:** Use `TaskOutput` tool to poll for completion, then validate.

### Q4: Token Usage Measurement

**Question:** How much do the validation hooks cost in tokens?

**Impact:** User deferred optimization, but need baseline.

**To Measure:** Track token usage before/after implementing DES.

### Q5: Template Inheritance

**Question:** Should templates support inheritance/composition?

**Example:** `execute-step.template.md` might extend `base-task.template.md`

**Proposed Answer:** Start simple (no inheritance), add if needed.

---

## Acceptance Criteria

### Must Have (P0)

- [ ] **AC-1:** Command-origin Task invocations are distinguishable from ad-hoc invocations
- [ ] **AC-2:** Pre-invocation validation blocks Task if mandatory sections missing
- [ ] **AC-3:** 14-phase TDD list is embedded in every step execution prompt
- [ ] **AC-4:** SubagentStop hook validates step file state after completion
- [ ] **AC-5:** Phases stuck in IN_PROGRESS are detected and flagged
- [ ] **AC-6:** TIMEOUT_INSTRUCTION is included in all step execution prompts (max_turns NOT available)
- [ ] **AC-7:** Audit trail captures all state transitions

### Should Have (P1)

- [ ] **AC-8:** Template validation produces actionable error messages
- [ ] **AC-9:** Recovery suggestions provided for each failure mode
- [ ] **AC-10:** BOUNDARY_RULES prevents scope creep
- [ ] **AC-11:** TIMEOUT_INSTRUCTION enables graceful partial completion

### Could Have (P2)

- [ ] **AC-12:** Template inheritance for common sections
- [ ] **AC-13:** Parallel execution support with state coordination
- [ ] **AC-14:** Token usage tracking for optimization
- [ ] **AC-15:** Visual progress dashboard

---

## Implementation Roadmap

### Phase 1: Foundation (Estimated: First)

1. Create `nWave/templates/prompt-templates/` directory structure
2. Implement `execute-step.template.md` with all mandatory sections
3. Implement `validate_prompt_template.py` validation script
4. Add DES metadata markers to prompts

### Phase 2: Lifecycle Management (Estimated: Second)

1. Update command files to use templates
2. Implement TIMEOUT_INSTRUCTION in all prompts (max_turns NOT available for Task tool)
3. Implement BOUNDARY_RULES for scope enforcement
4. Create state machine definition file

### Phase 3: Post-Execution Validation (Estimated: Third)

1. Implement SubagentStop hook (`post_subagent_validation.py`)
2. Configure hook in `.claude/settings.local.json`
3. Test with actual step executions
4. Implement failure recovery handlers

### Phase 4: Audit and Observability (Estimated: Fourth)

1. Implement audit trail logging
2. Enhance pre-commit hook with audit trail integration
3. Create validation summary reporting
4. Document all failure modes and recoveries

---

## Appendix A: Complete Template Example

```markdown
<!-- DES-ORIGIN: command:/nw:execute -->
<!-- DES-STEP-FILE: {step_file_path} -->
<!-- DES-VALIDATION: required -->
<!-- DES-VERSION: 1.0 -->

# AGENT_IDENTITY

You are the **{agent_name}** agent, a specialist in {agent_specialty}.

Your task is to execute step **{task_id}** of project **{project_id}**.

---

# TASK_CONTEXT

**Project:** {project_id}
**Step:** {task_id}
**Step File:** {step_file_path}

## Background
{self_contained_context.background}

## Technical Context
{self_contained_context.technical_context}

## Task Specification
**Name:** {task_specification.name}
**Description:** {task_specification.description}
**Motivation:** {task_specification.motivation}

## Acceptance Criteria
{task_specification.acceptance_criteria}

---

# TDD_14_PHASES

You MUST execute ALL 14 phases in order. For each phase:
1. Update step file status to IN_PROGRESS before starting
2. Execute the phase
3. Update step file with outcome IMMEDIATELY after completing

| # | Phase | Gate | Action |
|---|-------|------|--------|
| 0 | PREPARE | G1 | Remove @skip tag, verify exactly 1 acceptance test active |
| 1 | RED_ACCEPTANCE | G2 | Run acceptance test - MUST fail for business logic not implemented |
| 2 | RED_UNIT | G3 | Write unit test - MUST fail on assertion (not setup) |
| 3 | GREEN_UNIT | - | Implement MINIMAL code to pass unit test |
| 4 | CHECK_ACCEPTANCE | - | Check if acceptance test passes now |
| 5 | GREEN_ACCEPTANCE | G6 | Run ALL tests - must be green |
| 6 | REVIEW | G5 | Self-review using criteria below |
| 7 | REFACTOR_L1 | G6 | Naming improvements (business language) |
| 8 | REFACTOR_L2 | G6 | Method extraction (single responsibility) |
| 9 | REFACTOR_L3 | G6 | Class responsibilities (SRP) |
| 10 | REFACTOR_L4 | G6 | Architecture patterns |
| 11 | POST_REFACTOR_REVIEW | G6 | Validate refactoring quality |
| 12 | FINAL_VALIDATE | - | Run complete test suite |
| 13 | COMMIT | - | Commit with detailed message |

---

# QUALITY_GATES

- **G1:** Exactly ONE acceptance test scenario is active (no @skip)
- **G2:** Acceptance test fails for BUSINESS LOGIC not implemented (not infra issues)
- **G3:** Unit test fails on ASSERTION (not setup/compilation)
- **G4:** No mocks inside hexagon (domain/application layers use real objects)
- **G5:** Business language used in all test names and code
- **G6:** ALL tests green after this phase

---

# OUTCOME_RECORDING

After EACH phase, update the step file `tdd_cycle.phase_execution_log[N]`:

```json
{
  "status": "EXECUTED",
  "started_at": "ISO-timestamp",
  "ended_at": "ISO-timestamp",
  "duration_minutes": N,
  "outcome": "PASS",
  "outcome_details": "Specific description of what happened",
  "artifacts_created": ["list", "of", "files"],
  "test_results": {
    "total": N,
    "passed": N,
    "failed": N
  },
  "notes": "Any additional observations"
}
```

**For SKIPPED phases:**
```json
{
  "status": "SKIPPED",
  "blocked_by": "PREFIX: reason"
}
```

**Valid SKIPPED prefixes (allow commit):**
- `BLOCKED_BY_DEPENDENCY:` - External dependency unavailable
- `NOT_APPLICABLE:` - Phase doesn't apply to this task type
- `APPROVED_SKIP:` - Explicitly approved by reviewer

**Invalid SKIPPED prefix (BLOCKS commit):**
- `DEFERRED:` - Incomplete work that must be resolved

---

# BOUNDARY_RULES

⚠️ STRICT EXECUTION BOUNDARY ⚠️

**YOUR ONLY TASK:** Execute the 14-phase TDD cycle for step {task_id}

**ALLOWED:**
✅ Read/write the step file at {step_file_path}
✅ Create/modify source files per task specification
✅ Run tests using Bash tool
✅ Update phase_execution_log after each phase

**FORBIDDEN:**
❌ Execute /nw:* commands (you cannot invoke them)
❌ Start work on steps other than {task_id}
❌ Modify files outside allowed patterns
❌ Continue workflow after step completion
❌ Make architectural decisions outside task scope
❌ Skip phases without valid blocked_by reason

**ON COMPLETION:**
Return control IMMEDIATELY with execution summary.

---

# TIMEOUT_INSTRUCTION

**Base Turn Budget:** 50 turns (standard allocation for step execution)

> ⚠️ Note: There is no hard turn limit enforcement. You must self-regulate.

**Warning Thresholds:**

Monitor your turn count and expect these progress warnings:
- **Turn 30 (60% of budget)**: ⚠️ PROGRESS CHECK - Expected completion by turn 40
- **Turn 40 (80% of budget)**: ⚠️ TIME WARNING - Consider extension request or early exit
- **Turn 48 (95% of budget)**: 🚨 CRITICAL - Complete current phase and exit OR request extension NOW

**Extension Request Protocol:**

If you need additional turns beyond the 50-turn base budget:

1. Update step file with extension_request in execution_result:
   ```json
   {
     "execution_result": {
       "extension_request": {
         "requested_turns": 20,
         "reason": "Specific justification for additional turns",
         "current_phase": "PHASE_NAME",
         "estimated_completion_turn": 65,
         "critical_path": "What work requires the extension"
       }
     }
   }
   ```

2. Continue work with extended budget after recording request

**Progress Checkpoints:**
- By turn ~10: Should have completed PREPARE and RED phases
- By turn ~25: Should have completed GREEN phases
- By turn ~40: Should have completed REFACTOR phases
- By turn ~50: Should be finishing COMMIT or requesting extension

**Early Exit Protocol:**

If you realize you cannot complete reasonably:
1. Save all current progress to step file
2. Set current phase to IN_PROGRESS with detailed notes
3. Set task state to PARTIAL with recovery_suggestions
4. Return immediately - do NOT continue

**DO NOT:**
- Loop indefinitely trying to fix unfixable issues
- Continue past phase 13 (COMMIT) without extension
- Ignore turn budget warnings
- Request extension without clear justification

---

# REVIEW_CRITERIA

## Phase 6 (REVIEW) Checklist:
- [ ] Implementation follows SOLID principles
- [ ] Test coverage is adequate (aim for >80%)
- [ ] All acceptance criteria from task_specification are met
- [ ] Code is readable and maintainable
- [ ] No obvious security vulnerabilities (OWASP Top 10)
- [ ] No hardcoded secrets or credentials
- [ ] Business language used throughout

## Phase 11 (POST_REFACTOR_REVIEW) Checklist:
- [ ] Refactoring did not break any existing tests
- [ ] Refactoring improved code quality (naming, structure)
- [ ] No new duplication introduced
- [ ] Architecture patterns applied correctly
- [ ] All tests still pass after refactoring
- [ ] G4 maintained (no mocks inside hexagon)

Record all findings in phase notes.

---

BEGIN EXECUTION NOW.
```

---

## Appendix B: File Structure

```
nWave/
├── templates/
│   └── prompt-templates/
│       ├── execute-step.template.md
│       ├── _validation-schema.json
│       └── _section-definitions.yaml
├── hooks/
│   ├── validate_prompt_template.py
│   ├── post_subagent_validation.py
│   └── pre_commit_tdd_phases.py (existing)
├── data/
│   └── config/
│       └── step-execution-fsm.yaml
└── utils/
    └── audit.py
```

---

*Document prepared for multi-agent review. Pending feedback from: solution-architect, software-crafter, product-owner, troubleshooter.*
