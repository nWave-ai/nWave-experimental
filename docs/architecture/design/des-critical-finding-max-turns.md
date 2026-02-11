# CRITICAL FINDING: max_turns Is NOT a Task Tool Parameter

**Date:** 2026-01-22
**Severity:** CRITICAL - Requires Design Correction
**Source:** Claude Code Official Documentation

---

## The Incorrect Assumption

The DES design document assumed:

```python
Task(
    subagent_type="software-crafter",
    prompt="...",
    max_turns=50,  # ❌ THIS PARAMETER DOES NOT EXIST
)
```

**This is WRONG.** The Task tool does NOT accept a `max_turns` parameter.

---

## What max_turns Actually Is

From official Claude Code documentation:

> `--max-turns`: Limit the number of agentic turns (**print mode only**). Exits with an error when the limit is reached. No limit by default.

### Key Facts

| Aspect | Reality |
|--------|---------|
| **Type** | CLI flag, NOT Task tool parameter |
| **Availability** | Only in print mode (`-p` or `--print`) |
| **Context** | Non-interactive/headless sessions only |
| **Default** | No limit |
| **Effect** | Exits with error when reached |

### Usage Example (Correct)

```bash
# This works - CLI flag in print mode
claude -p "Fix linting errors" --max-turns 3

# This does NOT work - not available in interactive Task tool
Task(prompt="...", max_turns=50)  # ❌ INVALID
```

---

## Impact on DES Design

### Affected Sections

1. **Layer 3: Execution Lifecycle Management** - "max_turns limit on Task invocations" is impossible
2. **Timeout Strategy** - "Mechanism 1: max_turns Parameter" is invalid
3. **Timeout Strategy Table** - Recommended max_turns values are meaningless
4. **Template TIMEOUT_INSTRUCTION** - References to turn limits need rethinking

### Invalid Design Elements

```markdown
❌ "Set max_turns based on expected complexity"
❌ "max_turns=50 for full TDD cycle"
❌ "By turn 10: Should have completed PREPARE..."
```

---

## Revised Timeout Strategy

Since we cannot enforce turn limits programmatically, we must rely on:

### Strategy 1: Prompt-Based Soft Limits (Still Valid)

Include clear timeout instructions in the prompt:

```markdown
## EXECUTION DISCIPLINE

**Progress Expectations:**
- Complete PREPARE and RED phases within your first 10 tool calls
- Complete GREEN phases within your next 15 tool calls
- Complete REFACTOR phases within your next 15 tool calls
- If you have made 40+ tool calls without completing, STOP and return partial results

**Self-Monitoring Required:**
You must track your own progress. If you detect you are:
- Looping on the same error repeatedly (3+ attempts)
- Unable to make progress for 5+ consecutive tool calls
- Exceeding reasonable scope

Then STOP immediately, save progress to step file, and return with status PARTIAL.
```

**Limitation:** This is a "soft" limit - the LLM may not follow it perfectly.

### Strategy 2: SubagentStop Hook with Prompt Type (NEW)

Use a `type: "prompt"` hook to evaluate if agent should continue:

```json
{
  "hooks": {
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Evaluate this subagent's completion. Did it:\n1. Complete all assigned work?\n2. Get stuck in a loop?\n3. Exceed reasonable scope?\n\nReturn {\"continue\": false} if work is incomplete but agent should stop due to issues.",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Limitation:** This evaluates AFTER the agent thinks it's done, not during execution.

### Strategy 3: External Watchdog Process (NEW - Recommended)

Create an external process that monitors step file timestamps:

```python
# nWave/tools/execution_watchdog.py
def monitor_execution(step_file: str, timeout_minutes: int = 60):
    """
    External watchdog that detects stalled executions.

    Runs independently of Claude Code.
    """
    start_time = datetime.now()
    last_modified = get_mtime(step_file)

    while True:
        time.sleep(60)  # Check every minute

        elapsed = datetime.now() - start_time
        if elapsed.total_seconds() > timeout_minutes * 60:
            log_timeout(step_file, elapsed)
            send_alert(f"Execution of {step_file} exceeded {timeout_minutes} minutes")
            return "TIMEOUT"

        current_mtime = get_mtime(step_file)
        if current_mtime == last_modified:
            # No progress in last minute
            stall_time = datetime.now() - last_modified
            if stall_time.total_seconds() > 300:  # 5 minutes stalled
                log_stall(step_file, stall_time)
                send_alert(f"Execution of {step_file} stalled for {stall_time}")
        else:
            last_modified = current_mtime
```

**Limitation:** Requires external process management.

### Strategy 4: Structured Checkpoints in Step File (NEW)

Require agents to update step file with checkpoint timestamps:

```json
{
  "execution_checkpoints": [
    {"checkpoint": "START", "timestamp": "2026-01-22T10:00:00Z"},
    {"checkpoint": "RED_COMPLETE", "timestamp": "2026-01-22T10:15:00Z"},
    {"checkpoint": "GREEN_COMPLETE", "timestamp": "2026-01-22T10:35:00Z"}
  ]
}
```

SubagentStop hook can then validate:
- Checkpoints exist
- Time between checkpoints is reasonable
- Expected checkpoints are present

---

## Design Document Updates Required

### Section to Remove

```markdown
#### Mechanism 1: max_turns Parameter

```python
Task(
    subagent_type="software-crafter",
    prompt="...",
    max_turns=50,  # Hard limit on API round-trips
)
```
```

### Section to Add

```markdown
#### Mechanism 1: Prompt-Based Execution Discipline

Since Task tool has no turn limit parameter, we rely on prompt instructions:

- Clear progress expectations
- Self-monitoring requirements
- Explicit "STOP if stuck" instructions
- Checkpoint update requirements

#### Mechanism 2: External Watchdog

Independent process monitors step file activity:

- Detects stalled executions (no step file updates)
- Enforces absolute time limits
- Alerts on timeouts
```

### Table to Update

| Timeout Mechanism | Type | Reliability |
|-------------------|------|-------------|
| ~~max_turns parameter~~ | ~~Hard limit~~ | ~~INVALID~~ |
| Prompt instructions | Soft limit | Medium |
| SubagentStop hook | Post-hoc evaluation | High |
| External watchdog | Hard limit | High |
| Checkpoint validation | Progress tracking | High |

---

## Recommendation

1. **Remove** all references to `max_turns` as Task tool parameter
2. **Add** prompt-based execution discipline section
3. **Add** external watchdog as primary timeout mechanism
4. **Add** checkpoint validation in SubagentStop hook
5. **Update** TIMEOUT_INSTRUCTION template to focus on self-monitoring

---

## References

- Claude Code CLI Reference: `--max-turns` flag documentation
- Claude Code Subagents: No max_turns parameter mentioned
- Claude Code Hooks: SubagentStop can evaluate completion post-hoc

---

*This finding was discovered during empirical validation of DES design assumptions.*
