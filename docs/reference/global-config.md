# nWave Global Config Reference

**Location**: `~/.nwave/global-config.json`

This reference documents every configuration key available in nWave's global configuration file. Settings here apply to all features, waves, and CLI commands unless overridden at the feature level.

## File location and initialization

- **Path**: `~/.nwave/global-config.json`
- **Created by**: `nwave-ai install` (first run)
- **User-editable**: Yes, with a text editor
- **Verification**: Run `nwave-ai doctor` to validate your config

## Top-level structure

```json
{
  "rigor": { "profile": "..." },
  "documentation": { "density": "...", "expansion_prompt": "..." },
  "audit_logging_enabled": true,
  "audit_log_dir": "...",
  "update_check": { "frequency": "..." }
}
```

---

## Configuration keys

### `rigor` (object)

Controls how much ceremony, validation, and narrative detail applies to waves and output.

#### `rigor.profile` (string)

Selects a preset rigor level. Valid values: `lean`, `standard`, `thorough`, `exhaustive`, `custom`.

| Profile | Wave ceremony | Output detail | Doc density | Expansion prompt | Use case |
|---------|---|---|---|---|---|
| `lean` | Minimal | Minimal | `lean` | `always-skip` | Solo dev, fast iteration, low token budget |
| `standard` | Moderate | Moderate | `lean` | `ask` | Small teams, balanced approach (default) |
| `thorough` | High | High | `full` | `always-expand` | Regulated environments, audit trails |
| `exhaustive` | Maximum | Maximum | `full` | `always-expand` | Mission-critical, government, DoD |
| `custom` | (explicit per key) | (explicit per key) | (see `documentation.density` override) | (see `documentation.expansion_prompt` override) | Advanced; requires explicit config |

**Default**: `standard`

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

Controls how much narrative, examples, and optional expansions appear in wave output.

#### `documentation.density` (string, optional)

Specifies the default detail level for wave output. Valid values: `lean`, `full`.

- **`lean`**: Emits only load-bearing content (`[REF]` sections in L7 format). Prose is minimal; persona narrative, JTBD analysis, and alternatives are omitted unless explicitly requested via `--expand`. **Goal**: ≤60% token cost vs legacy multi-file baseline.

- **`full`**: Emits all available sections (`[REF]` + `[WHY]` + `[HOW]`). Prose is complete; persona narrative, JTBD analysis, alternatives, and migration guidance are inline. **Goal**: comprehensive documentation for handoff, audit, and future context recovery.

**Default behavior** (if key absent):
- If `rigor.profile` is `lean`, inherit `lean`.
- If `rigor.profile` is `standard`, inherit `lean` (lean is the default for new installs).
- If `rigor.profile` is `thorough` or `exhaustive`, inherit `full`.
- If `rigor.profile` is `custom`, default to `lean` (can be overridden).

**Explicit override**: Any value in `documentation.density` always wins, even if `rigor.profile` suggests a different density. This allows you to have `rigor: "exhaustive"` (high ceremony) with `density: "lean"` (minimal prose).

**Example**:
```json
{
  "documentation": {
    "density": "lean"
  }
}
```

#### `documentation.expansion_prompt` (string, optional)

Controls when wave end prompts offer optional expansions (JTBD narrative, alternatives, migration playbooks, etc.). Valid values: `ask`, `always-skip`, `always-expand`, `smart`.

- **`ask`**: (Default) At the end of each wave, prompt the user with a menu of available expansions. User can select one-shot additions without re-running the wave.

- **`always-skip`**: Never prompt; skip all expansions. Equivalent to always pressing "skip all" at the menu. Useful for fully automated / CI flows where user input is not expected.

- **`always-expand`**: Automatically include all available expansions. Equivalent to always pressing "expand all" at the menu. Useful when density is `full` or you want comprehensive documentation upfront.

- **`smart`** (v3.15+): Agent decides per feature type. Complex features get more expansions; simple fixes get fewer. Experimental; feedback welcome.

**Default behavior** (if key absent):
- If `rigor.profile` is `lean`, inherit `always-skip`.
- If `rigor.profile` is `standard` or `custom`, inherit `ask`.
- If `rigor.profile` is `thorough` or `exhaustive`, inherit `always-expand`.

**Note on interactivity**: When `expansion_prompt: "ask"`, the wave reaches an interactive prompt at the end. This requires a terminal (TTY). Non-interactive runs (e.g., CI pipelines) default to `always-skip` behavior.

**Example**:
```json
{
  "documentation": {
    "expansion_prompt": "ask"
  }
}
```

#### `documentation.default_expansions` (array of strings, optional)

Pre-selects specific expansions to include when `expansion_prompt: "ask"` and the user hits "expand recommended". Valid IDs per wave are listed in each wave's `feature-delta.md` Expansion catalog.

**Example**:
```json
{
  "documentation": {
    "default_expansions": ["jtbd-narrative", "alternatives-considered"]
  }
}
```

---

### `audit_logging_enabled` (boolean, optional)

Enable or disable event logging to the audit log. Valid values: `true`, `false`.

- **`true`**: Every wave, expansion choice, and tool invocation is logged to `audit_log_dir` with timestamp, feature ID, and outcome.
- **`false`**: No events are logged.

**Default**: `true` (unless telemetry is explicitly disabled globally).

**Example**:
```json
{
  "audit_logging_enabled": true
}
```

---

### `audit_log_dir` (string, optional)

Directory where audit log files (`.jsonl` format) are written. Paths are relative to `$HOME`.

- **Default**: `.nwave/audit/`
- **Interpretation**: `~/.nwave/audit/`

**Example**:
```json
{
  "audit_log_dir": ".nwave/audit"
}
```

---

### `update_check` (object, optional)

Controls how often nWave checks for new versions.

#### `update_check.frequency` (string, optional)

Valid values: `daily`, `weekly`, `monthly`, `never`.

- **`daily`**: Check once per day.
- **`weekly`**: Check once per week.
- **`monthly`**: Check once per month.
- **`never`**: Never check (offline mode).

**Default**: `weekly`

**Example**:
```json
{
  "update_check": {
    "frequency": "weekly"
  }
}
```

---

## Cascade and override semantics

**When a key is absent**, nWave cascades through these layers (in order):

1. **Explicit config value** in `~/.nwave/global-config.json` (if present)
2. **Rigor profile default** (if `rigor.profile` is set to a preset like `standard`)
3. **Hardcoded fallback** (if config file is missing entirely)

**Examples**:

### Example 1: Lean solo developer

```json
{
  "rigor": {
    "profile": "lean"
  }
}
```

**Cascade result**:
- `documentation.density` → `lean` (from rigor cascade)
- `documentation.expansion_prompt` → `always-skip` (from rigor cascade)
- `audit_logging_enabled` → `true` (hardcoded fallback)

### Example 2: Regulated environment with explicit prose override

```json
{
  "rigor": {
    "profile": "thorough"
  },
  "documentation": {
    "density": "lean"
  }
}
```

**Cascade result**:
- `documentation.density` → `lean` (explicit override wins, even though rigor is `thorough`)
- `documentation.expansion_prompt` → `always-expand` (from rigor cascade, thorough level)
- `audit_logging_enabled` → `true` (hardcoded fallback)

---

## Rigor profile cascade table

This table shows which `documentation.density` and `expansion_prompt` defaults apply when `rigor.profile` is set and those keys are absent from the config:

| Profile | Inherited density | Inherited prompt | Wave detail | Typical use |
|---------|---|---|---|---|
| `lean` | `lean` | `always-skip` | Minimal refs only | Solo iteration |
| `standard` | `lean` | `ask` | Refs + on-demand WHY/HOW | Balanced teams |
| `thorough` | `full` | `always-expand` | All sections inline | Regulated, audit-required |
| `exhaustive` | `full` | `always-expand` | All sections + all expansions | Mission-critical, DoD |
| `custom` | `lean` (if absent) | `ask` (if absent) | Explicit per key | Advanced |

---

## Important warnings

### Backup count = 0

If your config contains:

```json
{
  "backups": {
    "max_count": 0
  }
}
```

This **disables all backups**. nWave will not retain any backup copies of previous `feature-delta.md` versions. Restore functionality is disabled.

**Recommendation**: Set `max_count` to at least `3` to retain recent history. Only set to `0` in CI environments where state is ephemeral.

---

## Complete minimal example

```json
{
  "rigor": {
    "profile": "standard"
  },
  "documentation": {
    "density": "lean",
    "expansion_prompt": "ask"
  },
  "audit_logging_enabled": true,
  "update_check": {
    "frequency": "weekly"
  }
}
```

---

## Troubleshooting

**Q: My config file doesn't exist. What's the default?**

Run `nwave-ai install` to initialize. The first-run prompt will ask for density preference and create the file.

**Q: Can I edit the config manually?**

Yes. Use any text editor (vim, nano, VS Code, etc.). After editing, run `nwave-ai doctor` to validate. If the JSON is malformed, doctor will report a parse error.

**Q: What does "expansion_prompt: ask" mean if I'm running in CI?**

On non-interactive (no-TTY) environments, `ask` defaults to `always-skip` — no prompts are issued. Features still emit `lean` output (refs only). Expansions can only be triggered via `--expand <id>` flag or by changing `expansion_prompt` in the config.

**Q: Can I override density per feature?**

Not in v1. The global config applies to all features. Per-feature overrides are tracked as a future enhancement.
