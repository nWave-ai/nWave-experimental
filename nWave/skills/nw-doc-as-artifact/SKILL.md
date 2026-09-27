---
name: nw-doc-as-artifact
description: Render a DES-constructed document as local nWave-branded HTML for human understanding and collaborative review; HTML remains a generated projection.
user-invocable: false
disable-model-invocation: true
---

# Human document projection

The versioned document constructed by DES is the source; HTML is its generated
reading surface. Never write a second narrative, edit the HTML by hand, or use
an external URL as the only authority. Publication is optional and separate from
local rendering; never upload automatically.

## When

Use during meaningful DISCUSS refinement and at the agreed handoff, even for a
short brief. Also use for other long or living documents a human needs to read.
Do not generate views whose only consumer is software. Honor an explicitly
chosen alternative reading surface; an unavailable renderer is a reported gap,
not a new workflow gate.

## Render the actual authority

Read the `DOCUMENT` path returned by the constructor and resolve it under the
selected repository. Respect configured destinations; do not assume a default
brief path. Choose a persistent local HTML destination that does not overwrite
source, prototype or evidence. Use the existing shared renderer in the nWave
runtime environment (the interpreter running nWave, not the target project's
language or test toolchain):

```text
python -m des.adapters.driven.rendering.nwave_document SOURCE.md --out VIEW.html
```

In a framework source checkout the existing wrapper is also available:

```text
uv run python scripts/render_doc_html.py SOURCE.md --out VIEW.html
```

Both use the same packaged nWave brand assets. The renderer escapes content,
embeds local styles and reports unsupported constructs. Read its diagnostics and
inspect the generated view before claiming fidelity. This invocation must run
where the nWave Python package is available; if unavailable, report the concrete
runtime gap instead of guessing an interpreter or generating replacement HTML.
`des project --html PATH` shows delivery state, not a substitute for the product
conversation's brief.

## Facilitate with the view

The PO's semantic input should make intent, actors, journeys, relevant states,
examples, decisions and open questions understandable before formal detail.
Use the required `schema_version` 2 DISCUSS sections documented in `nw-discuss`
(JTBD, journey, Gherkin, Quint scenarios). Keep summaries brief; unexpanded
sections stay visible with honest status. Do not duplicate their content in scope or decisions.
Document language: `nw-human-collaboration`. Do not invent unsupported fields. Include
stable references to prototypes and mechanically rendered scenarios and make
clear which were reviewed. Explain unfamiliar terms on first use. If the human
cannot explain or challenge a consequence, clarify the semantic input and let
DES regenerate the source; styling cannot repair ambiguous requirements.

Share the local HTML path. Discuss one meaningful topic at a time. Regenerate the
same projection after source changes, and retain source identity alongside eval
evidence when comparing runs. Do not claim the view is current without rendering
it again. A local page does not imply a publicly hosted artifact or user approval.
The existing renderer supports `nwtree` disclosure blocks; use only supported
source constructs. No custom LLM-authored renderer, new ledger or progression gate.
