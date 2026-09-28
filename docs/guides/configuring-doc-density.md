# How to configure documentation density

This guide shows how to set `documentation.density` and
`documentation.expansion_prompt` in the global nWave config.

## Prerequisites

- nWave installed via `nwave-ai install` (if not, see the [installation guide](installation-guide/README.md))
- A text editor
- Basic familiarity with JSON files

## What these settings control

`documentation.density` selects a declared documentation preference; it does
not by itself change the sections that a wave produces. `nwave-ai doctor`
reports the resolved setting. `documentation.expansion_prompt` controls what
the assistant says about optional detail after a **completed** wave. The
assistant resolves it once at wave entry. There is no interactive CLI menu or
`--expand` flag. A single DES step, a refused or indeterminate wave, and a
stopped wave do not produce a proactive offer.

## Quick start: Change density via config

**Step 1**: Open your global config file.

```bash
vim ~/.nwave/config.json
```

(Under `NWAVE_AGENTS_HOME` instead, if you have that environment variable
set to an absolute path. On Windows this is still your resolved home
directory, not `%APPDATA%`.)

**Step 2**: Find or add the `documentation.density` key.

```json
{
  "documentation": {
    "density": "lean"
  }
}
```

Valid values: `"lean"` or `"full"`.

**Step 3**: Save the file and verify.

```bash
nwave-ai doctor
```

You should see a line such as:

```
Documentation density: lean (explicit override)
```

---

## Setting via `rigor.profile` instead

If you'd rather not set `documentation.density` explicitly, you can set
`rigor.profile` in the same file and let it cascade:

```json
{
  "rigor": {
    "profile": "lean"
  }
}
```

| Profile | Inherited density | Inherited expansion_prompt |
|---------|---|---|
| `lean` | `lean` | `always-skip` |
| `standard` | `lean` | `ask-intelligent` |
| `thorough` | `full` | `always-expand` |
| `exhaustive` | `full` | `always-expand` |
| `custom` | `lean` | `ask-intelligent` |

**There is no `nwave-ai` command that sets `rigor.profile`** — edit it by
hand. Do not confuse this with the `nw-rigor` skill/command: `nw-rigor`
configures an unrelated key, `model_runtime` (explicit provider/model pairs
per role), via `nwave-ai model set`. It has no notion of a rigor profile and
never derives a model from one.

An explicit `documentation.density` always overrides the `rigor.profile`
cascade for the mode, and an explicit `documentation.expansion_prompt`
always overrides it for the prompt, independently of each other:

```json
{
  "rigor": { "profile": "thorough" },
  "documentation": { "density": "lean" }
}
```

This resolves to `density: lean` with `expansion_prompt: always-expand`
(inherited from `thorough`, since `expansion_prompt` was not set explicitly).

---

## Getting more detail on a specific feature

Set `documentation.expansion_prompt` in `~/.nwave/config.json`:

| Value | After a completed wave |
|---|---|
| `ask` | Offer an optional explanation. |
| `always-skip` | Do not offer an explanation. |
| `always-expand` | Explain relevant detail directly without asking first. |
| `smart` | Offer an optional explanation only when the completed result contains a concrete alternative, trade-off, risk, constraint, or deferred consequence. |
| `ask-intelligent` | Use the `smart` condition and name at most two relevant topics from the actual result in the optional offer. This is the default when no preference or rigor profile is set. |

You can ask the assistant for more detail at any time, including with
`always-skip`. A direct question receives an answer; it does not change
accepted documents or trigger another DES step. Ignoring an offer also
changes nothing.

---

## Verification: Check your density setting

```bash
nwave-ai doctor
```

Look for the `documentation_density` check line, one of:

```
Documentation density: lean (explicit override)
Documentation density: lean (inherited from rigor.profile=standard)
Documentation density: lean (default (no config))
```

- `(explicit override)` — you set `documentation.density` directly.
- `(inherited from rigor.profile=...)` — derived from your `rigor.profile`.
- `(default (no config))` — no override anywhere; hard default (`lean`).

An invalid value (unknown `density`, unknown `expansion_prompt`, or unknown
`rigor.profile`) makes this check fail with a remediation message instead of
silently falling back.

---

## Troubleshooting

### Q: My config file doesn't exist. What's the default?

**A**: Run `nwave-ai install`. The first-run prompt asks for a density
preference (`lean` or `full`, defaulting to `lean` on Enter) and writes it;
a non-interactive install (`--yes`, or no TTY) silently writes `lean`.

### Q: Can I have different density for different features?

**A**: Not currently. The config applies globally (or per-project, if you
set it in `<repo>/.nwave/config.json`); there is no per-feature override.

### Q: What if I'm running in CI (non-interactive)?

**A**: `nwave-ai install` and the density prompt both fail-open to the
`lean` default when there is no TTY or `--yes` is passed; no prompt blocks
the run.

### Q: My teammate wants a different density. Should they change the global config?

**A**: Yes — change `documentation.density` in `~/.nwave/config.json` (their
own, unless you deliberately share a `NWAVE_AGENTS_HOME`), or set it in your
shared project's `<repo>/.nwave/config.json` if you want it to apply to
everyone working in that repo.

---

## Related guides

- **[nWave Global Config Reference](../reference/global-config.md)** — detailed reference for the config keys nWave actually reads
- **[Feature directory format reference](../reference/feature-format.md)** — understand `[REF]`, `[WHY]`, `[HOW]` section types
- **[How to author a feature using the L7 single-file model](feature-delta-l7-format.md)** — writing lean feature-delta files
