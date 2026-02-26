# User Stories: DES Housekeeping

Epic: DES Housekeeping — Automatic cleanup of DES operational files at session start.

Traces to job stories in: `docs/ux/des-housekeeping/jtbd-job-stories.md`

---

## US-HK-01: Audit Log Retention

### Problem

Kenji Nakamura is a full-stack developer who uses nWave daily across three projects. After six weeks of usage, his `.nwave/des/logs/` directory contains 30+ audit log files totaling 60MB. He never looks at logs older than a few days, but they accumulate silently. He discovers the bloat when investigating a slow `git status` and finds hundreds of untracked files in `.nwave/`.

### Who

- Developer | Daily nWave user across multiple projects | Wants a tool that manages its own disk footprint

### Solution

At session start, automatically remove audit log files older than a configurable retention period (default: 7 days). Retention period is configurable via `des-config.json` for users who need longer history.

### Domain Examples

#### 1: Standard Cleanup — Kenji opens Claude Code on Monday morning

Kenji's `.nwave/des/logs/` contains audit files from the past 3 weeks: `audit-2026-02-05.log` through `audit-2026-02-26.log`. Default retention is 7 days. Session start removes all files dated before 2026-02-19, keeping the 8 most recent (Feb 19-26). Kenji never notices -- his session starts normally.

#### 2: Custom Retention — Sofia Reyes keeps 30-day history for compliance

Sofia's team requires 30-day log retention for audit purposes. Her `.nwave/des-config.json` contains `"housekeeping": {"audit_retention_days": 30}`. Session start only removes files older than 30 days.

#### 3: Empty Directory — Fresh project with no logs yet

Amir Hassan opens Claude Code in a newly initialized project. `.nwave/des/logs/` does not exist or is empty. Housekeeping completes instantly with nothing to do. No errors, no output.

#### 4: Permission Error — Read-only log file

Kenji has an audit log file with read-only permissions (set by a backup tool). Housekeeping encounters a `PermissionError` when trying to delete it. The file is skipped, remaining files are cleaned normally, and the session starts without interruption.

### UAT Scenarios (BDD)

```gherkin
Feature: Audit Log Retention
  Housekeeping removes audit log files beyond the retention period
  at session start, silently and without blocking.

  Scenario: Remove logs beyond default 7-day retention
    Given Kenji's project has audit logs from 2026-02-05 through 2026-02-26
    And no custom housekeeping configuration exists
    And today is 2026-02-26
    When a new Claude Code session starts
    Then audit logs dated before 2026-02-19 are removed
    And audit logs from 2026-02-19 through 2026-02-26 are preserved
    And the session starts normally with no housekeeping output

  Scenario: Respect custom retention period from des-config.json
    Given Sofia's des-config.json contains {"housekeeping": {"audit_retention_days": 30}}
    And her project has audit logs spanning 45 days
    When a new Claude Code session starts
    Then only audit logs older than 30 days are removed
    And logs from the most recent 30 days are preserved

  Scenario: No logs to clean
    Given Amir's project has no .nwave/des/logs/ directory
    When a new Claude Code session starts
    Then housekeeping completes without errors
    And no directory is created

  Scenario: Permission error on individual log file
    Given Kenji's project has 15 audit log files
    And audit-2026-02-06.log has read-only permissions
    When housekeeping attempts to remove old logs
    Then audit-2026-02-06.log is skipped
    And all other eligible log files are removed
    And the session starts normally

  Scenario: Housekeeping completes within performance budget
    Given a project with 90 audit log files (3 months of daily usage)
    When housekeeping runs at session start
    Then all housekeeping operations complete in under 500ms total
```

### Acceptance Criteria

- [ ] Audit logs older than retention period (default 7 days) are removed at session start
- [ ] Retention period is configurable via `des-config.json` at `housekeeping.audit_retention_days`
- [ ] Missing `.nwave/des/logs/` directory does not cause errors
- [ ] Individual file deletion failures are skipped without affecting other files or the session
- [ ] No console output is produced during normal housekeeping operation

### Technical Notes

- Retention is determined by parsing the date from the filename (`audit-YYYY-MM-DD.log`), not file mtime -- filename is the source of truth created by `JsonlAuditLogWriter`
- Integration point: called from `session_start_handler.py` alongside existing update check
- Must respect the existing fail-open pattern (all exceptions exit 0)
- Today's log file must never be deleted regardless of retention period

---

## US-HK-02: Orphaned Signal File Cleanup

### Problem

Priya Sharma is debugging a test failure when her Claude Code session crashes (terminal killed, laptop reboot). When she starts a new session, a stale `des-task-active-myproject--step-3` signal file from the dead session remains in `.nwave/des/`. The next time she runs `/nw:deliver`, DES behaves as if a subagent is already running, causing confusion and requiring her to manually find and delete the orphan.

### Who

- Developer | Uses nWave for TDD delivery | Wants sessions to start from clean state regardless of how previous sessions ended

### Solution

At session start, detect and remove signal files (`des-task-active-*`, `des-task-active`, `deliver-session.json`) that are stale based on file age. A signal file is considered stale if it is older than a reasonable session duration threshold (default: 4 hours).

### Domain Examples

#### 1: Crashed Session Recovery — Priya restarts after a crash

Priya's `.nwave/des/` contains `des-task-active-myproject--step-3` created 18 hours ago (last night's session that crashed). She starts a new session. Housekeeping detects the file is older than 4 hours and removes it. Her new `/nw:deliver` starts cleanly.

#### 2: Concurrent Sessions — Tomasz has two terminals open

Tomasz has two Claude Code terminals open. Terminal A is running a `/nw:deliver` step and created `des-task-active-api-service--step-2` 45 minutes ago. Terminal B starts a new session. Housekeeping sees the signal file is only 45 minutes old (under the 4-hour threshold) and leaves it alone. Terminal A continues uninterrupted.

#### 3: Stale Deliver Session — Elena's deliver session marker from yesterday

Elena ran `/nw:deliver` yesterday and the finalize step was interrupted before it could clean up `deliver-session.json`. Today, writes to `src/` are being blocked by the session guard. Housekeeping removes the stale `deliver-session.json` (created over 4 hours ago), and Elena can write freely.

#### 4: Multiple Orphans — Carlos finds three stale signal files

Carlos has been working across multiple feature branches. Three `des-task-active-*` files from different days exist in `.nwave/des/`. All are older than 24 hours. Housekeeping removes all three in one pass.

### UAT Scenarios (BDD)

```gherkin
Feature: Orphaned Signal File Cleanup
  Housekeeping removes stale DES signal files at session start
  to prevent phantom blocks from crashed or interrupted sessions.

  Scenario: Remove orphaned signal file from crashed session
    Given Priya's .nwave/des/ contains des-task-active-myproject--step-3
    And the signal file was created 18 hours ago
    And the default staleness threshold is 4 hours
    When a new Claude Code session starts
    Then des-task-active-myproject--step-3 is removed
    And no output is produced

  Scenario: Preserve recent signal file from concurrent session
    Given Tomasz has des-task-active-api-service--step-2 created 45 minutes ago
    And the default staleness threshold is 4 hours
    When a new Claude Code session starts in another terminal
    Then des-task-active-api-service--step-2 is preserved

  Scenario: Remove stale deliver-session.json
    Given Elena's .nwave/des/ contains deliver-session.json created 26 hours ago
    When a new Claude Code session starts
    Then deliver-session.json is removed
    And source file writes are no longer blocked by the session guard

  Scenario: Remove multiple orphaned signal files
    Given Carlos has 3 des-task-active-* files all older than 24 hours
    And 1 des-task-active legacy singleton also older than 24 hours
    When a new Claude Code session starts
    Then all 4 stale signal files are removed

  Scenario: Empty DES directory
    Given the .nwave/des/ directory contains no signal files
    When housekeeping checks for orphans
    Then housekeeping completes without errors
```

### Acceptance Criteria

- [ ] Signal files (`des-task-active-*`, `des-task-active`) older than staleness threshold (default 4 hours) are removed
- [ ] `deliver-session.json` older than staleness threshold is removed
- [ ] Signal files younger than the staleness threshold are preserved (concurrent session safety)
- [ ] Staleness threshold is configurable via `des-config.json` at `housekeeping.signal_staleness_hours`
- [ ] Missing `.nwave/des/` directory does not cause errors

### Technical Notes

- Staleness is determined by file modification time (`os.path.getmtime`), not file content -- signal files contain a `created_at` field but mtime is cheaper and sufficient
- The `created_at` JSON field inside signal files can serve as a secondary check if mtime is unreliable (e.g., network filesystems)
- Signal file glob pattern: `.nwave/des/des-task-active*` (catches both namespaced and legacy singleton)
- `deliver-session.json` uses the same staleness logic
- The 4-hour default is generous: typical DES tasks complete in minutes; a 4-hour old signal is certainly orphaned

---

## US-HK-03: Skill Tracking Log Rotation

### Problem

Kenji Nakamura has been using nWave with skill tracking enabled for two months. His `.nwave/skill-loading-log.jsonl` file has grown to 15MB with thousands of entries. The file serves no purpose beyond recent observability -- old entries have no diagnostic value. But nothing ever trims it.

### Who

- Developer | Has skill tracking enabled | Wants bounded log file sizes without losing recent diagnostic data

### Solution

At session start, if the skill tracking log exceeds a size threshold (default: 1MB), truncate it by keeping only the most recent entries (tail of the file).

### Domain Examples

#### 1: Oversized Log Truncation — Kenji's 15MB skill log

Kenji's `.nwave/skill-loading-log.jsonl` is 15MB. Housekeeping detects it exceeds the 1MB threshold, reads the last 1000 lines (approximately 200KB), and rewrites the file with only those lines. The file drops from 15MB to ~200KB.

#### 2: Normal-Sized Log — Sofia's 400KB skill log

Sofia's skill tracking log is 400KB, well under the 1MB threshold. Housekeeping skips it entirely.

#### 3: Skill Tracking Disabled — Amir has no skill log

Amir has skill tracking disabled (default). No `.nwave/skill-loading-log.jsonl` exists. Housekeeping skips this check entirely.

### UAT Scenarios (BDD)

```gherkin
Feature: Skill Tracking Log Rotation
  Housekeeping truncates oversized skill tracking logs
  to prevent unbounded growth while preserving recent entries.

  Scenario: Truncate oversized skill tracking log
    Given Kenji's skill-loading-log.jsonl is 15MB
    And the default size threshold is 1MB
    When housekeeping runs at session start
    Then skill-loading-log.jsonl is truncated to approximately the last 1000 lines
    And the file size is significantly reduced
    And the most recent entries are preserved

  Scenario: Skip normal-sized skill tracking log
    Given Sofia's skill-loading-log.jsonl is 400KB
    And the default size threshold is 1MB
    When housekeeping runs at session start
    Then skill-loading-log.jsonl is not modified

  Scenario: No skill tracking log exists
    Given skill tracking is disabled
    And no skill-loading-log.jsonl file exists
    When housekeeping runs at session start
    Then no errors occur and no file is created

  Scenario: Truncation failure does not block session
    Given a skill-loading-log.jsonl that is locked by another process
    When housekeeping attempts to truncate it
    Then the truncation is skipped
    And the session starts normally
```

### Acceptance Criteria

- [ ] Skill tracking log exceeding size threshold (default 1MB) is truncated to the most recent ~1000 lines
- [ ] Logs below the size threshold are not touched
- [ ] Missing log file does not cause errors
- [ ] Truncation failures are silently skipped (fail-open)
- [ ] Size threshold is configurable via `des-config.json` at `housekeeping.skill_log_max_bytes`

### Technical Notes

- Truncation strategy: read last N lines (tail), write back to same file -- simple and atomic enough for this use case
- JSONL format means each line is independent -- no risk of corrupting a multi-line structure
- Tail-based truncation preserves the most diagnostically valuable entries (most recent)
- File size check (`os.path.getsize`) is the first gate -- skip everything if under threshold

---

## US-HK-04: Housekeeping Orchestration and Configuration

### Problem

The three housekeeping tasks (audit retention, signal cleanup, log rotation) need to run as a coordinated unit at session start. They must never block or delay the session, must respect user configuration, and must be invisible to the user under normal conditions.

### Who

- Developer | Any nWave user | Wants housekeeping to "just work" with zero configuration and zero visible impact

### Solution

Integrate housekeeping into the existing `session_start_handler.py` as a single coordinated call that runs all three housekeeping tasks. Each task is independent and fail-isolated. Configuration is read from `des-config.json` (optional -- sensible defaults when absent).

### Domain Examples

#### 1: Default Configuration — Kenji uses nWave out of the box

Kenji has never touched `des-config.json`. Housekeeping runs with defaults: 7-day audit retention, 4-hour signal staleness, 1MB skill log threshold. All three tasks run, each independently. Total time: ~50ms.

#### 2: Custom Configuration — Sofia overrides audit retention

Sofia's `des-config.json` contains:
```json
{
  "housekeeping": {
    "audit_retention_days": 30,
    "signal_staleness_hours": 8
  }
}
```
Housekeeping uses 30-day audit retention and 8-hour signal staleness. Skill log threshold uses the default 1MB since it is not specified.

#### 3: Housekeeping Disabled — Tomasz opts out entirely

Tomasz's `des-config.json` contains `"housekeeping": {"enabled": false}`. Housekeeping is skipped entirely. No file operations occur.

#### 4: Partial Failure — One task fails, others succeed

Kenji's audit log directory has a permission issue. Audit log cleanup raises an exception, which is caught. Signal file cleanup and log rotation proceed normally. Session starts without any user-visible indication of the partial failure.

### UAT Scenarios (BDD)

```gherkin
Feature: Housekeeping Orchestration
  Housekeeping runs all cleanup tasks at session start as a coordinated,
  fail-isolated, invisible operation with sensible defaults.

  Scenario: All housekeeping tasks run with defaults
    Given Kenji has no housekeeping configuration in des-config.json
    And his project has old audit logs, no orphaned signals, and a small skill log
    When a new Claude Code session starts
    Then audit log cleanup runs with 7-day retention
    And signal file cleanup runs with 4-hour staleness threshold
    And skill log rotation runs with 1MB size threshold
    And no console output is produced
    And total housekeeping time is under 500ms

  Scenario: Custom configuration overrides defaults
    Given Sofia's des-config.json specifies audit_retention_days as 30
    And signal_staleness_hours as 8
    When housekeeping runs
    Then audit retention uses 30 days
    And signal staleness uses 8 hours
    And skill log threshold uses the default 1MB

  Scenario: Housekeeping disabled via configuration
    Given Tomasz's des-config.json contains {"housekeeping": {"enabled": false}}
    When a new Claude Code session starts
    Then no housekeeping operations are performed

  Scenario: Partial failure isolation
    Given audit log cleanup will fail due to a permission error
    And signal file cleanup and skill log rotation will succeed
    When housekeeping runs
    Then signal files are cleaned and skill log is rotated
    And the audit log failure does not affect other tasks
    And the session starts normally with no error output

  Scenario: No .nwave directory exists
    Given a project with no .nwave/ directory at all
    When a new Claude Code session starts
    Then housekeeping completes immediately with no errors
    And no .nwave/ directory is created
```

### Acceptance Criteria

- [ ] Housekeeping runs at session start alongside the existing update check
- [ ] Each housekeeping task is independently fail-isolated (one failure does not affect others)
- [ ] All housekeeping completes within 500ms total under normal conditions
- [ ] No console output is produced during normal operation (invisible by default)
- [ ] Configuration is read from `des-config.json` under the `housekeeping` key
- [ ] Missing configuration uses sensible defaults (7 days, 4 hours, 1MB)
- [ ] Housekeeping can be entirely disabled via `housekeeping.enabled: false`
- [ ] Missing `.nwave/` directory does not trigger errors or directory creation

### Technical Notes

- Integration point: `session_start_handler.py:handle_session_start()` -- call housekeeping before or after the update check (order does not matter; both are independent)
- The existing `DESConfig` class should be extended with housekeeping properties (follows established pattern for `update_check` and `rigor` sub-configs)
- Housekeeping should be a separate module/service (not inline in the handler) for testability
- Each task wrapped in its own try/except -- the orchestrator never propagates exceptions
- Performance: file listing + age checks + unlink operations are all fast filesystem ops; 500ms budget is generous

---

## Story Dependency Map

```
US-HK-04 (Orchestration)
  |-- depends on --> US-HK-01 (Audit Log Retention)
  |-- depends on --> US-HK-02 (Signal File Cleanup)
  |-- depends on --> US-HK-03 (Skill Log Rotation)
```

Build order: US-HK-01, US-HK-02, US-HK-03 can be built in parallel. US-HK-04 integrates them.

Alternative: build US-HK-04 (orchestration shell) first with stubs, then fill in US-HK-01/02/03 as the tasks. This is the Outside-In TDD approach and is recommended.

## Configuration Schema

```json
{
  "housekeeping": {
    "enabled": true,
    "audit_retention_days": 7,
    "signal_staleness_hours": 4,
    "skill_log_max_bytes": 1048576
  }
}
```

All fields optional. Defaults applied when absent.
