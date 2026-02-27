# Component Boundaries: nWave Plugin Marketplace

**Date**: 2026-02-27

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                     nWave Source Repository                         │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ nWave/       │  │ src/des/     │  │ scripts/                 │  │
│  │  agents/     │  │  domain/     │  │  build_dist.py           │  │
│  │  tasks/nw/   │  │  application/│  │  build_plugin.py (NEW)   │  │
│  │  skills/     │  │  ports/      │  │  install/                │  │
│  │  templates/  │  │  adapters/   │  │    plugins/              │  │
│  │  hooks/      │  │              │  │    install_nwave.py      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘  │
│         │                 │                      │                   │
│         └────────┬────────┘                      │                   │
│                  │                               │                   │
│            ┌─────▼──────────────────────────┐    │                   │
│            │     build_plugin.py            │◄───┘                   │
│            │     (Plugin Build Pipeline)    │                        │
│            │                                │                        │
│            │  Reads: pyproject.toml version  │                        │
│            │  Copies: agents, skills, cmds   │                        │
│            │  Rewrites: DES imports          │                        │
│            │  Generates: plugin.json,        │                        │
│            │             hooks.json          │                        │
│            │  Validates: output structure    │                        │
│            └─────────────┬──────────────────┘                        │
│                          │                                           │
│                    ┌─────▼──────────────────┐                        │
│                    │  plugin/               │  (build output)        │
│                    │   .claude-plugin/      │                        │
│                    │     plugin.json        │                        │
│                    │   agents/              │                        │
│                    │   skills/              │                        │
│                    │   commands/            │                        │
│                    │   hooks/               │                        │
│                    │     hooks.json         │                        │
│                    │   scripts/             │                        │
│                    │     des/               │                        │
│                    │     des-hook           │                        │
│                    │   settings.json        │                        │
│                    └────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

## Boundary Definitions

### 1. Plugin Build Pipeline (NEW)

**Location**: `scripts/build_plugin.py`
**Responsibility**: Transform nWave source tree into Claude Code plugin layout
**Inputs**: nWave source directories, pyproject.toml, DES source
**Outputs**: `plugin/` directory ready for distribution
**Owns**:
- Source-to-plugin directory mapping rules
- hooks.json generation (plugin-specific hook format)
- plugin.json generation (metadata from pyproject.toml)
- DES import rewriting for plugin context
- Output validation

**Does NOT own**:
- Agent content (owned by agent definitions in nWave/agents/)
- Skill content (owned by skill files in nWave/skills/)
- Command content (owned by command files in nWave/tasks/nw/)
- DES business logic (owned by src/des/)
- Version (owned by pyproject.toml)

### 2. Plugin Package (Static Artifact)

**Location**: `plugin/` (build output)
**Responsibility**: Deliver nWave capabilities to Claude Code via plugin system
**Installed to**: `~/.claude/plugins/cache/nwave/` by Claude Code
**Owns**:
- Plugin-specific hook entry point (`scripts/des-hook`)
- Plugin metadata (`.claude-plugin/plugin.json`)
- Settings defaults (`settings.json`)

### 3. Existing Custom Installer (Unchanged)

**Location**: `scripts/install/install_nwave.py`
**Responsibility**: Install nWave to `~/.claude/` for users who prefer CLI installation
**Unchanged**: No modifications needed. Continues to work as before.

### 4. CI/CD Extension (Existing + Extension)

**Location**: `.github/workflows/release.yml`
**Extension**: Add plugin build step after existing build, before GitHub Release
**Owns**:
- Plugin build trigger (on release tag)
- Plugin directory packaging
- Marketplace submission automation (future)

## Boundary Interaction Rules

1. **Build pipeline reads, never writes, source**: `build_plugin.py` only reads from `nWave/` and `src/des/`. It writes exclusively to `plugin/`.
2. **Plugin and custom installer are independent**: They install to different directories and can coexist.
3. **Version flows one direction**: `pyproject.toml` -> `build_plugin.py` -> `plugin.json`. Never the reverse.
4. **DES code is copied, not referenced**: The plugin contains a complete copy of the DES module. No runtime dependency on `$HOME/.claude/lib/python`.

## Mapping Table: Source to Plugin

| Source Path | Plugin Path | Transformation |
|------------|-------------|----------------|
| `nWave/agents/nw-*.md` | `agents/nw-*.md` | Direct copy |
| `nWave/tasks/nw/*.md` | `commands/nw/*.md` | Direct copy (tasks/ renamed to commands/) |
| `nWave/skills/{agent}/*.md` | `skills/{agent}/*.md` | Direct copy |
| `src/des/**/*.py` | `scripts/des/**/*.py` | Copy + rewrite `from src.des` to `from des` |
| `nWave/scripts/des/*.py` | `scripts/des-scripts/*.py` | Copy (DES utility scripts) |
| `pyproject.toml:project.version` | `.claude-plugin/plugin.json:version` | Extract and inject |
| (generated) | `hooks/hooks.json` | Generate from DES hook config |
| (generated) | `scripts/des-hook` | Generate shell wrapper script |
| `nWave/templates/*.json` | `scripts/templates/*.json` | Copy (DES templates needed at runtime) |

## What Is NOT in the Plugin

| Excluded | Reason |
|----------|--------|
| `scripts/install/` | Custom installer -- separate distribution channel |
| `nwave_ai/` | PyPI CLI -- separate distribution channel |
| `tests/` | Not needed at runtime |
| `docs/` | Not needed at runtime |
| `.github/` | CI/CD config -- not runtime |
| `nWave/data/` | Reference materials loaded via skills, not direct file access |
| `nWave/framework-catalog.yaml` | Internal registry, not used by Claude Code plugin system |
| `nWave/templates/` (wave templates) | Loaded via commands, already in command definitions |
