# nWave Experimental

> **This is an experimental testing repo.** It contains pre-release features from `nWave-dev` that need validation before merging to master. Do not use this in production.

---

## What's Being Tested: OpenCode DES Plugin

The DES (Deterministic Execution System) is nWave's TDD discipline enforcement layer. It currently works only on Claude Code via Python hooks. This build adds **native OpenCode support** through a TypeScript plugin that uses OpenCode's hook system.

### What DES Does

During a `/nw:deliver` session, DES enforces which files you can modify in each TDD phase:

| Phase | Test Files | Production Files | Bash | Read |
|-------|-----------|-----------------|------|------|
| PREPARE | write/edit | write/edit | run | read |
| RED_ACCEPTANCE | write/edit | **blocked** | run | read |
| RED_UNIT | write/edit | **blocked** | run | read |
| GREEN | **blocked** | write/edit | run | read |
| COMMIT | **blocked** | edit only | run | read |

If you try to write a production file during RED phase, DES blocks the tool call and tells you why.

---

## Testing Instructions

### Prerequisites

- [OpenCode](https://github.com/opencode-ai/opencode) v1.2.15+ installed
- The OpenCode plugins directory exists: `~/.config/opencode/plugins/`
- `jq` installed for reading session state in Gate 3 (`apt install jq` or `brew install jq`)

> **Windows**: Use WSL. Paths like `~/.config/opencode/` expand to your WSL home directory.

### Step 1: Install the Plugin

Copy the TypeScript plugin to OpenCode's plugins directory:

```bash
cp src/des/opencode-plugin.ts ~/.config/opencode/plugins/nwave-des.ts
```

Restart OpenCode entirely (close and reopen, not just a new chat) to load the plugin.

### Step 2: Verify Plugin Loaded

In OpenCode, you should see two new tools available:
- `des_create_session` — Creates a DES enforcement session
- `des_advance_phase` — Advances the TDD phase

If these tools are not visible, the plugin did not load. Check OpenCode logs for errors.

### Step 3: Create a Test Session

Ask the agent (or call directly):

```
Call des_create_session with featureId="test-feature" and stepId="01-01"
```

Expected response:
```
DES session created: feature=test-feature, step=01-01, phase=NOT_STARTED.
Call des_advance_phase("PREPARE", "reason") to begin.
```

### Step 4: Advance Through Phases

Make **three separate calls**, one at a time (the plugin validates each transition):

```
Call des_advance_phase with nextPhase="PREPARE" and evidence="Setting up test environment"
```

```
Call des_advance_phase with nextPhase="RED_ACCEPTANCE" and evidence="Acceptance test ready"
```

```
Call des_advance_phase with nextPhase="RED_UNIT" and evidence="Unit tests written"
```

> RED_ACCEPTANCE and RED_UNIT share identical enforcement rules (test files only). We advance through RED_ACCEPTANCE to test the full transition chain, but enforcement testing focuses on RED_UNIT.

### Step 5: Test Phase Enforcement (Critical)

While in **RED_UNIT** phase, try to write or edit a production file:

```
Write the file src/hello.ts with content: console.log("hello")
```

**Expected behavior**: The tool call should be **blocked** with an error message like:
```
DES: Phase RED_UNIT does not allow writeProd — cannot write/create production file src/hello.ts. Only test files may be modified in RED phases.
```

Then try writing a test file (should be **allowed**):
```
Write the file tests/hello.test.ts with content: test("hello", () => {})
```

### Step 6: Test GREEN Phase (Reverse Enforcement)

```
Call des_advance_phase with nextPhase="GREEN" and evidence="All tests pass"
```

Now try writing a test file (should be **blocked**):
```
Write the file tests/another.test.ts with content: test("another", () => {})
```

And a production file (should be **allowed**):
```
Write the file src/hello.ts with content: console.log("hello world")
```

---

## What to Validate (PoC Gates)

These are the three critical validation points from [ADR-004](docs/adrs/ADR-004-opencode-des-native-typescript.md):

### Gate 1: Tool Blocking Works

`throw Error` in `tool.execute.before` actually prevents the tool from executing.

**How to test**: In RED_UNIT phase, attempt to write a production file (Step 5 above).

**Verify**:
1. An error message appears in the OpenCode chat (see Gate 2 for expected format)
2. The file was **not created** on disk — confirm with: `ls src/hello.ts` (should say "No such file")
3. The tool execution was blocked **before** writing, not rolled back after

- [ ] Pass: Error shown AND file does not exist on disk
- [ ] Fail: File was created despite the error (blocking did not work)

### Gate 2: Error Message Visible

The error message from DES is surfaced to the agent and/or user in the TUI.

**How to test**: When a tool is blocked (Step 5 above), check the error message in OpenCode chat.

**Expected error message** (exact format from the plugin):
```
DES: Phase RED_UNIT does not allow writeProd — cannot write/create production file src/hello.ts.
Only test files may be written or edited in RED phases.
```

The message must contain:
- The `DES:` prefix
- The current phase name (`RED_UNIT`)
- The blocked operation (`writeProd`)
- The file path that triggered the block
- An explanation of what IS allowed in the current phase

- [ ] Pass: Error message visible in chat with all fields above
- [ ] Fail: Tool silently fails, shows generic error, or message is missing fields

### Gate 3: After Hook Receives Correct Data

`tool.execute.after` receives the correct tool name and file path arguments.

**How to test**: After a **successful** write (e.g., writing a test file in RED_UNIT phase, or a production file in GREEN phase), check the session state:

```bash
cat .nwave/des/deliver-session.json | jq '{filesModified, currentPhase, turnCount}'
```

**Expected output** (after writing `tests/hello.test.ts` in RED_UNIT and `src/hello.ts` in GREEN):
```json
{
  "filesModified": [
    "tests/hello.test.ts",
    "src/hello.ts"
  ],
  "currentPhase": "GREEN",
  "turnCount": 8
}
```

- [ ] Pass: Written files appear in `filesModified` array with correct paths
- [ ] Fail: Array is empty, files are missing, or paths are wrong

---

## Audit Trail

All DES actions are logged to `.nwave/des/logs/des-audit.jsonl`. Each line is a JSON object:

```bash
cat .nwave/des/logs/des-audit.jsonl | jq .
```

Look for events like:
- `session_created` — New session started
- `phase_advanced` — Phase transition
- `tool_blocked` — Tool call was blocked by phase policy
- `tool_executed` — Tool call was allowed and completed

---

## Known Limitations

1. **Bash tool bypass**: DES cannot restrict what happens inside bash commands. An agent could theoretically use `echo > file.ts` to bypass file write restrictions. This is by design (same as Claude Code DES).

2. **No subagent enforcement**: If OpenCode spawns a subagent, the subagent may not inherit the DES session. This needs validation.

3. **Stale session detection**: Sessions older than 4 hours trigger a warning; older than 24 hours trigger an error-level audit entry. Neither blocks execution.

---

## Reporting Feedback

Please report your findings as issues on this repo or via Discord. Include:

1. **OpenCode version** (`opencode --version`)
2. **What you tested** (which gate, which phase)
3. **Expected vs actual behavior**
4. **Audit log excerpt** (relevant lines from `.nwave/des/logs/des-audit.jsonl`)
5. **Session state** (contents of `.nwave/des/deliver-session.json` if relevant)

---

## File Structure

| File | Purpose |
|------|---------|
| `src/des/opencode-plugin.ts` | The TypeScript DES plugin (855 LOC) |
| `tests/des/unit/opencode-plugin.test.ts` | Bun unit + integration tests (46 tests) |
| `scripts/install/plugins/opencode_des_plugin.py` | Python installer plugin |
| `docs/adrs/ADR-004-opencode-des-native-typescript.md` | Architecture decision record |
| `docs/feature/opencode-des/design/` | Architecture and component design docs |

---

*Below is the standard nWave README for reference.*

---

# nWave

AI agents that guide you from idea to working code — with you in control at every step.

nWave runs inside [Claude Code](https://claude.com/product/claude-code). You describe what to build. Specialized agents handle requirements, architecture, test design, and implementation. You review and approve at each stage.

## Quick Start

### Plugin (Recommended)

From Claude Code, run:

```
/plugin marketplace add nwave-ai/nwave
/plugin install nw@nwave-marketplace
```

Restart Claude Code and type `/nw:` to see all available commands.

### CLI Installer (Alternative)

Install from PyPI — useful for contributing or environments without plugin support:

```bash
pipx install nwave-ai
nwave-ai install
```

Agents and commands go to `~/.claude/`.

> **Don't have pipx?** Install with: `pip install pipx && pipx ensurepath`, then restart your terminal.
> **Windows users**: Use WSL (Windows Subsystem for Linux). Install with: `wsl --install`

Full setup details: **[Installation Guide](https://github.com/nWave-ai/nWave/blob/main/docs/guides/installation-guide.md)**
