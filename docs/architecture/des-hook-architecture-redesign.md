# DES Hook Architecture Redesign

## Architecture Analysis: Current State

This analysis is grounded in the actual source code as of 2026-02-06.

### Files Examined

| File | Role | Lines |
|------|------|-------|
| `src/des/adapters/drivers/hooks/claude_code_hook_adapter.py` | Driver adapter (entry point) | 441 |
| `src/des/adapters/driven/hooks/subagent_stop_hook.py` | "Driven" adapter implementing HookPort | 559 |
| `src/des/adapters/driven/logging/audit_logger.py` | Audit log writer (JSONL) | 406 |
| `src/des/ports/driver_ports/hook_port.py` | HookPort interface + HookResult | 62 |
| `src/des/application/orchestrator.py` | DESOrchestrator | 932 |
| `src/des/adapters/driven/logging/audit_events.py` | AuditEvent dataclass + EventType enum | 122 |
| `src/des/adapters/driven/validation/scope_validator.py` | Git-based scope checking | 212 |
| `src/des/domain/tdd_schema.py` | TDD phase schema loader | 262 |

---

### Violation 1: Duplicated Business Logic

**Location**: `claude_code_hook_adapter._verify_step_from_append_only_log()` (lines 181-314) duplicates `SubagentStopHook._validate_from_execution_log()` (lines 118-324).

Both implementations:
- Read `execution-log.yaml` via `yaml.safe_load()`
- Verify `project_id` matches
- Parse pipe-delimited event strings (`step_id|phase|status|data|timestamp`)
- Iterate TDD phases from schema checking for missing/invalid/skipped
- Build error messages with recovery suggestions
- Return validation results

The driver adapter copy is slightly simpler (returns tuples instead of `HookResult`), but the core validation logic is identical. This means a bug fix in one location will not propagate to the other.

**Hexagonal principle violated**: Business logic must live in the domain or application layer, never in adapters.

---

### Violation 2: Driver Adapter Bypasses Application Layer

**Location**: `claude_code_hook_adapter.handle_subagent_stop()` (lines 317-411).

Despite `create_orchestrator()` existing (lines 43-63) and `DESOrchestrator.on_subagent_complete()` being the proper entry point (orchestrator line 528), `handle_subagent_stop()` calls `_verify_step_from_append_only_log()` directly. The orchestrator and `SubagentStopHook` are never involved.

Flow that SHOULD happen:
```
handle_subagent_stop() -> orchestrator.on_subagent_complete() -> hook.on_agent_complete()
```

Flow that ACTUALLY happens:
```
handle_subagent_stop() -> _verify_step_from_append_only_log()  (local function, no port)
```

**Hexagonal principle violated**: Driver adapters must delegate to the application layer, not implement business logic themselves.

---

### Violation 3: Missing Audit Trail in Driver Adapter

**Location**: `claude_code_hook_adapter.py` -- the entire file.

The adapter handles two hook events but logs to the audit trail for neither:

- `handle_pre_task()`: Non-DES tasks (line 124) and orchestrator-mode tasks (line 137) return `allow` with zero audit record. Max-turns blocks (lines 99-115) have no audit record.
- `handle_subagent_stop()`: The entire function (lines 317-411) never calls `AuditLogger`, `log_audit_event()`, or any logging mechanism.

By contrast, `SubagentStopHook._validate_from_execution_log()` does log `HOOK_SUBAGENT_STOP_PASSED` and `HOOK_SUBAGENT_STOP_FAILED` events (lines 304-322). But since `handle_subagent_stop()` never calls `SubagentStopHook`, those audit events never fire.

**Consequence**: There is no record of hook invocations. If a subagent-stop validation fails or a pre-task block occurs, there is no evidence in the audit log.

---

### Violation 4: Driven Adapter Implements Driver Port

**Location**: `SubagentStopHook` in `src/des/adapters/driven/hooks/` implements `HookPort` from `src/des/ports/driver_ports/`.

In hexagonal architecture:
- **Driver ports** define how the outside world drives the application (inbound)
- **Driven ports** define how the application drives external systems (outbound)
- **Driver adapters** translate external protocols into calls on driver ports
- **Driven adapters** implement driven port interfaces

`SubagentStopHook` is placed in the driven adapter directory but implements a driver port. It also contains 200+ lines of business logic (TDD phase validation, skip reason checking, terminal phase enforcement). This is not adapter code -- it is domain logic wearing an adapter costume.

---

### Violation 5: No Port for PreToolUse Validation

**Location**: `handle_pre_task()` (lines 66-178).

The function contains three categories of validation logic directly in the driver adapter:

1. **Max-turns validation** (lines 98-115): Range checking, type checking
2. **DES marker detection** (lines 119-120): Regex pattern matching
3. **DES mode routing** (lines 129-138): Orchestrator vs execution mode decision

Only the DES execution-mode path (line 156) delegates to the orchestrator. Everything else is business logic in the adapter.

There is no `PreToolUsePort` interface. This means the validation rules cannot be tested independently, reused, or evolved without modifying the adapter.

---

### Violation 6: Naming Confusion

| Current Name | Location | Problem |
|-------------|----------|---------|
| `SubagentStopHook` | Driven adapter | Named after the Claude Code hook EVENT, not what it does. A "SubagentStop" is an event that fires in Claude Code. This class validates TDD phase completion. |
| `HookPort` | Driver ports | Too generic. Does not distinguish between PreToolUse and SubagentStop hook types. |
| `on_agent_complete()` | HookPort | Name suggests lifecycle notification, but it performs validation and returns pass/fail. |
| `hook` parameter | DESOrchestrator constructor | Generic name hides the dependency's purpose (step completion validation). |
| `_verify_step_from_append_only_log()` | Driver adapter | Implementation detail exposed as internal function name. Describes HOW not WHAT. |

---

### Violation 7: SubagentStopHook Creates Its Own Dependencies

**Location**: `SubagentStopHook._log_hook_event()` (line 341) and `_validate_and_log_scope_violations()` (line 367).

Both methods instantiate `get_audit_logger()` and `SystemTimeProvider()` internally rather than receiving them through the constructor. This violates dependency inversion and makes the class difficult to test with controlled dependencies.

---

## Proposed Architecture

### Component Diagram (Hexagonal Layers)

```
+========================================================================+
|                        OUTSIDE WORLD                                   |
|   Claude Code hooks (JSON on stdin, JSON on stdout, exit codes)        |
+========================================================================+
        |                                           |
        | PreToolUse event                          | SubagentStop event
        v                                           v
+------------------------------------------------------------------------+
|  DRIVER ADAPTER LAYER (inbound protocol translation)                   |
|                                                                        |
|  ClaudeCodeHookAdapter                                                 |
|    handle_pre_tool_use()  ----+                                        |
|    handle_subagent_stop() ----|---+                                    |
|    (JSON parse, exit code)    |   |                                    |
+-------------------------------|---|------------------------------------+
                                |   |
                                v   v
+------------------------------------------------------------------------+
|  DRIVER PORTS (application service interfaces)                         |
|                                                                        |
|  PreToolUsePort                  SubagentStopPort                      |
|    validate(input) -> Decision     validate(ctx) -> Decision           |
+------------------------------------------------------------------------+
                                |   |
                                v   v
+------------------------------------------------------------------------+
|  APPLICATION SERVICES (orchestration, audit logging)                   |
|                                                                        |
|  PreToolUseService                SubagentStopService                  |
|    implements PreToolUsePort        implements SubagentStopPort         |
|    - calls MaxTurnsPolicy           - calls ExecutionLogReader         |
|    - calls DesMarkerParser          - calls StepCompletionValidator    |
|    - calls PromptValidator          - calls ScopeChecker               |
|    - calls AuditLogWriter           - calls AuditLogWriter             |
+------------------------------------------------------------------------+
                |                              |
                v                              v
+------------------------------------------------------------------------+
|  DOMAIN LAYER (pure business rules, no I/O)                           |
|                                                                        |
|  MaxTurnsPolicy          StepCompletionValidator     DesMarkerParser   |
|    validate(value)         validate(events, schema)    parse(prompt)   |
|    -> PolicyResult         -> CompletionResult         -> Markers      |
|                                                                        |
|  TDDSchema (existing)    PhaseEventParser                              |
|    tdd_phases               parse(event_str)                           |
|    valid_statuses           -> PhaseEvent                              |
|    terminal_phases                                                     |
+------------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------------+
|  DRIVEN PORTS (outbound interfaces defined by application needs)       |
|                                                                        |
|  ExecutionLogReader           AuditLogWriter         ScopeChecker      |
|    read_step_events()           log_event()            check_scope()   |
|    read_project_id()                                                   |
|                                                                        |
|  TimeProvider (existing)     FileSystem (existing)                     |
+------------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------------+
|  DRIVEN ADAPTER LAYER (outbound infrastructure implementations)        |
|                                                                        |
|  YamlExecutionLogReader      JsonlAuditLogWriter     GitScopeChecker   |
|    reads execution-log.yaml    writes audit-*.log      runs git diff   |
|                                (JSONL, append-only)                    |
|                                                                        |
|  SystemTimeProvider (existing)  RealFileSystem (existing)              |
+------------------------------------------------------------------------+
                                    |
                                    v
+========================================================================+
|                        EXTERNAL SYSTEMS                                |
|   execution-log.yaml    .nwave/des/logs/audit-*.log    git repository  |
+========================================================================+
```

---

### Port Definitions

#### Driver Ports (Application Service Interfaces)

**PreToolUsePort**

```
Interface: PreToolUsePort

Purpose: Validates Task tool invocations before execution.
Called by: ClaudeCodeHookAdapter when PreToolUse hook fires for Task tool.

Methods:
  validate(input: PreToolUseInput) -> HookDecision

Input:
  PreToolUseInput:
    prompt: str           # Full Task prompt text
    max_turns: int | None # max_turns parameter (may be absent)
    subagent_type: str    # Type of subagent being created

Output:
  HookDecision:
    action: "allow" | "block"
    reason: str | None    # Block reason (None when allowed)
    exit_code: int        # 0=allow, 2=block
```

**SubagentStopPort**

```
Interface: SubagentStopPort

Purpose: Validates step completion when a subagent finishes.
Called by: ClaudeCodeHookAdapter when SubagentStop hook fires.

Methods:
  validate(context: SubagentStopContext) -> HookDecision

Input:
  SubagentStopContext:
    execution_log_path: str  # Absolute path to execution-log.yaml
    project_id: str          # Project identifier
    step_id: str             # Step identifier

Output:
  HookDecision:
    action: "allow" | "block"
    reason: str | None
    exit_code: int
    recovery_suggestions: list[str]  # For block decisions
```

#### Driven Ports (Outbound Interfaces)

**ExecutionLogReader**

```
Interface: ExecutionLogReader

Purpose: Reads step execution events from the append-only execution log.
Defined by: Application layer needs (NOT by YAML format).

Methods:
  read_project_id(log_path: str) -> str | None
    # Returns the project_id from the log, or None if not found

  read_step_events(log_path: str, step_id: str) -> list[PhaseEvent]
    # Returns parsed phase events for a specific step
    # Translates raw log format into domain PhaseEvent objects

Errors:
  LogFileNotFound     - log file does not exist
  LogFileCorrupted    - log file cannot be parsed
```

**AuditLogWriter**

```
Interface: AuditLogWriter

Purpose: Writes audit events to the compliance trail.
Defined by: Application layer audit requirements.

Methods:
  log_event(event: AuditEvent) -> None
    # Appends a single audit event to the log
    # Must be append-only (no modification of existing entries)
    # Must include ISO 8601 timestamp

Events logged:
  HOOK_PRE_TOOL_USE_ALLOWED     - Task invocation permitted
  HOOK_PRE_TOOL_USE_BLOCKED     - Task invocation rejected (with reason)
  HOOK_SUBAGENT_STOP_PASSED     - Step completion validated successfully
  HOOK_SUBAGENT_STOP_FAILED     - Step completion validation failed (with errors)
  SCOPE_VIOLATION               - Out-of-scope file modification detected
```

**ScopeChecker**

```
Interface: ScopeChecker

Purpose: Checks whether file modifications stay within allowed scope.
Defined by: Application layer scope enforcement needs.

Methods:
  check_scope(project_root: Path, allowed_patterns: list[str])
    -> ScopeCheckResult

Output:
  ScopeCheckResult:
    has_violations: bool
    out_of_scope_files: list[str]
    skipped: bool             # True if check could not be performed
    skip_reason: str | None
```

---

### Domain Layer Definitions

All domain components are pure functions/classes with no I/O dependencies.

**StepCompletionValidator**

```
Class: StepCompletionValidator

Purpose: THE SINGLE implementation of TDD phase completion validation.
Replaces: claude_code_hook_adapter._verify_step_from_append_only_log()
           AND SubagentStopHook._validate_from_execution_log()

Constructor:
  StepCompletionValidator(schema: TDDSchema)

Methods:
  validate(events: list[PhaseEvent]) -> CompletionResult

Input:
  PhaseEvent:
    phase_name: str    # e.g. "PREPARE", "RED_ACCEPTANCE"
    status: str        # e.g. "EXECUTED", "SKIPPED"
    outcome: str       # e.g. "PASS", "FAIL", or skip reason

Output:
  CompletionResult:
    is_valid: bool
    missing_phases: list[str]      # Phases with no event
    incomplete_phases: list[str]   # EXECUTED with invalid outcome
    invalid_skips: list[str]       # SKIPPED with invalid/blocking reason
    error_messages: list[str]      # Human-readable error descriptions
    recovery_suggestions: list[str]

Rules (from TDDSchema):
  1. All 7 TDD phases must have an event
  2. EXECUTED phases must have outcome PASS or FAIL
  3. Terminal phases (COMMIT) must have outcome PASS
  4. SKIPPED phases must have a valid skip prefix
  5. SKIPPED phases with blocking prefixes (DEFERRED) are invalid
  6. Zero events = SILENT_COMPLETION error
```

**MaxTurnsPolicy**

```
Class: MaxTurnsPolicy

Purpose: Validates max_turns parameter for Task tool invocations.
Replaces: Inline validation in handle_pre_task() lines 98-115.

Methods:
  validate(max_turns: int | None) -> PolicyResult

Output:
  PolicyResult:
    is_valid: bool
    reason: str | None   # Block reason

Rules:
  1. max_turns must not be None (MISSING_MAX_TURNS)
  2. max_turns must be an integer
  3. max_turns must be between 10 and 100 inclusive (INVALID_MAX_TURNS)
```

**DesMarkerParser**

```
Class: DesMarkerParser

Purpose: Detects and parses DES markers in Task prompts.
Replaces: Inline regex in handle_pre_task() lines 119-130.

Methods:
  parse(prompt: str) -> DesMarkers

Output:
  DesMarkers:
    is_des_task: bool          # Has DES-VALIDATION: required marker
    is_orchestrator_mode: bool # Has DES-MODE: orchestrator marker
    project_id: str | None     # From DES-PROJECT-ID marker
    step_id: str | None        # From DES-STEP-ID marker
```

**PhaseEventParser**

```
Class: PhaseEventParser

Purpose: Parses pipe-delimited event strings from execution-log.yaml.
Replaces: Inline parsing in both _verify_step_from_append_only_log()
           and SubagentStopHook._validate_from_execution_log().

Methods:
  parse(event_str: str) -> PhaseEvent

Input format: "step_id|phase|status|data|timestamp"
Output: PhaseEvent dataclass with typed fields
```

---

### Adapter Definitions

#### Driver Adapter: ClaudeCodeHookAdapter

```
Module: src/des/adapters/drivers/hooks/claude_code_hook_adapter.py

Purpose: THIN protocol adapter. Translates between Claude Code's hook
protocol (JSON stdin, JSON stdout, exit codes 0/1/2) and application
service calls. Contains ZERO business logic.

Responsibilities:
  1. Read JSON from stdin
  2. Parse into typed input objects
  3. Call appropriate application service port
  4. Translate HookDecision into JSON response + exit code
  5. Handle unexpected exceptions with fail-closed (exit 1)

Methods:
  handle_pre_tool_use() -> int
    - Parse stdin JSON -> PreToolUseInput
    - Call PreToolUsePort.validate(input)
    - Format HookDecision as JSON, return exit code

  handle_subagent_stop() -> int
    - Parse stdin JSON -> SubagentStopContext
    - Validate required fields (executionLogPath, projectId, stepId)
    - Validate absolute path
    - Call SubagentStopPort.validate(context)
    - Format HookDecision as JSON, return exit code

  main() -> None
    - Route sys.argv[1] to correct handler

What this adapter does NOT do:
  - Validate TDD phases (domain)
  - Check max_turns ranges (domain)
  - Parse DES markers (domain)
  - Read execution-log.yaml (driven adapter)
  - Write audit events (driven adapter)
  - Make allow/block decisions (application service)
```

#### Driven Adapter: YamlExecutionLogReader

```
Module: src/des/adapters/driven/execution_log/yaml_execution_log_reader.py

Purpose: Reads execution-log.yaml files and translates their format
into domain PhaseEvent objects.

Implements: ExecutionLogReader (driven port)

Responsibilities:
  1. Read YAML file from filesystem
  2. Extract project_id field
  3. Filter events by step_id
  4. Parse pipe-delimited event strings via PhaseEventParser
  5. Return list of PhaseEvent domain objects

Replaces:
  - File reading in SubagentStopHook._validate_from_execution_log() lines 132-153
  - File reading in _verify_step_from_append_only_log() lines 199-213
  - Event parsing loops in both locations

Error translation:
  FileNotFoundError -> LogFileNotFound
  yaml.YAMLError    -> LogFileCorrupted
```

#### Driven Adapter: JsonlAuditLogWriter

```
Module: src/des/adapters/driven/logging/jsonl_audit_log_writer.py

Purpose: Writes audit events in JSONL format to daily-rotated log files.

Implements: AuditLogWriter (driven port)

Based on: Existing AuditLogger class (mostly unchanged)

Responsibilities:
  1. Resolve log directory (env var -> config -> project-local -> global)
  2. Daily rotation with date-based naming (audit-YYYY-MM-DD.log)
  3. Append-only writes with SHA256 hash tracking
  4. File permission hardening (0o640)
  5. ISO 8601 timestamps

Changes from current AuditLogger:
  - Implements AuditLogWriter interface (driven port)
  - Receives TimeProvider through constructor (not self-created)
  - No global singleton (injected via constructor)
```

#### Driven Adapter: GitScopeChecker

```
Module: src/des/adapters/driven/validation/git_scope_checker.py

Purpose: Checks modified files against allowed patterns using git diff.

Implements: ScopeChecker (driven port)

Based on: Existing ScopeValidator class (refactored)

Responsibilities:
  1. Run git diff --name-only HEAD
  2. Compare modified files against allowed glob patterns
  3. Return violations or skipped result

Changes from current ScopeValidator:
  - Implements ScopeChecker interface (driven port)
  - Does NOT read step files (receives allowed_patterns as parameter)
  - Does NOT write audit events (caller handles audit)
  - Pure infrastructure concern
```

---

### Application Service Definitions

#### PreToolUseService

```
Class: PreToolUseService
Implements: PreToolUsePort

Constructor:
  PreToolUseService(
    max_turns_policy: MaxTurnsPolicy,
    marker_parser: DesMarkerParser,
    prompt_validator: ValidatorPort,     # Existing interface
    audit_writer: AuditLogWriter,
    time_provider: TimeProvider
  )

Method: validate(input: PreToolUseInput) -> HookDecision

Flow:
  1. Validate max_turns via MaxTurnsPolicy
     - If invalid: log HOOK_PRE_TOOL_USE_BLOCKED, return block
  2. Parse DES markers via DesMarkerParser
     - If not DES task: log HOOK_PRE_TOOL_USE_ALLOWED, return allow
     - If orchestrator mode: log HOOK_PRE_TOOL_USE_ALLOWED, return allow
  3. Validate prompt structure via ValidatorPort
     - If invalid: log HOOK_PRE_TOOL_USE_BLOCKED, return block
     - If valid: log HOOK_PRE_TOOL_USE_ALLOWED, return allow

Audit events generated:
  HOOK_PRE_TOOL_USE_ALLOWED  - every allowed invocation (with context)
  HOOK_PRE_TOOL_USE_BLOCKED  - every blocked invocation (with reason)
```

#### SubagentStopService

```
Class: SubagentStopService
Implements: SubagentStopPort

Constructor:
  SubagentStopService(
    log_reader: ExecutionLogReader,
    completion_validator: StepCompletionValidator,
    scope_checker: ScopeChecker,
    audit_writer: AuditLogWriter,
    time_provider: TimeProvider
  )

Method: validate(context: SubagentStopContext) -> HookDecision

Flow:
  1. Read project_id via ExecutionLogReader.read_project_id()
     - If not found: return block (LOG_FILE_NOT_FOUND)
     - If mismatch: return block (PROJECT_ID_MISMATCH)
  2. Read step events via ExecutionLogReader.read_step_events()
  3. Validate completion via StepCompletionValidator.validate()
     - If invalid: log HOOK_SUBAGENT_STOP_FAILED, return block
  4. Check scope via ScopeChecker.check_scope()
     - If violations: log SCOPE_VIOLATION (warning, does not block)
  5. Log HOOK_SUBAGENT_STOP_PASSED, return allow

Audit events generated:
  HOOK_SUBAGENT_STOP_PASSED  - successful validation
  HOOK_SUBAGENT_STOP_FAILED  - failed validation (with error details)
  SCOPE_VIOLATION            - out-of-scope files detected (warning)
```

---

### Data Flow Diagrams

#### Flow 1: PreToolUse -- Non-DES Task (max_turns present)

```
Claude Code                ClaudeCodeHookAdapter          PreToolUseService
    |                              |                              |
    |-- JSON stdin --------------->|                              |
    |   {tool_input:               |                              |
    |     {prompt: "...",          |                              |
    |      max_turns: 30}}         |                              |
    |                              |-- parse JSON                 |
    |                              |-- create PreToolUseInput     |
    |                              |                              |
    |                              |-- validate(input) ---------->|
    |                              |                              |-- MaxTurnsPolicy.validate(30)
    |                              |                              |   -> valid
    |                              |                              |-- DesMarkerParser.parse(prompt)
    |                              |                              |   -> is_des_task=false
    |                              |                              |-- AuditLogWriter.log_event(
    |                              |                              |     HOOK_PRE_TOOL_USE_ALLOWED)
    |                              |                              |
    |                              |<-- HookDecision(allow) ------|
    |                              |                              |
    |<-- {"decision":"allow"} -----|                              |
    |    exit code 0               |                              |
```

#### Flow 2: PreToolUse -- Missing max_turns

```
Claude Code                ClaudeCodeHookAdapter          PreToolUseService
    |                              |                              |
    |-- JSON stdin --------------->|                              |
    |   {tool_input:               |                              |
    |     {prompt: "...",          |                              |
    |      max_turns: null}}       |                              |
    |                              |-- parse JSON                 |
    |                              |-- create PreToolUseInput     |
    |                              |                              |
    |                              |-- validate(input) ---------->|
    |                              |                              |-- MaxTurnsPolicy.validate(None)
    |                              |                              |   -> MISSING_MAX_TURNS
    |                              |                              |-- AuditLogWriter.log_event(
    |                              |                              |     HOOK_PRE_TOOL_USE_BLOCKED,
    |                              |                              |     reason="MISSING_MAX_TURNS")
    |                              |                              |
    |                              |<-- HookDecision(block) ------|
    |                              |                              |
    |<-- {"decision":"block",  ----|                              |
    |     "reason":"..."}          |                              |
    |    exit code 2               |                              |
```

#### Flow 3: SubagentStop -- All Phases Valid

```
Claude Code        ClaudeCodeHookAdapter     SubagentStopService      Domain/Ports
    |                      |                          |                     |
    |-- JSON stdin ------->|                          |                     |
    |   {executionLogPath: |                          |                     |
    |    "/abs/path",      |                          |                     |
    |    projectId: "foo", |                          |                     |
    |    stepId: "01-01"}  |                          |                     |
    |                      |-- parse JSON             |                     |
    |                      |-- validate fields        |                     |
    |                      |-- validate abs path      |                     |
    |                      |                          |                     |
    |                      |-- validate(ctx) -------->|                     |
    |                      |                          |-- read_project_id ->|
    |                      |                          |   (ExecutionLogReader)
    |                      |                          |<-- "foo" -----------|
    |                      |                          |   (matches)         |
    |                      |                          |                     |
    |                      |                          |-- read_step_events->|
    |                      |                          |   (ExecutionLogReader)
    |                      |                          |<-- [7 PhaseEvents]--|
    |                      |                          |                     |
    |                      |                          |-- validate() ------>|
    |                      |                          |   (StepCompletion-  |
    |                      |                          |    Validator)       |
    |                      |                          |<-- is_valid=true ---|
    |                      |                          |                     |
    |                      |                          |-- check_scope() --->|
    |                      |                          |   (ScopeChecker)    |
    |                      |                          |<-- no violations ---|
    |                      |                          |                     |
    |                      |                          |-- log_event() ----->|
    |                      |                          |   (AuditLogWriter)  |
    |                      |                          |   HOOK_SUBAGENT_    |
    |                      |                          |   STOP_PASSED       |
    |                      |                          |                     |
    |                      |<-- HookDecision(allow) --|                     |
    |                      |                          |                     |
    |<-- {"decision":      |                          |                     |
    |     "allow"}         |                          |                     |
    |    exit code 0       |                          |                     |
```

#### Flow 4: SubagentStop -- Missing Phases

```
Claude Code        ClaudeCodeHookAdapter     SubagentStopService      Domain/Ports
    |                      |                          |                     |
    |-- JSON stdin ------->|                          |                     |
    |                      |-- validate(ctx) -------->|                     |
    |                      |                          |-- read_step_events->|
    |                      |                          |<-- [5 PhaseEvents]--|
    |                      |                          |   (missing REVIEW,  |
    |                      |                          |    COMMIT)          |
    |                      |                          |                     |
    |                      |                          |-- validate() ------>|
    |                      |                          |   (StepCompletion-  |
    |                      |                          |    Validator)       |
    |                      |                          |<-- is_valid=false---|
    |                      |                          |   missing=[REVIEW,  |
    |                      |                          |    COMMIT]          |
    |                      |                          |                     |
    |                      |                          |-- log_event() ----->|
    |                      |                          |   HOOK_SUBAGENT_    |
    |                      |                          |   STOP_FAILED       |
    |                      |                          |   {missing_phases,  |
    |                      |                          |    error_messages}  |
    |                      |                          |                     |
    |                      |<-- HookDecision(block) --|                     |
    |                      |                          |                     |
    |<-- {"decision":      |                          |                     |
    |     "block",         |                          |                     |
    |     "reason":"...",  |                          |                     |
    |     recovery: [...]} |                          |                     |
    |    exit code 2       |                          |                     |
```

---

### Audit Logging Strategy

#### Where Audit Events Are Generated

Audit events are generated exclusively in the **application service layer**.

| Layer | Generates Audit Events? | Rationale |
|-------|------------------------|-----------|
| Driver Adapter | NO | Protocol translation only. Does not know business context. |
| Application Service | YES | Has full context: which hook, which step, what decision, why. |
| Domain | NO | Pure business rules. No side effects. No I/O. |
| Driven Adapter | NO | Infrastructure concern. Implements AuditLogWriter but does not decide what to log. |

This means:
- `PreToolUseService` logs every allow and every block with full context
- `SubagentStopService` logs every pass and every fail with error details
- The `AuditLogWriter` driven port is called by services, implemented by `JsonlAuditLogWriter`

#### Audit Event Schema

Every audit event includes:

```
{
  "timestamp": "2026-02-06T14:30:45.123Z",    # ISO 8601, millisecond precision
  "event": "HOOK_PRE_TOOL_USE_BLOCKED",        # Event type from EventType enum
  "hook_type": "PreToolUse",                    # Which Claude Code hook
  "feature_name": "audit-log-refactor",         # Project/feature (if DES task)
  "step_id": "01-03",                           # Step (if DES task)
  "decision": "block",                          # allow or block
  "reason": "MISSING_MAX_TURNS",                # Block reason (null if allowed)
  "details": {                                  # Context-specific details
    "max_turns": null,
    "is_des_task": false
  }
}
```

#### Complete Event Catalog

| Event Type | Hook | Trigger | Details Included |
|-----------|------|---------|-----------------|
| `HOOK_PRE_TOOL_USE_ALLOWED` | PreToolUse | Task invocation permitted | max_turns, is_des_task, mode |
| `HOOK_PRE_TOOL_USE_BLOCKED` | PreToolUse | Task invocation rejected | reason, max_turns value |
| `HOOK_SUBAGENT_STOP_PASSED` | SubagentStop | All phases valid | step_id, phases_validated count |
| `HOOK_SUBAGENT_STOP_FAILED` | SubagentStop | Validation failed | missing_phases, invalid_phases, error_messages |
| `SCOPE_VIOLATION` | SubagentStop | Out-of-scope files | out_of_scope_files, allowed_patterns, severity |

---

### Naming Conventions

#### Rename Map

| Current Name | Proposed Name | Rationale |
|-------------|--------------|-----------|
| `SubagentStopHook` (class) | **Removed** | Business logic moves to `StepCompletionValidator` (domain). File I/O moves to `YamlExecutionLogReader` (driven adapter). Audit logging moves to `SubagentStopService` (application). |
| `HookPort` (interface) | **Split into** `PreToolUsePort` + `SubagentStopPort` | One port per hook event type. Clear naming. |
| `on_agent_complete()` | `validate()` on `SubagentStopPort` | Says what it does: validates. |
| `_verify_step_from_append_only_log()` | **Removed** | Replaced by `SubagentStopService` calling `StepCompletionValidator`. |
| `handle_pre_task()` | `handle_pre_tool_use()` | Matches Claude Code's hook event name exactly. |
| `handle_subagent_stop()` | `handle_subagent_stop()` | Already correct. |
| `hook` (orchestrator param) | Orchestrator no longer directly owns this | Services are independent. |
| `AuditLogger` (class) | `JsonlAuditLogWriter` | Describes the format (JSONL) and role (writer). |
| `log_audit_event()` (function) | **Removed** (global singleton) | Replaced by injected `AuditLogWriter` port. |
| `ScopeValidator` (class) | `GitScopeChecker` | Says what tool it uses (git) and what it does (checks scope). |

#### Directory Structure

```
src/des/
  domain/
    step_completion_validator.py    # NEW - single validation implementation
    max_turns_policy.py             # NEW - max_turns business rules
    des_marker_parser.py            # NEW - DES marker parsing
    phase_event.py                  # NEW - PhaseEvent + PhaseEventParser
    tdd_schema.py                   # EXISTING - unchanged

  ports/
    driver_ports/
      pre_tool_use_port.py          # NEW - replaces HookPort for PreToolUse
      subagent_stop_port.py         # NEW - replaces HookPort for SubagentStop
      validator_port.py             # EXISTING - unchanged
    driven_ports/
      execution_log_reader.py       # NEW - reads execution log
      audit_log_writer.py           # NEW - writes audit events
      scope_checker.py              # NEW - checks file scope
      filesystem_port.py            # EXISTING - unchanged
      time_provider_port.py         # EXISTING - unchanged

  application/
    pre_tool_use_service.py         # NEW - PreToolUse orchestration
    subagent_stop_service.py        # NEW - SubagentStop orchestration
    orchestrator.py                 # EXISTING - may delegate to above services

  adapters/
    drivers/
      hooks/
        claude_code_hook_adapter.py # EXISTING - simplified to thin adapter
    driven/
      execution_log/
        yaml_execution_log_reader.py  # NEW - reads YAML execution log
      logging/
        jsonl_audit_log_writer.py     # NEW - replaces audit_logger.py
        audit_events.py               # EXISTING - unchanged
      validation/
        git_scope_checker.py          # NEW - replaces scope_validator.py
      filesystem/
        real_filesystem.py            # EXISTING - unchanged
      time/
        system_time.py                # EXISTING - unchanged
```

---

### Migration Notes

#### Files to Remove After Migration

| File | Reason |
|------|--------|
| `src/des/adapters/driven/hooks/subagent_stop_hook.py` | Business logic extracted to domain. File I/O extracted to driven adapter. Audit logging extracted to application service. |
| `src/des/ports/driver_ports/hook_port.py` | Replaced by `PreToolUsePort` and `SubagentStopPort`. `HookResult` replaced by `HookDecision` + `CompletionResult`. |
| `src/des/adapters/driven/logging/audit_logger.py` | Replaced by `JsonlAuditLogWriter` implementing `AuditLogWriter` port. |
| `src/des/adapters/driven/validation/scope_validator.py` | Replaced by `GitScopeChecker` implementing `ScopeChecker` port. |

#### DESOrchestrator Migration Plan

The `DESOrchestrator` (932 lines) currently owns pre-task validation (`validate_prompt()`, line 206), post-execution validation (`on_subagent_complete()`, line 528), step execution with stale detection, turn counting, timeout monitoring, and schema version routing. The redesign affects only the first two responsibilities.

**Phase 1: Delegation (no breaking changes)**

Create `PreToolUseService` and `SubagentStopService` as new classes. Modify `DESOrchestrator` to delegate:

- `validate_prompt()` (line 206): Currently calls `self._validator.validate_prompt()`, then does DES marker parsing (regex at lines 222-240), audit event construction (lines 252-273), and audit logging (lines 276+). After redesign, this method becomes a one-liner delegating to `PreToolUseService.validate()`.
- `on_subagent_complete()` (line 528): Currently a one-liner calling `self._hook.on_agent_complete()`. After redesign, delegates to `SubagentStopService.validate()`.
- `create_with_defaults()` (line 178): Updated to inject services instead of raw `SubagentStopHook`. The constructor parameter `hook: HookPort` is replaced by `subagent_stop_service: SubagentStopPort`.

**Phase 2: Constructor signature change**

- Replace `hook: HookPort` parameter with `subagent_stop_service: SubagentStopPort` and `pre_tool_use_service: PreToolUsePort`.
- Remove `_validator: ValidatorPort` (absorbed by `PreToolUseService`).
- Tests that construct `DESOrchestrator` directly (e.g., `TestOrchestratorHookIntegration`) update constructor calls.

**Phase 3: Unaffected responsibilities remain in orchestrator**

The following `DESOrchestrator` methods are NOT part of this redesign and remain unchanged:

- `execute_step()` -- step execution lifecycle
- `execute_step_with_stale_check()` -- stale detection wrapper
- `detect_schema_version()` / `get_phase_count_for_schema()` -- schema routing
- `TurnCounter` / `TimeoutMonitor` / `InvocationLimitsValidator` integration
- `render_prompt()` / `prepare_adhoc_prompt()` -- prompt rendering

**Orchestrator test impact**: `TestOrchestratorHookIntegration` in `test_us003_post_execution_validation.py` (2 tests) uses `DESOrchestrator.create_with_defaults()` and calls `on_subagent_complete()`. These tests are at a reasonable boundary (orchestrator entry point) and survive Phase 1 unchanged. They require constructor updates in Phase 2.

#### Backward Compatibility

- The external protocol (JSON stdin/stdout, exit codes) is unchanged
- `ClaudeCodeHookAdapter` remains the entry point with same CLI interface
- The module path `src.des.adapters.drivers.hooks.claude_code_hook_adapter` is unchanged; `~/.claude/settings.json` hook commands continue to work
- The `HookResult` compound-path workaround (`path?project_id=x&step_id=y`) is eliminated -- `SubagentStopContext` carries these as proper typed fields

#### Schema v1.x Compatibility Decision

**Decision: Drop Schema v1.x support.** See ADR-6 below.

Schema v1.x (JSON step files with 14-phase cycle) is handled by `SubagentStopHook._validate_from_step_file()` (153 lines, lines 408-559). This code path:
- Is triggered when the compound path ends with `.json` (line 91-93)
- Uses a completely different data format (JSON step file with `phase_execution_log` array)
- Has no equivalent in the driver adapter path (adapter only handles Schema v2.0)

The Schema v2.0 migration was completed in prior steps. The rollback handler (`schema_rollback_handler.py`) exists as a safety net but has not been triggered. Preserving v1.x validation logic in the new architecture would require a second domain validator and a second driven adapter for JSON step files, doubling the scope with no current consumers.

If v1.x support is needed in the future, the `SchemaRollbackHandler` can restore step files to v1.x format, and a `JsonStepFileReader` driven adapter can be added at that time.

---

### Test Migration Strategy

#### Governing Principle

> "Acceptance tests should still pass because we are changing implementation details and other tests should not fail otherwise we are coupling tests and implementation. Testing should happen at the public interface -- everything else is an implementation detail."

This principle means: if a test breaks during this refactoring, the test was coupled to implementation, not to behavior. The fix is to rewrite the test at the correct boundary, not to preserve the implementation for the test's sake.

**The public interface is**: JSON on stdin, exit code (0/1/2), JSON on stdout. Internal classes (`SubagentStopHook`, `HookResult`, compound path format, `_verify_step_from_append_only_log`) are all implementation details.

#### Prerequisite: Rewrite Tests BEFORE Refactoring Internals

Test migration is **Step 0** of the implementation plan. Tests must be rewritten to use the public interface boundary BEFORE any internal restructuring begins. This ensures:

1. Tests define the expected behavior independent of implementation
2. Refactoring can proceed with confidence that passing tests prove correctness
3. No "fix the tests to match the new code" step at the end

#### Test File Inventory

| File | Coupling Type | Tests Affected | Action |
|------|--------------|----------------|--------|
| `tests/des/acceptance/test_us003_post_execution_validation.py` | **Direct SubagentStopHook import** on 8 lines (100, 142, 184, 229, 275, 321, 379, 420) | `TestPostExecutionStateValidation`: 8 test methods | Rewrite to external protocol boundary |
| `tests/des/acceptance/test_us003_post_execution_validation.py` | Orchestrator entry point | `TestOrchestratorHookIntegration`: 2 test methods | Keep as-is (correct boundary); update constructor in Phase 2 |
| `tests/des/integration/test_hook_configuration.py` | **Private function name assertion** on line 259 | `TestHookAdapterFunctionality.test_hook_adapter_accepts_schema_v2_input` | Remove private function assertion |
| `tests/des/integration/test_hook_configuration.py` | Public function existence checks | `TestHookAdapterReference.test_hook_adapter_is_importable` (line 46) | Update: `handle_pre_task` renamed to `handle_pre_tool_use` |

#### Classification: Bad Coupling vs. Legitimate Breakage

**Bad coupling (tests testing implementation, not behavior):**

- `TestPostExecutionStateValidation` (8 tests): Instantiates `SubagentStopHook()` directly, calls `hook.on_agent_complete(compound_path)`, asserts on `HookResult.validation_status`, `HookResult.abandoned_phases`, `HookResult.error_type`, etc. These test the internal class's API, not the system's external behavior. A user of this system never calls `SubagentStopHook()` -- Claude Code sends JSON on stdin and reads JSON on stdout.

- `TestHookAdapterFunctionality.test_hook_adapter_accepts_schema_v2_input` (line 259): Asserts `hasattr(claude_code_hook_adapter, "_verify_step_from_append_only_log")`. This tests the existence of a private function by name. The underscore prefix explicitly marks it as an implementation detail.

**Correct boundary (keep with minor updates):**

- `TestOrchestratorHookIntegration` (2 tests): Uses `DESOrchestrator.create_with_defaults()` and calls `on_subagent_complete()`. This tests through an application-layer entry point, which is a reasonable integration test boundary. These tests survive Phase 1 of the orchestrator migration. Phase 2 requires updating the constructor call.

- `TestHookAdapterReference` (3 tests): Tests that the module file exists, is importable, and has `main()`. These test the deployment contract and are valid.

- `TestHookInstallerConfiguration` (3 tests): Tests installer scripts reference the correct module. These are valid deployment tests.

- `TestHookConfigurationIntegrity` (2 tests): Tests `~/.claude/settings.json` has correct hook entries. Valid deployment tests.

#### Prescribed Test Rewrite Pattern

The 8 `TestPostExecutionStateValidation` tests must be rewritten to invoke the hook adapter through its external protocol:

```python
# BEFORE (coupled to implementation):
from src.des.adapters.driven.hooks.subagent_stop_hook import SubagentStopHook

hook = SubagentStopHook()
compound_path = f"{log_file}?project_id=test-project&step_id=01-01"
result = hook.on_agent_complete(step_file_path=compound_path)
assert result.validation_status == "PASSED"

# AFTER (tests public interface):
import subprocess
import json

stdin_payload = json.dumps({
    "hook_type": "SubagentStop",
    "executionLogPath": str(log_file),
    "projectId": "test-project",
    "stepId": "01-01"
})

proc = subprocess.run(
    ["python3", "-m", "des.adapters.drivers.hooks.claude_code_hook_adapter",
     "subagent-stop"],
    input=stdin_payload,
    capture_output=True,
    text=True
)

assert proc.returncode == 0  # 0=allow, 2=block
response = json.loads(proc.stdout)
assert response["decision"] == "allow"
```

This pattern:
- Uses the same protocol Claude Code uses (stdin JSON, exit code, stdout JSON)
- Survives ANY internal refactoring (class renames, file moves, layer changes)
- Tests observable behavior, not implementation structure
- Can be wrapped in a test helper for readability

#### Test Helper (recommended)

```python
def invoke_hook(hook_type: str, payload: dict) -> tuple[int, dict]:
    """Invoke hook adapter through its external protocol.

    Returns (exit_code, response_dict).
    """
    proc = subprocess.run(
        ["python3", "-m",
         "des.adapters.drivers.hooks.claude_code_hook_adapter",
         hook_type],
        input=json.dumps(payload),
        capture_output=True,
        text=True
    )
    response = json.loads(proc.stdout) if proc.stdout else {}
    return proc.returncode, response
```

#### Integration Test Fix

For `test_hook_configuration.py` line 259:

```python
# BEFORE (tests private function name):
assert hasattr(claude_code_hook_adapter, "_verify_step_from_append_only_log")

# AFTER (tests public function):
assert hasattr(claude_code_hook_adapter, "handle_subagent_stop")
```

The test already asserts `handle_subagent_stop` exists on line 264. The private function assertion on line 259 should be removed entirely.

#### Rename Impact

`handle_pre_task()` is renamed to `handle_pre_tool_use()` (see Naming Conventions). The importability test at `test_hook_configuration.py` line 46 must update:

```python
# BEFORE:
assert hasattr(claude_code_hook_adapter, "handle_pre_task")

# AFTER:
assert hasattr(claude_code_hook_adapter, "handle_pre_tool_use")
```

#### Migration Execution Order

1. **Step 0a**: Rewrite 8 `TestPostExecutionStateValidation` tests to use external protocol
2. **Step 0b**: Remove `_verify_step_from_append_only_log` assertion from `test_hook_configuration.py`
3. **Step 0c**: Verify all rewritten tests pass against current (unchanged) implementation
4. **Step 1+**: Proceed with internal refactoring (tests remain green throughout)

---

### Key Design Decisions

**ADR-1: Audit logging in application services, not adapters**

- **Status**: Accepted
- **Context**: Audit events require business context (which hook, what decision, why) that adapters do not have. Currently, `SubagentStopHook` generates audit events (lines 304-322) but the driver adapter path through `_verify_step_from_append_only_log()` generates none (Violation 3).
- **Decision**: Application services are the sole producers of audit events.
- **Alternatives Considered**:
  - *Keep audit logging in driven adapter (SubagentStopHook)*: Rejected because the driver adapter bypass (Violation 2) means audit events only fire on one of two code paths. Moving audit generation to the application service guarantees every invocation is logged regardless of which code path reached it.
  - *Add audit logging to the driver adapter as well*: Rejected because this would create two audit generation points with different context levels, risking inconsistent or duplicated audit records.
- **Consequences**:
  - Positive: Every hook invocation (allow or block) generates an audit record. The driven adapter only handles the write mechanics.
  - Positive: Audit events include full business context (step_id, project_id, decision reason).
  - Negative: Application services gain a side-effect dependency (AuditLogWriter), making them slightly harder to unit test (requires mock or stub for the writer port).

**ADR-2: Single StepCompletionValidator replaces two implementations**

- **Status**: Accepted
- **Context**: Identical validation logic exists in two locations (134 lines duplicated): `claude_code_hook_adapter._verify_step_from_append_only_log()` (lines 181-314) and `SubagentStopHook._validate_from_execution_log()` (lines 118-324).
- **Decision**: Extract to a single domain class that takes parsed `PhaseEvent` objects.
- **Alternatives Considered**:
  - *Minimal fix: Delete `_verify_step_from_append_only_log()` and make `handle_subagent_stop()` call `orchestrator.on_subagent_complete()` (3-step fix)*: This eliminates duplication (~50 lines changed, zero new files) and fixes Violations 1, 2, and 3. Rejected as the sole solution because `SubagentStopHook` itself contains 200+ lines of business logic in a driven adapter (Violation 4). The minimal fix removes the duplicate but preserves the fundamental layering violation. However, this alternative is acknowledged as a valid incremental first step -- see "Phased Implementation" note below.
  - *Move validation into DESOrchestrator directly*: Rejected because it would increase the orchestrator's already-large size (932 lines) and violate single responsibility.
- **Consequences**:
  - Positive: Bug fixes apply once. Validation rules are testable with in-memory data. No file I/O in business rules.
  - Negative: Requires migration of 8 acceptance test methods in `test_us003_post_execution_validation.py` that currently instantiate `SubagentStopHook` directly (see Test Migration Strategy).
  - Negative: Creates a new domain class and port that did not previously exist, increasing the component count.

**Phased implementation note**: The minimal 3-step fix (delete adapter duplicate, delegate to orchestrator, inject dependencies into SubagentStopHook) can serve as an intermediate step. It addresses Violations 1, 2, 3, and 7 with ~50 lines of changes and zero new files. The full domain extraction (this ADR) can follow as a second phase addressing Violations 4, 5, and 6. This phased approach reduces risk by delivering incremental value.

**ADR-3: Split HookPort into two typed ports**

- **Status**: Accepted
- **Context**: `HookPort` is a single interface covering two fundamentally different operations (PreToolUse validation and SubagentStop validation) with incompatible signatures. `on_agent_complete()` takes a compound path string and returns `HookResult`, while a PreToolUse operation would need prompt text and max_turns and return allow/block.
- **Decision**: Create `PreToolUsePort` and `SubagentStopPort` with specific input/output types.
- **Alternatives Considered**:
  - *Keep single HookPort, add a second method for PreToolUse*: Rejected because a single interface with two unrelated methods violates Interface Segregation Principle. Consumers needing only PreToolUse validation would still depend on SubagentStop's signature.
  - *No port for PreToolUse (keep inline in adapter)*: Rejected because this preserves Violation 5 (no port for PreToolUse validation), keeping business logic in the adapter.
- **Consequences**:
  - Positive: Type safety. Clear contracts. Each port evolves independently.
  - Negative: Two interfaces to maintain instead of one. Consumers (e.g., DESOrchestrator) must know which port to inject.
  - Negative: `HookResult` is replaced by `HookDecision` + `CompletionResult`, requiring updates to any code that consumes `HookResult`.

**ADR-4: Driver adapter contains zero business logic**

- **Status**: Accepted
- **Context**: `claude_code_hook_adapter.py` (441 lines) currently contains max_turns validation, DES marker parsing, TDD phase validation, and direct file I/O. This violates hexagonal architecture by placing business logic in the driver adapter layer (Violations 2, 3, 5).
- **Decision**: All business logic moves to domain or application layer. Adapter only handles JSON parse, service call, JSON format, exit code.
- **Alternatives Considered**:
  - *Extract only max_turns and DES marker checks to domain functions, keep adapter routing*: Rejected because partial extraction creates inconsistency -- some business logic in domain, some in adapter. The validation rules for max_turns range, DES marker patterns, and TDD phase checking are all business rules that belong in the same layer.
  - *Keep adapter thick but well-tested*: Rejected because testing business rules through stdin/stdout simulation is fragile and slow. Domain classes with in-memory inputs are faster and more reliable to test.
- **Consequences**:
  - Positive: The adapter is testable by mocking the service port. Business rules are testable without stdin/stdout simulation.
  - Positive: Addresses Violations 2, 3, and 5 simultaneously.
  - Negative: Application services become the coordination point. Debugging a hook failure requires tracing through adapter, service, domain, and driven adapter layers instead of reading one function.
  - Negative: The adapter shrinks from ~441 lines to ~60 lines, but the total system line count increases because the same logic is now spread across more files with explicit interfaces.

**ADR-5: ExecutionLogReader as driven port instead of direct file I/O**

- **Status**: Accepted
- **Context**: Both current implementations directly call `yaml.safe_load()` and parse pipe-delimited strings inline. The YAML format and pipe-delimited encoding are infrastructure details mixed into business logic.
- **Decision**: Define an `ExecutionLogReader` driven port. The YAML format is an infrastructure detail hidden behind the port.
- **Alternatives Considered**:
  - *Pass raw YAML dict to domain validator*: Rejected because the domain layer would depend on the YAML structure (key names, nesting), coupling business logic to the persistence format.
  - *Use a utility function instead of a port*: Rejected because a utility function is not injectable or replaceable for testing. A driven port allows testing the application service with an in-memory stub.
- **Consequences**:
  - Positive: Domain and application layers are decoupled from the YAML file format. A different log format (database, API) could be substituted without changing business logic.
  - Positive: The `PhaseEventParser` (pipe-delimited string parsing) is encapsulated in the driven adapter, keeping the domain model clean.
  - Negative: Adds an interface and an implementation class where a direct `yaml.safe_load()` call previously sufficed. This indirection is overhead for a system that will likely always use YAML files.

**ADR-6: Drop Schema v1.x support**

- **Status**: Accepted
- **Context**: `SubagentStopHook._validate_from_step_file()` (153 lines, lines 408-559) handles Schema v1.x JSON step files with 14-phase cycle. The Schema v2.0 migration is complete. The driver adapter (`_verify_step_from_append_only_log`) only handles v2.0. The `SchemaRollbackHandler` exists as a safety net but has not been triggered.
- **Decision**: Schema v1.x validation logic is not carried forward into the new architecture. The 153-line `_validate_from_step_file()` method is removed along with `SubagentStopHook`.
- **Alternatives Considered**:
  - *Preserve v1.x support with a second driven adapter (JsonStepFileReader)*: Rejected because it doubles the scope (second reader port implementation, second validation path, second set of tests) for a format with no current consumers.
  - *Add deprecation period with runtime warnings*: Rejected because there is no mechanism to produce v1.x step files in the current system. The migration is already complete.
- **Consequences**:
  - Positive: Reduces scope by ~153 lines and avoids creating a parallel driven adapter for a dead format.
  - Positive: Simplifies SubagentStopService to a single validation path.
  - Negative: If a future requirement reintroduces v1.x step files, a new `JsonStepFileReader` driven adapter and corresponding validation logic must be built from scratch.
  - Negative: The `SchemaRollbackHandler` (which downgrades step files to v1.x) becomes less useful since there is no v1.x validator to consume the downgraded files. It may need removal or update in a future cleanup.

---

## Architecture Review

```yaml
review_id: "arch_rev_20260206_review_01"
reviewer: "solution-architect (review mode)"
artifact: "docs/architecture/des-hook-architecture-redesign.md"
iteration: 1
review_date: "2026-02-06"

overall_assessment: "CONDITIONALLY_APPROVED"
verdict: "Architecturally sound redesign with accurate violation analysis. Requires revisions in test migration strategy and should document rejection of simpler alternatives before proceeding."

strengths:
  - "All 7 violations verified against source code with correct line references. No false positives detected."
  - "Hexagonal layer separation is textbook: driver adapters (protocol), application services (orchestration+audit), domain (pure business rules), driven ports (outbound interfaces), driven adapters (infrastructure). Dependency direction is consistently inward."
  - "The StepCompletionValidator consolidation eliminates 134 lines of duplicated validation logic (Violation 1), ensuring bug fixes apply once."
  - "Audit event generation exclusively in application services (ADR-1) is the correct placement. Application layer has full business context needed for meaningful audit records."
  - "Splitting HookPort into PreToolUsePort and SubagentStopPort (ADR-3) eliminates a leaky abstraction. The two operations have incompatible signatures and independent evolution paths."
  - "Data flow diagrams (Flows 1-4) are precise and trace complete request paths from stdin to stdout. Each diagram identifies every component touched."
  - "The external protocol contract (JSON stdin/stdout, exit codes 0/1/2) is explicitly preserved, and the module entry point path is unchanged."
  - "ADR-4 (zero business logic in adapter) directly addresses Violations 2, 3, and 5 simultaneously."
  - "Driven port definitions (ExecutionLogReader, AuditLogWriter, ScopeChecker) are defined by application needs, not technology format. This is correct hexagonal practice."
  - "Complete rename map with rationale for every name change. No ambiguous renames."

issues_identified:
  test_migration_strategy:
    - issue: "MISSING: No test migration strategy for existing acceptance tests that directly import SubagentStopHook"
      severity: "HIGH"
      location: "Document is missing a Test Migration section"
      evidence: |
        tests/des/acceptance/test_us003_post_execution_validation.py directly imports
        SubagentStopHook on lines 100, 142, 184, 229, 275, 321, 379, 420:
          from src.des.adapters.driven.hooks.subagent_stop_hook import SubagentStopHook
          hook = SubagentStopHook()
          hook_result = hook.on_agent_complete(step_file_path=compound_path)

        These 8 test methods will FAIL when SubagentStopHook is removed. The compound
        path format (path?project_id=x&step_id=y) and HookResult attributes
        (validation_status, abandoned_phases, etc.) are all implementation details
        the tests are coupled to.

        Additionally, tests/des/integration/test_hook_configuration.py line 259 asserts:
          assert hasattr(claude_code_hook_adapter, "_verify_step_from_append_only_log")
        This tests a private function by name and will break when it is removed.
      recommendation: |
        Add a "Test Migration Strategy" section that:
        1. Identifies every test file that imports SubagentStopHook, HookResult, or
           references _verify_step_from_append_only_log by name
        2. For each test class, specifies the new test boundary:
           - TestPostExecutionStateValidation scenarios should test through
             SubagentStopPort.validate() or ClaudeCodeHookAdapter stdin/stdout
           - TestOrchestratorHookIntegration tests are ALREADY at correct boundary
             (orchestrator entry point) - these should survive with minimal changes
           - TestHookAdapterFunctionality line 259 must stop testing private functions
        3. Classifies which test failures are "bad coupling" (testing implementation)
           vs "legitimate breakage" (testing behavior that moved)
        4. The stakeholder explicitly stated tests that break indicate bad test coupling.
           Document this principle and use it to guide the migration.

    - issue: "Acceptance tests test at the wrong boundary (implementation class, not public interface)"
      severity: "HIGH"
      location: "tests/des/acceptance/test_us003_post_execution_validation.py"
      evidence: |
        The stakeholder requirement states: "Testing should happen at the public
        interface - everything else is an implementation detail."

        The public interface is: JSON on stdin -> exit code + JSON on stdout.
        Internal classes (SubagentStopHook, HookResult, compound path format) are
        ALL implementation details.

        Current acceptance tests instantiate SubagentStopHook directly and assert on
        HookResult.validation_status. This is testing a driven adapter's internal
        behavior, not the system's external behavior.
      recommendation: |
        The architecture document should prescribe that acceptance tests be rewritten
        to test through the external protocol boundary:

        # BEFORE (coupled to implementation):
        hook = SubagentStopHook()
        result = hook.on_agent_complete(compound_path)
        assert result.validation_status == "PASSED"

        # AFTER (tests public interface):
        stdin_json = json.dumps({"executionLogPath": path, "projectId": "test", "stepId": "01-01"})
        exit_code, stdout_json = invoke_hook_adapter("subagent-stop", stdin_json)
        assert exit_code == 0
        assert json.loads(stdout_json)["decision"] == "allow"

        This aligns with the stakeholder's principle and makes tests survive ANY
        internal refactoring.

  simpler_alternatives_not_documented:
    - issue: "ADRs lack 'Alternatives Considered' section. A simpler 3-step fix could address 4 of 7 violations without 13 new files."
      severity: "MEDIUM"
      location: "ADR-1 through ADR-5"
      evidence: |
        A minimal fix exists that addresses Violations 1, 2, 3, and 7:
        Step 1: Delete _verify_step_from_append_only_log() from claude_code_hook_adapter.py
        Step 2: Make handle_subagent_stop() call orchestrator.on_subagent_complete()
                (same pattern handle_pre_task() already uses for DES execution mode)
        Step 3: Inject AuditLogger and TimeProvider via SubagentStopHook constructor

        This eliminates code duplication, restores proper delegation, adds audit
        logging, and fixes dependency inversion - all in ~50 lines of changes to
        existing files with zero new files.

        Remaining violations (4: placement, 5: no PreToolUsePort, 6: naming) are
        structural but lower risk - they can be addressed incrementally.
      recommendation: |
        Each ADR should document at least one rejected alternative with rationale:

        ADR-2 alternative: "Delete adapter duplicate, delegate to existing SubagentStopHook"
        Rejection rationale: "SubagentStopHook itself has business logic that should
        be in domain layer. Patching the delegation fixes duplication but preserves
        the fundamental layering violation."

        ADR-4 alternative: "Extract only max_turns and DES marker checks to domain
        functions, keep adapter routing"
        Rejection rationale: "Partial extraction creates inconsistency - some business
        logic in domain, some in adapter. Full extraction preferred for consistency."

        This demonstrates the full redesign was chosen deliberately, not by default.

  over_engineering_risk:
    - issue: "Three proposed domain classes are trivially thin wrappers that could be plain functions"
      severity: "LOW"
      location: "Domain Layer Definitions - MaxTurnsPolicy, DesMarkerParser, PhaseEventParser"
      evidence: |
        MaxTurnsPolicy: Validates a number is between 10 and 100. 3 if-statements.
        DesMarkerParser: 2-3 regex matches returning a dataclass.
        PhaseEventParser: A single line.split('|') with field assignment.

        Each of these will be a file with ~20-30 lines of code, half of which is
        boilerplate (imports, docstring, class definition).
      recommendation: |
        Consider consolidating these into fewer domain modules:
        - phase_event.py: PhaseEvent dataclass + parse() function + PhaseEventParser
        - hook_policies.py: MaxTurnsPolicy + DesMarkerParser (both are pre-task policies)

        Or keep them as separate classes but in shared modules rather than separate files.
        This is a SUGGESTION, not a blocking issue - separate files are fine if the
        team prefers one-class-per-file convention.

  adr_consequences_incomplete:
    - issue: "ADR consequences list only positive outcomes. Negative trade-offs not documented."
      severity: "MEDIUM"
      location: "ADR-1 through ADR-5"
      evidence: |
        ADR-2 consequence: "Bug fixes apply once. Validation rules are testable
        with in-memory data. No file I/O in business rules."
        Missing negative: "Requires migration of 8 acceptance test methods that
        currently instantiate SubagentStopHook directly."

        ADR-3 consequence: "Type safety. Clear contracts. Each port evolves independently."
        Missing negative: "Two interfaces to maintain instead of one. Consumers must
        know which port to inject."

        ADR-4 consequence: "The adapter is testable by mocking the service port.
        Business rules are testable without stdin/stdout simulation."
        Missing negative: "Application services become the new coordination point.
        If a bug occurs, debugging requires tracing through adapter -> service ->
        domain -> driven adapter chain instead of reading one function."
      recommendation: |
        Follow Nygard ADR template strictly. Each ADR consequence section should have:
        - Positive consequences (benefits)
        - Negative consequences (costs, risks, trade-offs)
        - Neutral consequences (things that change without clear benefit/cost)

  orchestrator_impact_underspecified:
    - issue: "DESOrchestrator migration path is vague"
      severity: "MEDIUM"
      location: "Migration Notes > Impact on DESOrchestrator"
      evidence: |
        The document states: "DESOrchestrator can delegate to these services or be
        refactored incrementally."

        DESOrchestrator is 932 lines with significant existing responsibilities
        (schema versioning, stale detection, turn counting, timeout monitoring).
        It currently owns validate_prompt() and on_subagent_complete().

        The proposed PreToolUseService and SubagentStopService will overlap with
        orchestrator responsibilities. The document doesn't specify:
        1. Whether orchestrator.validate_prompt() delegates to PreToolUseService
           or is replaced by it
        2. Whether orchestrator.on_subagent_complete() delegates to
           SubagentStopService or is replaced by it
        3. Who owns the DES marker detection (currently in adapter AND orchestrator)
        4. How existing orchestrator tests are affected
      recommendation: |
        Add specific migration plan for DESOrchestrator:
        - Phase 1: Create services, orchestrator delegates to them
        - Phase 2: Move remaining logic, orchestrator becomes thin coordinator
        - Specify which orchestrator methods are affected and how
        - Identify orchestrator tests that need updating

  schema_v1_compatibility_gap:
    - issue: "Schema v1.x compatibility path not fully specified"
      severity: "LOW"
      location: "Migration Notes > Backward Compatibility"
      evidence: |
        The document mentions: "Schema v1.x compatibility path in
        SubagentStopHook._validate_from_step_file() can be preserved in
        SubagentStopService if needed"

        _validate_from_step_file() is 153 lines (lines 408-559) handling JSON step
        files. Where this code goes is not specified. If SubagentStopService needs
        v1.x compatibility, it must either:
        a) Contain the v1.x logic (business logic in application layer - acceptable)
        b) Delegate to a separate domain validator (another new class)
        c) Drop v1.x support (breaking change)
      recommendation: |
        Decide explicitly: Is Schema v1.x still needed?
        - If YES: Specify where _validate_from_step_file() logic moves
        - If NO: State "Schema v1.x support is dropped in this redesign" as ADR-6

priority_validation:
  q1_largest_bottleneck:
    evidence: "Code duplication across 134 lines, bypassed application layer, missing audit trail"
    assessment: "YES"
    concern: "None - these are genuine structural problems causing maintenance risk"

  q2_simple_alternatives:
    alternatives_documented: "NONE"
    rejection_justified: "MISSING"
    assessment: "INADEQUATE"
    concern: "A 3-step minimal fix could address Violations 1,2,3,7 without 13 new files. This simpler approach should be documented and rejected with explicit rationale before committing to full redesign."

  q3_constraint_prioritization:
    constraints_quantified: "YES - line counts and duplication identified"
    constraint_free_first: "YES - addresses root causes"
    minority_constraint_dominating: "NO"
    assessment: "CORRECT"

  q4_data_justified:
    key_decision: "Full hexagonal decomposition with 13 new files"
    supporting_data: "7 verified violations, 134 lines duplicated, zero audit trail on adapter path"
    assessment: "JUSTIFIED"

  verdict: "PASS (with conditions)"
  conditions:
    - "Document simpler alternatives with rejection rationale"
    - "Add test migration strategy"

risk_assessment:
  migration_risk:
    level: "MEDIUM"
    description: "13 new files + 4 files removed. Large surface area for migration errors."
    mitigation: "Phased migration: create new components first, run both paths in parallel, switch over when tests pass."

  test_breakage_risk:
    level: "HIGH"
    description: "8 acceptance test methods in test_us003 directly import SubagentStopHook. 1 integration test checks private function name. All will break."
    mitigation: "Rewrite tests to use public interface (JSON stdin/stdout) BEFORE starting refactoring. Tests should drive the redesign, not follow it."

  orchestrator_coupling_risk:
    level: "MEDIUM"
    description: "DESOrchestrator (932 lines) has deep integration with current hook infrastructure. Migration path is underspecified."
    mitigation: "Define explicit orchestrator migration phases. Keep orchestrator delegation working throughout migration."

  external_validity_risk:
    level: "LOW"
    description: "Hook adapter module path unchanged. settings.json hook configuration unaffected. Exit code semantics preserved."
    mitigation: "Integration test test_hook_configuration.py validates adapter exists and is importable."

external_validity_check:
  result: "PASS"
  details: |
    After refactoring:
    1. ClaudeCodeHookAdapter.main() still routes sys.argv[1] to handler functions
    2. handle_pre_tool_use() reads stdin JSON, calls PreToolUsePort, writes stdout JSON
    3. handle_subagent_stop() reads stdin JSON, calls SubagentStopPort, writes stdout JSON
    4. Exit codes 0/1/2 semantics preserved
    5. Module path src.des.adapters.drivers.hooks.claude_code_hook_adapter unchanged
    6. ~/.claude/settings.json hook commands reference this module path - unaffected
    7. Hooks will continue to fire and work correctly after refactoring

    The only external validity concern is in the TEST SUITE, not the production code.
    Tests coupled to implementation details will break, but the production hooks
    remain externally valid.

approval_conditions:
  must_fix_before_implementation:
    - severity: "HIGH"
      item: "Add Test Migration Strategy section identifying every test file affected and specifying new test boundaries"
    - severity: "HIGH"
      item: "Acknowledge that existing acceptance tests violate the stakeholder's principle (testing implementation, not public interface) and prescribe test rewrites"
  should_fix:
    - severity: "MEDIUM"
      item: "Add 'Alternatives Considered' to each ADR, including the minimal 3-step fix"
    - severity: "MEDIUM"
      item: "Add negative consequences to each ADR"
    - severity: "MEDIUM"
      item: "Specify DESOrchestrator migration path in concrete phases"
  nice_to_have:
    - severity: "LOW"
      item: "Consider consolidating micro-domain-classes (MaxTurnsPolicy, DesMarkerParser, PhaseEventParser) into fewer modules"
    - severity: "LOW"
      item: "Decide explicitly on Schema v1.x compatibility (keep, migrate, or drop)"

critical_issues_count: 0
high_issues_count: 2
medium_issues_count: 4
low_issues_count: 2
```
