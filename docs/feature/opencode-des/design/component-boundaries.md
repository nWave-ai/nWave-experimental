# Component Boundaries: OpenCode DES Plugin

**Feature**: opencode-des
**Date**: 2026-03-03

---

## TypeScript Plugin Components

### 1. Hook Router

**Responsibility**: Entry point for all OpenCode hook events. Routes to appropriate handler.

**Interfaces**:
- Receives `tool.execute.before(input, output)` from OpenCode
- Receives `tool.execute.after(input)` from OpenCode
- Receives `stop(input)` from OpenCode
- Receives `experimental.session.compacting(input, output)` from OpenCode

**Delegates to**: Phase Enforcer, Audit Writer, Compaction Handler

**Boundary rule**: Contains no enforcement logic. Pure routing.

---

### 2. Phase Enforcer

**Responsibility**: Validates tool calls against current TDD phase policy. Blocks violations by throwing.

**Inputs**: Tool name, tool arguments (file path), current session state
**Outputs**: Normal return (allow) or thrown Error (block)

**Domain rules**:
- RED phases: only test files may be written/edited
- GREEN phase: only production files may be written/edited
- COMMIT phase: no new files (write blocked), edits allowed
- No active session: allow everything

**Dependencies**: State Manager (read), File Classifier (classify), Audit Writer (log violations)

---

### 3. Phase Transition Manager

**Responsibility**: Validates and executes phase transitions per the v4.0 schema transition map.

**Valid transitions**:
```
NOT_STARTED -> PREPARE
PREPARE -> RED_ACCEPTANCE
RED_ACCEPTANCE -> RED_UNIT | PREPARE (retry)
RED_UNIT -> GREEN
GREEN -> COMMIT
COMMIT -> COMPLETED
```

**Inputs**: Current phase, requested next phase, evidence string
**Outputs**: Success with updated state, or error string

**Dependencies**: State Manager (read/write), Audit Writer (log transition)

---

### 4. State Manager

**Responsibility**: Loads and saves DES session state from/to `deliver-session.json`.

**File location**: `{cwd}/.nwave/des/deliver-session.json`
**Operations**: Load (returns session or null), Save (writes JSON), Create (initializes new session), Atomic write (write-to-temp + rename)

**Error handling**: Returns null on missing/corrupt file. Read retry once on parse failure (race condition recovery -- handles mid-rename reads). Never throws.

---

### 5. Audit Writer

**Responsibility**: Appends timestamped JSONL entries to `des-audit.jsonl`.

**File location**: `{cwd}/.nwave/des/logs/des-audit.jsonl`
**Operations**: Append single line. Creates directory and file if missing.
**Format**: `{"event":"...","timestamp":"ISO8601",...}\n`

**Error handling**: Swallows write errors. Audit logging must never block enforcement.

---

### 6. File Classifier

**Responsibility**: Determines whether a file path refers to test code or production code.

**Test file signals**:
- Path contains `/tests/` or `/test/`
- Filename matches `test_*`, `*_test.*`, `*.test.*`, `*.spec.*`
- Path contains `conftest` (treated as test infrastructure)

**Production file**: anything not classified as test

**Pure function**: no I/O, no state.

---

### 7. Compaction Handler

**Responsibility**: Injects DES state into OpenCode's compaction context to preserve state across context window resets.

**Triggered by**: `experimental.session.compacting` hook
**Action**: Pushes a `<des-state>` block into `output.context` array
**Content**: Feature ID, step ID, current phase, files modified, tests-ran flag

---

### 8. Stale Session Detector

**Responsibility**: Determines if the current DES session is stale based on elapsed time since `startedAt`.

**Pure function**: Takes session `startedAt` timestamp and current time, returns `{ stale: boolean, severity: "warning" | "error" }`.

**Thresholds**:
- < 4 hours: not stale (`{ stale: false }`)
- 4-24 hours: warning (`{ stale: true, severity: "warning" }`)
- > 24 hours: error (`{ stale: true, severity: "error" }`)

**No I/O, no state**: Called by Phase Enforcer on each `tool.execute.before`.

---

### 9. Custom Tools (des_create_session, des_advance_phase)

**Responsibility**: Provides agent-callable tools for session creation and phase advancement.

**Tools**:
- `des_create_session(featureId, stepId)` -- Creates a new DES session with phase=NOT_STARTED. Called by the orchestrator before subagent dispatch.
- `des_advance_phase(next_phase, evidence)` -- Advances the TDD phase. Called by the executing subagent.

**Validation**: `des_create_session` requires non-empty featureId and stepId. `des_advance_phase` checks transition validity and evidence non-empty.
**Side effects**: Both update session state and log audit events.

---

## Python Installer Plugin Components

### OpenCodeDESPlugin

**Responsibility**: Installs the TypeScript DES plugin file to OpenCode's plugins directory.

**Interfaces**: `InstallationPlugin` ABC (install, verify, uninstall)

**Source discovery**: `context.framework_source / "des" / "opencode-plugin.ts"` or `context.project_root / "src" / "des" / "opencode-plugin.ts"`

**Target**: `~/.config/opencode/plugins/nwave-des.ts`

**Manifest**: `.nwave-des-manifest.json` in plugins directory

**Priority**: 39 (between opencode-commands at 38 and des at 50)

**Dependencies**: `["opencode-commands"]` (DES depends on OpenCode config directory existing, not on skills/agents)

---

## Boundary Summary

| Component | Reads From | Writes To | Throws |
|---|---|---|---|
| Hook Router | OpenCode hook params | Nothing | Never |
| Phase Enforcer | State Manager, File Classifier | Nothing | Error (on violation) |
| Phase Transition Manager | State Manager | State Manager | Never (returns error string) |
| State Manager | deliver-session.json | deliver-session.json | Never (returns null) |
| Audit Writer | Nothing | des-audit.jsonl | Never (swallows errors) |
| File Classifier | Nothing | Nothing | Never |
| Compaction Handler | State Manager | OpenCode compaction context | Never |
| Stale Session Detector | Session startedAt timestamp | Nothing | Never (pure function) |
| Custom Tools | State Manager | State Manager, Audit Writer | Never (returns error string) |

---

## Uninstall Behavior

### Manifest-based Uninstall (primary)

1. Read `.nwave-des-manifest.json` from `~/.config/opencode/plugins/`
2. Remove each file listed in the manifest (`nwave-des.ts`)
3. Remove the manifest file itself

### Fallback (manifest missing)

1. Check if `~/.config/opencode/plugins/nwave-des.ts` exists
2. If found: remove it, log warning that manifest was missing
3. If not found: nothing to uninstall, return success

**No hash checking**: Overkill for a single-file plugin. If the user edited the file, they can re-install.
**No backup**: Single file, easily re-installed via `nwave install`.
