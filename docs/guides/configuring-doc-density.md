# Documentation Detail and Wave-End Explanations

`documentation.density` is a retained preference. It does not change the
sections produced by a wave. New installations do not prompt for it or write
it. `nwave-ai doctor` reports its resolved value as a diagnostic; do not set
it to control document length. Ask the assistant for a shorter or more detailed
result when you need one.

`documentation.expansion_prompt` **does** control optional explanation after
a completed wave. The installed assistant reads this preference from the
global `~/.nwave/config.json` at wave entry. If you set `NWAVE_AGENTS_HOME`,
use its `.nwave/config.json` instead. Project-level settings do not override
this global preference. No expansion offer follows a single DES step, a
refused or indeterminate wave, or a stopped wave. There is no interactive CLI
menu or `--expand` flag.

## Choose the wave-end response

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

An explicit `documentation.expansion_prompt` takes precedence over the legacy
`rigor.profile` fallback. `nw-rigor` configures provider/model pairs through
`model_runtime`; it does not set that profile. You can ask directly for more
detail at any time, including with `always-skip`. A direct request does not
change accepted documents or run another DES step.

`nwave-ai status` shows the resolved wave-end mode and its source without
writing files. An invalid explicit expansion value is refused before an
installation or a wave begins; correct the global value to one from the table.
An invalid retained density value does not select output, but the current
`des wave-entry` also refuses it: remove that obsolete key if it blocks work.

See the [global configuration reference](../reference/global-config.md) for
the legacy cascade and [feature format reference](../reference/feature-format.md)
for document sections.
