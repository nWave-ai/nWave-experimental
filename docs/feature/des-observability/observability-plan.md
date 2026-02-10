# DES Observability Infrastructure Design

**Feature**: des-observability
**Author**: platform-architect (Apex)
**Date**: 2026-02-10
**Status**: DESIGN (Phase 3 -- Platform Design)

---

## 1. Current State Analysis

### 1.1 Event Inventory (from source code and audit log)

The following table maps every code path in the four hook handlers to its current
audit logging behavior. Events marked "MISSING" represent observability gaps.

| Handler | Code Path | Event Logged | Fields | Gap? |
|---------|-----------|-------------|--------|------|
| `handle_pre_tool_use` | Entry | `HOOK_INVOKED` | handler, input_summary | No |
| `handle_pre_tool_use` | Empty stdin | (none) | -- | **YES** |
| `handle_pre_tool_use` | JSON parse error | (none) | -- | **YES** |
| `handle_pre_tool_use` | Service: allow | `HOOK_PRE_TOOL_USE_ALLOWED` | context | No |
| `handle_pre_tool_use` | Service: block | `HOOK_PRE_TOOL_USE_BLOCKED` | reason | No |
| `handle_pre_tool_use` | Exception | `HOOK_ERROR` | error, handler | No |
| `handle_pre_tool_use` | Return exit code | (none) | -- | **YES** |
| `handle_subagent_stop` | Entry | `HOOK_INVOKED` | handler, input_summary | No |
| `handle_subagent_stop` | Empty stdin | (none) | -- | **YES** |
| `handle_subagent_stop` | JSON parse error | (none) | -- | **YES** |
| `handle_subagent_stop` | Non-DES passthrough | `HOOK_INVOKED` (reused) | handler=subagent_stop_passthrough | Misleading |
| `handle_subagent_stop` | Service: allow | `HOOK_SUBAGENT_STOP_PASSED` | feature_name, step_id | No |
| `handle_subagent_stop` | Service: block | `HOOK_SUBAGENT_STOP_FAILED` | feature_name, step_id, errors | No |
| `handle_subagent_stop` | Exception | `HOOK_ERROR` | error, handler | No |
| `handle_subagent_stop` | Return exit code | (none) | -- | **YES** |
| `handle_post_tool_use` | Entry | `HOOK_INVOKED` | handler, input_summary | No |
| `handle_post_tool_use` | Empty stdin | (none) | -- | **YES** |
| `handle_post_tool_use` | JSON parse error | (none) | -- | **YES** |
| `handle_post_tool_use` | Context injected | (none) | -- | **YES** |
| `handle_post_tool_use` | No context | (none) | -- | **YES** |
| `handle_post_tool_use` | Exception | `HOOK_ERROR` | error, handler | No |
| `handle_post_tool_use` | Return exit code | (none) | -- | **YES** |
| `handle_pre_write` | Entry | (none) | -- | **YES** |
| `handle_pre_write` | Empty stdin | (none) | -- | **YES** |
| `handle_pre_write` | JSON parse error | (none) | -- | **YES** |
| `handle_pre_write` | Policy: allowed | (none) | -- | **YES** |
| `handle_pre_write` | Policy: blocked | (none) | -- | **YES** |
| `handle_pre_write` | Exception | (none) | -- | **YES** |
| `handle_pre_write` | Return exit code | (none) | -- | **YES** |

### 1.2 Quantitative Evidence from Today's Log

Source: `.nwave/logs/des/audit-2026-02-10.log` (2,560 lines)

| Event Type | Count | Notes |
|-----------|-------|-------|
| `HOOK_INVOKED` | 780 | Entry diagnostic for 3 of 4 handlers |
| `HOOK_PRE_TOOL_USE_ALLOWED` | 161 | Service-level decision |
| `HOOK_PRE_TOOL_USE_BLOCKED` | 157 | Service-level decision |
| `HOOK_SUBAGENT_STOP_PASSED` | 118 | Service-level decision |
| `HOOK_SUBAGENT_STOP_FAILED` | 144 | Service-level decision |
| `HOOK_TRANSCRIPT_NO_MARKERS` | 67 | Diagnostic, non-DES passthrough |
| `HOOK_TRANSCRIPT_ERROR` | 10 | Transcript file missing |
| `COMMIT_VERIFIED` | 70 | Sub-event of subagent_stop |
| `COMMIT_NOT_VERIFIED` | 32 | Sub-event of subagent_stop |
| `LOG_INTEGRITY_WARNING` | 95 | Timestamp fabrication detected |
| `LOG_INTEGRITY_CORRECTED` | 10 | Timestamps corrected |
| `TASK_INVOCATION_STARTED` | 498 | From installer/test framework |
| `TASK_INVOCATION_VALIDATED` | 364 | From installer/test framework |
| `HOOK_PRE_TASK_PASSED` | 36 | Legacy event (hardcoded 2026-01-26 timestamp) |
| `HOOK_PRE_TASK_BLOCKED` | 18 | Legacy event (hardcoded 2026-01-26 timestamp) |
| `HOOK_ERROR` | 0 | No crashes today |

Key observations:
- 780 HOOK_INVOKED but only 161+157=318 pre_tool_use decisions = 462 invocations are subagent_stop/post_tool_use entries (cross-checked with handler field)
- Zero `pre_write`/`pre_edit` events in the entire log despite active deliver sessions
- Legacy events (`HOOK_PRE_TASK_PASSED/BLOCKED`) use hardcoded timestamps from January, indicating stale test fixtures contaminating production audit logs
- No timing data on any event -- impossible to detect slow hooks
- No correlation between pre_tool_use ALLOWED and the corresponding subagent_stop for the same Task

### 1.3 Gap Severity Assessment

| # | Gap | Severity | Impact |
|---|-----|----------|--------|
| G1 | `handle_pre_write` has zero logging | **CRITICAL** | Session guard decisions are invisible. A blocked write looks identical to a non-invoked hook. Cannot audit whether orchestrator bypassed DES. |
| G2 | No exit code logged at handler return | **HIGH** | Claude Code shows "hook error" for both exit 1 (crash) and exit 2 (block). Without exit code in audit log, must read Claude Code's UI or stderr to distinguish. |
| G3 | No correlation ID across hook lifecycle | **HIGH** | Cannot trace PreToolUse(allow) -> SubagentStop(pass/fail) -> PostToolUse(inject) for the same Task invocation. Today's log has 780 HOOK_INVOKED events with no way to group them per-task. |
| G4 | No hook execution timing | **HIGH** | Hooks run synchronously; Claude Code has a timeout (likely 60s). Slow hooks cause silent failures. No way to measure or alert on hook latency. |
| G5 | `handle_post_tool_use` decision not logged | **MEDIUM** | Whether additionalContext was injected is invisible. If PostToolUse fails to inject context, the orchestrator silently loses the DES completion notification. |
| G6 | Empty stdin / JSON parse errors not logged | **MEDIUM** | These are fail-open paths (return 0 / allow). Without logging, a broken Claude Code protocol change silently bypasses all validation. |
| G7 | stderr not captured in audit log | **MEDIUM** | Python import errors, uncaught exceptions in module load -- all go to stderr which Claude Code captures but our audit log does not. |
| G8 | Legacy events with hardcoded timestamps | **LOW** | Test fixtures writing `HOOK_PRE_TASK_PASSED` with `2026-01-26T10:00:00` pollute the audit log. Confusing during investigation but not a functional gap. |

---

## 2. Proposed Event Taxonomy

### 2.1 Design Principles

1. **Every handler entry gets a HOOK_INVOKED** -- consistent across all 4 handlers.
2. **Every handler exit gets a HOOK_COMPLETED** -- captures exit_code, duration, and decision.
3. **Decision events remain in the application service layer** -- no change to existing PreToolUseService/SubagentStopService logging.
4. **Protocol-level anomalies get explicit events** -- empty stdin, JSON parse failures, stderr capture.
5. **Correlation via `hook_id`** -- a UUID generated at handler entry, propagated to all events within that invocation.
6. **Task lifecycle correlation via `task_correlation_id`** -- derived from agent_id or signal file, linking PreToolUse -> SubagentStop -> PostToolUse.

### 2.2 Complete Event Catalog

#### 2.2.1 Adapter-Level Events (claude_code_hook_adapter.py)

These are emitted by the adapter layer (protocol translation), not the application services.

```
HOOK_INVOKED
  When: Handler entry, after stdin read, before any processing
  Fields:
    hook_id: str           # UUID4, unique per invocation
    handler: str           # "pre_tool_use" | "subagent_stop" | "post_tool_use" | "pre_write"
    input_summary: dict    # Handler-specific summary (sanitized, no secrets)
    timestamp: str         # ISO 8601

HOOK_COMPLETED
  When: Handler exit, just before sys.exit()
  Fields:
    hook_id: str           # Same UUID as HOOK_INVOKED
    handler: str
    exit_code: int         # 0=allow, 1=error, 2=block
    decision: str          # "allow" | "block" | "error" | "passthrough"
    duration_ms: float     # Wall-clock time from entry to exit
    task_correlation_id: str | null  # Links to Task lifecycle (see 3.1)
    timestamp: str

HOOK_PROTOCOL_ANOMALY
  When: Empty stdin, JSON parse failure, or unexpected protocol shape
  Fields:
    hook_id: str
    handler: str
    anomaly_type: str      # "empty_stdin" | "json_parse_error" | "missing_field"
    detail: str            # Error message or description
    fallback_action: str   # "allow" | "block" (what the hook did)
    timestamp: str

HOOK_ERROR
  When: Unhandled exception in handler (existing event, enhanced)
  Fields:
    hook_id: str
    handler: str
    error_type: str        # Exception class name
    error_message: str     # Exception message (truncated to 500 chars)
    stderr_capture: str    # First 1000 chars of stderr if available
    exit_code: int         # Always 1 for pre_tool_use/subagent_stop, 0 for post_tool_use
    duration_ms: float
    timestamp: str
```

#### 2.2.2 Pre-Write/Edit Events (NEW -- currently zero logging)

```
HOOK_PRE_WRITE_INVOKED
  When: handle_pre_write() entry
  Fields:
    hook_id: str
    handler: str           # "pre_write" | "pre_edit"
    file_path: str         # The file being written/edited
    session_active: bool   # deliver-session.json exists?
    des_task_active: bool  # des-task-active signal exists?
    timestamp: str

HOOK_PRE_WRITE_ALLOWED
  When: SessionGuardPolicy returns blocked=False
  Fields:
    hook_id: str
    file_path: str
    reason: str            # "no_session" | "allowed_path" | "not_protected" | "des_active"
    timestamp: str

HOOK_PRE_WRITE_BLOCKED
  When: SessionGuardPolicy returns blocked=True
  Fields:
    hook_id: str
    file_path: str
    reason: str            # Full block reason from policy
    timestamp: str
```

#### 2.2.3 Application Service Events (existing -- no changes)

These events are already emitted by PreToolUseService and SubagentStopService.
The only enhancement is adding `hook_id` for correlation.

```
HOOK_PRE_TOOL_USE_ALLOWED   (existing, add hook_id)
HOOK_PRE_TOOL_USE_BLOCKED   (existing, add hook_id)
HOOK_SUBAGENT_STOP_PASSED   (existing, add hook_id)
HOOK_SUBAGENT_STOP_FAILED   (existing, add hook_id)
COMMIT_VERIFIED             (existing, add hook_id)
COMMIT_NOT_VERIFIED         (existing, add hook_id)
LOG_INTEGRITY_WARNING       (existing, no change)
LOG_INTEGRITY_CORRECTED     (existing, no change)
SCOPE_VIOLATION             (existing, no change)
```

#### 2.2.4 PostToolUse Decision Events (NEW)

```
HOOK_POST_TOOL_USE_INJECTED
  When: PostToolUseService returns additionalContext (non-None)
  Fields:
    hook_id: str
    context_type: str       # "continuation" | "failure_notification"
    feature_name: str
    step_id: str
    is_des_task: bool
    timestamp: str

HOOK_POST_TOOL_USE_PASSTHROUGH
  When: PostToolUseService returns None (no injection)
  Fields:
    hook_id: str
    is_des_task: bool
    reason: str             # "not_des_task" | "no_recent_event" | "no_failure"
    timestamp: str
```

### 2.3 Event Naming Convention

Pattern: `HOOK_{HANDLER}_{OUTCOME}`

- `HOOK_INVOKED` / `HOOK_COMPLETED` -- adapter lifecycle (all handlers)
- `HOOK_PRE_TOOL_USE_ALLOWED` / `HOOK_PRE_TOOL_USE_BLOCKED` -- PreToolUse decisions
- `HOOK_PRE_WRITE_ALLOWED` / `HOOK_PRE_WRITE_BLOCKED` -- PreWrite decisions
- `HOOK_SUBAGENT_STOP_PASSED` / `HOOK_SUBAGENT_STOP_FAILED` -- SubagentStop decisions
- `HOOK_POST_TOOL_USE_INJECTED` / `HOOK_POST_TOOL_USE_PASSTHROUGH` -- PostToolUse decisions
- `HOOK_PROTOCOL_ANOMALY` -- protocol-level issues
- `HOOK_ERROR` -- unhandled exceptions

---

## 3. Correlation Strategy

### 3.1 Hook Invocation Correlation (`hook_id`)

Each handler invocation generates a UUID4 at entry. This UUID is passed through
to the application service via a new optional parameter on the AuditEvent dataclass,
or via a context object.

**Implementation approach**: Thread the `hook_id` through a simple parameter rather
than thread-local or context variable, since hooks are single-threaded processes.

```
# At handler entry:
hook_id = str(uuid.uuid4())

# Passed to service:
service.validate(..., hook_id=hook_id)

# Service includes in all audit events:
AuditEvent(event_type=..., data={..., "hook_id": hook_id})
```

**Cost**: One UUID generation per hook invocation (~0.01ms). Negligible.

### 3.2 Task Lifecycle Correlation (`task_correlation_id`)

A Task tool invocation generates 3 hook events in sequence:
1. PreToolUse:Task (before Task starts)
2. SubagentStop (when agent finishes)
3. PostToolUse:Task (after Task returns to parent)

To correlate these, use `agent_id` as the natural key:
- PreToolUse does NOT have agent_id yet (agent not created). Generate a correlation ID and store it in the signal file.
- SubagentStop receives `agent_id` in hook_input. Read correlation ID from signal file.
- PostToolUse receives the same `tool_input` (including prompt). Read correlation ID from the most recent audit event.

**Signal file enhancement**: Add `task_correlation_id` to the signal written by
`_create_des_task_signal()`:

```json
{
  "step_id": "01-01",
  "project_id": "build-pipeline-elimination",
  "created_at": "2026-02-10T21:25:59Z",
  "task_correlation_id": "a1b2c3d4-...",
  "agent_type": "nw-software-crafter"
}
```

For non-DES tasks (no signal file), use `agent_id` directly as the correlation ID
where available.

### 3.3 Correlation in Audit Log

After implementation, a single DES Task lifecycle produces this audit trail:

```jsonl
{"event":"HOOK_INVOKED","hook_id":"aaa","handler":"pre_tool_use","task_correlation_id":"COR-1",...}
{"event":"HOOK_PRE_TOOL_USE_ALLOWED","hook_id":"aaa","task_correlation_id":"COR-1",...}
{"event":"HOOK_COMPLETED","hook_id":"aaa","exit_code":0,"decision":"allow","duration_ms":35,...}
{"event":"HOOK_INVOKED","hook_id":"bbb","handler":"subagent_stop","task_correlation_id":"COR-1",...}
{"event":"COMMIT_VERIFIED","hook_id":"bbb","task_correlation_id":"COR-1",...}
{"event":"HOOK_SUBAGENT_STOP_PASSED","hook_id":"bbb","task_correlation_id":"COR-1",...}
{"event":"HOOK_COMPLETED","hook_id":"bbb","exit_code":0,"decision":"allow","duration_ms":1200,...}
{"event":"HOOK_INVOKED","hook_id":"ccc","handler":"post_tool_use","task_correlation_id":"COR-1",...}
{"event":"HOOK_POST_TOOL_USE_INJECTED","hook_id":"ccc","task_correlation_id":"COR-1",...}
{"event":"HOOK_COMPLETED","hook_id":"ccc","exit_code":0,"decision":"passthrough","duration_ms":15,...}
```

---

## 4. Performance Monitoring

### 4.1 Hook Execution Timing

Each `HOOK_COMPLETED` event includes `duration_ms`. Measurement approach:

```python
import time

def handle_pre_tool_use() -> int:
    start_ns = time.perf_counter_ns()
    try:
        # ... existing logic ...
        return exit_code
    finally:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        _log_hook_completed(hook_id, handler, exit_code, decision, duration_ms)
```

`time.perf_counter_ns()` is used because:
- Monotonic (immune to clock adjustments)
- Nanosecond resolution (vs `time.time()` millisecond resolution)
- Zero overhead (no syscall on Linux, reads TSC directly)

### 4.2 Performance Budgets

Based on Claude Code's synchronous hook model, the following budgets apply:

| Handler | Target p50 | Target p99 | Alert Threshold |
|---------|-----------|-----------|-----------------|
| pre_tool_use | < 50ms | < 200ms | > 500ms |
| subagent_stop | < 200ms | < 2000ms | > 5000ms |
| post_tool_use | < 30ms | < 100ms | > 300ms |
| pre_write | < 10ms | < 50ms | > 100ms |

Rationale:
- `pre_tool_use`: Simple validation, file reads. 50ms is generous.
- `subagent_stop`: Reads YAML, runs git commands, validates completion. 200ms typical, 2s for large logs.
- `post_tool_use`: Scans JSONL backward. Fast for recent events.
- `pre_write`: File existence checks only. Sub-10ms expected.

### 4.3 Slow Hook Detection

When `duration_ms` exceeds the alert threshold, the `HOOK_COMPLETED` event
includes an additional field:

```json
{
  "event": "HOOK_COMPLETED",
  "hook_id": "...",
  "duration_ms": 5234,
  "slow_hook": true,
  "slow_hook_threshold_ms": 5000
}
```

This enables simple detection via `jq` without needing separate alerting infrastructure.

---

## 5. Error Classification

### 5.1 Exit Code Semantics

| Exit Code | Meaning | Claude Code UI | DES Audit Event |
|-----------|---------|---------------|-----------------|
| 0 | Allow / continue | (invisible) | `HOOK_COMPLETED` with decision="allow" |
| 1 | Fail-closed error | "hook error" | `HOOK_ERROR` + `HOOK_COMPLETED` with decision="error" |
| 2 | Validation block | "hook error" | `HOOK_COMPLETED` with decision="block" |

The fundamental problem: Claude Code displays "hook error" for BOTH exit 1 and
exit 2. The user cannot distinguish "DES correctly blocked an invalid Task" from
"DES crashed with an import error."

### 5.2 Classification in Audit Log

After this design, the audit log always tells you the truth:

| Scenario | Audit Trail | How to Find |
|----------|-------------|-------------|
| DES correctly blocks invalid Task | `HOOK_PRE_TOOL_USE_BLOCKED` + `HOOK_COMPLETED(exit_code=2, decision="block")` | `jq 'select(.exit_code == 2)'` |
| DES crashes during validation | `HOOK_ERROR(error_type, error_message)` + `HOOK_COMPLETED(exit_code=1, decision="error")` | `jq 'select(.exit_code == 1)'` |
| DES allows valid Task | `HOOK_PRE_TOOL_USE_ALLOWED` + `HOOK_COMPLETED(exit_code=0, decision="allow")` | `jq 'select(.decision == "allow")'` |
| DES silently passes through (empty stdin) | `HOOK_PROTOCOL_ANOMALY(anomaly_type="empty_stdin")` + `HOOK_COMPLETED(exit_code=0)` | `jq 'select(.event == "HOOK_PROTOCOL_ANOMALY")'` |
| Hook process killed by timeout | No `HOOK_COMPLETED` for the `hook_id` in `HOOK_INVOKED` | `HOOK_INVOKED` without matching `HOOK_COMPLETED` |
| Python import fails before handler | No `HOOK_INVOKED` at all | Absence of expected events (requires external monitoring) |

### 5.3 Timeout Detection

If Claude Code kills a hook process (timeout), the handler never reaches the
`finally` block, so `HOOK_COMPLETED` is never written. This creates a detectable
pattern: `HOOK_INVOKED` without a corresponding `HOOK_COMPLETED` for the same
`hook_id`.

Detection query:

```bash
# Find orphaned HOOK_INVOKED (no matching HOOK_COMPLETED)
jq -r 'select(.event == "HOOK_INVOKED") | .hook_id' audit.log | sort > /tmp/invoked.txt
jq -r 'select(.event == "HOOK_COMPLETED") | .hook_id' audit.log | sort > /tmp/completed.txt
comm -23 /tmp/invoked.txt /tmp/completed.txt
```

### 5.4 stderr Capture

When an exception occurs, stderr output from the Python process (import errors,
traceback fragments) is currently lost. The adapter's main() function should
capture stderr to a buffer and include it in the `HOOK_ERROR` event:

```python
# In main(), wrap handler calls with stderr capture
import io, contextlib

stderr_buffer = io.StringIO()
with contextlib.redirect_stderr(stderr_buffer):
    exit_code = handler()

# If exit_code indicates error, include stderr in HOOK_ERROR
stderr_output = stderr_buffer.getvalue()[:1000]
```

Constraint: This only captures stderr from Python code within the process. If
Python itself fails to start (syntax error in module), stderr goes directly to
Claude Code and cannot be captured by the process.

---

## 6. Implementation Roadmap

### 6.1 Priority Order

Implementation is ordered by gap severity and dependency chain.

#### Phase 1: Foundation (CRITICAL -- unblocks all other phases)

**P1-1: Add hook_id generation to adapter**

File: `src/des/adapters/drivers/hooks/claude_code_hook_adapter.py`

Changes:
- Add `import uuid` at top
- Generate `hook_id = str(uuid.uuid4())` at the start of each handler
- Pass `hook_id` to `_log_hook_invoked()` and new `_log_hook_completed()`
- Add `hook_id` field to all `HOOK_INVOKED` events

Tests:
- Unit test: hook_id is a valid UUID4
- Unit test: hook_id is unique per invocation
- Unit test: hook_id appears in HOOK_INVOKED event

Estimate: 1 TDD step

**P1-2: Add HOOK_COMPLETED event**

File: `src/des/adapters/drivers/hooks/claude_code_hook_adapter.py`

Changes:
- Add `_log_hook_completed(hook_id, handler, exit_code, decision, duration_ms)` function
- Add timing with `time.perf_counter_ns()` at handler entry
- Call `_log_hook_completed()` in `finally` block of each handler
- Wrap in try/except (logging must never break the hook)

Tests:
- Unit test: HOOK_COMPLETED emitted on allow path
- Unit test: HOOK_COMPLETED emitted on block path
- Unit test: HOOK_COMPLETED emitted on error path
- Unit test: duration_ms is positive float
- Unit test: exit_code matches handler return value

Estimate: 1 TDD step

#### Phase 2: Pre-Write Observability (CRITICAL gap G1)

**P2-1: Add logging to handle_pre_write**

File: `src/des/adapters/drivers/hooks/claude_code_hook_adapter.py`

Changes:
- Add HOOK_INVOKED logging at entry (like other handlers)
- Add HOOK_PRE_WRITE_ALLOWED / HOOK_PRE_WRITE_BLOCKED logging after policy check
- Add HOOK_COMPLETED logging at exit
- All in try/except (fail-open for Write/Edit)

Tests:
- Unit test: HOOK_INVOKED emitted with handler="pre_write"
- Unit test: HOOK_PRE_WRITE_ALLOWED emitted when session not active
- Unit test: HOOK_PRE_WRITE_ALLOWED emitted for allowed path
- Unit test: HOOK_PRE_WRITE_BLOCKED emitted when guard blocks
- Unit test: HOOK_COMPLETED emitted with correct exit_code

Estimate: 1 TDD step

#### Phase 3: Protocol Anomaly Logging (gap G6)

**P3-1: Log empty stdin and JSON parse errors**

File: `src/des/adapters/drivers/hooks/claude_code_hook_adapter.py`

Changes:
- In each handler's empty-stdin branch: emit `HOOK_PROTOCOL_ANOMALY(anomaly_type="empty_stdin")`
- In each handler's JSON parse branch: emit `HOOK_PROTOCOL_ANOMALY(anomaly_type="json_parse_error")`
- Include `fallback_action` field ("allow" or "block")

Tests:
- Unit test: empty stdin produces HOOK_PROTOCOL_ANOMALY
- Unit test: malformed JSON produces HOOK_PROTOCOL_ANOMALY
- Unit test: fallback_action matches actual handler behavior

Estimate: 1 TDD step

#### Phase 4: PostToolUse Decision Logging (gap G5)

**P4-1: Add decision logging to PostToolUseService**

File: `src/des/application/post_tool_use_service.py`

Changes:
- Accept `audit_writer` and `time_provider` as constructor dependencies
- Emit `HOOK_POST_TOOL_USE_INJECTED` when returning context
- Emit `HOOK_POST_TOOL_USE_PASSTHROUGH` when returning None

Alternative: Keep PostToolUseService unchanged and add logging in the adapter
layer (simpler, avoids changing PostToolUseService interface).

Preferred approach: Adapter-layer logging (consistent with other adapter events).

File: `src/des/adapters/drivers/hooks/claude_code_hook_adapter.py`

Changes:
- After `service.check_completion_status()` returns, log the decision
- If `additional_context` is non-None: log HOOK_POST_TOOL_USE_INJECTED
- If `additional_context` is None: log HOOK_POST_TOOL_USE_PASSTHROUGH

Tests:
- Unit test: INJECTED event when context returned
- Unit test: PASSTHROUGH event when no context

Estimate: 1 TDD step

#### Phase 5: Task Lifecycle Correlation (gap G3)

**P5-1: Add task_correlation_id to signal file**

File: `src/des/adapters/drivers/hooks/claude_code_hook_adapter.py`

Changes:
- In `_create_des_task_signal()`: generate and store `task_correlation_id`
- In `handle_pre_tool_use()`: include `task_correlation_id` in HOOK_COMPLETED
- In `handle_subagent_stop()`: read `task_correlation_id` from signal before removal
- In `handle_post_tool_use()`: read `task_correlation_id` from most recent audit event

Tests:
- Unit test: signal file contains task_correlation_id
- Unit test: HOOK_COMPLETED includes task_correlation_id for DES tasks
- Unit test: subagent_stop reads correlation_id from signal
- Integration test: full lifecycle produces consistent correlation_id

Estimate: 2 TDD steps

**P5-2: Thread hook_id into application services**

Files:
- `src/des/ports/driven_ports/audit_log_writer.py` -- add optional `hook_id` to AuditEvent
- `src/des/application/pre_tool_use_service.py` -- accept and forward hook_id
- `src/des/application/subagent_stop_service.py` -- accept and forward hook_id

Changes:
- Add `hook_id: str | None = None` to `AuditEvent` dataclass
- Add `hook_id` parameter to service `validate()` methods
- Forward to all `AuditEvent` instances created within services
- JsonlAuditLogWriter includes `hook_id` in JSON output when non-None

Tests:
- Unit test: hook_id propagates from service to audit event
- Unit test: hook_id appears in serialized JSON
- Unit test: hook_id=None omits field from JSON (backward compatible)

Estimate: 1 TDD step

#### Phase 6: stderr Capture and Enhanced HOOK_ERROR (gap G7)

**P6-1: Capture stderr in error events**

File: `src/des/adapters/drivers/hooks/claude_code_hook_adapter.py`

Changes:
- In `main()`: add stderr redirect to StringIO buffer
- On exception: include truncated stderr in HOOK_ERROR event
- Add `error_type` (exception class name) to HOOK_ERROR

Tests:
- Unit test: stderr captured in HOOK_ERROR data
- Unit test: stderr truncated to 1000 chars
- Unit test: error_type is exception class name

Estimate: 1 TDD step

### 6.2 Dependency Graph

```
P1-1 (hook_id) ──> P1-2 (HOOK_COMPLETED) ──> P5-2 (thread hook_id to services)
                                           ──> P6-1 (stderr capture)
                   P2-1 (pre_write logging)     [independent]
                   P3-1 (protocol anomaly)      [independent]
                   P4-1 (post_tool_use decision) [independent]
                   P5-1 (task_correlation_id)   [independent]
```

P1-1 and P1-2 are prerequisites for P5-2 and P6-1.
P2-1, P3-1, P4-1, and P5-1 can proceed in parallel after P1-1.

### 6.3 Total Effort

8 TDD steps across 6 phases. Each step is one `*deliver` cycle with
RED-GREEN-REFACTOR. Estimated wall-clock: 4-6 hours of agent time.

### 6.4 Architectural Constraints

1. **AuditEvent dataclass change** (P5-2): Adding `hook_id` to AuditEvent is a
   port interface change. All existing tests that construct AuditEvent must remain
   passing (default None ensures backward compatibility).

2. **No new dependencies**: uuid is stdlib. time is stdlib. No new packages.

3. **No service interface changes for P2-1/P3-1/P4-1**: All new logging in these
   phases happens in the adapter layer, not the application services. This keeps
   the hexagonal boundary clean.

4. **Performance budget**: Each new log_event() call adds ~0.5ms (file append).
   Pre-write handler adds 2 calls (INVOKED + COMPLETED). Total overhead per
   Write/Edit: ~1ms. Acceptable given the 100ms budget.

---

## 7. Dashboard and Query Examples

All queries operate on the JSONL audit log using standard Unix tools (`jq`, `grep`).
No external dependencies.

### 7.1 Troubleshooting: "Why did Claude Code show hook error?"

This is the exact scenario that motivated this design. Currently requires 30+ minutes
of investigation. After implementation, it takes one command.

```bash
# Show all blocks and errors from the last hour with exit codes
jq -r 'select(.event == "HOOK_COMPLETED" and .exit_code > 0) |
  "\(.timestamp) exit=\(.exit_code) handler=\(.handler) decision=\(.decision)"' \
  .nwave/logs/des/audit-2026-02-10.log | tail -20
```

Interpretation:
- `exit=2, decision=block` -- DES correctly blocked an invalid invocation. Read the
  corresponding `HOOK_PRE_TOOL_USE_BLOCKED` event for the reason.
- `exit=1, decision=error` -- DES crashed. Read the `HOOK_ERROR` event for the traceback.

### 7.2 Troubleshooting: "Did my Task get blocked or allowed?"

```bash
# Find all decisions for a specific subagent type
jq -r 'select(.event == "HOOK_COMPLETED" and .handler == "pre_tool_use") |
  "\(.timestamp) \(.decision) \(.exit_code) hook_id=\(.hook_id)"' \
  .nwave/logs/des/audit-2026-02-10.log | tail -10
```

### 7.3 Troubleshooting: "What happened to my DES Task lifecycle?"

```bash
# Trace a complete Task lifecycle by correlation ID
CORR_ID="a1b2c3d4-..."
jq -r "select(.task_correlation_id == \"$CORR_ID\") |
  \"\(.timestamp) \(.event) hook_id=\(.hook_id // \"n/a\")\"" \
  .nwave/logs/des/audit-2026-02-10.log
```

### 7.4 Troubleshooting: "Are hooks running slowly?"

```bash
# Show slow hooks (>500ms)
jq -r 'select(.event == "HOOK_COMPLETED" and .duration_ms > 500) |
  "\(.timestamp) \(.handler) \(.duration_ms)ms"' \
  .nwave/logs/des/audit-2026-02-10.log
```

### 7.5 Troubleshooting: "Is the session guard working?"

```bash
# Show all pre_write decisions (currently ZERO events -- the critical gap)
jq -r 'select(.event | startswith("HOOK_PRE_WRITE")) |
  "\(.timestamp) \(.event) file=\(.file_path // "n/a")"' \
  .nwave/logs/des/audit-2026-02-10.log
```

### 7.6 Monitoring: "Hook timeout detection"

```bash
# Find HOOK_INVOKED without matching HOOK_COMPLETED (possible timeouts)
comm -23 \
  <(jq -r 'select(.event == "HOOK_INVOKED") | .hook_id' audit.log | sort) \
  <(jq -r 'select(.event == "HOOK_COMPLETED") | .hook_id' audit.log | sort)
```

### 7.7 Daily Summary Dashboard

```bash
# Daily hook health summary
echo "=== DES Hook Health Summary ==="
echo ""
echo "--- Decisions ---"
jq -r '.event' .nwave/logs/des/audit-2026-02-10.log | sort | uniq -c | sort -rn
echo ""
echo "--- Exit Code Distribution ---"
jq -r 'select(.event == "HOOK_COMPLETED") | .exit_code' \
  .nwave/logs/des/audit-2026-02-10.log | sort | uniq -c | sort -rn
echo ""
echo "--- Slow Hooks (>500ms) ---"
jq -r 'select(.event == "HOOK_COMPLETED" and .duration_ms > 500) |
  "\(.handler): \(.duration_ms)ms"' .nwave/logs/des/audit-2026-02-10.log | head -10
echo ""
echo "--- Protocol Anomalies ---"
jq -r 'select(.event == "HOOK_PROTOCOL_ANOMALY") |
  "\(.anomaly_type): \(.handler)"' .nwave/logs/des/audit-2026-02-10.log | sort | uniq -c
echo ""
echo "--- Errors ---"
jq -r 'select(.event == "HOOK_ERROR") |
  "\(.handler): \(.error_type) - \(.error_message)"' \
  .nwave/logs/des/audit-2026-02-10.log
```

### 7.8 Orphaned Subagent Detection

```bash
# Find Tasks that got PreToolUse ALLOW but never hit SubagentStop
# (agent may have been killed, or SubagentStop hook not firing)
comm -23 \
  <(jq -r 'select(.event == "HOOK_COMPLETED" and .handler == "pre_tool_use"
      and .decision == "allow" and .task_correlation_id != null)
    | .task_correlation_id' audit.log | sort -u) \
  <(jq -r 'select(.event == "HOOK_COMPLETED" and .handler == "subagent_stop"
      and .task_correlation_id != null)
    | .task_correlation_id' audit.log | sort -u)
```

---

## 8. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| hook_id adds import cost (uuid module) | Low | Low | uuid is stdlib, already loaded by Python runtime in most cases. Measure in P1-1. |
| HOOK_COMPLETED logging fails in finally block | Medium | High | Wrap in try/except (same pattern as HOOK_INVOKED). Test explicitly. |
| task_correlation_id lost if signal file deleted by external process | Low | Medium | Graceful degradation: log with null correlation_id. |
| Audit log grows too large with new events | Medium | Low | Each handler adds 1-2 events. Current rate: ~2560 events/day. After: ~4000/day. At ~200 bytes/event, that is ~800KB/day. Negligible. |
| time.perf_counter_ns() unavailable (Python < 3.7) | Very Low | Low | DES already requires Python 3.10+. Non-issue. |

---

## 9. What This Design Does NOT Cover

1. **External monitoring/alerting** -- No Prometheus, Grafana, or PagerDuty integration. File-based only per constraint.
2. **Log retention/rotation** -- Daily files already rotate by date. No archival policy designed here.
3. **Real-time dashboards** -- All queries are batch (grep/jq). No streaming or live tail tooling.
4. **Hook configuration observability** -- Whether Claude Code's `settings.json` correctly routes hooks is outside DES scope.
5. **Application-level business metrics** -- TDD phase success rates, step completion times, etc. These are derived analytics, not infrastructure observability.

---

## 10. Acceptance Criteria

The implementation is complete when:

1. Every handler (pre_tool_use, subagent_stop, post_tool_use, pre_write) emits `HOOK_INVOKED` at entry and `HOOK_COMPLETED` at exit.
2. `HOOK_COMPLETED` includes `exit_code`, `decision`, `duration_ms`, and `hook_id`.
3. `handle_pre_write` emits `HOOK_PRE_WRITE_ALLOWED` or `HOOK_PRE_WRITE_BLOCKED` for every invocation.
4. Empty stdin and JSON parse errors produce `HOOK_PROTOCOL_ANOMALY` events.
5. PostToolUse decisions are logged (INJECTED or PASSTHROUGH).
6. `hook_id` correlates all events within a single handler invocation.
7. `task_correlation_id` links PreToolUse -> SubagentStop -> PostToolUse for DES tasks.
8. All new logging is wrapped in try/except (never breaks hook execution).
9. All existing tests pass without modification (backward-compatible AuditEvent changes).
10. The daily summary dashboard query (Section 7.7) produces meaningful output.

---

## 11. Log Format Standardization (User Requirement)

Current DES logs have inconsistent, verbose, and hard-to-query formats. This section addresses the requirement to make logs more **readable, queryable, and less token-intensive**.

### 11.1 Current Problems

#### execution-log.yaml: Pipe-Delimited Strings in YAML

Current format (pipe-delimited strings):
```yaml
events:
  - "01-01|PREPARE|EXECUTED|PASS|2026-02-10T12:01:00Z"
  - "01-01|RED_ACCEPTANCE|EXECUTED|PASS|2026-02-10T12:02:00Z"
```

Problems:
- **Not queryable**: Cannot use standard YAML tools to filter by step_id or phase
- **Not parseable**: Requires custom split-on-pipe logic; breaks if data contains `|`
- **YAML abuse**: Storing structured data as opaque strings inside YAML defeats the purpose
- **Token intensive**: When LLMs read the file, they see raw strings they must mentally parse
- **Comments get lost**: YAML dump removes human-friendly comments

#### audit-log JSONL: Inconsistent Keys

Current issues:
- Some events use `feature_name`, others use `project_id` for the same concept
- Legacy events (`HOOK_PRE_TASK_PASSED`) use hardcoded timestamps from January 2026
- Key order varies by event type, making visual scanning difficult
- Verbose field names (`input_summary`, `has_max_turns`) consume tokens when LLMs read logs

### 11.2 Proposed: execution-log.yaml Structured Format

Replace pipe-delimited strings with proper YAML objects:

```yaml
schema_version: "3.0"
project_id: "build-pipeline-elimination"
events:
  - sid: "01-01"
    p: PREPARE
    s: EXECUTED
    d: PASS
    t: "2026-02-10T12:01:00Z"
  - sid: "01-01"
    p: RED_ACCEPTANCE
    s: EXECUTED
    d: PASS
    t: "2026-02-10T12:02:00Z"
```

Field mapping (short keys for token efficiency):
- `sid` = step_id
- `p` = phase
- `s` = status (EXECUTED | SKIPPED)
- `d` = data (PASS | FAIL | skip reason)
- `t` = timestamp

Benefits:
- **Queryable**: `yq '.events[] | select(.sid == "01-01" and .p == "COMMIT")'`
- **Token efficient**: ~40 chars per entry vs ~55 for pipe format
- **Standard YAML**: Tools like yq, Python yaml.safe_load work natively
- **Migration**: Bump schema_version to "3.0", add reader support for both formats

### 11.3 Proposed: Audit Log Compact JSONL Format

Standardize field naming and use short keys:

Current (verbose):
```json
{"event":"HOOK_INVOKED","handler":"pre_tool_use","input_summary":{"has_max_turns":true,"subagent_type":"nw-software-crafter"},"timestamp":"2026-02-10T21:25:59.030505+00:00"}
```

Proposed (compact):
```json
{"e":"HI","h":"ptu","ts":"21:25:59Z","sub":"nw-software-crafter","mt":true}
```

Short key mapping:
- `e` = event (with short codes: HI=HOOK_INVOKED, HC=HOOK_COMPLETED, HA=ALLOWED, HB=BLOCKED, HE=ERROR, etc.)
- `h` = handler (ptu=pre_tool_use, ss=subagent_stop, ptl=post_tool_use, pw=pre_write)
- `ts` = timestamp (time only, date is in filename)
- `hid` = hook_id
- `cid` = task_correlation_id
- `sub` = subagent_type
- `mt` = max_turns
- `ex` = exit_code
- `dur` = duration_ms
- `dec` = decision
- `r` = reason

Benefits:
- **~60% token reduction** per line
- **Date in filename** (audit-2026-02-10.log), so timestamps only need HH:MM:SSZ
- **Consistent keys** across all event types
- **Still jq-queryable**: `jq 'select(.e == "HB")'` for all blocks

### 11.4 Migration Strategy

1. **execution-log.yaml**: Bump to schema_version "3.0". YamlExecutionLogReader supports both "2.0" (pipe) and "3.0" (structured). CLI `log_phase` writes "3.0" format. SubagentStop handler reads both.

2. **audit-log**: Version via filename convention: `audit-v2-2026-02-10.log`. New writer uses compact format. Old reader supports both. No migration of historical logs needed.

3. **Backward compatibility**: Both readers detect format automatically. Old tools see new format as valid (just different keys). New tools handle old format gracefully.

### 11.5 Impact on Existing Code

| Component | Change |
|-----------|--------|
| `src/des/cli/log_phase.py` | Write structured YAML objects instead of pipe strings |
| `src/des/adapters/driven/hooks/yaml_execution_log_reader.py` | Support both pipe (v2) and structured (v3) formats |
| `src/des/adapters/driven/logging/jsonl_audit_log_writer.py` | Use compact keys, time-only timestamps |
| `src/des/adapters/driven/logging/jsonl_audit_log_reader.py` | Support both verbose (v1) and compact (v2) keys |
| `src/des/domain/phase_event.py` | No change (internal model unchanged) |
| `src/des/application/subagent_stop_service.py` | No change (uses PhaseEvent, not raw format) |

### 11.6 Acceptance Criteria for Format Standardization

1. execution-log.yaml uses structured YAML objects (schema_version "3.0")
2. Audit log uses compact JSONL keys (~60% smaller per line)
3. Both readers support old and new formats (backward compatible)
4. CLI `log_phase` writes new format
5. All existing tests pass with format autodetection
6. `jq` and `yq` queries work on new formats

---

## 12. Audit Logging Toggle (User Requirement: OFF by Default)

### 12.1 Problem

Audit logging is currently **always enabled**, creating `.nwave/logs/des/audit-*.log` files for every nWave user even if they don't need observability. This is "log pollution" — files accumulate silently, consuming disk space and creating confusion for users who don't use DES monitoring.

### 12.2 Requirement

- Audit logging **OFF by default** (no log files created unless explicitly enabled)
- Enable via `.nwave/des-config.json` (the nWave configuration file)
- No log pollution for users who don't opt in
- Document the option clearly

### 12.3 Current State Analysis

| Component | Config Check | Location |
|-----------|-------------|----------|
| `DESConfig` class | `audit_logging_enabled` property | `~/.claude/des/config.yaml` (global) |
| Orchestrator (`_log_audit_event_if_enabled`) | Checks `DESConfig` | Line 374 |
| Hook adapter (factory functions) | **No check** — always creates `JsonlAuditLogWriter` | Lines 65, 87, 110 |
| `_log_hook_invoked()` | **No check** — always writes | Line 110 |
| Service layer (PreToolUse, SubagentStop) | Receives writer via DI — always writes | N/A |

**Gap**: The hook adapter — the main source of audit events — bypasses `DESConfig` entirely.

### 12.4 Design: NullObject Pattern

The cleanest hexagonal approach: the composition root (hook adapter factory functions) decides which `AuditLogWriter` implementation to inject based on config.

```
DESConfig.audit_logging_enabled == true  → JsonlAuditLogWriter (writes to disk)
DESConfig.audit_logging_enabled == false → NullAuditLogWriter  (no-op)
```

**NullAuditLogWriter**: Implements `AuditLogWriter` port with empty `log_event()`. No disk I/O, no directory creation.

### 12.5 Config Consolidation

**Before**: Two separate config files for DES:
- `~/.claude/des/config.yaml` — `audit_logging_enabled` (global, YAML)
- `.nwave/des-config.json` — `audit_log_dir` (project-local, JSON)

**After**: Single config file:
- `.nwave/des-config.json` — both `audit_logging_enabled` and `audit_log_dir` (project-local, JSON)

The user requested "dal file di configurazione di nWave" (from the nWave config file). `.nwave/des-config.json` is the natural location:
- Project-local (per-project control)
- Already used for DES config (`audit_log_dir`)
- JSON format (consistent with existing usage)

### 12.6 DESConfig Changes

```python
class DESConfig:
    """Loads DES config from .nwave/des-config.json (project-local)."""

    def __init__(self, config_path: Path | None = None, cwd: Path | None = None):
        if config_path is None:
            effective_cwd = cwd or Path.cwd()
            config_path = effective_cwd / ".nwave" / "des-config.json"
        self._config_path = config_path
        self._config_data = self._load_configuration()

    def _load_configuration(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {}  # No file = all defaults
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    @property
    def audit_logging_enabled(self) -> bool:
        """OFF by default. Enable with {"audit_logging_enabled": true}."""
        return self._config_data.get("audit_logging_enabled", False)
```

Key changes:
1. **Default `False`** (OFF by default)
2. **Read from `.nwave/des-config.json`** (project-local JSON)
3. **No auto-creation** — missing file = defaults (no pollution)
4. **JSON format** (consistent with existing `.nwave/des-config.json`)

### 12.7 Hook Adapter Changes

Factory functions check config before creating audit writer:

```python
def _create_audit_writer() -> AuditLogWriter:
    """Create audit writer based on config. Returns NullAuditLogWriter if disabled."""
    config = DESConfig()
    if not config.audit_logging_enabled:
        return NullAuditLogWriter()
    return JsonlAuditLogWriter()

def create_pre_tool_use_service() -> PreToolUseService:
    audit_writer = _create_audit_writer()  # was: JsonlAuditLogWriter()
    ...

def create_subagent_stop_service() -> SubagentStopService:
    audit_writer = _create_audit_writer()  # was: JsonlAuditLogWriter()
    ...

def _log_hook_invoked(handler, summary=None) -> None:
    config = DESConfig()
    if not config.audit_logging_enabled:
        return
    ...
```

### 12.8 User Configuration

To enable audit logging, add to `.nwave/des-config.json`:

```json
{
  "audit_logging_enabled": true,
  "audit_log_dir": ".nwave/logs/des"
}
```

If `.nwave/des-config.json` doesn't exist or `audit_logging_enabled` is missing/false: no audit files created.

### 12.9 Impact on Observability Phases P1-P6

All observability improvements (hook_id, HOOK_COMPLETED, pre_write logging, etc.) are still implemented — they only produce output when `audit_logging_enabled: true`. The NullAuditLogWriter silently drops events when disabled.

This means:
- **Development/debugging**: Enable logging, get full observability
- **Production/normal use**: Logging off, zero overhead, no file pollution

### 12.10 Acceptance Criteria

1. No `.nwave/logs/des/` files created when `audit_logging_enabled` is absent or `false`
2. Full audit logging when `audit_logging_enabled: true` in `.nwave/des-config.json`
3. `DESConfig` reads from `.nwave/des-config.json` (project-local)
4. `NullAuditLogWriter` implements `AuditLogWriter` port (no-op)
5. Hook adapter uses `NullAuditLogWriter` when logging disabled
6. All existing tests pass
7. Configuration documented in `.nwave/des-config.json` comments or README
