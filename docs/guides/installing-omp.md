# Installing nWave for OMP (oh-my-pi)

## Goal

After this guide, nWave is discoverable and verified for OMP across all
OMP sessions (global install under `~/.omp/`), and you can confirm the
DES PreToolUse hook wiring with a short checklist.

## Prerequisites

- **Python 3.10 or later** — Check with `python3 --version`
- **uv** (recommended) **or pipx** (fallback) — Package installer. Install with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh    # uv (recommended)
  # or, as a fallback:
  python3 -m pip install pipx && pipx ensurepath     # pipx
  ```
- **OMP** — Install oh-my-pi via its official installer. Verify with
  `which omp` or `ls ~/.omp/agent/`.

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

### Step 2: Install into OMP (global)

```bash
nwave-ai install --platform omp
```

The installer writes to `~/.omp/agent/` (agents, skills, and DES extension).
Shared runtime assets (DES module + audit log) remain under `~/.claude/` so
they are reusable across supported tools.

**Auto-detect note:** if OMP is present and auto-detect includes it,
`nwave-ai install` alone may be enough. Prefer `--platform omp` when you
want an explicit OMP-only install.

**PI_CONFIG_DIR override:** if OMP uses a custom config root (set via
`PI_CONFIG_DIR`), the installer resolves paths through the same env var.
Export it before running the installer:

```bash
PI_CONFIG_DIR=my-omp-profile nwave-ai install --platform omp
```

### Step 3: Verify installation

```bash
nwave-ai doctor
```

Expected output: confirmation that DES hooks are installed and writable.

### OMP global install checklist

After install, run the checklist once to confirm global scope:

```bash
test -f "$HOME/.omp/agent/.nwave-des-manifest.json"
test -d "$HOME/.omp/agent/agents"
test -d "$HOME/.omp/agent/skills"
test -d "$HOME/.claude/lib/python/des"
test -f "$HOME/.claude/des-audit.jsonl"
nwave-ai doctor
```

Expected outcome:

- All `test -f` / `test -d` checks pass.
- `nwave-ai doctor` returns `9/9 checks passed, 0 failed`.
- `~/.omp/agent/.nwave-des-manifest.json` exists and contains the DES
  extension SHA256 manifest.

One-shot copy/paste:

```bash
nwave-ai install --platform omp --yes && test -f "$HOME/.omp/agent/.nwave-des-manifest.json" && test -d "$HOME/.omp/agent/agents" && test -d "$HOME/.omp/agent/skills" && test -d "$HOME/.claude/lib/python/des" && test -f "$HOME/.claude/des-audit.jsonl" && nwave-ai doctor
```

## What Got Installed

| Path | Purpose |
|------|---------|
| `~/.omp/agent/.nwave-des-manifest.json` | nWave DES install manifest for OMP |
| `~/.omp/agent/agents/` | OMP agent definitions |
| `~/.omp/agent/skills/` | nWave skills (global for all OMP sessions) |
| `~/.claude/lib/python/des/` | nWave DES validation module |
| `~/.claude/des-audit.jsonl` | Audit log (created at install if missing; appended on hook fire) |

## End-to-End Smoke Test

### Step 1: Start a new OMP session

Begin a fresh OMP session so the newly installed agents and skills are loaded.

### Step 2: Run a tool action

In OMP, invoke a simple tool action (for example a shell command or small file edit).

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

Or manually remove OMP-specific nWave artifacts:

```bash
rm ~/.omp/agent/.nwave-des-manifest.json
rm -rf ~/.omp/agent/agents/nw-*
rm -rf ~/.omp/agent/skills/nw-*
```

To remove nWave entirely (CLI + tool wiring):

```bash
nwave-ai uninstall
uv tool uninstall nwave-ai    # or: pipx uninstall nwave-ai
```

## Common Issues

### DES extension not detected

**Symptom:** `nwave-ai doctor` reports the DES extension missing for OMP.

**Cause:** The DES TypeScript extension (`nwave_des.ts`) must be discoverable
under `~/.omp/agent/`. If `PI_CONFIG_DIR` is set, the installer wrote to a
different root than OMP reads.

**Fix:** Confirm the installed path matches OMP's active config root:

```bash
echo "OMP config root: ${HOME}/${PI_CONFIG_DIR:-.omp}/agent"
ls "${HOME}/${PI_CONFIG_DIR:-.omp}/agent/.nwave-des-manifest.json"
```

If they differ, re-run the install with the correct `PI_CONFIG_DIR` value.

### Skills not visible in OMP

**Symptom:** Installed skills do not appear in OMP skill listings.

**Fix:** Confirm the skills directory:

```bash
ls "$HOME/${PI_CONFIG_DIR:-.omp}/agent/skills/" | grep nw-
```

If skills are missing, re-run:

```bash
nwave-ai install --platform omp --yes
```

## References

- **nWave architecture**: See the [Architecture Guide](../architecture/) for DES
  enforcement and hook contracts
- **Cursor twin guide**: [Installing for Cursor](./installing-cursor.md)
- **Codex guide**: [Installing for Codex CLI](./installing-codex.md)
