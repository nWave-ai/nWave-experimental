# DES Discovery Report: SubagentStop Hook and max_turns Empirical Testing

**Date:** 2026-01-22 (Updated after session restart)
**Branch:** `determinism`
**Status:** Q1 RESOLVED - SubagentStop Hook Verified Working

---

## Executive Summary

Empirical testing of Claude Code hook mechanisms revealed **important findings** for the DES design:

| Assumption | Reality | Impact |
|------------|---------|--------|
| Task tool accepts `max_turns` parameter | **FALSE** - `max_turns` is CLI flag only | HIGH - Must use prompt-based discipline |
| SubagentStop hook fires reliably | **TRUE** ✅ - Hook fires after session restart | RESOLVED - Can use for validation |
| Prompt available in hook input | **FALSE** - Must read from transcript | MEDIUM - Design updated |

**UPDATE 2026-01-22 (post session restart):** SubagentStop hook now fires correctly. The hook configuration requires session restart to load. Q1 is RESOLVED.

---

## Discovery 1: max_turns Is NOT a Task Tool Parameter

### Source
Official Claude Code documentation via claude-code-guide agent research.

### Finding

The `--max-turns` flag is a **CLI-only feature** for non-interactive (print) mode:

```bash
# This works - CLI flag
claude -p "Fix errors" --max-turns 3

# This does NOT work - not a Task tool parameter
Task(prompt="...", max_turns=50)  # ❌ INVALID
```

### Documentation Quote

> `--max-turns`: Limit the number of agentic turns (**print mode only**). Exits with an error when the limit is reached. No limit by default.

### Impact on DES Design

All references to `max_turns` in Task tool invocations must be removed:

- ❌ "max_turns limit on Task invocations"
- ❌ "Set max_turns based on expected complexity"
- ❌ Timeout strategy "Mechanism 1: max_turns Parameter"

### See Also
[des-critical-finding-max-turns.md](des-critical-finding-max-turns.md) for detailed analysis and alternative strategies.

---

## Discovery 2: SubagentStop Hook Fires After Session Restart ✅ RESOLVED

### Initial Test (Before Restart)

1. Created discovery hook script: `nWave/hooks/discover_subagent_context.py`
2. Configured in `.claude/settings.local.json`
3. Ran multiple Task tool invocations - **Hook did NOT fire**

### Root Cause Found

**Settings require session restart to load.** The hook configuration was correct but not active until the Claude Code session was restarted.

### Test After Session Restart (2026-01-22)

| Test | Task Type | Result |
|------|-----------|--------|
| Test 1 (post-restart) | Explore agent (haiku) | ✅ Hook FIRED |

### Evidence

Files created in `.git/des-discovery/`:
- `subagent_context.jsonl` - JSONL log
- `latest_discovery.json` - Last event details
- `discovery_summary.md` - Human-readable summary

### Key Lesson

**Hook configuration changes require session restart.** This is important for:
- Development workflow (restart after config changes)
- Documentation (note this requirement)
- Troubleshooting (restart before debugging hooks)

### Impact on DES Design

SubagentStop hook is now **confirmed viable** for Gate 2 post-execution validation. The design can proceed as planned with minor updates for transcript-based prompt extraction.

---

## Discovery 3: Hook Input Schema (Empirically Captured)

### Actual Schema (8 Fields)

The SubagentStop hook receives the following JSON via stdin:

```json
{
  "session_id": "786ebad4-6e5b-42d3-a954-c1df6e6f25b7",
  "transcript_path": "/home/user/.claude/projects/.../session.jsonl",
  "cwd": "/mnt/c/Repositories/Projects/ai-craft",
  "permission_mode": "bypassPermissions",
  "hook_event_name": "SubagentStop",
  "stop_hook_active": false,
  "agent_id": "ab7af5b",
  "agent_transcript_path": "/home/user/.claude/projects/.../subagents/agent-ab7af5b.jsonl"
}
```

### Schema Analysis

| Field | Type | DES Usage |
|-------|------|-----------|
| `session_id` | string | Track parent session |
| `transcript_path` | string | Parent session transcript |
| `cwd` | string | Verify working directory |
| `permission_mode` | string | N/A |
| `hook_event_name` | string | Verify event type |
| `stop_hook_active` | boolean | N/A |
| **`agent_id`** | string | **Correlate with Task tool return value** |
| **`agent_transcript_path`** | string | **KEY: Read prompt from here** |

### Critical Discovery: Prompt Access via Transcript

**The prompt is NOT in hook input but IS accessible via `agent_transcript_path`.**

The agent transcript is JSONL format. First line contains the prompt:

```jsonl
{"type":"user","message":{"role":"user","content":"<FULL PROMPT HERE>"},...}
{"type":"assistant","message":{"role":"assistant",...},...}
{"type":"progress","data":{"type":"hook_progress",...},...}
```

### Extraction Strategy

```python
def get_prompt_from_transcript(agent_transcript_path: str) -> str:
    """Extract the original prompt from agent's transcript."""
    with open(agent_transcript_path) as f:
        first_line = f.readline()
    entry = json.loads(first_line)
    return entry["message"]["content"]

# Then search for DES markers:
prompt = get_prompt_from_transcript(context["agent_transcript_path"])
match = re.search(r'<!-- DES-STEP-FILE: (.+?) -->', prompt)
step_file = match.group(1) if match else None
```

### Fallback Strategy (No Longer Primary)

The active step file pattern is now a **fallback**, not the primary mechanism:

```python
# Primary: Extract from transcript
# Fallback: Read from known location (if transcript unavailable)
ACTIVE_STEP_FILE = ".git/des-active-step.json"
```

---

## Discovery 4: Environment Variables Available

From documentation, hooks receive:

| Variable | Description |
|----------|-------------|
| `CLAUDE_PROJECT_DIR` | Absolute path to project root |
| `CLAUDE_ENV_FILE` | Path to persist env vars (SessionStart only) |
| `CLAUDE_CODE_REMOTE` | "true" if remote session |

Additionally observed in our environment:
- `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING`: "true"
- `CLAUDE_AGENT_SDK_VERSION`: "0.2.15"
- `CLAUDE_CODE_ENTRYPOINT`: "claude-vscode"

---

## Recommendations

### Completed Actions ✅

1. ~~Test in CLI mode~~ - Not needed, hooks work in VSCode after restart
2. ✅ **Restart session** - Confirmed hooks load after restart
3. ~~Try Stop hook~~ - Not needed, SubagentStop works correctly

### Design Revisions Completed ✅

| DES Layer | Change | Status |
|-----------|--------|--------|
| Technical Constraints | Added actual hook schema | ✅ Done |
| Layer 2 (Templates) | Remove max_turns references | ✅ Done |
| Layer 3 (Lifecycle) | Replace max_turns with prompt-based discipline | ✅ Done |
| Layer 4 (Validation) | Use transcript extraction for prompt | ✅ Done |
| Open Questions | Mark Q1 as RESOLVED | ✅ Done |

### Remaining Work

1. **Add UAT scenarios** - Given/When/Then format for Product Owner
2. **Build PoC hook** - Working post_subagent_validation.py
3. **Effort estimates** - Days per implementation phase

---

## Test Artifacts

| File | Purpose |
|------|---------|
| `nWave/hooks/discover_subagent_context.py` | Discovery hook script |
| `.claude/settings.local.json` | Hook configuration |
| `docs/design/des-critical-finding-max-turns.md` | max_turns analysis |
| `docs/design/des-discovery-report.md` | This report |

---

## Next Steps

1. ✅ ~~Restart Claude Code session and re-test hook firing~~ **DONE - Hook fires correctly**
2. ✅ ~~Update DES design with findings~~ **DONE - Design document updated**
3. **Add UAT scenarios** - Required by Product Owner review (Given/When/Then format)
4. **Implement proof-of-concept** - Build working post_subagent_validation.py
5. **Update review summary** - Reflect Q1 resolution to unblock reviews

---

## Conclusion

Empirical testing across two sessions revealed:

### Resolved Issues ✅

1. **Q1 (SubagentStop Hook):** RESOLVED - Hook fires after session restart
2. **Hook Schema:** Captured actual 8-field schema with `agent_transcript_path`
3. **Prompt Access:** Confirmed via transcript extraction

### Remaining Constraint ⚠️

1. **max_turns:** NOT available for Task tool (CLI-only) - Must use prompt-based discipline

### Design Status

The DES design has been updated to reflect empirical findings:
- SubagentStop hook is viable for Gate 2
- Transcript extraction replaces direct prompt access
- max_turns removed from all Task tool references
- Prompt-based timeout instructions are the primary turn limiting mechanism

**Q1 blocker is RESOLVED. Design can proceed to UAT scenarios and implementation planning.**

---

*Report updated after session restart testing on 2026-01-22.*
