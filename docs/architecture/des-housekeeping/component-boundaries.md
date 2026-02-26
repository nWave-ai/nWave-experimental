# Component Boundaries: DES Housekeeping

Companion to: `docs/architecture/des-housekeeping/architecture-design.md`
Traces to: `docs/requirements/des-housekeeping/user-stories.md`

---

## Component Map

```
src/des/
  application/
    housekeeping_service.py     [NEW]  -- HousekeepingService + HousekeepingConfig
  adapters/
    driven/
      config/
        des_config.py           [MOD]  -- Add _housekeeping() + 4 properties
    drivers/
      hooks/
        session_start_handler.py [MOD]  -- Add _run_housekeeping() call
  domain/
    audit_log_path_resolver.py  [USE]  -- Reuse for audit log dir resolution
  ports/
    driven_ports/
      time_provider_port.py     [USE]  -- Inject for deterministic time
```

---

## Component 1: HousekeepingConfig (Value Object)

**Location**: `src/des/application/housekeeping_service.py`

**Responsibility**: Hold housekeeping configuration with typed defaults. Decouples service from DESConfig adapter.

**Fields**:
- `enabled` (bool, default: True)
- `audit_retention_days` (int, default: 7)
- `signal_staleness_hours` (int, default: 4)
- `skill_log_max_bytes` (int, default: 1_048_576)
- `nwave_dir` (Path) -- resolved `.nwave/` directory
- `audit_log_dir` (Path | None) -- resolved audit log directory (None = use AuditLogPathResolver)

**Invariants**:
- Immutable (frozen dataclass)
- All numeric fields have positive defaults
- `enabled=False` means service does nothing

**Dependencies**: None (pure value object)

---

## Component 2: HousekeepingService (Application Service)

**Location**: `src/des/application/housekeeping_service.py`

**Responsibility**: Orchestrate 3 cleanup tasks with per-task fail-isolation.

**Public Contract**:
- `run_housekeeping(config, time_provider)` -- entry point, runs all tasks, returns nothing, never raises

**Internal Tasks** (each wrapped in independent try/except):
1. Audit log retention: list files in audit dir, parse dates from filenames, delete those beyond retention cutoff
2. Signal file cleanup: glob for `des-task-active*` and check `deliver-session.json`, stat mtime, delete stale
3. Skill log rotation: check file size, if over threshold, read tail lines, rewrite file

**Dependencies** (injected via parameters):
- `HousekeepingConfig` -- configuration values
- `TimeProvider` -- current time (for date/age calculations)

**Dependency direction**: Application layer depends only on domain and ports. No adapter imports.

**Error contract**: Never raises. Every task silently catches exceptions. Every file-level operation within a task silently catches exceptions.

---

## Component 3: DESConfig Extension (Driven Adapter Modification)

**Location**: `src/des/adapters/driven/config/des_config.py`

**Change**: Add `_housekeeping()` private method + 4 public properties.

**New members**:
- `_housekeeping() -> dict` -- Returns `housekeeping` sub-dict from config, defaulting to `{}`
- `housekeeping_enabled -> bool` -- Default: True
- `housekeeping_audit_retention_days -> int` -- Default: 7
- `housekeeping_signal_staleness_hours -> int` -- Default: 4
- `housekeeping_skill_log_max_bytes -> int` -- Default: 1_048_576

**Pattern**: Identical to `_rigor()` / `rigor_profile`, `_update_check()` / `update_check_frequency`.

**No breaking changes**: All new members, no existing signatures modified.

---

## Component 4: session_start_handler Integration (Driving Adapter Modification)

**Location**: `src/des/adapters/drivers/hooks/session_start_handler.py`

**Change**: Add housekeeping execution before update check.

**New function**: `_run_housekeeping(des_config: DESConfig) -> None`
- Reads housekeeping config from DESConfig properties
- Constructs HousekeepingConfig value object
- Constructs HousekeepingService
- Calls `run_housekeeping()`
- Entire function wrapped in try/except (fail-open)

**Modified function**: `handle_session_start()`
- Build DESConfig once, pass to both `_run_housekeeping()` and `_build_update_check_service()`
- Call `_run_housekeeping()` before update check
- Existing try/except structure preserved

**Wiring responsibilities** (adapter's job):
- Resolve `.nwave/` directory path from cwd
- Resolve audit log directory via `AuditLogPathResolver`
- Construct `SystemTimeProvider` for production use
- Map DESConfig properties to HousekeepingConfig fields

---

## Boundary Rules

### What HousekeepingService Does NOT Do

- Does not read stdin or write stdout (that is the handler's job)
- Does not construct DESConfig (that is the handler's wiring job)
- Does not import from `des.adapters.*` (application layer must not reference adapters)
- Does not create `.nwave/` directory if absent
- Does not log to console or audit trail

### What session_start_handler Does NOT Do

- Does not implement cleanup logic (delegated to HousekeepingService)
- Does not know retention periods or staleness thresholds (comes from config)
- Does not iterate files or check mtimes (service's job)

### What DESConfig Does NOT Do

- Does not validate config values (properties return raw values with defaults)
- Does not have side effects (read-only for housekeeping; no `save_housekeeping_state()` needed)

---

## Data Flow

### Audit Log Retention

```
AuditLogPathResolver.resolve() -> audit_log_dir (Path)
  |
  iterdir() -> [Path("audit-2026-02-05.log"), Path("audit-2026-02-26.log"), ...]
  |
  parse_date_from_filename(filename) -> date | None
  |
  today (from TimeProvider) - retention_days = cutoff_date
  |
  if file_date < cutoff_date AND file_date != today: unlink()
```

### Signal File Cleanup

```
nwave_des_dir = nwave_dir / "des"
  |
  glob("des-task-active*") + check("deliver-session.json")
  |
  os.path.getmtime(file) -> mtime_timestamp
  |
  now (from TimeProvider) - staleness_hours = cutoff_timestamp
  |
  if mtime < cutoff_timestamp: unlink()
```

### Skill Log Rotation

```
skill_log = nwave_dir / "skill-loading-log.jsonl"
  |
  os.path.getsize(skill_log) -> size_bytes
  |
  if size_bytes <= threshold: return (no-op)
  |
  read all lines -> keep last 1000 -> rewrite file
```

---

## Test Boundaries

### Unit Tests (fast, isolated, `tmp_path`)

| Behavior | Fixture | Assertion |
|----------|---------|-----------|
| Orchestration: disabled config | HousekeepingConfig(enabled=False) + populated tmp_path | No files deleted |
| Orchestration: one task fails | Raise exception in one task, verify others run | Other cleanup results observed |
| Orchestration: missing .nwave | Empty tmp_path | No errors |
| Audit: remove old, keep recent | tmp_path with dated audit files + fixed TimeProvider | Only old files deleted |
| Audit: today never deleted | tmp_path with today's file + retention=0 | Today's file preserved |
| Audit: permission error | Read-only file in tmp_path | File skipped, others deleted |
| Audit: missing dir | tmp_path without logs dir | No error |
| Signal: remove stale | tmp_path with old signal files + fixed TimeProvider | Stale files deleted |
| Signal: preserve recent | tmp_path with recent signal file | File preserved |
| Signal: deliver-session.json | tmp_path with old deliver-session.json | File deleted |
| Skill: truncate oversized | tmp_path with large JSONL file | File truncated to ~1000 lines |
| Skill: skip under threshold | tmp_path with small JSONL file | File unchanged |
| Skill: missing file | tmp_path without skill log | No error |
| DESConfig: defaults | No config file | Properties return defaults |
| DESConfig: custom values | Config with housekeeping overrides | Properties return custom values |

### Integration Tests

| Behavior | What | Assertion |
|----------|------|-----------|
| Handler integration | Call handle_session_start() with housekeeping-relevant files in tmp_path | Files cleaned, exit 0 |
| Fail-isolation | Force housekeeping error, verify update check still runs | Both independent |

---

## Scenario-to-Step Mapping

| Scenario (from acceptance-criteria.md) | Roadmap Step |
|-----------------------------------------|-------------|
| Remove logs beyond 7-day retention | Step 3 |
| Respect custom retention period | Step 1 + Step 3 |
| No logs directory exists | Step 3 |
| Permission error on log file | Step 3 |
| Audit log performance budget | Step 3 |
| Today's log preserved | Step 3 |
| Remove orphaned signal file | Step 4 |
| Preserve recent signal file | Step 4 |
| Remove stale deliver-session.json | Step 4 |
| Preserve recent deliver-session.json | Step 4 |
| Remove multiple orphans | Step 4 |
| No signal files exist | Step 4 |
| Custom staleness threshold | Step 1 + Step 4 |
| Truncate oversized skill log | Step 5 |
| Skip normal-sized skill log | Step 5 |
| No skill tracking log exists | Step 5 |
| Truncation failure | Step 5 |
| Custom size threshold | Step 1 + Step 5 |
| All tasks run with defaults | Step 2 + Step 6 |
| Individual task failure isolation | Step 2 |
| Housekeeping disabled | Step 1 + Step 2 |
| No .nwave directory | Step 2 |
| Total performance budget | Step 6 |
| Housekeeping alongside update check | Step 6 |
