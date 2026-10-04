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

Use during meaningful DISCUSS refinement when it helps the conversation or
the human asks. At the completed-wave handoff, full density invokes the final
render automatically, including for a short brief; lean retains the document
and handoff unless the human asks for a view. Also use for other long or living
documents a human needs to read.
Do not generate views whose only consumer is software. Honor an explicitly
chosen alternative reading surface; an unavailable renderer is a reported gap,
not a new workflow gate.

## Completed-wave density

Each installed wave reads `des wave-entry` once at its start and retains that
complete terminal result. Its
`WAVE-DOCUMENTATION-DENSITY` row is the frozen view preference; it is separate
from `WAVE-END-OFFER` and `documentation.expansion_prompt`. The row does not
prove that a wave has completed. A full-density view is due only after the
**whole wave succeeds**, from each distinct authoritative Markdown `DOCUMENT:`
locator returned by a successful DES constructor in that wave. A `DOCUMENT:`
row on an `Indeterminate` result is not success. A single successful DES step,
an earlier turn, or a stopped wave never triggers this completed-wave render.
If the completed wave has no such DES Markdown document, report that no local
view applies; do not invent a wave document or render a YAML file or handoff.
DISCUSS, DESIGN, DEVOPS and DISTILL construct DES Markdown: a missing constructor
capture or missing `DOCUMENT:` row there is unknown evidence, not a documentless
success. Pass the actual capture or report the completion port's `Indeterminate`.
Lean keeps the authoritative document and handoff and adds no automatic
completed-wave view. Density never selects a provider or model and never
weakens mandatory checks.

Use the exact successful constructor locator, which may be `PATH.md#Heading`
for DESIGN. Keep the complete locator in the handoff and user report; remove
the `#Heading` only to select the filesystem source. Resolve the source under
the selected repository root. Before any render, require an existing regular
`.md` file at a repository-relative path with no URL, absolute path, `.` or
`..` component, symlink or path escape. Choose the adjacent `.html` path under
that root. Refuse a symlink destination or an existing unrelated HTML file;
regenerate an existing nWave projection only when its source banner identifies
this same Markdown authority. If these checks fail, state WHAT path failed,
WHY it is unsafe or unavailable, and HOW to repair it. Do not claim a view was
generated. The completion port performs these checks for every source and
destination before rendering any view. The renderer's direct write is not
atomic against a concurrent path change.

At whole-wave success only, capture the complete terminal of each successful
DES constructor that produced an authoritative `DOCUMENT:` row. Invoke the
executable `des wave-entry --complete` port in the nWave runtime, passing the
captured entry terminal and every relevant constructor terminal:

```text
des wave-entry --repo-root ROOT --wave WAVE --complete \
  --entry-result ENTRY.txt --constructor-result CONSTRUCTOR.txt
```

Repeat `--constructor-result` for each constructor. The host's invocation of
`--complete` attests whole-wave completion; captured DES terminals alone cannot
prove it. Do not invoke the port after a lone DES step or a stopped wave. The
port reads no configuration, enforces lean/full and path safety, and invokes
the existing packaged renderer. Read its WHAT/WHY/HOW and `HTML:` rows, then
inspect the resulting page before reporting the source locator and local view
path. On renderer failure, report the observed cause and exact safe retry;
keep Markdown as authority and do not report HTML success. DISCUSS may already have rendered during refinement:
at a full-density completed handoff, regenerate that **same** local view from
the final DES authority rather than creating a competing page. If a completed
wave produced several distinct DES Markdown authorities, render each source
once and report each source and view. Publication remains a separate action.

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
