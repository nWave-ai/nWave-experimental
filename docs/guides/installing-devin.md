# Installing nWave for Devin CLI

## Goal

After this guide, nWave skills are installed into Devin CLI's global discovery
root (`~/.config/devin/skills/`) and you can confirm the installation with a
short checklist.

**What Devin gets:** 181 nWave methodology skills available as native Devin
skills. The DES runtime tier (pre-tool validation) requires a `preToolUse`-
equivalent hook in Devin CLI; probe its availability before relying on it.

## Prerequisites

- **Python 3.10 or later** — Check with `python3 --version`
- **uv** (recommended) **or pipx** (fallback) — Install with:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh    # uv (recommended)
  # or, as a fallback:
  python3 -m pip install pipx && pipx ensurepath     # pipx
  ```
- **Devin CLI** — Install from [devin.ai](https://devin.ai/). Verify with
  `which devin` or `ls ~/.config/devin/`.

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

### Step 2: Install into Devin (global)

```bash
nwave-ai install --platform devin
```

The installer copies all public nWave skills into `~/.config/devin/skills/` and
writes a `.nwave-manifest.json` ownership file there so future upgrades and
uninstalls know exactly which directories belong to nWave.

**Auto-detect note:** if Devin CLI is present and auto-detect includes it,
`nwave-ai install` alone may be enough. Prefer `--platform devin` when you want
an explicit Devin-only install.

### Step 3: Verify installation

```bash
python scripts/install/verify_nwave.py --platform devin
```

Expected output: all plugin checks pass.

### Devin global install checklist

After install, confirm the key paths are in place:

```bash
test -d "$HOME/.config/devin/skills"
test -f "$HOME/.config/devin/skills/.nwave-manifest.json"
ls "$HOME/.config/devin/skills/" | grep "^nw-" | wc -l
```

Expected outcome:

- Both `test` commands pass.
- The `ls` count is 181 (or the current release count).

One-shot copy/paste:

```bash
nwave-ai install --platform devin --yes \
  && test -d "$HOME/.config/devin/skills" \
  && test -f "$HOME/.config/devin/skills/.nwave-manifest.json" \
  && echo "Devin skills installed: $(ls "$HOME/.config/devin/skills/" | grep -c '^nw-') skills"
```

## What Got Installed

| Path | Purpose |
|------|---------|
| `~/.config/devin/skills/nw-*/` | nWave methodology skill directories |
| `~/.config/devin/skills/.nwave-manifest.json` | nWave ownership manifest for Devin |
| `~/.claude/lib/python/des/` | DES runtime module (shared across tools) |
| `~/.claude/des-audit.jsonl` | Audit log (created at install if missing) |

**Note on DES enforcement:** Devin's DES `preToolUse` hook availability has not
yet been probed against a running Devin CLI host. Until that spike is complete,
DES pre-tool validation may not fire. The skills themselves (methodology
guidance, workflow orchestration) work independently of the hook.

## Upgrading

Re-run `nwave-ai install --platform devin` to pick up the latest skills. The
installer replaces only manifest-owned skill directories; your own
non-`nw-`-prefixed Devin skills are never touched.

## Uninstall

```bash
nwave-ai uninstall
```

Or remove Devin-specific nWave artifacts manually:

```bash
# Read the manifest first to see what will be removed:
cat ~/.config/devin/skills/.nwave-manifest.json | jq '.installed_skills[]'

# Remove each listed skill directory, then the manifest:
rm -rf ~/.config/devin/skills/nw-*    # only nWave-prefixed skills
rm ~/.config/devin/skills/.nwave-manifest.json
```

To remove nWave entirely (CLI + tool wiring):

```bash
nwave-ai uninstall
uv tool uninstall nwave-ai    # or: pipx uninstall nwave-ai
```

## Common Issues

### Skills not discovered

**Symptom:** Devin does not list nWave skills in its registry.

**Steps:**

```bash
# Confirm the directory exists and contains skill dirs:
ls ~/.config/devin/skills/ | grep "^nw-" | head -5

# Confirm each skill has a SKILL.md:
ls ~/.config/devin/skills/nw-design/
```

If the files are present but Devin does not surface them, restart Devin CLI so
it rescans its global skills root.

### Wrong skill count after upgrade

Re-run the installer — a stale manifest may be tracking skills that were renamed
or removed in the new release:

```bash
nwave-ai install --platform devin --yes
python scripts/install/verify_nwave.py --platform devin
```

### Path rewrite issues in skill bodies

Skill bodies contain `~/.claude/lib/python/des` paths. These are pointer strings
used by the DES runtime resolver and are intentionally kept as-is. References to
`~/.claude/skills/` however are rewritten to `~/.config/devin/skills/` by the
installer. If you see a path mismatch, re-run the installer.

## References

- **nWave architecture**: See the [Architecture Guide](../architecture/) for DES
  enforcement and hook contracts
- **Cursor twin guide**: [Installing for Cursor](./installing-cursor.md)
- **Codex twin guide**: [Installing for Codex CLI](./installing-codex.md)
- **OMP twin guide**: [Installing for OMP](./installing-omp.md)
