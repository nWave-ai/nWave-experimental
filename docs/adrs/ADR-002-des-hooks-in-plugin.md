# ADR-002: DES Hooks Packaging in Plugin

## Status

Accepted

## Context

The DES (Deterministic Execution System) uses Claude Code hooks (PreToolUse, PostToolUse, SubagentStop, SessionStart, SubagentStart) to enforce TDD phases. Currently, the custom installer:

1. Copies `src/des/` to `~/.claude/lib/python/des/` with import rewriting
2. Registers hooks in `~/.claude/settings.json` with commands using `PYTHONPATH=$HOME/.claude/lib/python`
3. Resolves Python interpreter path at install time

The plugin system works differently:
- Plugins are copied to `~/.claude/plugins/cache/{name}/`
- Hook commands in `hooks/hooks.json` use `${CLAUDE_PLUGIN_ROOT}` variable
- Plugin cannot modify `~/.claude/settings.json` directly
- Plugin hooks are isolated from global settings hooks

The core question: how does the DES Python module run inside a plugin sandbox?

## Decision

Bundle DES as a self-contained Python module inside the plugin's `lib/des/` directory, invoked directly by hook commands that set PYTHONPATH to the plugin's lib directory.

**Plugin hook architecture:**

```
hooks/hooks.json
  └── command: "python3 ${CLAUDE_PLUGIN_ROOT}/lib/des/adapters/drivers/hooks/claude_code_hook_adapter.py pre-task"

lib/des/
  ├── __init__.py
  ├── domain/
  ├── application/
  ├── ports/
  └── adapters/
```

**Note**: Prior art on `feat/claude-code-plugin` shows hooks invoking `python3 ${CLAUDE_PLUGIN_ROOT}/lib/des/adapters/drivers/hooks/claude_code_hook_adapter.py` directly — no shell wrapper needed. This eliminates the extra process hop.

The DES module is identical to the one installed by the custom installer, with `from src.des` rewritten to `from des` (same transform already implemented in `des_plugin.py`).

**Python interpreter**: Uses `python3` from PATH (not a resolved absolute path). Plugin environments cannot control which Python is used, so we rely on the system Python. DES dependencies (pyyaml, pydantic) must be available in the system Python.

## Alternatives Considered

### Alternative 1: DES as MCP server inside plugin

- **What**: Bundle DES as an MCP server in `.mcp.json`, exposing `des_validate_phase` and `des_start_step` as tools
- **Evaluation**: MCP servers provide a cleaner process isolation model. The DES server would run as a long-lived process, eliminating per-hook startup cost. However, MCP enforcement is cooperative (agent must call the tool) vs coercive (hooks intercept all tool use).
- **Why Rejected**: Changes the enforcement model from "system intercepts" to "agent cooperates." This is the Phase 2 approach for cross-platform DES. For the Claude Code plugin, native hooks provide the same hard enforcement as the custom installer. MCP would be a regression in enforcement quality.

### Alternative 2: Reference global DES installation

- **What**: Plugin hooks point to `$HOME/.claude/lib/python` where the custom installer placed DES
- **Evaluation**: Zero duplication. Hooks in plugin use the same DES module as custom installer.
- **Why Rejected**: Creates a dependency between plugin and custom installer. If the user only installs the plugin (no custom installer), DES would be missing. Plugin must be self-contained.

### Alternative 3: Inline hook logic in shell scripts (no Python)

- **What**: Rewrite DES hook logic as shell scripts that check phase files directly
- **Evaluation**: Eliminates Python dependency entirely. Shell is universally available.
- **Why Rejected**: DES hook logic is complex (1,086 lines in orchestrator.py alone). Rewriting in shell would be error-prone, unmaintainable, and untestable. The zero-shell-scripts policy also applies.

## Consequences

### Positive
- Plugin is fully self-contained -- no dependency on custom installer
- Same DES enforcement quality as custom installer (coercive hooks)
- Import rewriting code already exists and is tested
- Shell wrapper is 5 lines, trivially auditable

### Negative
- DES module is duplicated between plugin and custom installer installations (if both active)
- Relies on `python3` in PATH. Dependency mitigation: prior art on `feat/claude-code-plugin` migrates execution-log and roadmap from YAML to JSON, eliminating pyyaml dependency. If JSON migration is complete, DES needs only stdlib.
- DES runtime templates (step-tdd-cycle-schema.json, roadmap-schema.json) must also be bundled in the plugin

### Security Considerations
- Hooks read/write only project-local `.nwave/des/` directory (session state, execution logs)
- PYTHONPATH is scoped to `${CLAUDE_PLUGIN_ROOT}/lib/` — isolated from system packages and custom installer
- Hook scripts emit diagnostic errors to stderr on failure (not silent)
- No settings.json modification — hook registration is static in hooks.json
