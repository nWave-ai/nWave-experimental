# How to configure documentation density

This guide shows you how to set the `documentation.density` and
`documentation.expansion_prompt` preferences in nWave's config, and what
those values currently do (and do not yet do).

## Prerequisites

- nWave installed via `nwave-ai install` (if not, see the [installation guide](installation-guide/README.md))
- A text editor
- Basic familiarity with JSON files

## What this actually controls today

`documentation.density` and `documentation.expansion_prompt` are validated
and resolved by `scripts/shared/density_config.py:resolve_density()`, and the
resolved value is surfaced by `nwave-ai doctor`. That is the current, real
surface: a declared preference you can inspect and verify. There is **no**
`--expand` CLI flag and **no** implemented wave-end expansion menu in the
current codebase — if earlier docs or your memory of nWave described either,
that described a plan, not shipped behavior. If you want more detail on a
specific feature, ask the assisting LLM directly during the wave; it produces
the extra detail through the existing DES typed document producer rather
than through a separate expansion mechanism.

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

There is currently no `--expand` flag and no wave-end expansion prompt
implementation to drive automatically. If `lean` output leaves out detail
you want for one feature, ask the assisting LLM in the conversation for
that detail; it can produce it through the existing DES document producer
without you touching global configuration or waiting for a future feature.

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
