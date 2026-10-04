# nw-density-resolution-contract

Reference for the documentation-density resolution contract. The tree holds no
`nWave/skills/nw-density-resolution-contract/SKILL.md`; the contract lives in
code and in the wave-entry step described below.

**Sources:** `src/des/domain/documentation_density.py` (resolver),
`src/des/cli/wave_entry.py` (`des wave-entry`), `nwave_ai/status.py`
(`nwave-ai status`), `nWave/skills/nw-doc-as-artifact/SKILL.md` (how the
assistant uses the result).

## Resolver

`resolve_density(global_config)` is a pure function over an already-parsed
config dict. It returns `Density(mode, expansion_prompt, provenance)`.
`resolve_density_result` returns the same value, or an `IllegalChoice`
(field, value, accepted values) for a closed-set value outside its legal set.

| Field | Legal values |
|---|---|
| `mode` (`documentation.density`) | `lean`, `full` |
| `expansion_prompt` (`documentation.expansion_prompt`) | `ask`, `always-skip`, `always-expand`, `smart`, `ask-intelligent` |

Cascade for `mode`, first match wins:

1. Explicit `documentation.density` (provenance `explicit_override`).
2. `rigor.profile` mapping (provenance `rigor.profile=<name>`).
3. Default `lean` (provenance `default`).

`expansion_prompt`: an explicit value always wins, whichever branch chose
`mode`; otherwise the `rigor.profile` mapping; otherwise `ask-intelligent`.

| `rigor.profile` | `mode` | `expansion_prompt` |
|---|---|---|
| `lean` | `lean` | `always-skip` |
| `standard` | `lean` | `ask-intelligent` |
| `thorough` | `full` | `always-expand` |
| `exhaustive` | `full` | `always-expand` |
| `custom` | `lean` | `ask-intelligent` |

`resolve_density` raises `ValueError` for a density or explanation choice
outside its accepted set, an unknown or non-string `rigor.profile`, or a
`documentation`/`rigor` section that is not a JSON object. Profile labels are
not guarantees of quality or coverage.

## Meaning of the two fields

| Field | Selects | Does not select |
|---|---|---|
| `mode` | After an applicable completed wave: `full` renders local HTML from the DES Markdown document; `lean` keeps the authoritative document and handoff | Sections of a wave document; a provider or model; mandatory checks |
| `expansion_prompt` | Optional explanation in chat after a completed wave | The HTML view; a provider or model; mandatory checks |

Provider and model are chosen only through `model_runtime`
(`nwave-ai model set`). Tests, reviews and examination required by the delivery
route stay in force under every value.

## Consumers

| Consumer | Behavior |
|---|---|
| `des wave-entry --repo-root ROOT --wave WAVE` | Read-only. Reads the global config once and prints `WAVE-DOCUMENTATION-DENSITY`, `WAVE-DOCUMENTATION-PROVENANCE` and the `WAVE-END-OFFER` rows. Absent file: cascade default. Unreadable or malformed file, unknown `rigor.profile`, or non-object section: `Indeterminate`, no offer. Illegal `documentation.density` or `documentation.expansion_prompt`: `Refusal` naming field, value and accepted values |
| `des wave-entry ... --complete --entry-result PATH --constructor-result PATH` | Host-asserted completion. Does not reread config; uses the density recorded in the captured entry terminal. `lean`: prints `LOCAL-VIEW: not requested; authoritative DES documents and handoffs remain`, writes nothing. `full`: renders each distinct `DOCUMENT:` Markdown locator from the successful constructor terminals to the adjacent `.html` with the packaged renderer, after path checks, and prints `HTML:` rows |
| `nwave-ai status` | Read-only. Prints the resolved density and provenance, and separately the wave-end explanation value and source. Resolves density without `expansion_prompt` |
| `nwave-ai doctor` | Reports resolved density, provenance and reading surface. Invalid active documentation or rigor values fail the check and name the config to repair. Does not render documents |
| `nwave-ai install` | Checks only an explicit `documentation.expansion_prompt` before writing files. Does not ask for or write a density |

## Completion semantics

- DES has no whole-wave completion record. Invoking `--complete` is the host's
  assertion; the terminal says so in `COMPLETION-EVIDENCE`.
- The CLI does not detect completion, and nothing in DES verifies that the host
  invokes it. The `nw-doc-as-artifact` skill instructs the assistant to do so at
  whole-wave success.
- A lone DES step, an earlier turn, a stopped wave, or a `DOCUMENT:` row on an
  `Indeterminate` terminal is not completion.
- `discuss`, `design`, `devops` and `distill` require a captured constructor
  terminal with a `DOCUMENT:` row; absence is `Indeterminate`. Other waves with
  no DES Markdown authority report `LOCAL-VIEW: no applicable DES Markdown
  authority`.

## Telemetry

No event is emitted for density resolution. `DocumentationDensityEvent` has no
constructor call site in the code; treat any earlier mention of it as
designed-not-built.

See [global configuration reference](../global-config.md) and
[Documentation detail and wave-end explanations](../../guides/configuring-doc-density.md).
