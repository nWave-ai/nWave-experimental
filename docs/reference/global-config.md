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
config writer merges the legacy files for the tier being written into its
canonical file, backs up the original bytes next to each retired file as
`<name>.unified-config.bak`, and deletes that retired file. A project-only
write does not migrate the global tier. Changing `mode` migrates the global
tier and changes only activation; documentation, attribution, model selection,
and other explicit preferences remain intact. Conflicting or malformed input
must be repaired before retrying. Read-only commands do not migrate files and
never use the retired paths as runtime fallbacks.

## Top-level structure (global file)

```json
{
  "activation": { "mode": "..." },
  "rigor": { "profile": "..." },
  "documentation": { "density": "...", "expansion_prompt": "..." },
  "attribution": { "enabled": true, "trailer": "..." },
  "updates": { "check": false, "install": false, "controlled_launch": false },
  "model_runtime": { "default": { "provider": "...", "model": "..." }, "roles": {} }
}
```

`documentation` is optional. Fresh installs do not write it. `density` selects
whether a completed wave gets a local HTML view of its DES Markdown document
(`full`) or keeps the authoritative document and handoff (`lean`); it does not
reshape the document's sections. `expansion_prompt` controls optional
explanation in chat after a completed wave and does not open a CLI menu. They
are separate controls.

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

### `updates` (object, optional, global only)

`check` and `install` are independent boolean permissions, both off when
absent. Only explicit `true` grants a permission. The retired `update_check`
field grants neither permission.

```bash
nwave-ai update consent check on
nwave-ai update consent install on --confirm-old-sessions-closed
nwave-ai update consent controlled-launch on --confirm-controlled-launch
```

A check-only grant cannot install anything. Automatic installation requires
both permissions and the separate controlled-launch commitment. Revoke any
grant with its command and `off` (without a confirmation flag). Revoking
`check` prevents both automatic actions; revoking `install` or
`controlled-launch` leaves check-only behavior when checking is enabled.

Before granting install permission, close all older host sessions that started
before the activity registry was installed. The confirmation flag records your
statement; nWave cannot independently detect those older sessions. A false
confirmation can leave active work unprotected.

The controlled-launch confirmation means that future host sessions sharing
this package use `nwave-ai run HOST -- ARGS`. On POSIX, `HOST` can be
`claude-code`, `codex`, `opencode`, or `copilot`. For example:

```bash
nwave-ai run codex -- --no-daemon
nwave-ai run claude-code --
```

The wrapper records its session before starting the host. Both automatic
release checks and installation require controlled prelaunch and idle evidence
before the first release request. Ordinary native starts give guidance only:
native hooks cannot provide a reliable admission boundary. An explicit
`nwave-ai update --check` remains available outside controlled startup.

The selected registry lives under `<agents_home>/.nwave/activity/`. A shared
package lock and registry also live beside the owned virtual environment,
outside the directory that replacement removes. They coordinate sessions using
different configuration homes but the same package. Other sessions, unknown or
malformed records, or unfinished local work prevent both automatic actions.
Check-only startup needs check permission; installation also needs install
permission, the legacy-session confirmation, and the controlled-launch
commitment. The exclusive coordination covers discovery through completion.

Direct starts, disabled hooks, and detached work are outside the controlled
lifetime guarantee. Close that work before enabling automatic installation.
A surviving child process leaves its session record for explicit recovery;
the wrapper does not guess that work has ended.

Use `nwave-ai update sessions` to inspect the registry. Close a session in its
host first. If a record remains after that session has ended, remove it only
with `nwave-ai update sessions close KEY --confirm-closed`. Records are not
cleared from guessed process state or age.

An unsupported release channel, development installation, or missing install
provenance can refuse an update; permission is not a compatibility guarantee.
Read the reported stage and recovery action before retrying. No broad rollback
is implied.

Interrupted replacement leaves durable stage evidence in both the selected and
package registries. Even if the package version is now current, checks and
ordinary updates report `update-incomplete`, not success. After stopping all
remaining updater processes and affected sessions, use the reported environment
and project root:

```bash
nwave-ai update --recover --yes --confirm-stopped
```

Recovery proves the pinned package version, repeats the selected-host preflight
and synchronization, then applies the registered artifact migration. It clears
the evidence only after all stages succeed. If the pinned package is missing or
wrong, follow the reported package-owner restoration command first. Do not
delete the marker to bypass recovery.

`nwave-ai update --check` remains an explicit read-only check.
`nwave-ai update --yes --root PATH` remains an explicit installation request;
it is not a command to grant persistent automatic-update consent. It takes the
replacement lock but does not establish global idle: close active work before
requesting a manual installation.

---

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

These are separate controls:

- `documentation.expansion_prompt` controls optional explanation in chat.
- `documentation.density` controls whether a completed wave gets a local HTML
  view (`full`) or keeps the authoritative document and handoff (`lean`).
- `model_runtime` selects an explicit provider/model pair. Density and
  `rigor.profile` never select a provider or model.
- Required verification remains part of the selected delivery route. None of
  these preferences disables its tests, reviews, or examination obligations.

The names `lean` and `exhaustive` are labels, not measured guarantees of quality
or coverage. Selecting a profile, a density or a model does not establish that
verification passed.

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

Valid values: `lean`, `full`. Fresh installs do not set it. It selects the
completed-wave reading surface, not the sections of a wave document:

- **`full`**: after a completed wave, `des wave-entry --complete` renders a
  **local HTML** view of each distinct DES Markdown `DOCUMENT:` locator from the
  successful constructors. The Markdown stays the authority; the HTML is a
  generated projection next to it.
- **`lean`**: no view is rendered. The authoritative DES documents and handoff
  remain.

**How the value reaches a wave.** `des wave-entry --repo-root ROOT --wave WAVE`
reads the global config once at wave entry, read-only, and prints
`WAVE-DOCUMENTATION-DENSITY: lean|full` with its
`WAVE-DOCUMENTATION-PROVENANCE`. The assistant keeps that captured terminal.
The row records the preference; it does not show that the wave completed.

**Completion is asserted by the host, not detected.** DES has no whole-wave
completion ledger. The CLI does not detect completion and nothing in DES checks
that the host calls the completion mode. The wave skill instructs the assistant
to call it at the end of a wave that really completed; treat that as an
instruction, not a proven behavior. The call itself is the host's assertion:

```text
des wave-entry --repo-root ROOT --wave WAVE --complete \
  --entry-result ENTRY.txt --constructor-result CONSTRUCTOR.txt
```

`--entry-result PATH` is the captured entry terminal. `--constructor-result
PATH` is a captured successful DES constructor terminal; repeat it once per
constructor. What the mode does, from `src/des/cli/wave_entry.py`:

- It does not reread the config. It takes the density from the captured entry
  terminal, which must record `DELIVERY-OUTCOME: Success`, the same `WAVE`, and
  density `full` or `lean`.
- For `discuss`, `design`, `devops` and `distill`, at least one constructor
  capture with a `DOCUMENT:` row is required. A missing capture or row is
  `Indeterminate` (unknown evidence), not a documentless success. A constructor
  terminal whose `DELIVERY-OUTCOME` is not `Success` is refused.
- With `lean`, it prints `LOCAL-VIEW: not requested; authoritative DES
  documents and handoffs remain` and writes nothing.
- With `full`, it checks every source and destination before rendering any
  view. The source must be an existing regular repository-relative `.md` file
  (a `#Heading` suffix is dropped only to pick the file; no URL, absolute path,
  `.`/`..` component or symlink). The view is the adjacent `.html`. It refuses a
  symlink destination and an existing HTML file that is not an nWave projection
  of the same Markdown. It then renders with the packaged renderer and prints
  `HTML:` rows and any `RENDER-DIAGNOSTIC:` rows. If a wave has no DES Markdown
  authority it prints `LOCAL-VIEW: no applicable DES Markdown authority`.
- Its terminal states `COMPLETION-EVIDENCE: host asserted whole-wave completion;
  captured DES terminals alone do not prove it`.
- A renderer failure is `Indeterminate` and an output may be partial; the
  renderer's direct write is not atomic against a concurrent path change.

**Cascade** (first match wins):
1. Explicit `documentation.density` in config.
2. `rigor.profile` mapping (see table below), if `rigor.profile` is set.
3. Hard default: `lean`.

A value outside `lean`/`full` is refused by `des wave-entry` (it names the field,
the value and the accepted values; the wave does not begin). `nwave-ai status`
shows the same condition as `Documentation density: invalid (...)`.

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

`nwave-ai status` is read-only and reports two separate lines: the resolved
documentation density with its provenance and what it means after an applicable
completed wave (`local HTML from the completed wave's DES document` for `full`,
`authoritative documents and handoffs` for `lean`), and the wave-end
explanation preference with its source. Density is resolved without
`expansion_prompt`, so an invalid explanation value does not hide the density
line.

`doctor` reports the resolved density, provenance, and completed-wave reading
surface. It fails its documentation check for an invalid density, explanation
preference, or rigor value and names the configuration file to repair.
It does not render documents. An invalid `documentation.expansion_prompt` or
`documentation.density` also refuses `des wave-entry`; an invalid
`documentation.expansion_prompt` refuses `nwave-ai install`. An unknown
`rigor.profile`, a non-object `documentation`/`rigor` section, or an unreadable
or malformed config file make `des wave-entry` return `Indeterminate` with no
offer; it never guesses the preference.

The doctor's legacy reader treats an unreadable or malformed whole file as
absent. Its density result alone does not establish that such a file is valid.

---

## Troubleshooting

**Q: My config file doesn't exist. What's the default?**

No file is needed to read defaults. New repositories are inactive under
`opt-in`; attribution defaults to off and verbosity to standard when no tier
declares a value. The density resolver defaults to `lean` (no local HTML view
after a completed wave); wave-end explanations default to `ask-intelligent`
after completed waves.
Installation does not ask for density or create a file just to store it.
A command that writes configuration creates its relevant file.

**Q: Can I edit the config manually?**

Yes. Run `nwave-ai status` afterward to see effective values and their
sources. `nwave-ai doctor` checks installation health and active documentation
choices. Wave entry remains authoritative for unreadable or malformed
documentation configuration; it does not guess a usable preference.

**Q: Can I override density per project or per feature?**

Per-project overrides are limited to the closed set `nwave-ai project set`
accepts (`enabled`, `verbosity`, `attribution`); there is no per-project or
per-feature `documentation.density` override today.
