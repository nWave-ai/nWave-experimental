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
