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
- **run** — one dispatch via the Claude Code `Agent` tool, with its trace + artifacts captured.
- **checks** — a small set of targeted assertions (not one monolithic check).
- **score** — a comparable number you can track across runs to catch regressions.

Replaces "vibes" with measurable signals: *did it invoke the right skill? run the expected tools? respect the conventions? produce the typed verdict?*

## Definition of Done — before you write the eval

Write the success criteria FIRST, before implementing the agent/skill or its eval. Four check categories:

| Category | Question | Graded by |
|---|---|---|
| OUTCOME | Did the task get completed? (artifact exists, verdict emitted) | deterministic |
| PROCESS | Was the right skill loaded + the expected tool/step sequence run? | deterministic |
| STYLE | Does the output respect nWave conventions (sections, format)? | model-graded |
| EFFICIENCY | No useless commands / no token blowup? | deterministic |

If you cannot state DoD before writing the skill, the skill's job is not yet defined — stop and define it.

## Workflow

Create these as TaskCreate items at the start; run in order.

1. **Define success first** — write the DoD (4 categories above) as concrete checks. Gate: every check is falsifiable.
2. **Manual trigger probe** — dispatch the agent once by hand to surface hidden assumptions. Gate: you have seen one real trace.
3. **Build the dataset** — 10-20 prompts in a CSV (see Dataset). Include explicit-invocation, implicit-from-description, contextual, and NEGATIVE-CONTROLS (`should_trigger=false`). Gate: >=2 negative controls present.
4. **Deterministic grading** — parse the captured trace (JSONL) -> assert on tools run, files created, step sequence. Gate: grader runs with zero human judgement.
5. **Qualitative grading** — model-graded rubric (JSON-Schema output) for STYLE/quality. Gate: rubric emits typed JSON, not prose.
6. **Grow coverage from failures** — every real failure/manual fix becomes one new eval row. Gate: regression net only grows from observed gaps, never speculatively.

## Capturing the trace (nWave mechanism)

nWave does NOT use `codex exec` — agents are dispatched via the Claude Code **`Agent` tool** (`subagent_type`, `prompt`); resume a spawned agent with **`SendMessage`**. The run is captured from the sub-agent's transcript (the `agent-*.jsonl` files in the transcript dir), which already exists:

- **Transcript JSONL** — each sub-agent run writes a JSONL transcript; the hook payload exposes its path as `agent_transcript_path` (the same field `src/des/.../hooks/skill_tracking_hooks.py:maybe_track_skill_loads` and `deliver_progress_handler.py` already consume). Each line is one event: `tool_use` (name + input), `tool_result`, assistant text.
- **What to parse from it**:
  - skill loaded? -> `Read` tool_use whose path matches `skills/.../SKILL.md` (this is exactly what `skill_tracking_hooks` scans for).
  - expected tools run? -> tool_use `name` values (e.g. `mcp__tsunami__callers_of` present, `Grep` absent).
  - files created? -> `Write`/`Edit` tool_use inputs + the artifact on disk.
  - sequence? -> ordered list of tool_use names.
- **Final message** — the agent's last assistant message is the eval's textual artifact (feeds the model-graded rubric).
- **Artifacts** — any file the agent wrote (ADR, review, design doc) is graded by existence + structure.

Capture pattern: dispatch via `Agent`, then read the transcript path + the on-disk artifacts. For a one-off eval you can dispatch and inspect the returned final message + written files directly; for a tracked net, persist the transcript alongside the dataset row.

## Deterministic graders (nWave-native signals)

Parse the trace, assert mechanically. nWave-specific, high-value signals:

| Signal | Assertion | Why it matters |
|---|---|---|
| Right skill loaded | `Read` of the expected `SKILL.md` appears | skill that is catalogued but never loaded = inferior output |
| Code analysis via Tsunami, not grep | `mcp__tsunami__callers_of` / `reads_of` present, `Grep` for the same intent absent | the standing Tsunami-first preference (degrade-LOUD if absent) |
| Typed verdict emitted | final message / artifact contains the agent's typed verdict shape (e.g. APPROVED/REJECTED/INDETERMINATE) | reviewer agents must not return prose-only |
| Gate respected | no bypass marker; expected gate/step trailer present | off-spine dispatch guard |
| Artifact structure | required sections present (grep the written file) | OUTCOME completeness |
| Efficiency | tool_use count within a ceiling; no redundant re-reads | token economy |
| Negative control | for `should_trigger=false`, the skill/tool was NOT invoked | guards against over-eager invocation |

Bind to detectors/Tsunami where useful: e.g. assert the agent used `mcp__tsunami__never_wired` to prove wiring rather than asserting from a catalog entry (catalogued != wired).

## Qualitative grader (model-graded rubric)

For STYLE / design-quality / review-quality (not mechanically checkable). The grader is a model call that MUST return typed JSON, not prose:

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

Rules: small rubric (3-7 checks), each check single-purpose, `notes` cites evidence. JSON-Schema-validate the output so a malformed rubric run fails closed rather than passing on vibes.

## Dataset

10-20 rows, CSV, small on purpose. Minimum columns:

```csv
id,prompt,should_trigger,expected_skill,expected_tools,expected_artifact,notes
ev-01,"Design the ADR for X",true,nw-design-patterns,"Write",docs/.../adr-*.md,explicit
ev-07,"Just fix this typo",false,,,,"negative control - architect must not fire"
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

`tests/evals/` (sibling to the 5-layer suite), NOT `docs/` — these are executable, not documentation. Keep `runs/` out of the committed bloat; commit the dataset + rubric + scores, not raw transcripts.

## Principles

1. **Define success before you write the skill** — no DoD, no skill.
2. **Small targeted checks beat monolithic ones** — many cheap signals catch regressions early; one giant assertion hides them.
3. **Every manual fix is a future eval** — coverage is earned from observed failures.
4. **Negative controls are mandatory** — an agent that fires when it shouldn't is as broken as one that doesn't fire.
5. **name + description are the invocation contract** — test them, don't bypass them with explicit invocation only.
6. **Least privilege** — eval graders are read-only over traces + artifacts.
7. **Stay lean** — over-specifying up front recreates the ATD bloat this method exists to avoid.

## Example: eval for `nw-solution-architect`

DoD — dispatching the architect on a design prompt must produce a structured ADR via the right skill, using Tsunami for code facts.

Dataset rows (excerpt):

```csv
id,prompt,should_trigger,expected_skill,expected_tools,expected_artifact,notes
sa-01,"Design architecture for the handoff-state-algebra feature; write the ADR",true,nw-design-patterns,"mcp__tsunami__callers_of,Write","docs/**/adr-*.md",explicit design
sa-02,"What ADRs exist for the gate layer?",true,,"mcp__tsunami__adr_section",,implicit code-fact lookup
sa-03,"Rename this variable to camelCase",false,,,,negative control - not an architecture task
```

Deterministic grader (over the captured trace + artifact):

- PROCESS: `Read` of `nw-design-patterns/SKILL.md` present.
- PROCESS: code facts came from `mcp__tsunami__callers_of`/`adr_section`, NOT `Grep`/`Bash grep`.
- OUTCOME: an `adr-*.md` was `Write`-n and on disk.
- OUTCOME: artifact contains the required ADR sections (`## Context`, `## Decision`, `## Consequences`).
- NEGATIVE (sa-03): architect did not author an ADR.

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

Score = deterministic checks (binary, weighted) + rubric `score`, tracked per run. A drop on `tsunami-not-grep` or `adr-sections-present` flags a behavioral regression before it ships.
