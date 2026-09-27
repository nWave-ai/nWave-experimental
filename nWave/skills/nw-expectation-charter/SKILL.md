---
name: nw-expectation-charter
description: "Supplies or reviews source-blind qualitative charter facts for deterministic DES construction when EXAMINE applies."
user-invocable: false
---

# Expectation Charter

The charter gives Vera an independent human oracle. It is derived from the
same durable value intent as the acceptance oracle, but never from design,
tests or implementation.

## Disqualification

A context that read architecture details, the executable contract body, tests,
implementation, diffs or producer claims cannot author the charter. Dispatch a
fresh `nw-product-owner` with value-side inputs only. No prompt can
decontaminate a context.

## Applicability and discovery

Run only when the resident route determines that EXAMINE applies. Discover
every direct entry under the assigned expectation-charter namespace and classify
the whole namespace:

- `Missing` or `Empty` -> a fresh PO supplies qualitative facts to DES;
- `Valid` -> reuse the selected value's member without a PO turn; if it is
  missing, construct only that member and preserve valid siblings;
- `Invalid(reason)` -> block; never filter a malformed, unfilled, nested,
  ambiguous or path-unsafe member away.

When examine is false, skip PO, charter and Vera entirely.

## Construction contract

The caller invokes the existing public step:

```text
des po --repo-root ROOT --project --charter --value N --input FILE
```

Use the persisted scope: `--project`, `--epic ID`, `--feature ID`, or
`--slice FEATURE_ID SLICE_ID`. `--input -` reads stdin. For a missing selected
charter, input is a closed JSON object with integer `schema_version: 1` and
nonblank strings `intent`, `observation` and `public_start_recipe`.
`observation` must equal the persisted selected value's observation exactly.
Missing semantic facts require clarification before a model turn. Invalid
types, extra keys or conflicting observations refuse. A valid selected member
ignores supplied input without opening it and buys no new PO turn.

DES invokes a fresh installed PO with effective structured-reply-only tools in
a private directory. It supplies only those three value-side facts and
independently loads role and charter knowledge. If isolation is unavailable,
return Indeterminate; do not fall back to a source-reaching invocation.

The PO returns exactly `outcome`, a nonblank `diagnostic`, and `charter`.
An accepted `charter` contains nonblank `intent`, `exploration`,
`negative_observation`, and a nonempty array of nonblank `positive_observations`.
A rejected or indeterminate response has `charter: null`. Rejection asks for
clarification; diagnostics never become inferred charter facts.

## DES-owned charter content

DES alone writes `value-N.md` in the assigned namespace. The PO never writes
Markdown. DES constructs exactly these canonical sections, in order:

- `## Intent` — human intent and user/operator perspective;
- `## Preconditions` — one exact modality-appropriate `PublicStartRecipe`
  through a real product surface, from a clean state: a CLI invocation's
  exact argv; a public library's exact import plus the exact setup and call
  an external consumer would write; an HTTP/RPC endpoint plus the exact
  request; or a URL plus the exact ordered UI action sequence. Preparing
  internal state or invoking a domain/application port directly is not a
  `PublicStartRecipe`;
- `## Charter` — what to explore to verify intent, without reading source,
  tests or diffs;
- `## Expected observations (oracle)` — concrete positive observation
  bullets, plus at least one bullet whose text begins `Negative:` for what
  must not happen; and
- `## Session log (append-only)` — an empty table for Vera's session
  observations.

No synonym, paraphrase or reordering of these five headings is acceptable;
the software matches them verbatim. Do not include internal names, expected
implementation, test names, diffs or a precomputed verdict. A CLI, API or
infrastructure capability may be the user surface when that is what a real
operator observes.

## Value conservation

Every `Preconditions`, positive observation and `Negative:` bullet must be a
lossless projection of the immutable value seed or a cited durable product
authority: clarify wording only, never add or remove an input class, case,
surface, failure mode, quality or promise. A `Negative:` bullet negates the
same promised observation on the same admitted input/surface — it is not a
new scenario. If desired behavior is missing from the seed and no durable
authority covers it, block or clarify at value authority; never guess a new
requirement to fill the gap. The same law binds the `PublicStartRecipe`:
DES copies the supplied recipe unchanged; the PO neither recovers nor replaces
it. Supplied facts may cite a public product document, but must also contain
the exact recipe: the isolated PO cannot read that document. Never recover it
from architecture, design, source or tests. If supplied facts do not identify
an exact modality-appropriate recipe, reject for `CLARIFICATION_NEEDED`;
DES writes no charter.

The charter path and validated content digest join the delivery evidence; they
do not become a second delivery authority or progress artifact.

Namespaces are `docs/product/expectations/_project/`, `_epic/ID/`,
`FEATURE_ID/`, or `_slice/FEATURE_ID/SLICE_ID/` under the same expectations
root. Every direct member must be canonical and bound to its persisted value.
DES embeds the value position and source fingerprint, initializes the session
log, and preserves valid appended rows on reuse.

Include the constructed authority in Git before candidate verification so
the candidate snapshot contains it. EXAMINE consumes the candidate-bound
`expectation_charters` projection alongside selected acceptance and public
observations. A charter is an expectation, not proof of product behavior.
