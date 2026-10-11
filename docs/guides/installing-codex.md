# Installing nWave for Codex CLI

Use this guide to install the nWave CLI into Codex. You need Python 3.10 or
later, Codex CLI, and a published `nwave-ai` package or a checked-out source
tree. Restart Codex after installation so it loads the new assets.

## Install from a published package

```bash
uv tool install nwave-ai     # recommended
# or, as a fallback:
pipx install nwave-ai
```

### Step 2: Install into Codex

The installer automatically detects Codex and wires the DES PreToolUse hook
globally in `~/.codex/`. Run:

```bash
nwave-ai install
```

**Explicit Codex installation** (if auto-detect doesn't find Codex):

```bash
nwave-ai install --platform codex
```

`pipx install nwave-ai` is a supported alternative to `uv tool install`.
Read the installer's final validation before opening Codex. A package name or
workflow definition does not identify a particular release; pin a version or
use an exact release receipt when your project requires one.

## Install from this source tree

From the nWave checkout:

```bash
uv sync
uv run python -m nwave_ai.cli install --platform codex
```

This installs from the checked-out revision. Keep the checkout if you plan to
run its CLI again.

### Codex global install checklist

After install, run the checklist once to confirm global scope:

```bash
test -f "$HOME/.codex/hooks.json"
test -f "$HOME/.codex/.nwave-des-manifest.json"
test -d "$HOME/.codex/agents"
test -d "$HOME/.claude/lib/python/des"
test -f "$HOME/.claude/des-audit.jsonl"
nwave-ai doctor
```

Expected outcome:

- All `test -f` / `test -d` checks pass.
- `nwave-ai doctor` returns `9/9 checks passed, 0 failed`.
- `~/.codex/hooks.json` contains a `PreToolUse` hook entry.

One-shot copy/paste:

```bash
nwave-ai install --platform codex --yes && test -f "$HOME/.codex/hooks.json" && test -f "$HOME/.codex/.nwave-des-manifest.json" && test -d "$HOME/.codex/agents" && test -d "$HOME/.claude/lib/python/des" && test -f "$HOME/.claude/des-audit.jsonl" && python3 -c "import json,os; d=json.load(open(os.path.expanduser('~/.codex/hooks.json'))); assert isinstance(d,dict) and 'PreToolUse' in d.get('hooks', {})" && nwave-ai doctor
```

## Enable a project

In the project where you want nWave active:

```bash
nwave-ai project enable
nwave-ai status
```

`status` reports the effective activation, running CLI version, and whether
Codex installation manifests were found. It does not validate every Codex
action. If you installed from source, call the checkout's absolute
`.venv/bin/nwave-ai` path from the project directory instead.

The project command writes `.nwave/config.json` and updates `.gitignore`.
It can also add a managed section to `AGENTS.md` with your consent; `--yes`
accepts that optional guidance step. Commit the project config if teammates
should inherit the activation setting.

## Verify and recover

After restarting Codex, run `$nw-buddy` in the enabled project. If Codex does
not show the installed nWave skills, check the installer's reported Codex
validation and run `nwave-ai status` in that project. Reinstall with the
explicit `--platform codex` flag after correcting the reported cause.

`nwave-ai doctor` checks the Claude Code installation. A Codex-only install
may therefore report missing Claude Code assets; use the Codex installer
validation for that host. `status` is a read-only view, not a hook execution
test.

To remove nWave's installed assets, run `nwave-ai uninstall`. Remove the CLI
package separately with the same application installer you used to add it.
