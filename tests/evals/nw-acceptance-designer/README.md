# Eval: nw-acceptance-designer — consolidate-on-add behavior (slice-08)

slice-08 of `sustainable-test-suite` (DDD-7). EXTENDS the `nw-agent-evals` substrate
with ONE new deterministic grader row — it does NOT author a new eval framework.

## What it validates

The agent BEHAVIOR slice-07's metric can only SEE once declared: does an ATD/crafter run
actually CONSOLIDATE-ON-ADD — reuse the ATD-authored shared step vocabulary — when it adds
a slice? slice-07 added the `--consolidate-on-add` MODE + the gain calc to the gate; its
own scope note defers the agent behavior to eval. This slice closes that: an executable,
deterministic, git-free eval over a captured agent TRACE.

## Definition of Done (nw-agent-evals 4 categories)

| Category | Check | Graded by |
|---|---|---|
| OUTCOME | the grader emits a closed verdict for every trace | deterministic |
| PROCESS | signal #2 ("steps reuse the ATD-authored shared vocabulary") detected from `Write`/`Edit` tool_use entries — import-from-shared + reuse of an existing shared step definition + CONSOLIDATE/REUSE intent | deterministic |
| EFFICIENCY | git-free, no live dispatch, no network — trace-JSONL in, verdict out | deterministic |
| (no STYLE leg) | fully mechanical — no model-graded / prose-only check in this slice | n/a |

## The signal (mechanical, no prose-only)

- `consolidate-on-add` — a newly-authored step file IMPORTS the shared step/schema
  vocabulary module AND binds a declarative step to an EXISTING shared step definition
  (reuse, not re-declaration) AND the run declared a CONSOLIDATE/REUSE intent.
- `add-only` — fresh per-feature step definitions, re-declaring own constants/steps, no
  import-from-shared, no reuse, no CONSOLIDATE intent → the grader flags it.
- `indeterminate` — the trace cannot be parsed for the signal → degrade-LOUD, never a
  fabricated pass.

## Fixtures (the dataset, deliberately small)

- `fixtures/trace_consolidate_on_add.jsonl` — a captured ATD run that reused the shared
  vocabulary (signal #2 present) → expects `consolidate-on-add`.
- `fixtures/trace_add_only.jsonl` — a captured ATD run that only added fresh steps
  (signal #2 absent, negative control) → expects `add-only`.
- `fixtures/trace_empty.jsonl` — an empty/unparseable trace → expects `indeterminate`.

## Run

```bash
uv run pytest tests/evals/nw-acceptance-designer/ -o addopts="" -q
```

## Status

Active-RED at HEAD: `grade_consolidate_on_add` does not exist in the substrate yet, so all
3 scenarios fail with a clean `AssertionError` (MISSING_FUNCTIONALITY). DELIVER makes them
GREEN by adding the deterministic grader row (the crafter's contract, below).
```
