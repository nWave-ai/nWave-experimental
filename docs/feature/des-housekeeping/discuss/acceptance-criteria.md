# Acceptance Criteria: DES Housekeeping

Consolidated BDD scenarios for the DES Housekeeping epic.
Each feature file corresponds to one user story.
Traces to: `docs/requirements/des-housekeeping/user-stories.md`

---

## Feature: Audit Log Retention (US-HK-01)

```gherkin
Feature: Audit Log Retention
  As part of session-start housekeeping, DES removes audit log files
  beyond the retention period to prevent unbounded disk growth.

  Background:
    Given the default audit retention period is 7 days

  # Happy path (Job Story 1 + 3)
  Scenario: Remove logs beyond default 7-day retention
    Given Kenji's project has audit log files:
      | filename              | age_days |
      | audit-2026-02-05.log  | 21       |
      | audit-2026-02-10.log  | 16       |
      | audit-2026-02-18.log  | 8        |
      | audit-2026-02-19.log  | 7        |
      | audit-2026-02-20.log  | 6        |
      | audit-2026-02-26.log  | 0        |
    And no custom housekeeping configuration exists
    And today is 2026-02-26
    When session-start housekeeping runs
    Then the following files are removed:
      | audit-2026-02-05.log |
      | audit-2026-02-10.log |
      | audit-2026-02-18.log |
    And the following files are preserved:
      | audit-2026-02-19.log |
      | audit-2026-02-20.log |
      | audit-2026-02-26.log |

  # Configuration (Job Story 3 — customization)
  Scenario: Respect custom retention period from des-config.json
    Given Sofia's des-config.json contains:
      """json
      {"housekeeping": {"audit_retention_days": 30}}
      """
    And her project has audit logs spanning 45 days
    When session-start housekeeping runs
    Then only audit logs older than 30 days are removed
    And logs from the most recent 30 days are preserved

  # Edge case — empty state
  Scenario: No logs directory exists
    Given Amir's project has no .nwave/des/logs/ directory
    When session-start housekeeping runs
    Then no errors occur
    And no directories are created

  # Error path — permission failure
  Scenario: Permission error on individual log file
    Given Kenji's project has 15 audit log files older than 7 days
    And audit-2026-02-06.log has read-only permissions
    When housekeeping attempts to remove old logs
    Then audit-2026-02-06.log is skipped
    And all other eligible files are successfully removed
    And the session starts with exit code 0

  # Property — performance budget
  @property
  Scenario: Audit log cleanup completes within performance budget
    Given a project with 90 audit log files
    When housekeeping runs audit log cleanup
    Then cleanup completes in under 200ms

  # Edge case — today's log is never deleted
  Scenario: Today's log is preserved regardless of retention
    Given today is 2026-02-26
    And audit-2026-02-26.log exists
    And retention is set to 0 days
    When session-start housekeeping runs
    Then audit-2026-02-26.log is preserved
```

---

## Feature: Orphaned Signal File Cleanup (US-HK-02)

```gherkin
Feature: Orphaned Signal File Cleanup
  As part of session-start housekeeping, DES removes stale signal files
  left by crashed or interrupted sessions to prevent phantom blocks.

  Background:
    Given the default signal staleness threshold is 4 hours

  # Happy path (Job Story 2)
  Scenario: Remove orphaned signal file from crashed session
    Given Priya's .nwave/des/ contains des-task-active-myproject--step-3
    And the file modification time is 18 hours ago
    When session-start housekeeping runs
    Then des-task-active-myproject--step-3 is removed

  # Safety — concurrent session protection (Job Story 2 — anxiety path)
  Scenario: Preserve recent signal file from concurrent session
    Given Tomasz's .nwave/des/ contains des-task-active-api-service--step-2
    And the file modification time is 45 minutes ago
    When session-start housekeeping runs
    Then des-task-active-api-service--step-2 is preserved

  # deliver-session.json (Job Story 2)
  Scenario: Remove stale deliver-session.json
    Given Elena's .nwave/des/ contains deliver-session.json
    And the file modification time is 26 hours ago
    When session-start housekeeping runs
    Then deliver-session.json is removed

  # Preserve recent deliver-session.json
  Scenario: Preserve recent deliver-session.json from active session
    Given a deliver-session.json created 30 minutes ago
    When session-start housekeeping runs
    Then deliver-session.json is preserved

  # Multiple orphans
  Scenario: Remove multiple orphaned signal files in one pass
    Given .nwave/des/ contains:
      | file                                 | age_hours |
      | des-task-active-proj-a--step-1       | 48        |
      | des-task-active-proj-b--step-2       | 25        |
      | des-task-active-proj-c--step-3       | 72        |
      | des-task-active                      | 30        |
    When session-start housekeeping runs
    Then all 4 signal files are removed

  # Edge case — empty directory
  Scenario: No signal files exist
    Given .nwave/des/ contains no des-task-active files
    And no deliver-session.json exists
    When session-start housekeeping runs
    Then housekeeping completes without errors

  # Configuration
  Scenario: Custom staleness threshold
    Given des-config.json contains:
      """json
      {"housekeeping": {"signal_staleness_hours": 8}}
      """
    And a signal file created 5 hours ago
    When session-start housekeeping runs
    Then the signal file is preserved (5 hours < 8 hour threshold)
```

---

## Feature: Skill Tracking Log Rotation (US-HK-03)

```gherkin
Feature: Skill Tracking Log Rotation
  As part of session-start housekeeping, DES truncates oversized skill
  tracking logs to prevent unbounded growth while preserving recent entries.

  Background:
    Given the default skill log size threshold is 1MB

  # Happy path (Job Story 3)
  Scenario: Truncate oversized skill tracking log
    Given Kenji's skill-loading-log.jsonl is 15MB with 50000 lines
    When session-start housekeeping runs
    Then skill-loading-log.jsonl is truncated to the last 1000 lines
    And the most recent 1000 entries are preserved
    And older entries are discarded

  # Below threshold — no action
  Scenario: Skip normal-sized skill tracking log
    Given Sofia's skill-loading-log.jsonl is 400KB
    When session-start housekeeping runs
    Then skill-loading-log.jsonl is not modified

  # Missing file — no error
  Scenario: No skill tracking log exists
    Given no skill-loading-log.jsonl file exists in .nwave/
    When session-start housekeeping runs
    Then no errors occur
    And no file is created

  # Error path — locked file
  Scenario: Truncation failure does not block session
    Given skill-loading-log.jsonl is 5MB
    And the file is locked by another process
    When housekeeping attempts to truncate it
    Then the truncation is skipped
    And the session starts normally with exit code 0

  # Configuration
  Scenario: Custom size threshold
    Given des-config.json contains:
      """json
      {"housekeeping": {"skill_log_max_bytes": 5242880}}
      """
    And skill-loading-log.jsonl is 3MB
    When session-start housekeeping runs
    Then skill-loading-log.jsonl is not modified (3MB < 5MB threshold)
```

---

## Feature: Housekeeping Orchestration (US-HK-04)

```gherkin
Feature: Housekeeping Orchestration
  Housekeeping runs all cleanup tasks at session start as a coordinated,
  fail-isolated, invisible operation with sensible defaults.

  # Happy path — all tasks with defaults
  Scenario: All housekeeping tasks run with default configuration
    Given Kenji has no housekeeping configuration in des-config.json
    And his project has:
      | artifact                      | state           |
      | audit logs older than 7 days  | 12 files        |
      | des-task-active-old           | 20 hours stale  |
      | skill-loading-log.jsonl       | 200KB           |
    When a new Claude Code session starts
    Then 12 old audit logs are removed
    And the stale signal file is removed
    And the skill log is not modified (under threshold)
    And no console output is produced

  # Partial failure — isolation
  Scenario: Individual task failure does not affect other tasks
    Given audit log cleanup will raise a PermissionError
    And signal file cleanup will succeed
    And skill log rotation will succeed
    When session-start housekeeping runs
    Then signal files are cleaned successfully
    And skill log rotation runs successfully
    And the session starts with exit code 0

  # Disabled housekeeping
  Scenario: Housekeeping disabled via configuration
    Given des-config.json contains:
      """json
      {"housekeeping": {"enabled": false}}
      """
    And the project has stale signal files and old audit logs
    When a new Claude Code session starts
    Then no housekeeping file operations are performed

  # No .nwave directory at all
  Scenario: Project with no .nwave directory
    Given the project directory contains no .nwave/ directory
    When a new Claude Code session starts
    Then housekeeping completes immediately
    And no .nwave/ directory is created
    And no errors are raised

  # Performance
  @property
  Scenario: Total housekeeping completes within performance budget
    Given a project with 90 audit logs, 5 stale signal files, and a 10MB skill log
    When session-start housekeeping runs
    Then all operations complete in under 500ms total

  # Integration with update check
  Scenario: Housekeeping runs alongside update check without interference
    Given both housekeeping and update check are enabled
    When a new Claude Code session starts
    Then both housekeeping and update check execute
    And neither operation blocks or interferes with the other
    And the session produces at most one additionalContext message (from update check, not housekeeping)
```

---

## Cross-Cutting Concerns

### Fail-Open Contract

All housekeeping code paths MUST satisfy:

```gherkin
@property
Scenario: Housekeeping never blocks session start
  Given any combination of file system errors during housekeeping
  When session-start hook completes
  Then the exit code is 0
  And the Claude Code session starts normally
```

### No Side Effects on Missing State

```gherkin
@property
Scenario: Housekeeping never creates directories or files
  Given housekeeping runs in a project where .nwave/ does not exist
  When housekeeping completes
  Then no new directories or files have been created
```
