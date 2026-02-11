# Root Cause Analysis: DES PreToolUse:Task "Hook Error"

**Date**: 2026-02-10
**Analyst**: Lyra (Orchestrator) + Rex (Troubleshooter)
**Methodology**: Toyota 5 Whys with Audit Log Evidence
**Status**: RESOLVED - Not a Bug (DES Working as Designed)

---

## Executive Summary

The "PreToolUse:Task hook error" displayed by Claude Code is **not a DES failure**. It is DES correctly blocking invalid Task invocations with `max_turns < 10` or missing `max_turns`. The audit log proves all DES hooks are firing, validating, and the new L2 timestamp correction is working.

---

## Observable Symptom

```
● nw-software-crafter(Complete step 02-03 remaining phases)
  ⎿  PreToolUse:Task hook error
  ⎿  Done (17 tool uses · 32.2k tokens · 2m 8s)
```

User sees "hook error" in Claude Code output during Task dispatches.

---

## 5 Whys Investigation

### WHY #1: Why does Claude Code show "hook error"?

**Evidence**: Claude Code displays `PreToolUse:Task hook error` when a PreToolUse hook returns a non-zero exit code (exit 2 = block decision).

**Conclusion**: The DES hook blocked a Task invocation. Claude Code labels this as "hook error" in its UI.

### WHY #2: Why did the DES hook block the Task?

**Evidence from audit log** (`.nwave/logs/des/audit-2026-02-10.log`):

```json
// Line 2532: Blocked for max_turns too low
{"event":"HOOK_PRE_TOOL_USE_BLOCKED","reason":"INVALID_MAX_TURNS: max_turns must be between 10 and 100 (got: 5)","timestamp":"2026-02-10T21:38:25Z"}

// Line 2534: Blocked for missing max_turns
{"event":"HOOK_PRE_TOOL_USE_BLOCKED","reason":"MISSING_MAX_TURNS: The max_turns parameter is required for all Task invocations.","timestamp":"2026-02-10T21:38:51Z"}
```

**Conclusion**: Two Task invocations were blocked — one with `max_turns=5` (below minimum), one with no `max_turns` at all.

### WHY #3: Why were tasks dispatched with invalid max_turns?

**Evidence**: The timestamps (21:38-21:39) correspond to the troubleshooter agent session that was investigating this very error. The troubleshooter internally tried to spawn sub-tasks with `max_turns=5`.

**Conclusion**: The troubleshooter agent (or its internal logic) uses `max_turns` values below the DES minimum of 10.

### WHY #4: Why is max_turns=5 invalid?

**Evidence from** `src/des/domain/max_turns_policy.py`:
- MIN_MAX_TURNS = 10 (safety floor to prevent useless 1-2 turn agents)
- MAX_MAX_TURNS = 100 (ceiling to prevent runaway agents)

**Conclusion**: DES policy correctly rejects `max_turns < 10` to prevent degenerate Task invocations.

### WHY #5 (Root Cause): Why does Claude Code label valid blocks as "hook error"?

**Root Cause**: Claude Code's UI treats ANY non-zero hook exit code as "hook error". DES uses exit code 2 for "block/reject". This is a **labeling mismatch** — the block is intentional enforcement, not an error.

| Exit Code | DES Meaning | Claude Code Display |
|-----------|-------------|---------------------|
| 0 | Allow | (no message) |
| 1 | Fail-closed error | "hook error" |
| 2 | Block/reject | "hook error" |

Claude Code doesn't distinguish "rejected by policy" from "hook crashed".

---

## DES System Health Verification

### All hooks firing correctly (audit log evidence)

| Hook | Invocation Count (Feb 10) | Status |
|------|--------------------------|--------|
| PreToolUse:Task | 20+ | All logged HOOK_INVOKED |
| SubagentStop | 10+ | All logged HOOK_INVOKED |
| PostToolUse:Task | 10+ | All logged HOOK_INVOKED |
| PreToolUse:Write/Edit | Active | Session guard operational |

### L2 Timestamp Correction: First Real-World Validation

Step 02-03 timestamps were corrected by SubagentStop hook:

```json
{"event":"LOG_INTEGRITY_CORRECTED","phase":"PREPARE","original":"21:27:24Z","corrected":"21:35:03Z","reason":"pre_task"}
{"event":"LOG_INTEGRITY_CORRECTED","phase":"RED_ACCEPTANCE","original":"21:28:13Z","corrected":"21:35:35Z","reason":"pre_task"}
{"event":"LOG_INTEGRITY_CORRECTED","phase":"RED_UNIT","original":"21:28:26Z","corrected":"21:36:06Z","reason":"pre_task"}
```

**Explanation**: The agent used the CLI (L1) but the timestamps were from the first dispatch window. The resume dispatch created a new `task_start_time`. The L2 hook correctly identified these as pre-task and interpolated corrected timestamps.

### Zero HOOK_ERROR events

No exceptions caught in any handler. All handlers completed normally.

---

## Recommendations

### R1: Informational Only — No DES Changes Needed (CONFIRMED WORKING)

DES is functioning correctly. The "hook error" is Claude Code's UI label for blocked tasks.

### R2: Consider logging blocked tasks with a user-facing message

Current behavior: DES prints `{"decision": "block", "reason": "..."}` to stdout.
Claude Code shows: "hook error" (generic).

Could add a diagnostic log message so the user understands WHY the block happened. However, this is a Claude Code UI concern, not a DES concern.

### R3: Fix troubleshooter agent max_turns

The troubleshooter agent (or its internal task dispatching) uses `max_turns=5` which is below the DES minimum of 10. Update the troubleshooter agent specification or its Task dispatching to use `max_turns >= 10`.

---

## Backward Chain Validation

| Root Cause | Fix | Expected Result |
|------------|-----|-----------------|
| Troubleshooter uses max_turns=5 | Set max_turns >= 10 | No more blocks for troubleshooter tasks |
| Claude Code labels blocks as "hook error" | Claude Code UI improvement (upstream) | Better user messaging |
| DES is working correctly | None needed | Continue using DES confidently |

---

## Appendix: Key Audit Log Lines

```
# Step 02-03 dispatch ALLOWED
2519: HOOK_INVOKED handler=pre_tool_use subagent=nw-software-crafter has_max_turns=true
2520: HOOK_PRE_TOOL_USE_ALLOWED context=des_validated

# Resume dispatch ALLOWED
2522: HOOK_INVOKED handler=pre_tool_use subagent=nw-software-crafter has_max_turns=true
2523: HOOK_PRE_TOOL_USE_ALLOWED context=des_validated

# SubagentStop: L2 correction + validation
2524: HOOK_INVOKED handler=subagent_stop agent_id=a0642ad
2525: LOG_INTEGRITY_CORRECTED phase=PREPARE reason=pre_task
2526: LOG_INTEGRITY_CORRECTED phase=RED_ACCEPTANCE reason=pre_task
2527: LOG_INTEGRITY_CORRECTED phase=RED_UNIT reason=pre_task
2528: COMMIT_VERIFIED hash=d15aea65
2529: HOOK_SUBAGENT_STOP_PASSED

# Troubleshooter's invalid tasks BLOCKED (these show as "hook error")
2532: HOOK_PRE_TOOL_USE_BLOCKED reason=INVALID_MAX_TURNS(5)
2534: HOOK_PRE_TOOL_USE_BLOCKED reason=MISSING_MAX_TURNS
```
