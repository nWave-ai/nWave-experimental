---
name: nw-agent-evals
description: Lightweight eval method for testing nWave AGENTS and SKILLS (LLM behavior) as a lean alternative to heavy BDD/ATD. An eval = one prompt -> one captured run (trace + artifacts) -> a small set of checks -> a comparable score over time. Load when validating agent behavior, building a regression net for an agent/skill, or reducing agent-test bloat.
user-invocable: false
disable-model-invocation: true
---

# Agent Evals

## Why this exists

Agents are LLMs — non-deterministic. Traditional BDD/unit testing tests them *badly* and breeds bloat (measured: 294K test LOC, 5.5:1 test:src, step reuse 1.10x vs >=4x target). Evals are the lean way to verify agent behavior: a few targeted signals instead of a monolithic spec.

This skill is the **antithesis of ATD over-specification**. Keep it small. The anti-pattern is up-front exhaustive specification — that IS the bloat.

| | `nw-agent-testing` (sibling skill) | `nw-agent-evals` (this skill) |
|---|---|---|
| Form | static 5-layer manual checklist | executable dataset + grader + score over time |
| Use | one-shot design review of a spec | repeatable regression net for behavior |
| Output | pass/fail judgement | comparable score, trend across runs |

Use both: `nw-agent-testing` to vet the spec, `nw-agent-evals` to watch behavior over time.

## What an eval is

One eval = **prompt -> run -> checks -> score**.

- **prompt** — a single input that should (or should NOT) trigger the agent/skill.
- **run** — one provider turn through the selected nWave adapter, with its
  available native evidence and artifacts captured.
- **checks** — a small set of targeted assertions (not one monolithic check).
- **score** — a comparable number you can track across runs to catch regressions.

Replaces "vibes" with measurable signals: *did it invoke the right skill, run
the expected tools, respect the conventions and produce the required observable
effect?* Never grade a terminal-text grammar as a behavioral outcome.

## Definition of Done — before you write the eval

Write the success criteria FIRST, before implementing the agent/skill or its eval. Four check categories:

| Category | Question | Graded by |
|---|---|---|
| OUTCOME | Did the task get completed through its public effect or provider-enforced semantic outcome? | deterministic |
| PROCESS | Was required skill delivery or use evidenced, with only behavior-relevant tool observations? | deterministic |
| STYLE | Does the output respect nWave conventions (sections, format)? | model-graded |
| EFFICIENCY | No useless commands / no token blowup? | deterministic |

If you cannot state DoD before writing the skill, the skill's job is not yet defined — stop and define it.

## Workflow

Run these steps in order:

1. **Define success first** — write a small set of falsifiable checks in the
   four categories above.
2. **Use one representative probe when needed** — capture the provider-native
   evidence that the selected adapter actually exposes.
3. **Add only the cases needed** — include a positive case and a relevant
   negative control; grow the set from observed failures.
4. **Grade deterministic evidence** — check public effects, admitted tool
   evidence, and structured artifacts. Do not derive a verdict from terminal
   prose.
5. **Grade semantic quality separately** — use the provider-enforced structured
   result and retain narrative feedback only as diagnostic evidence.

## Capturing provider evidence

The selected adapter owns the provider projection. Claude roles run through
the Claude adapter; Codex roles run through the Codex adapter's `codex exec`
projection. Do not substitute one provider's trace shape, tool names, or
launcher for the other's.

Distinguish these three facts when evaluating a skill:

| Fact | Evidence | What it establishes |
|---|---|---|
| **Preloaded knowledge** | The role declares the skill in frontmatter and `load_role_instructions` materializes it in the provider instruction. | The role received the skill before the turn. It creates no native `Read` event. |
| **Native read** | A provider-native tool event reads a conditional `SKILL.md` path. Claude's existing transcript tracker records this form. | The turn fetched that file on demand. It does not prove that the knowledge affected the result. |
| **Actual use** | A predicted, observable effect or a capability-specific tool/result is present, with no simpler explanation. | The role applied the skill sufficiently for this eval. A catalog entry, preload, or `Read` alone is insufficient. |

The adapter returns a provider-enforced structured terminal result for semantic
facts. Its stdout, stderr, recorder entry, and any provider-native tool trace
are provenance or diagnostic evidence; do not parse model-authored prose into
control flow. For a Claude subagent transcript, reuse
`des.application.skill_tracking_service.read_transcript_tool_calls` rather
than creating another JSONL parser. For Codex, inspect only the JSONL events and recorder evidence
that its adapter preserves. If the required observation is absent on the
selected provider, report that check as **INDETERMINATE**; do not infer it from
another projection.

Check an artifact on disk as well as its reported tool event. Only ask for a
tool when the behavior requires it. Tool order and an exact command sequence
are not general quality signals.

## Deterministic graders (nWave-native signals)

Parse the trace, assert mechanically. nWave-specific, high-value signals:

| Signal | Assertion | Why it matters |
|---|---|---|
| Declared preload | resolved role instruction contains the declared skill once | verifies delivery of resident knowledge, not its use |
| Conditional read | native `Read` event for the resolved skill path, where the provider exposes one | verifies on-demand fetch, not semantic use |
| Capability-specific behavior | required public effect or justified tool/result is present | tests actual application of the skill |
| Semantic outcome observed | provider-enforced outcome plus the required public effect are present | separates semantic judgement from terminal serialization |
| Artifact structure | the DES-produced document contains required sections and facts | checks durable outcome without asking the model to author it |
| Efficiency | compare only a measured, relevant excess such as duplicate calls | avoids arbitrary ceilings |
| Negative control | the unsupported behavior or unnecessary skill effect is absent | guards against over-eager invocation |

Bind to the code-fact CLI where useful: e.g. assert the agent invoked `des code-fact query.callers-of` rather than relying on a catalog entry (catalogued != wired). Note that feature-level change-scope analysis has no stable CLI today — an eval must not demand a capability the production CLI does not expose, or it grades the tooling rather than the agent.

## Qualitative grader (model-graded rubric)

For STYLE / design-quality / review-quality (not mechanically checkable), bind
the provider's structured-output facility to the existing rubric schema. The
model supplies semantic judgements; the provider validates the ephemeral
result and the adapter maps it to host types. Do not place a JSON template in
the prompt or parse terminal prose. Narrative notes remain diagnostic.

```json
{
  "overall_pass": true,
  "score": 0,
  "checks": [
    {"id": "adr-has-context-section", "pass": true, "notes": ""},
    {"id": "tradeoffs-quantified",   "pass": false, "notes": "no numbers"}
  ]
}
```

Rules: keep the rubric small, make each check single-purpose, and have
`notes` cite evidence. Provider-validate the structured result so an invalid
grading turn fails closed rather than passing on vibes.

When behavior under eval supplies a DESIGN decision, the LLM returns semantic
facts in its structured result. DES constructs the durable document through
its existing producer from those facts. Evaluate the boundary as two linked
observations: facts are valid for the request, then the DES-produced document
contains them. The LLM does not author a durable ADR or brief.

For an EXAMINE eval, preserve the source-blind boundary. Give the examiner the
available observation packet, not source access; an absent observation remains
**INDETERMINATE** rather than becoming an inferred pass or failure.

## Dataset

Use the smallest CSV dataset that covers the observed positive behavior and a
relevant negative control. Minimum columns:

```csv
id,prompt,should_trigger,expected_skill,expected_observation,notes
ev-01,"Provide semantic design facts for X",true,nw-design-patterns,"accepted facts; DES producer constructs durable document",explicit
ev-07,"Just fix this typo",false,,,"negative control - no design facts"
```

- Mix: explicit-invocation, implicit-from-description (does `description` alone trigger it?), contextual, and NEGATIVE-CONTROLS (`should_trigger=false`).
- `name` + `description` are the PRIMARY invocation signal — implicit rows test exactly that.
- Coverage grows from real failures, never speculatively.

## Where evals live

```
tests/evals/<agent-or-skill-name>/
  dataset.csv          # the prompt set
  rubric.json          # model-graded rubric (JSON-Schema)
  README.md            # DoD + how to run
  runs/                # captured transcripts + scores per run (gitignored or pruned)
```

Reuse the existing `tests/evals/` facility; do not create a new general
harness. Keep raw provider records out of committed bloat unless a test needs a
small, scrubbed fixture.

## Principles

1. **Define success before you write the skill** — no DoD, no skill.
2. **Small targeted checks beat monolithic ones** — many cheap signals catch regressions early; one giant assertion hides them.
3. **Every manual fix is a future eval** — coverage is earned from observed failures.
4. **Negative controls are mandatory** — an agent that fires when it shouldn't is as broken as one that doesn't fire.
5. **name + description are the invocation contract** — test them, don't bypass them with explicit invocation only.
6. **Least privilege** — eval graders are read-only over traces + artifacts.
7. **Stay lean** — over-specifying up front recreates the ATD bloat this method exists to avoid.

## Example: eval for `nw-solution-architect`

DoD — the architect returns valid semantic design facts for a design request.
When structural code facts are necessary and the role can obtain them, they
are provider-labelled and support the decision. DES then constructs the ADR;
the architect never authors it.

Dataset rows (excerpt):

```csv
id,prompt,should_trigger,expected_skill,expected_observation,notes
sa-01,"Provide design facts for the handoff-state-algebra feature",true,nw-design-patterns,"accepted facts; DES-produced ADR contains the facts",design
sa-02,"What ADRs exist for the gate layer?",true,,"provider-labelled code facts support the answer when code facts are needed",lookup
sa-03,"Rename this variable to camelCase",false,,,negative control - not an architecture task
```

Deterministic grader (over the captured trace + artifact):

- DELIVERY: the role's resolved instruction contains the declared preload once;
  a conditional native read is checked only when this case requires it.
- OUTCOME: the provider-enforced result has valid semantic facts for the
  requested decision.
- OUTCOME: the existing DES producer constructs an ADR that contains those
  facts and required sections (`## Context`, `## Decision`, `## Consequences`).
- EVIDENCE: when structural analysis is necessary, its provider and confidence
  labels support the decision; do not demand a fixed shell spelling or order.
- NEGATIVE (sa-03): no architecture facts or durable-design production occurs.

Model-graded rubric (STYLE/quality):

```json
{
  "overall_pass": false,
  "score": 70,
  "checks": [
    {"id": "context-states-problem", "pass": true,  "notes": "clear problem framing"},
    {"id": "decision-is-singular",   "pass": true,  "notes": ""},
    {"id": "consequences-quantified","pass": false, "notes": "tradeoffs qualitative only"}
  ]
}
```

Score = deterministic checks (binary, weighted) + rubric `score`, tracked per
comparable run. A missing required fact, DES document, or relevant supporting
observation flags a regression; unavailable evidence is reported as
**INDETERMINATE**.
