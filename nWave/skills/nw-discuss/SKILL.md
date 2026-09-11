---
name: nw-discuss
description: Routes a product question or outcome into the DES steps.
user-invocable: true
argument-hint: '<product question or outcome>'
---
# NW-DISCUSS
Have the LLM return the closed semantic DISCUSS JSON (request, outcomes, scope,
decisions, and ordered values) and construct the authority through DES:
```bash
printf '%s' "$DISCUSS_JSON" | des discuss --repo-root ROOT --input -
```
The LLM owns the semantic values, their supplied order and dependencies; each
dependency list names already preceding values in that same supplied order. DES
renders Markdown and projects those values to the typed handover; it does not
write product Markdown from the LLM or invoke a provider. `NEXT` is advisory.
Public results are `Success`, `Refusal`, `Retry`, and `Indeterminate`.

Plain `--input -` intentionally refuses a persisted brief or value graph that
the supplied one contradicts, before any write. For a deliberate upstream
correction of the same Request, use the explicit constructor:
```bash
printf '%s' "$DISCUSS_JSON" | des discuss --repo-root ROOT --input - --replace-current
```
The replacement is selective: every DESIGN authority and acceptance projection
already bound to an observation that survives the correction is preserved, and
only an observation the corrected graph drops or renames loses the facts keyed
to it. The correction refuses before writing when no persisted graph carries
this Request. Do not imply replacement without that flag.
