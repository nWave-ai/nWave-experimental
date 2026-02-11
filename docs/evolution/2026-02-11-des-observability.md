# DES Observability Infrastructure

**Date**: 2026-02-11
**Project ID**: des-observability
**Status**: COMPLETED
**Steps**: 11 active + 1 pre-completed (00-01), all verified

## Motivation

The DES hook enforcement system had 8 observability gaps (G1-G8) identified
during production use. Hooks executed silently with no audit trail, making
debugging impossible. Key gaps:

- **G1**: `handle_pre_write` had ZERO logging events
- **G2**: No HOOK_COMPLETED event (couldn't track timing or exit codes)
- **G3**: No correlation between related events (hook_id, task_correlation_id)
- **G4**: No hook_id for event correlation
- **G5**: PostToolUse decisions invisible
- **G6**: Protocol anomalies (empty stdin, JSON errors) silently swallowed
- **G7**: stderr lost on exceptions

Additionally, execution statistics (turns, tokens) were not tracked, and the
execution log format (pipe-delimited strings) was not queryable.

## What Changed

### Hook Lifecycle Events (Steps 01-01 through 04-01)
- hook_id (UUID4) generated at start of every handler invocation
- HOOK_COMPLETED event with timing (duration_ms), exit_code, decision
- HOOK_PRE_WRITE_ALLOWED/BLOCKED events with file_path and reason
- HOOK_PROTOCOL_ANOMALY for empty stdin and JSON parse errors
- HOOK_POST_TOOL_USE_INJECTED/PASSTHROUGH decision logging

### Event Correlation (Steps 05-01, 05-02)
- task_correlation_id stored in signal file, threaded through lifecycle
- hook_id propagated from adapter through services to all audit events
- AuditEvent dataclass extended with optional hook_id field

### Error Capture (Step 06-01)
- stderr captured via contextlib.redirect_stderr on exceptions
- error_type (exception class name) added to HOOK_ERROR events
- stderr truncated to 1000 chars

### Execution Statistics (Steps 07-01, 07-02)
- PhaseEvent extended with optional turns_used, tokens_used
- log_phase CLI accepts --turns-used and --tokens-used flags
- SubagentStopContext carries stats for future use

### Log Format v3.0 (Step 08-01)
- Structured YAML objects replace pipe-delimited strings
- Format: `{sid, p, s, d, t}` with optional `tu`, `tk` for stats
- YamlExecutionLogReader auto-detects v2.0 (string) vs v3.0 (dict)
- Backward compatible: v2.0 logs remain readable

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Logging location | Adapter layer only | Hexagonal boundary: services don't know about hooks |
| Error handling | try/except around all logging | Audit failure never breaks hook behavior |
| Correlation | UUID4 per hook + per task | Two-level correlation: within-hook and across-lifecycle |
| Log format | Short YAML keys (sid, p, s, d, t) | Compact on disk, queryable with yq |
| Stats source | SubagentStopContext (future-proofed) | Claude Code may add stats to hook_input later |

## Deliver-Level Quality

- **Phase 3 (Refactoring)**: Extracted `_read_and_parse_stdin()`, `_log_hook_error()`,
  `_normalize_message_content()`, `_log_transcript_audit()`, `_StdinParseResult` value class,
  `_add_execution_stats()` from adapter and service. L1-L4 applied.
- **Phase 4 (Adversarial Review)**: D1 (HIGH) — `extract_des_context_from_transcript()`
  84 lines with 5-level nesting. Refactored to 47 lines, max 3-level nesting.
- **Phase 5 (Mutation Testing)**: Found real bug in `_extract_terminal_phases()` (calling
  `.get()` on None). Fixed. `deliver_integrity_verifier.py`: 12/26 killed (14 survivors
  all cosmetic: dataclass decorators, error message text formatting).
- **Phase 6 (Integrity Verification)**: All 11 steps verified with complete DES traces.

## Bugs Found During Deliver

1. `verify_deliver_integrity.py`: used `s["step_id"]` but roadmap uses `s["id"]` key
2. `_parse_execution_log()`: skipped v3.0 structured dict entries (only handled strings)
3. `tdd_schema.py`: `_extract_terminal_phases()` set `terminal_config = None` then `.get()`
4. Self-referential contamination: subagents using `PYTHONPATH=src` executed modified source

## Files Modified (16 production files)

```
src/des/adapters/driven/hooks/yaml_execution_log_reader.py
src/des/adapters/driven/logging/jsonl_audit_log_writer.py
src/des/adapters/drivers/hooks/claude_code_hook_adapter.py
src/des/application/pre_tool_use_service.py
src/des/application/prompt_validator.py
src/des/application/schema_rollback_handler.py
src/des/application/subagent_stop_service.py
src/des/application/validator.py
src/des/cli/log_phase.py
src/des/cli/verify_deliver_integrity.py
src/des/domain/deliver_integrity_verifier.py
src/des/domain/phase_event.py
src/des/domain/tdd_schema.py
src/des/domain/validation_error_detector.py
src/des/ports/driven_ports/audit_log_writer.py
src/des/ports/driver_ports/subagent_stop_port.py
```

## Test Results

- 907 passed, 69 skipped, 0 failures
- Test categories: 155 acceptance, 2 e2e, 34 integration, 785 unit
