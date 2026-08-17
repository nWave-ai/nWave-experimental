# Expectation Charter

One source-blind human oracle is one direct Markdown member of
`docs/product/expectations/<delivery-id>/`. The directory name is the exact
schema-valid DeliveryContract `delivery-id`; the filename is a short intent
slug. `des dispatch` validates every direct member and never filters an invalid
one away.

The charter is not a second delivery authority. It carries only value-side
intent, a reproducible start recipe and independently observable outcomes for
one terminal EXAMINE pass. Design, tests, implementation and producer verdicts
are prohibited. The session log is the only growing section.

## Template

```markdown
# <intent, as a human sentence>
ID: <delivery-id> · Persona: <who>

## Intent
<the value-side outcome and why it matters>

## Preconditions
<PublicStartRecipe: CLI argv, or public library import+setup+call, or
endpoint+request, or URL+ordered UI actions — exact tree and public surface,
from a clean state>

## Charter
Explore <surface> to verify <intent>, without reading source, tests or diffs.

## Expected observations (oracle)
- <positive observable outcome in user or operator language>
- Negative: <what must not happen>

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
```

The start recipe must identify the exact tree and executable surface. If the
runtime reports a different root, discard the observation and rerun against the
intended tree. A filled charter contains at least one positive observation and
one `Negative:` observation; it never precomputes PASS/FAIL.
