---
name: nw-discuss
description: PO-led product conversation, visible feedback increments and a DES-constructed human-readable brief.
user-invocable: true
argument-hint: '<product question or outcome>'
---
# NW-DISCUSS

Read `~/.claude/skills/nw-human-collaboration/SKILL.md` to offer and conduct
interactive refinement with the human. Honor an already selected final-review
or full-delegation mode; the LLM manages the dialogue and progression.

Read `~/.claude/skills/nw-role-invocation/SKILL.md` before delegating. Invoke
the installed `nw-product-owner` role natively for semantic facts; `des po
--repo-root ROOT --feature ID` buys decomposition only, and `des discuss --input`
buys no turn.

The Product Owner owns this conversation. Use `nw-product-owner` with its
resident collaboration, JTBD, BDD and value-slicing knowledge. Do not treat
`des po` decomposition as completion of DISCUSS. The host relays questions and
runs requested tools within authorization. Offer visual exploration for changed
user experiences; select UX/UI help and a bounded spike only when useful.

Have the PO return the closed semantic DISCUSS JSON (request, outcomes, scope,
decisions, ordered values, and the four explicit sections `jtbd`, `journey`,
`gherkin`, `quint_scenarios`; `schema_version` 2) and construct the authority through DES:
```bash
printf '%s' "$DISCUSS_JSON" | des discuss --repo-root ROOT --feature FEATURE_ID --input -
```
The LLM owns the semantic values, their supplied order and dependencies; each
dependency list names already preceding values in that same supplied order. DES
renders Markdown and projects those values to the typed handover; it does not
write product Markdown from the LLM or invoke a provider. `NEXT` is advisory.
Public results are `Success`, `Refusal`, `Retry`, and `Indeterminate`.

Project and feature documents are separate. Scope is mandatory: use `--project`
for the project brief (`documents.<wave>.destination`, default `docs/product/*`) or
`--feature ID` (`[a-z0-9][a-z0-9-]*`) to `des discuss` or
`des po`: defaults are `docs/feature/ID/brief.md` and
`docs/feature/ID/{architecture,acceptance,operations}/brief.md`. Configure
templates with `documents.feature.<wave>.destination` containing `{feature}`;
set a per-feature override with `nwave-ai project feature-document ID WAVE
PATH`, under the directory of that feature's resolved DISCUSS document.
The scope is stored in the handover, so
`des design`, `des distill` and roles inherit it without a flag; DEVOPS requires the explicit scope;
a different `--feature` is refused. Old flat paths are never treated as feature
documents and nothing is migrated automatically.

Plain `--input -` intentionally refuses a persisted brief or value graph that
the supplied one contradicts, before any write. For a deliberate upstream
correction of the same Request, use the explicit constructor:
```bash
printf '%s' "$DISCUSS_JSON" | des discuss --repo-root ROOT --feature FEATURE_ID --input - --replace-current
```
The replacement is selective: every DESIGN authority and acceptance projection
already bound to an observation that survives the correction is preserved, and
only an observation the corrected graph drops or renames loses the facts keyed
to it. The correction refuses before writing when no persisted graph carries
this Request. Do not imply replacement without that flag.

## Shared human view

Read `nw-doc-as-artifact` and render the constructed product brief to local nWave
HTML during meaningful refinement and at the agreed handoff. Use the document
path reported by DES, which honors global/project configuration; never assume
`docs/product/brief.md`. The view serves human comprehension even for a short
brief. Reuse the packaged renderer, not LLM-authored HTML. This is a working
surface, not a publication requirement or DES progression gate. If rendering is
unavailable, expose that gap and keep the conversation readable in the host.

Keep actor/value in outcomes and confirmed decisions, proposals, assumptions
and open questions explicit in decisions. DES always renders four sections,
with "not explored" / "not run" placeholders when a section is declared
unexpanded. Current input is `schema_version` 2: every section key is REQUIRED
and tagged, so deferral is an explicit state, never an omission. It never needs
a long elicitation. Start with brief existing facts; do not repeat them in scope
or decisions. Deepen a section when the human requests it, and ask only
questions that affect a decision. Do not run Quint merely to fill its section.
Run `des discuss --describe-input` for the full schema and a copyable example
instead of recalling it; in short:
- Document language and its exception: see `nw-human-collaboration`. DES renders
  the journey as a qualitative arc from `human_emotion` and `status`; missing
  emotions show as UNKNOWN. It is not measured intensity.
- `jtbd`, `journey`, `gherkin`: `{"status": "not_explored"}` or
  `{"status": "provided", ...}` carrying `human`/`llm` jobs, `steps`, or
  `scenarios` (each entry has `status` proposed, confirmed or open).
- `quint_scenarios`: `{"status": "not_run"}` or `generated` with model, tool
  (name, version, command incl. seed/bounds), trace and events; only with real
  tool output. DES records that evidence; it does not run or verify Quint.
- `human_emotion` is the human's only; omit it rather than guess.
Illegal state combinations refuse before any write, and the refusal names
`--describe-input`. Legacy `schema_version` 1 input (sections optional and
untagged) is still accepted but is not migrated; do not emit it for new work.
Do not claim a path proves review.
The host forwards the human's corrections to the PO and explicitly selects
`--replace-current` for an authorized revision. Re-render the same local HTML
projection after a meaningful change; never edit the generated files by hand.

When the PO judges Quint relevant (or the human requests it), it runs inside the
conversation as specified by `nw-po-scenario-exploration` (mode sequence, evidence,
availability). No solver is a prerequisite for DISCUSS. Frontend/backend contracts and implementation planning
remain DESIGN/DELIVER responsibilities; DISCUSS supplies the experience and
visible increments those activities must preserve.

Scope choices are mandatory and mutually exclusive: Project, Epic(id), Feature(id), or Slice(feature_id, slice_id). Epic documents use configured `documents.epic` templates under `docs/epic/ID`; slice documents use their feature destinations and retain both identities in the handover. The choice belongs to the LLM. DES never infers it from missing input.

Document scope must be explicit for DISCUSS, PO and DEVOPS. The examples select a feature; alternatives are `--project`, `--epic EPIC_ID`, or `--slice FEATURE_ID SLICE_ID`. Select exactly one. Later steps inherit the persisted scope.
