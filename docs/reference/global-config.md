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
- **Created by**: A fresh install may leave both files absent. Configuration
  writes create the relevant tier: `mode`, `model set`, or `attribution` for
  machine settings; `project enable|disable|set` for project settings.
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

`documentation` is optional. Fresh installs do not write it. The retained
`density` value does not reshape wave documents; `expansion_prompt` controls
optional explanation after a completed wave and does not open a CLI menu.

`update_check` is retired. It does not control update checks and is removed
on the next explicit global or project config write; read-only commands do
not rewrite the file.

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

**There is no `nwave-ai` command that sets `rigor.profile`.** The global
fallback affects the wave-end explanation mode when an explicit
`documentation.expansion_prompt` is absent; a project copy is not an override.
The `nw-rigor` skill/command configures `model_runtime.default` or
`model_runtime.roles.<role>` via `nwave-ai model set` instead. It never derives
a model from a rigor level.

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

Valid values: `lean`, `full`. The resolver reports this preference through
`nwave-ai doctor`; it is diagnostic-only. No shipped wave producer changes its
output sections based on this value. Fresh installs do not set it.

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
`ask-intelligent`. For the seven installed waves, `des wave-entry` reads the
global preference once before work starts. The assistant applies it only
after that wave completes; it never opens an interactive CLI menu and makes
no offer after a lone DES step or an unsuccessful wave. `nwave-ai status`
shows the resolved value; `doctor` reports density, not this value.

| Value | Assistant response after a completed wave |
|---|---|
| `ask` | Offers optional detail. |
| `always-skip` | Does not offer detail. |
| `always-expand` | Explains pertinent detail directly, without asking. |
| `smart` | Offers detail only if the result contains a concrete optional alternative, trade-off, risk, constraint, or deferred consequence. |
| `ask-intelligent` | Uses the same condition as `smart` and names at most two specific relevant topics from the completed result. |

The offer is a chat response, not a document edit. Accepting or ignoring it
does not change accepted documents or execute another DES step. You may ask
for more detail directly at any time, even with `always-skip`.

`nwave-ai install` checks an explicit active `documentation.expansion_prompt`
before writing installation files. An invalid value stops the install with
accepted values in the error; correct the global value and retry. Installation
does not ask for or write a density preference.


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

Sets the machine attribution preference; project configuration can override
it, and credit is added only for active repositories with a supported commit
hook. Managed by `nwave-ai attribution <on|off|status>`; `status` reports the
effective preference and its source. See that command's own `--help` for the
shape written (`{"enabled": bool, "trailer": "..."}`).

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

`doctor` reports the resolved legacy documentation density and its provenance,
for example `Documentation density: lean (explicit override); diagnostic-only
(does not change wave output)`. `nwave-ai status` reports the active wave-end
explanation preference and source. An invalid `documentation.expansion_prompt`
refuses installation and `des wave-entry`; `doctor` is not a substitute for
either validation. An invalid old density does not select output, but current
`des wave-entry` refuses it: remove that obsolete key.

---

## Troubleshooting

**Q: My config file doesn't exist. What's the default?**

No file is needed to read defaults. New repositories are inactive under
`opt-in`; attribution defaults to off and verbosity to standard when no tier
declares a value. The density resolver defaults to `lean` (diagnostic-only);
wave-end explanations default to `ask-intelligent` after completed waves.
Installation does not ask for density or create a file just to store it.
A command that writes configuration creates its relevant file.

**Q: Can I edit the config manually?**

Yes. Run `nwave-ai status` afterward to see effective values and their
sources. `nwave-ai doctor` checks installation health, but wave-entry can
refuse an invalid documentation choice even if a legacy density diagnostic
did not fail.

**Q: Can I override density per project or per feature?**

Per-project overrides are limited to the closed set `nwave-ai project set`
accepts (`enabled`, `verbosity`, `attribution`); there is no per-project or
per-feature `documentation.density` override today.
