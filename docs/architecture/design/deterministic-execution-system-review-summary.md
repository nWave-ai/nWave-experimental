# Deterministic Execution System - Multi-Agent Review Summary

**Date:** 2026-01-22 (Updated with Q1 Resolution)
**Design Document:** [deterministic-execution-system-design.md](deterministic-execution-system-design.md)
**Branch:** `determinism`

---

## Review Panel

| Reviewer | Role | Verdict |
|----------|------|---------|
| **Morgan** | Solution Architect | CONDITIONALLY APPROVED |
| **Crafty** | Software Crafter | NEEDS WORK |
| **Sage** (PO) | Product Owner | BLOCKED (3/8 DoR) |
| **Sage** (Troubleshooter) | Failure Analyst | NOT READY (6 unmitigated risks) |

---

## ✅ BLOCKER #1 RESOLVED: SubagentStop Hook Context Verified

> **Q1 was resolved on 2026-01-22 via empirical testing after session restart.**

### Resolution Details

- **Hook fires correctly** after session restart (settings require restart to load)
- **8-field schema captured** including critical `agent_transcript_path`
- **Prompt accessible** via transcript first line (not in hook input directly)

### Verified Schema

```json
{
  "session_id": "...",
  "transcript_path": "...",
  "cwd": "...",
  "permission_mode": "bypassPermissions",
  "hook_event_name": "SubagentStop",
  "stop_hook_active": false,
  "agent_id": "ab7af5b",           // ← Correlate with Task return
  "agent_transcript_path": "..."   // ← Contains prompt in first line
}
```

### Key Finding: max_turns NOT Available

The design assumed `max_turns` parameter exists for Task tool. **This is FALSE** - it's CLI-only. Design updated to use prompt-based turn discipline.

## Remaining Blockers

### BLOCKER #2: Missing UAT Scenarios (Product Owner)

Given/When/Then scenarios required before implementation. See draft scenarios below.

---

## Aggregated Findings by Category

### Architecture (Solution Architect)

| Finding | Severity | Action |
|---------|----------|--------|
| Missing observability layer | Medium | Add Layer 0 for metrics/tracing |
| Coupling between validation scripts | Medium | Single source of truth for phase list |
| FSM guards not implemented | High | Add callable guard predicates |
| No saga pattern for recovery | Medium | Design compensating transactions |
| Settings schema for hooks unverified | Critical | Verify Claude Code support |

### Implementation (Software Crafter)

| Finding | Severity | Action |
|---------|----------|--------|
| G4 (no hexagon mocks) cannot be automated | Medium | Add static analysis |
| Template validation regex fragile | Medium | Use canonical markers only |
| Validation scripts mix responsibilities | High | Separate into modules |
| FSM is documentation not code | Medium | Clarify if runtime intended |
| No test matrix defined | High | Add test coverage plan |

### Product (Product Owner)

| Finding | Severity | Action |
|---------|----------|--------|
| No UAT scenarios (Given/When/Then) | Critical | Add 5-7 scenarios |
| No persona tracing | High | Map to Marcus/Priya/Alex |
| No effort estimates | High | Add days per phase |
| Technical acceptance criteria | Medium | Rewrite for outcomes |
| No business value metrics | Medium | Quantify ROI |

### Failure Analysis (Troubleshooter)

| Risk | Likelihood | Impact | Status |
|------|------------|--------|--------|
| SubagentStop hook doesn't fire | Medium | High | **NOT ADDRESSED** |
| Step file corruption | Low | High | **NOT ADDRESSED** |
| Race condition on file access | Low | Medium | Deferred |
| Git state divergence | Medium | Medium | **NOT ADDRESSED** |
| Incomplete work passes gates | Medium | High | **NOT ADDRESSED** |

---

## Top 10 Required Changes (Prioritized)

### P0 - Must Fix Before Implementation

1. ✅ ~~**Resolve Q1 empirically**~~ - SubagentStop schema captured (8 fields)
2. ✅ ~~**Verify Claude Code hook settings schema**~~ - Works after session restart
3. **Add UAT scenarios** - 5-7 Given/When/Then covering happy path and failures
4. **Implement atomic file writes** - Prevent step file corruption
5. **Add external watchdog** - Detect orphaned IN_PROGRESS when process dies

### P1 - Must Fix During Implementation

6. **Single source of truth for phases** - Extract to `tdd_phases.yaml`
7. **Implement FSM guards** - Callable predicates, not just documentation
8. **Separate validation modules** - Split concerns for testability
9. **Store commit SHA in step file** - Detect git state divergence
10. **Add effort estimates** - Days per implementation phase

---

## Recommended Architectural Changes

### Change 1: Add Discovery Hook First (NEW)

Before implementing any validation, discover what SubagentStop actually provides:

```json
{
  "hooks": {
    "SubagentStop": [{
      "hooks": [{
        "type": "command",
        "command": "python nWave/hooks/discover_subagent_context.py"
      }]
    }]
  }
}
```

### Change 2: External Watchdog Process (NEW)

Add process that runs independently:

```python
# nWave/tools/execution_watchdog.py
def find_orphaned_executions(project_root, stale_threshold_minutes=30):
    """Find step files with IN_PROGRESS phases older than threshold."""
    # ... implementation from troubleshooter review
```

### Change 3: Atomic File Operations (UPDATED)

Replace all step file writes with:

```python
def save_step_file_atomic(path: str, data: dict):
    temp_path = path + ".tmp"
    backup_path = path + ".bak"

    with open(temp_path, "w") as f:
        json.dump(data, f, indent=2)

    # Validate before replacing
    with open(temp_path) as f:
        json.load(f)

    if Path(path).exists():
        shutil.copy(path, backup_path)

    os.rename(temp_path, path)
```

### Change 4: Single Phase Source of Truth (UPDATED)

```yaml
# nWave/data/config/tdd_phases.yaml
version: "1.0"
phases:
  - name: PREPARE
    index: 0
    gate: G1
    description: "Remove @skip tag, verify exactly 1 acceptance test active"
  # ... all 14 phases
```

All scripts import from this file.

### Change 5: YAML Frontmatter for Metadata (UPDATED)

Replace HTML comments with standard frontmatter:

```markdown
---
des:
  origin: "command:/nw:execute"
  step_file: "{step_file_path}"
  validation: required
  version: "1.0"
---

# AGENT_IDENTITY
...
```

---

## Missing UAT Scenarios (To Be Added)

### Scenario 1: Happy Path - Command Filtered and Validated

```gherkin
Given Marcus invokes /nw:execute @software-crafter "steps/01-01.json"
When DES processes the Task invocation
Then the prompt contains "<!-- DES-VALIDATION: required -->" marker
And pre-invocation validation checks all 14 TDD phases are embedded
And validation PASSES
And Task tool is invoked with validated prompt
```

### Scenario 2: Validation Failure - Missing TDD Phases

```gherkin
Given an orchestrator creates a Task prompt missing REFACTOR_L3 phase
When DES pre-invocation validation runs
Then validation FAILS with error "INCOMPLETE: TDD phase 'REFACTOR_L3' not mentioned"
And Task tool is NOT invoked
And orchestrator receives actionable error message
```

### Scenario 3: Post-Execution - Abandoned Phase Detected

```gherkin
Given a software-crafter agent completed work on step "01-01.json"
And phase GREEN_UNIT was left with status "IN_PROGRESS"
When SubagentStop hook fires
Then post-execution validation FAILS
And error "Phase GREEN_UNIT left IN_PROGRESS (abandoned)" is logged
And step file state is marked FAILED with recovery suggestions
```

### Scenario 4: Timeout - Agent Hits Turn Limit

```gherkin
Given a software-crafter agent is executing step "01-01.json"
And max_turns is set to 50
When agent reaches turn 50 without completing
Then agent saves partial progress to step file
And agent returns with status "PARTIAL_COMPLETION"
And remaining phases are documented in recovery_suggestions
```

### Scenario 5: Crash Recovery - Orphaned Execution

```gherkin
Given Marcus was running /nw:execute that crashed 45 minutes ago
And step file "01-01.json" has phase RED_UNIT with status "IN_PROGRESS"
When external watchdog runs with 30-minute threshold
Then orphaned execution is detected
And Marcus is notified "Orphaned execution: 01-01.json phase RED_UNIT stale for 45 minutes"
And recovery options are provided
```

---

## Open Questions Resolution Status

| Question | Status | Resolution |
|----------|--------|------------|
| Q1: Hook context contents | ✅ **RESOLVED** | 8-field schema captured; prompt via transcript |
| Q2: Parallel execution | Deferred | Sequential MVP accepted |
| Q3: Background agent monitoring | Deferred | Use TaskOutput polling |
| Q4: Token usage measurement | Deferred | Track post-implementation |
| Q5: Template inheritance | Rejected | Keep simple (no inheritance) |
| **NEW: max_turns** | ❌ **NOT AVAILABLE** | CLI-only; use prompt discipline |

---

## Next Steps

### Completed ✅

1. [x] Create discovery hook to capture SubagentStop context
2. [x] Run test invocation and analyze results (after session restart)
3. [x] Update design based on actual hook capabilities
4. [x] Update design to remove max_turns assumption

### Before Implementation Sprint

5. [ ] Add 5-7 UAT scenarios to design document
6. [ ] Map requirements to Marcus/Priya/Alex personas
7. [ ] Add effort estimates (days) per phase
8. [ ] Create ADRs for key decisions (FSM, metadata embedding, sequential MVP)

### Implementation Sprint 1 (Foundation)

9. [ ] Extract phase definitions to single YAML file
10. [ ] Implement prompt template with YAML frontmatter
11. [ ] Implement atomic file write utility
12. [ ] Create validation module structure

---

## Appendix: Reviewer Agent IDs (for Resume)

- Solution Architect: `ac2f799`
- Software Crafter: `a336dd0`
- Product Owner: `a47ebd0`
- Troubleshooter: `ad8f0b1`

---

*Summary compiled from parallel multi-agent review session.*
