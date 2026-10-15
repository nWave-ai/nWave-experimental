# Installing nWave for Cursor

## Goal

After this guide, nWave is discoverable and verified for Cursor across all
Cursor projects (global install under `~/.cursor/`), and you can confirm the
DES PreToolUse-equivalent hook wiring with a short checklist.

## Prerequisites

- **Python 3.10 or later** — Check with `python3 --version`
- **uv** (recommended) **or pipx** (fallback) — Package installer. Install with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh    # uv (recommended)
  # or, as a fallback:
  python3 -m pip install pipx && pipx ensurepath     # pipx
  ```
- **Cursor** — Install from [cursor.com](https://cursor.com/). Verify with
  `which cursor` or `ls ~/.cursor/`.

## Install

### Step 1: Install nWave CLI

```bash
uv tool install nwave-ai     # recommended
# or, as a fallback:
pipx install nwave-ai
```

For this experimental preview channel (no PyPI), install from the clone instead:

```bash
uv run python -m nwave_ai.cli install
```

### Step 2: Install into Cursor (global)

```bash
nwave-ai install --platform cursor
```

The resulting hook installation is global for all Cursor projects via
`~/.cursor/hooks.json`. Shared runtime assets (DES module + audit log) remain
under `~/.claude/` so they are reusable across supported tools.

**Auto-detect note:** if Cursor is present and auto-detect includes it,
`nwave-ai install` alone may be enough. Prefer `--platform cursor` when you
want an explicit Cursor-only install.

### Step 3: Verify installation

```bash
nwave-ai doctor
```

Expected output: confirmation that DES hooks are installed and writable.

### Cursor global install checklist

After install, run the checklist once to confirm global scope:

```bash
test -f "$HOME/.cursor/hooks.json"
test -f "$HOME/.cursor/.nwave-des-manifest.json"
test -d "$HOME/.cursor/agents"
test -d "$HOME/.claude/lib/python/des"
test -f "$HOME/.claude/des-audit.jsonl"
nwave-ai doctor
```

Expected outcome:

- All `test -f` / `test -d` checks pass.
- `nwave-ai doctor` returns `9/9 checks passed, 0 failed`.
- `~/.cursor/hooks.json` contains a `preToolUse` hook entry in the top-level
  `hooks` map (Cursor's PreToolUse-equivalent event name).

One-shot copy/paste:

```bash
nwave-ai install --platform cursor --yes && test -f "$HOME/.cursor/hooks.json" && test -f "$HOME/.cursor/.nwave-des-manifest.json" && test -d "$HOME/.cursor/agents" && test -d "$HOME/.claude/lib/python/des" && test -f "$HOME/.claude/des-audit.jsonl" && python3 -c "import json,os; d=json.load(open(os.path.expanduser('~/.cursor/hooks.json'))); assert isinstance(d,dict) and 'preToolUse' in d.get('hooks', {})" && nwave-ai doctor
```

## What Got Installed

| Path | Purpose |
|------|---------|
| `~/.cursor/hooks.json` | Event-keyed Cursor hook configuration (global) |
| `~/.cursor/.nwave-des-manifest.json` | nWave DES install manifest for Cursor |
| `~/.cursor/agents/` | Cursor agent definitions (when installed) |
| `~/.agents/` | Shared skills registry (cross-tool) |
| `~/.claude/lib/python/des/` | nWave DES validation module |
| `~/.claude/des-audit.jsonl` | Audit log (created at install if missing; appended on hook fire) |

## End-to-End Smoke Test

### Step 1: Restart Cursor

Quit and reopen Cursor so global hooks under `~/.cursor/` are loaded.

### Step 2: Run a tool action

In Cursor Agent, invoke a simple shell or edit action (for example `ls` or a
small file edit).

### Step 3: Check the audit log

```bash
cat ~/.claude/des-audit.jsonl | jq 'select(.event == "HOOK_INVOKED" and .handler == "pre_tool_use")' | head -3
```

If you see at least one matching JSON object, DES enforcement is wired. If the
log is empty or missing, re-run the checklist above.

## Uninstall

```bash
nwave-ai uninstall
```

Or manually remove Cursor-specific nWave artifacts:

```bash
rm ~/.cursor/.nwave-des-manifest.json
# Edit ~/.cursor/hooks.json to remove nWave entries; do not delete the file
# if you keep other Cursor hooks.
```

To remove nWave entirely (CLI + tool wiring):

```bash
nwave-ai uninstall
uv tool uninstall nwave-ai    # or: pipx uninstall nwave-ai
```

## Common Issues

### Hook event name mismatch

**Symptom:** Checklist file checks pass, but the one-shot `preToolUse` assertion
fails.

**Cause:** Cursor uses `preToolUse` (camelCase) in `hooks.json`, not
`PreToolUse` (PascalCase used by Claude Code / Codex).

**Fix:** Confirm the key with:

```bash
python3 -c "import json,os; print(sorted(json.load(open(os.path.expanduser('~/.cursor/hooks.json'))).get('hooks', {})))"
```

### Hook didn't fire / audit log is empty

```bash
jq '.hooks | keys' ~/.cursor/hooks.json
# Expected to include: "preToolUse"

test -d "$HOME/.claude/lib/python/des"
touch ~/.claude/des-audit.jsonl
nwave-ai doctor
```

If all checks pass but the audit log stays empty after a Cursor Agent tool
action, file a bug report with the output of `nwave-ai doctor`.

## References

- **Cursor hooks documentation**: [cursor.com/docs/hooks](https://cursor.com/docs/hooks)
- **nWave architecture**: See the [Architecture Guide](../architecture/) for DES
  enforcement and hook contracts
- **Codex twin guide**: [Installing for Codex CLI](./installing-codex.md)
