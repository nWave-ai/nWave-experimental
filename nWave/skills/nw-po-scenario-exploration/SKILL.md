---
name: nw-po-scenario-exploration
description: Explore a disputed product behavior through actual Quint traces and mechanically rendered scenarios that the human can review.
user-invocable: false
disable-model-invocation: true
---

# Product Scenario Exploration

Use when concrete examples leave an order, timing, concurrency or state interaction
unclear, or the human requests model-generated alternatives. The PO keeps the
relevance judgment: no Quint for a settled behavior. Once chosen (or requested for
the current feature), Quint is a step INSIDE the PO-human collaboration sequence,
not an afterthought and not a separate offer. It imposes no wave, solver-owned
route or mandatory formal-method gate.

## Collaboration sequence (single owner of this policy)

| Mode | Sequence |
|---|---|
| Interactive | initial concrete examples -> model the actual assumptions -> actual Quint traces -> deterministic domain rendering -> human judgment -> if choices/model changed, revise and regenerate -> DES brief/handoff |
| Auto (delegated) | same steps without waiting; the actual generated scenarios, assumptions and every unresolved doubt appear in BOTH the human HTML rendering and the durable handoff (`quint_scenarios`, `decisions`). Silence or no human reply is never approval; record it as open |

Question and value authority stay with the human unless explicitly delegated. The
LLM orchestrates; DES constructs. Default documents are English; the human
conversation uses the human's language (`nw-human-collaboration`). The modeler
writes readable Quint; the PO never needs to read code.

## Human authority

The human owns the intended behavior. The PO proposes contrasting scenarios and
records the judgment, actor and conditions. A repeated choice supports those
cases only; it does not prove general translation fidelity. Disagreement may
expose an incorrect translation, ambiguity, changed intent or unclear rendering.

The LLM orchestrates tool use within the active roles' capabilities. A Read-only
PO asks its parent for execution; it does not acquire Bash or install authority.
DES constructs existing structured documents; this skill introduces no new DES
command and no solver-controlled route.

## Availability and installation

The execution owner probes `quint --version`, including a configured local binary
when applicable. If unavailable, explain its purpose and offer a host-appropriate
installation once, as for Agda. Install only with authorization; preserve an
earlier acceptance or refusal. Check the host's Node/npm availability and the
official Quint installation instructions before suggesting commands.
On refusal or unsupported tooling, continue ordinary scenario discussion and
mark formal exploration unavailable. Never present invented traces as tool output.

## Model to human review

- Select a concrete operation pair and observation; where M2 is in use, identify
  its candidate relation. One example pair does not establish a general law.
- Separate recorded human choices from modeler assumptions. Timing needs an
  explicit clock/unit; simulation steps alone are not seconds. Name delivery,
  fairness and failure-detection assumptions rather than hiding them.
- Generate traces from the actual model. Retain model identity, tool version,
  command, seed/bounds and raw trace. Simulation is not exhaustive verification;
  Quint exploration does not establish FRET realizability or conflict diagnosis.
- Use a verified deterministic renderer with explicit domain action templates.
  Show actors, order, actual versus observed state, time and relevant conditions.
  Preserve trace indices and model identity; disclose any prefix or projection.
  Unsupported actions are reported, never filled in with invented narration.
  If no suitable renderer is available, report that integration gap.
- Let the human review the readable scenarios without reading Quint or formulas:
  correct, incorrect, depends, unclear, or a proposed correction. Show assumptions
  and allow challenging the wording itself; do not preselect acceptance.
- Record the judgment against the exact model/scenario. An open question remains
  open; silence is not approval. Revise the model after an actual decision, then
  generate fresh scenarios for review. Keep automated review distinct from the
  human's semantic judgment and respect explicitly delegated collaboration mode.

Tool reference: https://quint.sh/docs/quint

## DISCUSS integration and HTML

The PO supplies the unresolved product question and the actor's observations.
The host selects a model-capable helper for the bounded Quint work and executes
within authorized tooling. The helper owns the model and raw trace evidence;
it does not decide product intent. Return model assumptions explicitly to the PO.

Render trace events through domain templates, then share the readable scenario
in the local nWave HTML view using `nw-doc-as-artifact`. This has two distinct
transformations: trace-to-domain-scenario (must preserve events mechanically)
and document-to-branded-HTML (the existing shared renderer). The HTML renderer
alone does not implement the trace transformation. If that first component is
absent, report it instead of writing an LLM paraphrase and calling it mechanical.

After actual feedback, the PO supplies the revised DISCUSS semantic input to the
host. Preserve the decision (or, in auto mode, the unreviewed status), conditions, assumptions and open doubts in `decisions`, and the
generated scenarios in the required `quint_scenarios` section of `schema_version` 2 (model path and
identity, tool name/version/command, trace path, events with `trace_index`). Keep
seed and bounds in `tool.command`, or in the trace artifact's own metadata; no
extra field exists. Without real tool output send `{"status": "not_run"}`;
`des discuss --describe-input` shows the exact shape. DES constructs the brief; the host renders
its updated view. Re-explore a changed model before reusing old scenario feedback.
No automatic installation, model approval, wave transition or runtime proof.
