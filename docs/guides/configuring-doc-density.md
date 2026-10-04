# Documentation Detail and Wave-End Explanations

Two independent settings shape what you get after a completed wave. Neither
changes the sections of a wave document, selects a provider or model, or
weakens tests, reviews or examination that the delivery route requires. Ask the
assistant for a shorter or more detailed result when you need one.

## Local HTML view: `documentation.density`

New installations do not prompt for it or write it.

| Value | After an applicable completed wave |
|---|---|
| `lean` (default) | No view. The authoritative DES document and handoff remain. |
| `full` | A local HTML view of each DES Markdown document the wave's constructors returned, written next to its Markdown. The Markdown stays the authority. |

Set it with an explicit value in the global config:

```json
{
  "documentation": { "density": "full" }
}
```

How it works, and its limits:

- `des wave-entry` reads the value once at wave entry and prints it as
  `WAVE-DOCUMENTATION-DENSITY`. That row is a preference; it does not show that
  the wave completed.
- The view is rendered only by `des wave-entry --complete --entry-result PATH
  --constructor-result PATH`, called by the host after it asserts that the
  whole wave completed. DES has no whole-wave completion record. The CLI does not
  detect completion, and nothing in DES verifies that the host makes the call;
  the wave skill instructs the assistant to make it. It is not made after a lone
  DES step, an earlier turn or a stopped wave.
- The call needs the captured entry terminal and each successful constructor
  terminal. Without them the mode refuses or reports `Indeterminate`; it does
  not guess. If a wave has no DES Markdown document, it reports that no local
  view applies.
- Path checks come before any render: the source must be a regular
  repository-relative `.md` file without symlinks, and the destination must not
  be a symlink or an unrelated HTML file. A failed check is refused with WHAT,
  WHY and HOW; no view is reported.
- With `lean` the same call writes nothing and prints that no view was
  requested.
- Check the generated page yourself. A local page is not a published artifact
  and does not mean anyone approved the document.

`nwave-ai status` shows the resolved density, its source and this meaning
without writing files.

## Wave-end explanation: `documentation.expansion_prompt`

`documentation.expansion_prompt` controls optional explanation in chat after
a completed wave. The installed assistant reads this preference from the
global `~/.nwave/config.json` at wave entry. If you set `NWAVE_AGENTS_HOME`,
use its `.nwave/config.json` instead. Project-level settings do not override
this global preference. No expansion offer follows a single DES step, a
refused or indeterminate wave, or a stopped wave. There is no interactive CLI
menu or `--expand` flag.

### Choose the wave-end response

Add only the preference you want to change; no configuration file is needed
for the default:

```json
{
  "documentation": { "expansion_prompt": "ask-intelligent" }
}
```

| Value | After a completed wave |
|---|---|
| `ask` | Offer optional explanation. |
| `always-skip` | Do not offer explanation. |
| `always-expand` | Explain pertinent detail without asking first. |
| `smart` | Offer detail only for a concrete optional alternative, trade-off, risk, constraint, or deferred consequence in the result. |
| `ask-intelligent` | Use the `smart` condition and name at most two relevant topics; this is the default. |

An explicit `documentation.expansion_prompt` takes precedence over the
`rigor.profile` fallback. `rigor.profile` labels (`lean`, `exhaustive`) are not
guarantees of quality or coverage. `nw-rigor` configures provider/model pairs
through `model_runtime`; it does not set that profile, and a density or profile
never picks a model. You can ask directly for more detail at any time,
including with `always-skip`. A direct request does not change accepted
documents or run another DES step. The explanation offer and the HTML view are
separate: accepting or ignoring one does not affect the other.

`nwave-ai status` shows the resolved wave-end mode and its source without
writing files. An invalid explicit expansion value is refused before an
installation or a wave begins; correct the global value to one from the table.
An invalid `documentation.density` (anything but `lean` or `full`) is refused by
`des wave-entry` with the field, the value and the accepted values named;
correct it in the global config.

See the [global configuration reference](../reference/global-config.md) for
the cascade and the `--complete` details, and the
[feature format reference](../reference/feature-format.md) for document
sections.
