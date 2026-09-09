---
name: nw-throughput
description: Evidence-led orchestration for maximizing delivery throughput with independent fan-out, one heavy local box, and concise whole-value evidence.
user-invocable: true
---

# nw-throughput

## Constraint

The bottleneck is usually the shared machine or a causal boundary, not the
number of available agents. Keep cloud reasoning busy while allowing at most
one heavy local build/test/install workload. Measure load and stop adding lanes
when contention increases end-to-end wall time.

## Strategy

1. Select the nearest measurable constraint and shortest falsifier.
2. Fan out only independent work with disjoint ownership in detached worktrees.
3. Keep one heavy local build/test/install box; serialize its use.
4. Fan in on the whole delivered value. Keep required review, EXAMINE,
   integration, observation and cleanup; the orchestrating LLM chooses and
   invokes them, while DES persists typed facts and advisory `NEXT` data.
5. Measure wall time, cost, tokens, retries, tool calls, and human
   intervention against the outcome.

## Feature evolution before cleanup

After the LLM has completed whole-feature review and required evidence, it runs
`des lane integrate --repo-root ROOT --worktree PATH --keep-worktree`; after
that whole-feature integration it invokes `des evolution --repo-root ROOT
--input -` once on destination `ROOT` before cleanup. Never invoke it per slice;
DES does not impose a completion gate. The
closed v1 JSON carries `schema_version`, explicit `date` (`YYYY-MM-DD`) and
`feature_id`, `purpose`, `key_decisions`, `delivered_work`,
`verification_results`, `problems`, `lessons`, and `durable_artifacts`.
Problems and lessons use explicit applicability plus a nonblank reason; use
`not_applicable` rather than invented content. Destinations default to
`docs/evolution/YYYY-MM-DD-{feature-id}.md` and use
`documents.evolution.destination` from unified global configuration with a
project override. On resumed finalization retry the exact same input; it is
idempotent. This command invokes no provider and does not choose a phase,
feature size or cleanup action.

Example shape: `{"schema_version":1,"date":"2026-09-09","feature_id":"feature-id","purpose":"...","key_decisions":["..."],"delivered_work":["..."],"verification_results":["..."],"problems":{"applicability":"not_applicable","reason":"...","items":[]},"lessons":{"applicability":"applicable","reason":"...","items":["..."]},"durable_artifacts":[{"label":"evidence","path":"docs/evidence.md"}]}`. Artifact paths are repository-relative or HTTPS.

Preserve and commit the generated evolution document and its evidence on `ROOT`
before cleanup, then explicitly run `des lane finalize --repo-root ROOT
--worktree PATH`. Finalize only removes a clean lane whose tip is already
reachable from `ROOT`; it never merges or reintegrates. The destination may have
advanced with the evolution-document commit after integration. LLM chooses these
commands; `NEXT` remains advisory.

For features and bugfixes alike, the orchestrating LLM evaluates and revises
S/M/L from current evidence, selects applicable waves and upstream corrections,
and may ignore `NEXT`. DES does not use a size label to route or execute work.
