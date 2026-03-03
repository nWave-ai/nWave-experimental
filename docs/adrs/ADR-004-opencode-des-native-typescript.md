# ADR-004: OpenCode DES as Native TypeScript Plugin

## Status

Proposed (pending PoC validation)

## Context

nWave's DES (Deterministic Execution System) enforces TDD phase discipline on AI agents through hooks. The existing Claude Code implementation uses Python: a hook adapter receives JSON on stdin, delegates to application services (PreToolUseService, SubagentStopService), and returns exit codes.

OpenCode v1.2.15 requires a different approach. Its plugin system expects TypeScript files in `~/.config/opencode/plugins/` that export hook handlers as async functions. The key architectural question: should the OpenCode DES be a native TypeScript implementation, or should it call the existing Python DES via subprocess?

### Business Drivers

- **Time-to-market**: OpenCode support is the final piece for multi-platform nWave
- **Maintainability**: Two implementations (Python + TypeScript) create dual-maintenance burden
- **Performance**: Every tool call triggers the DES hook; latency matters
- **Reliability**: DES enforcement must be deterministic and fail-safe

### Constraints

- OpenCode plugins must be TypeScript (platform requirement)
- DES runtime logic is ~1,600 lines across orchestrator, services, and domain
- The TDD phase enforcement core is ~200 lines of actual business rules
- Python DES has external dependency on stdlib only (post-YAML-to-JSON migration)
- OpenCode runs on Bun, which includes a full `fs` module

## Validation Gate

Before this ADR moves to Accepted, a proof-of-concept must validate:

1. `throw Error` in `tool.execute.before` blocks tool execution in OpenCode v1.2.15
2. Error message is surfaced to the agent/user (visible in TUI or logs)
3. `tool.execute.after` receives correct tool name and arguments

If the PoC fails on item (1), the entire hook-based enforcement model is invalid and this ADR must be rejected in favor of an alternative approach.

## Decision

Implement the OpenCode DES as a **native TypeScript plugin** (`nwave-des.ts`) that reimplements the phase enforcement rules in TypeScript. The plugin is a single self-contained file with zero npm dependencies, using only Bun/Node.js built-in `fs` and `path` modules.

The TypeScript plugin implements the **enforcement subset** of DES -- specifically the phase-aware tool gating and audit logging. It does NOT replicate the full Python DES (orchestrator, template validation, schema routing, stale execution detection). Those features remain Claude Code-specific and are not needed for OpenCode's plugin model.

### Scope Boundary

**In scope (TypeScript reimplementation):**
- Phase tool policy enforcement (which tools allowed per phase)
- File classification (test vs production)
- Session state persistence (deliver-session.json)
- Audit logging (des-audit.jsonl)
- Phase transition validation
- Compaction context preservation

**Out of scope (Python DES only):**
- DES orchestrator (prompt rendering, schema version routing)
- Template validation (9 mandatory sections)
- Full stale execution detection (TS has lightweight staleness warnings; Python has full blocking via `StaleExecutionDetector`)
- Import rewriting
- Max turns policy (handled by OpenCode's `steps` field in agent frontmatter)
- DES marker parsing (DES markers are a Claude Code Task tool concept)

## Alternatives Considered

### Alternative 1: Python Subprocess Bridge

- **What**: TypeScript plugin spawns `python3` subprocess for each hook, passing JSON stdin/stdout exactly like Claude Code
- **Expected Impact**: 100% behavior parity with Claude Code DES
- **Why Rejected**:
  1. **Performance**: ~50ms subprocess startup per tool call. At 100+ tool calls per deliver session, adds 5+ seconds of latency. OpenCode's in-process plugins run in <1ms.
  2. **Dependency**: Requires Python 3 installed and on PATH. OpenCode users may not have Python (Bun is the only runtime requirement).
  3. **Complexity**: Requires installing the full Python DES module to `~/.config/opencode/lib/python/des/` plus PYTHONPATH management. Doubles the installation surface.
  4. **Fragility**: Two process models (Bun + Python) increase failure modes. Process communication via stdin/stdout adds serialization overhead.
  5. **Maintenance**: Still requires TypeScript glue code plus the full Python DES -- more total code than a native TS implementation of the enforcement subset.

### Alternative 2: DES as MCP Server (Cross-Platform)

- **What**: Build DES as a Python MCP server that both Claude Code and OpenCode consume via MCP protocol
- **Expected Impact**: Single implementation serves both platforms
- **Why Rejected**:
  1. **Enforcement model regression**: MCP enforcement is cooperative (agent must call the tool). Hook enforcement is coercive (system intercepts all tool calls). DES's value is coercive enforcement -- agents cannot bypass it.
  2. **Latency**: MCP adds HTTP/SSE round-trip per tool validation. Hooks are in-process.
  3. **Operational complexity**: Long-running MCP server process must be started, monitored, and restarted on failure. Hooks are stateless.
  4. **Research explicitly warned**: The feasibility research (2026-03-02) identifies MCP as the "Phase 2 approach" and warns it "changes the enforcement model from system intercepts to agent cooperates."

### Alternative 3: Shared WebAssembly Module

- **What**: Compile DES rules to WASM, load from both Python (via wasmtime) and TypeScript (via Bun WASM support)
- **Expected Impact**: Single source of truth for enforcement rules
- **Why Rejected**:
  1. **Complexity**: WASM compilation toolchain adds significant build complexity
  2. **File I/O**: WASM cannot do file I/O natively; requires host bindings for state persistence
  3. **Overkill**: The enforcement rules are ~200 lines. Maintaining them in two languages is simpler than a WASM build pipeline.
  4. **Debugging**: WASM debugging is significantly harder than TypeScript or Python

## Consequences

### Positive

- **Performance**: In-process TypeScript hooks execute in <1ms (vs ~50ms for Python subprocess)
- **Zero dependencies**: No Python required. Plugin uses only Bun/Node built-ins (`fs`, `path`)
- **Self-contained**: Single `.ts` file, trivially auditable (~300 lines)
- **Platform-native**: Uses OpenCode's hook API idiomatically (throw to block, return to allow)
- **Simplified scope**: Only enforcement rules are reimplemented, not the full DES orchestrator

### Negative

- **Dual maintenance**: Phase enforcement rules exist in both Python and TypeScript. Changes to TDD phases (e.g., adding a phase, changing allowed tools) must be synchronized.
  - **Mitigation**: Phase enforcement rules are small (~50 lines of policy data). Changes are infrequent (TDD phases have not changed since v4.0). A CI test comparing both implementations' allowed/blocked decisions on a fixture set will catch drift. Note: the TypeScript plugin adds phase-granular file restrictions (RED=test-only, GREEN=prod-only) that the Python DES does not enforce at the tool level, so "drift" applies only to shared behaviors (phase names, transition map), not to the new enforcement rules.
- **Feature gap**: TypeScript plugin lacks advanced DES features (stale detection, template validation, schema routing). These are Claude Code-specific and not critical for phase enforcement.
- **Testing**: TypeScript plugin requires its own test suite separate from Python DES tests.
  - **Mitigation**: Enforcement logic is small (~200 lines of rules). Acceptance tests can verify behavior on both platforms.

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Phase rules drift between Python and TypeScript | Medium | High | CI fixture test comparing allowed/blocked decisions on shared behaviors. Phase-granular enforcement is TS-only, so drift applies only to phase names and transition map. |
| OpenCode plugin API changes | Low | Medium | Depend only on stable hooks (`tool.execute.before`, `tool.execute.after`, `stop`). Avoid experimental hooks for critical features. |
| `stop` hook not firing for subagents | Low | Medium | Validated by research (Issue #5894 pertains to BatchTool only, not task tool). Build PoC to verify before production deployment. |
