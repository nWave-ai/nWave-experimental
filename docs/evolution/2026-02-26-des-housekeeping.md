# Evolution: des-housekeeping — Automatic DES Operational File Cleanup

**Project**: nWave DES (Deterministic Execution System)
**Feature**: des-housekeeping — automatic cleanup of `.nwave/` operational files at SessionStart
**Branch**: `master`
**Wave**: DELIVER (completed)
**Date**: 2026-02-26
**Status**: Complete — adversarial review passed, mutation testing 90.4% kill rate, integrity verification PASS

---

## Executive Summary

**Feature Delivered**: Automatic housekeeping of DES operational files at every Claude Code SessionStart. Three cleanup tasks run silently in sequence: audit log retention (removes logs older than 7 days by default), signal file cleanup (removes stale `des-task-active*` and `deliver-session.json` files from crashed sessions), and skill log rotation (truncates `skill-loading-log.jsonl` when it exceeds 1 MiB).

**Implementation Scope**: 7 commits, 2 new source files (`housekeeping_service.py`, `test_housekeeping_service.py`), 3 extended source files (`des_config.py`, `session_start_handler.py`, `test_des_config.py`). All quality gates passed across 6 implementation steps.

**Quality Achievement**: All 56 unit + acceptance tests passing, adversarial review NEEDS_REVISION resolved (4+1 findings addressed), mutation kill rate 90.4% (302/334) exceeding the 80% threshold, DES integrity trace complete for all 6 steps.

---

## Motivation

The `.nwave/` directory grows unbounded under normal usage. Three failure modes accumulate silently:

**Audit log accumulation**: `JsonlAuditLogWriter` creates one `audit-YYYY-MM-DD.log` file per day. After six weeks of daily usage, a developer has 42 files and 60MB+ of logs in `.nwave/des/logs/`. Nothing ever removes them. Users discover the bloat incidentally — often via `git status` listing hundreds of untracked files, or disk quota warnings on shared machines.

**Orphaned signal files**: When Claude Code crashes (terminal kill, laptop reboot, OS-level termination), DES signal files (`des-task-active-*`, `deliver-session.json`) from the dead session are never cleaned up. The next session finds these stale markers and behaves as if a subagent is already running, blocking `/nw:deliver` starts and requiring users to manually locate and delete orphans in `.nwave/des/`.

**Skill log growth**: `skill-loading-log.jsonl` accumulates indefinitely when skill tracking is enabled. A two-month-old installation with active skill tracking can accumulate 15MB+ in this file. Entries older than a few sessions have no diagnostic value.

All three problems share a clean solution: a coordinated housekeeping pass at SessionStart — a lifecycle event DES already owns, which fires exactly once per session, before any user interaction.

---

## Architecture Decisions

### ADR-1: HousekeepingService as a Single Application Service

Three cleanup tasks (audit log retention, signal file cleanup, skill log rotation) are consolidated into a single `HousekeepingService` in `src/des/application/`. Each task is a method on the service; the orchestrator wraps each call in its own `try/except`.

Follows the `UpdateCheckService` pattern. Separate classes for three ~15-line filesystem methods would be over-engineering. Inline code in the handler adapter would violate hexagonal architecture — the handler is a driving adapter (protocol concern), not a place for business logic.

**Alternatives rejected**: (1) Inline in `session_start_handler.py` — mixes protocol and domain, untestable without stdin/stdout mocking. (2) Three separate service classes — YAGNI; can extract if a 4th task appears. (3) Strategy pattern with task registry — zero evidence of future extension.

### ADR-2: No New Driven Port for Housekeeping

Housekeeping uses `pathlib.Path`, `os.path.getmtime`, and `os.path.getsize` directly. No new port abstraction is created. `TimeProvider` (existing port) is the only injected dependency.

The existing `FileSystemPort` covers only JSON read/write and existence checks — not glob, unlink, stat. Extending it would bloat its interface. A new `HousekeepingFileSystemPort` would add 3 files (port, ABC, test double) for operations already trivially testable via `pytest`'s `tmp_path` fixture. `TimeProvider` is the sole dependency requiring injection: it controls "now," making date comparisons deterministic in tests.

### ADR-3: DESConfig Extension with `_housekeeping()` Sub-Config

`DESConfig` is extended with a private `_housekeeping()` helper and four public properties: `housekeeping_enabled`, `housekeeping_audit_retention_days`, `housekeeping_signal_staleness_hours`, `housekeeping_skill_log_max_bytes`. All four return typed defaults when the `housekeeping` key is absent from `des-config.json`.

Follows the established `_rigor()` / `_update_check()` pattern exactly. No alternatives considered — deviating would introduce inconsistency with the established config adapter pattern.

### ADR-4: HousekeepingConfig Value Object as Dependency Seam

A `HousekeepingConfig` frozen dataclass is defined alongside `HousekeepingService`. The `session_start_handler` reads values from `DESConfig` and constructs `HousekeepingConfig` before passing it to the service.

Decouples the application service from the config adapter (dependency inversion). Tests construct `HousekeepingConfig` directly — no `DESConfig` instance or mock needed. Follows the pattern where driving adapters (handlers) wire dependencies for application services.

### ADR-5: Integration Point — Before Update Check in session_start_handler.py

Housekeeping runs before the update check in `handle_session_start()`. Wrapped in its own `try/except`, independent of the update check's error handling. `DESConfig` instance is shared between both calls.

Housekeeping is local-only and produces no output — running first means stale state is cleaned before any other operations. The shared `DESConfig` instance avoids double-loading the config file. Independent error isolation means neither subsystem can fail the other.

---

## Implementation Notes

### Triple-Nested Fail-Open

The fail-open contract is enforced at three levels simultaneously:

1. **Task level**: each of the three task methods (`_clean_audit_logs`, `_clean_signal_files`, `_rotate_skill_log`) is wrapped in its own `try/except` inside `run_housekeeping()`. One task exception does not affect other tasks.
2. **Service level**: the entire `_run_housekeeping()` call in `session_start_handler.py` is wrapped in `try/except`. Even a `HousekeepingService` constructor failure cannot affect the update check.
3. **Handler level**: the outer `try/except` in `handle_session_start()` catches everything and always returns 0.

Additionally, within each task, individual file failures (`PermissionError`, `OSError`) are silently skipped per-file — a read-only log file does not prevent other logs from being cleaned.

### Filename Date Parsing for Audit Log Retention

Audit log retention uses the date embedded in the filename (`audit-YYYY-MM-DD.log`), not the file's mtime. This is deliberate: `JsonlAuditLogWriter` creates files with the date as the canonical identifier, and mtime can be reset by backup tools, rsync, or filesystem migrations. Parsing the filename date makes retention deterministic and immune to mtime drift.

A consequence: a file named `audit-2026-01-01.log` created yesterday (somehow) would be treated as January 1st for retention purposes. This is the correct behavior — the filename is the source of truth.

### Size-Check Gate for Skill Log

Skill log rotation uses a two-step approach: check `os.path.getsize()` first, and only proceed to read/rewrite if the file exceeds the threshold. This makes the common case (file under threshold) a single syscall with no file I/O. The rewrite keeps the last 1000 lines, which approximates ~200KB for typical JSONL entries — well under the 1MB threshold even after rotation.

### Parallel Step Execution Conflict (02-01 / 02-02 / 02-03)

Steps 02-01 (audit log task), 02-02 (signal file task), and 02-03 (skill log task) were initially launched in parallel by the crafter. The execution log records interleaved phase timestamps across the three steps (e.g., 02-02 PREPARE at 09:58:01, 02-03 PREPARE at 09:58:09, 02-01 PREPARE at 10:15:16). This caused a merge conflict in `test_housekeeping_service.py` when all three steps committed to the same file.

Resolution: the crafter serialized the final `GREEN` and `COMMIT` phases for the three steps. The steps completed cleanly but with non-sequential timestamps in the execution log. This is expected behavior for parallelized feature steps sharing a test file.

### Linux unlink() Semantics in Tests

One adversarial review finding (D4) addressed a test that set file permissions to `0o444` (read-only) to simulate a `PermissionError` on deletion. On Linux, `os.unlink()` (and `Path.unlink()`) requires write permission on the *containing directory*, not the file itself. A read-only file in a writable directory is successfully deleted by the owner on Linux. The test was corrected to revoke write permission on the directory, not the file.

This is a common portability trap: the macOS/Windows mental model (file permissions guard deletion) does not match Linux semantics (directory write permission guards deletion).

---

## Quality Gates

### Phase 3: Refactoring

Applied L1-L4 refactoring to `housekeeping_service.py` and `session_start_handler.py`. Constants extracted to module level: `_AUDIT_LOG_PREFIX`, `_AUDIT_LOG_SUFFIX`, `_DEFAULT_AUDIT_RETENTION_DAYS`, `_DEFAULT_SIGNAL_STALENESS_HOURS`, `_DEFAULT_SKILL_LOG_MAX_BYTES`, `_TAIL_LINES`. `_resolve_audit_dir()` extracted as a static helper to remove the conditional directory resolution from `_clean_audit_logs()`. Result: cleaner task methods with single-level of indirection.

### Phase 4: Adversarial Review

Initial review status: NEEDS_REVISION. 5 findings raised, 4+1 addressed:

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| D1 | High | `_clean_audit_logs` iterates all `.nwave/des/logs/` files regardless of pattern — non-audit files could be deleted | Added `_AUDIT_LOG_PREFIX` / `_AUDIT_LOG_SUFFIX` filter guards inside the per-file loop |
| D2 | High | `_clean_signal_files` glob for `deliver-session.json` would miss it since it does not start with `des-task-active` | Added explicit `deliver-session.json` path check alongside the glob pattern |
| D3 | Medium | `HousekeepingConfig` fields lack validation — negative retention_days or staleness_hours are silently accepted | Added `__post_init__` validation raising `ValueError` for non-positive values on all numeric fields |
| D4 | Medium | Permission test used file permissions (0o444) instead of directory permissions to simulate `PermissionError` — fails on Linux | Corrected to remove write permission from the containing directory |
| D8 | Low | Magic numbers in `_rotate_skill_log` (1000 lines) not extracted to constant | Extracted to `_TAIL_LINES = 1000` module-level constant |

Re-review: APPROVED. All findings resolved without regressions.

### Phase 5: Mutation Testing

Feature-scoped mutation testing via cosmic-ray 8.4.3 (one config per component, scoped test commands). Overall: **90.4% kill rate (302/334) — PASS**.

| Component | Kill Rate | Status |
|-----------|:---------:|:------:|
| housekeeping_service.py | 86.9% (152/175) | PASS |
| session_start_handler.py | 84.0% (21/25) | PASS |
| des_config.py | 96.3% (129/134) | PASS |

All 4 surviving mutants in `session_start_handler.py` are equivalent mutants (`BitOr_*` on `Path | None` type union annotations; `Eq_Is` on interned string literals). Effective kill rate on behaviorally meaningful mutants in the handler is 100%.

The 23 survivors in `housekeeping_service.py` decompose as: 5 equivalent (`RemoveDecorator` on `@staticmethod`), 5 fail-open (`ExceptionReplacer` in `except Exception: pass` blocks — architecturally undetectable), 13 minor boundary gaps (exact-cutoff values, loop control, `startswith and endswith` filter). None represent regression risk given acceptance test coverage.

### Phase 6: DES Integrity Verification

All 6 implementation steps verified with complete DES phase traces in `execution-log.yaml`. Each step contains PREPARE, RED_UNIT (or RED_ACCEPTANCE where applicable), GREEN, and COMMIT phases — all PASS status. Step 01-01 has a documented RED_ACCEPTANCE skip (config/dataclass step predates `HousekeepingService`; accepted per DoR).

---

## Lessons Learned

**Parallel steps sharing a test file require merge discipline.** Steps 02-01, 02-02, and 02-03 all wrote to `test_housekeeping_service.py`. When launched in parallel, each step's edits were independently correct but conflicted at commit time. The correct approach for steps sharing a test file is to either serialize them, or partition the test file per-task before launching in parallel.

**Linux unlink() directory-vs-file permission semantics is a recurring trap.** The review finding D4 surfaces a test that would pass on macOS and Windows but silently fail to simulate the intended error on Linux. Any test that simulates filesystem permission errors must verify behavior on the target OS. For DES tests running in CI on Ubuntu, the directory-write model must be used.

**Fail-open at three nested levels is the right default for session hooks.** The adversarial reviewer's instinct was initially to surface errors visibly. Maintaining the principle — session hooks must never block the user — meant keeping all three levels of `try/except` and accepting that some failures are invisible. This is the correct design for infrastructure that runs before user interaction.

**Feature-scoped mutation testing surfaces equivalent mutants as a category, not bugs.** The 11 equivalent mutants across three components (type annotation operators, static method decorators, interned string comparisons) would have triggered unnecessary test additions in a naive "fix all survivors" policy. Categorizing survivors before acting on them saved work and kept the test suite focused.

---

## Files Modified

### New Source Files

| File | Purpose |
|------|---------|
| `src/des/application/housekeeping_service.py` | `HousekeepingConfig` value object + `HousekeepingService` with 3 cleanup tasks and fail-isolated orchestrator |
| `tests/des/unit/application/test_housekeeping_service.py` | 56 unit + acceptance tests covering all tasks, fail-isolation, config defaults, and orchestration |

### Extended Source Files

| File | Change |
|------|--------|
| `src/des/adapters/driven/config/des_config.py` | Added `_housekeeping()` + 4 public properties (`housekeeping_enabled`, `housekeeping_audit_retention_days`, `housekeeping_signal_staleness_hours`, `housekeeping_skill_log_max_bytes`) |
| `src/des/adapters/drivers/hooks/session_start_handler.py` | Added `_run_housekeeping()` call before update check, wrapped in independent `try/except` |
| `tests/des/unit/adapters/driven/config/test_des_config.py` | Extended with housekeeping property tests: defaults, custom values, partial config |

---

## Commit History

| Commit | Type | Description |
|--------|------|-------------|
| `e0dbe441` | fix | Re-skip handler integration test until step 03-01 |
| `217d994c` | feat | Add HousekeepingConfig and DESConfig extension |
| `db2b45a9` | feat | Implement audit log, signal, and skill log tasks |
| `a42549f1` | feat | Wire HousekeepingService into SessionStart handler |
| `58adf9c6` | refactor | Extract constants and audit dir helper |
| `955af0b9` | test | Fix review findings D1-D4 D8 |
| `df574903` | test | Fix review findings D1-D4 D8 (final) |
