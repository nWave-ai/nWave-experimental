---
name: nw-expectation-charter
description: "Authors or reviews one value-side, source-blind expectation charter for a delivery whose validated contract requires EXAMINE."
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

Run only when validated `applicability.examine=true`. Discover every direct
entry under `docs/product/expectations/{delivery-id}/` and classify the whole
namespace:

- `Missing` or `Empty` -> a fresh PO may author;
- `Valid(NonEmptySeq<ValidatedCharter>)` -> reuse every member in deterministic
  order;
- `Invalid(reason)` -> block; never filter a malformed, unfilled, nested,
  ambiguous or path-unsafe member away.

When examine is false, skip PO, charter and Vera entirely.

## Charter content

Write one concise direct member of the assigned namespace using exactly the
canonical section headings, in order:

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
`des dispatch` matches them verbatim. Do not include internal names, expected
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
copy or losslessly project it from the supplied immutable value-side facts.
Those facts may carry a citation to a public product document, but must also
carry the exact recipe: the Write-only PO never reads that document. Never
recover the recipe from architecture, design, source or tests; when the
supplied facts do not state an exact modality-appropriate recipe, return
`CLARIFICATION_NEEDED` and write nothing rather than inventing one.

The charter path and validated content digest join the delivery evidence; they
do not become a second delivery authority or progress artifact.
