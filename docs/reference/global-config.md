# nWave Global Config Reference

**Location**: `~/.nwave/config.json`

This reference documents the configuration keys nWave actually reads from its
two canonical configuration files: the global file above and the per-project
file at `<repo>/.nwave/config.json`. Global values apply to every project
unless a project sets its own override.

## File locations and initialization

- **Global path**: `~/.nwave/config.json` (under `NWAVE_AGENTS_HOME` instead
  of your home directory, when that environment variable is set to an
  absolute path).
- **Project path**: `<repo>/.nwave/config.json`.
- **Created by**: `nwave-ai install` (first run), or any `nwave-ai` command
  that writes configuration (`mode`, `model set`, `attribution`,
  `project enable|disable|set`).
- **User-editable**: Yes, with a text editor.
- **Verification**: Run `nwave-ai doctor` to validate your config.

### Historical files (retired, migrated automatically)

Older installs used three separate files: `~/.nwave/global-config.json`,
`<repo>/.nwave/des-config.json`, and `<repo>/.nwave/local-config.json` (the
per-project activation marker, `{"enabled_for_repo": true|false}`). The
config writer merges any of these it finds into the two canonical files
above the next time it writes configuration, backs up the original bytes
next to each retired file as `<name>.unified-config.bak`, and deletes the
retired file. You do not need to migrate these by hand, and new tooling
never reads `global-config.json`, `des-config.json`, or `local-config.json`
directly.

## Top-level structure (global file)

```json
{
  "activation": { "mode": "..." },
  "rigor": { "profile": "..." },
  "documentation": { "density": "...", "expansion_prompt": "..." },
  "attribution": { "enabled": true, "trailer": "..." },
  "model_runtime": { "default": { "provider": "...", "model": "..." }, "roles": {} }
}
```

Per-project overrides live in `<repo>/.nwave/config.json` instead, with a
smaller, closed set of public keys: `enabled` (activation marker),
`verbosity`, `attribution`, and `model_runtime` (set via `nwave-ai model set --project ...`, not via `project set`).
`audit_logging_enabled` and `audit_log_dir` are also project-tier keys (see
below), not global ones.

---

## Configuration keys

### `activation` (object, optional)

Controls the default activation mode for unmarked projects (repos without an
explicit per-project marker).

#### `activation.mode` (string, optional)

Valid values: `opt-in` (default) | `all`.

- **`opt-in`** (default): Unmarked projects are **inactive**. Hooks silently
  exit 0. Only projects whose `<repo>/.nwave/config.json` has `enabled: true`
  are active.
- **`all`**: Unmarked projects are **active** by default. Hooks fire in every
  repo unless that project's `<repo>/.nwave/config.json` has `enabled: false`.

**Default**: `opt-in`.

**How to set this**:

```bash
nwave-ai mode opt-in    # unmarked repos inactive (default)
nwave-ai mode all       # unmarked repos active
```

**Per-project override**: `nwave-ai project enable` / `nwave-ai project
disable` write the `enabled` field into the current repo's
`.nwave/config.json`; that value always wins over the global mode for that
repo.

**Example**:
```json
{
  "activation": {
    "mode": "opt-in"
  }
}
```

**For the complete mental model**, see [Activating nWave in a Project](../guides/activating-nwave-per-project.md).

---

### `rigor` (object)

#### `rigor.profile` (string)

Valid values: `lean`, `standard`, `thorough`, `exhaustive`, `custom`. When
set, it is the fallback source the documentation-density resolver uses for
`documentation.density` and `documentation.expansion_prompt` **whenever those
keys are absent** (see the cascade table below).

**There is no `nwave-ai` command that sets `rigor.profile`.** It must be
edited by hand in `~/.nwave/config.json` (or a project's
`.nwave/config.json`). The `nw-rigor` skill/command configures a different
key — `model_runtime.default` or `model_runtime.roles.<role>`, an explicit
provider/model pair — via `nwave-ai model set`. It does not read, write, or
choose `rigor.profile`, and it never derives a model from a rigor level.

**Example**:
```json
{
  "rigor": {
    "profile": "lean"
  }
}
```

---

### `documentation` (object)

#### `documentation.density` (string, optional)

Valid values: `lean`, `full`. Resolved by
`scripts/shared/density_config.py:resolve_density()` and surfaced by
`nwave-ai doctor` as a `documentation_density` check line. As of this
writing the resolved value is exposed for diagnostics; no shipped wave
producer branches its output section set on it, so treat it as declared
intent to verify with `doctor`, not as a lever that currently reshapes wave
output on its own.

**Cascade** (first match wins):
1. Explicit `documentation.density` in config.
2. `rigor.profile` mapping (see table below), if `rigor.profile` is set.
3. Hard default: `lean`.

**Example**:
```json
{
  "documentation": {
    "density": "lean"
  }
}
```

#### `documentation.expansion_prompt` (string, optional)

Valid values: `ask`, `always-skip`, `always-expand`, `smart`,
`ask-intelligent`. Same resolver and same caveat as `documentation.density`
above: it is validated and resolved by `resolve_density()` and reported by
`nwave-ai doctor`, but there is no shipped `--expand` CLI flag and no
implemented wave-end expansion menu to consume it yet. If you want more
detail on a specific feature today, ask the assisting LLM directly during
the wave; it produces additional detail through the existing DES document
producer rather than through a persisted, freeform handoff document.

`nwave-ai install` checks existing documentation preferences before writing any
installation files, including when `--density-only` is used. An invalid
`documentation.expansion_prompt` stops the install with an error that lists
valid values. Correct the value in `~/.nwave/config.json` and run install again;
the refused install leaves that file unchanged.


**Cascade** (independent of the density cascade above): explicit value wins;
else the `rigor.profile` mapping; else hard default `ask-intelligent`.

**Example**:
```json
{
  "documentation": {
    "expansion_prompt": "ask"
  }
}
```

---

### `attribution` (object, optional)

Controls whether commits get an attribution trailer. Managed by
`nwave-ai attribution <on|off|status>`; see that command's own `--help` for
the exact shape written (`{"enabled": bool, "trailer": "..."}`).

---

### `audit_logging_enabled` / `audit_log_dir` (project-tier keys)

These are written to a **project's** `.nwave/config.json` (defaults
`audit_logging_enabled: true`, `audit_log_dir: ".nwave/des/logs"` on first
write), not to the global file. `audit_log_dir` is resolved with this
priority: explicit caller argument > `DES_AUDIT_LOG_DIR` environment
variable > `audit_log_dir` in the project's `.nwave/config.json` >
`<project>/.nwave/des/logs` > `~/.claude/des/logs`.

---

## Rigor profile cascade table

Density/prompt inherited when `rigor.profile` is set and
`documentation.density` / `documentation.expansion_prompt` are absent:

| Profile | Inherited density | Inherited expansion_prompt |
|---------|---|---|
| `lean` | `lean` | `always-skip` |
| `standard` | `lean` | `ask-intelligent` |
| `thorough` | `full` | `always-expand` |
| `exhaustive` | `full` | `always-expand` |
| `custom` | `lean` | `ask-intelligent` |

If neither `documentation.density`/`expansion_prompt` nor `rigor.profile` is
set, the hard default is `lean` + `ask-intelligent`.

---

## `backups.max_count` (install-time key)

```json
{
  "backups": {
    "max_count": 3
  }
}
```

Read by the installer's backup pruning (`scripts/install/install_utils.py`)
from `~/.nwave/config.json`. Caps how many `nwave-*` backup directories the
installer retains; `0` disables retention. Unset uses the installer's
built-in default cap of `10`.

---

## Verifying your config

```bash
nwave-ai doctor
```

`doctor` reports the resolved documentation density and its provenance, one
of:

- `Documentation density: lean (explicit override)`
- `Documentation density: lean (inherited from rigor.profile=standard)`
- `Documentation density: lean (default (no config))`

An unknown `rigor.profile` value, or a non-object `documentation`/`rigor`
section, fails this check with a remediation message rather than falling
back silently.

---

## Troubleshooting

**Q: My config file doesn't exist. What's the default?**

Run `nwave-ai install` to initialize it. The first-run prompt asks for a
density preference and writes the file.

**Q: Can I edit the config manually?**

Yes. After editing, run `nwave-ai doctor` to validate; a malformed-JSON or
out-of-range value is reported with an error code and remediation text.

**Q: Can I override density per project or per feature?**

Per-project overrides are limited to the closed set `nwave-ai project set`
accepts (`enabled`, `verbosity`, `attribution`); there is no per-project or
per-feature `documentation.density` override today.
