---
name: nw-throughput
description: Evidence-led orchestration for maximizing delivery throughput with causal fan-out, associative boundary composition, one heavy local box, and concise terminal evidence.
user-invocable: true
---

# nw-throughput

## Constraint

The bottleneck is usually the shared machine or a causal boundary, not the
number of available agents. Keep cloud reasoning busy while allowing at most
one heavy local build/test/install workload. Measure load and stop adding lanes
when contention increases end-to-end wall time.

## Fan out only independent work

Freeze the shared interface first, then assign disjoint file ownership in
isolated worktrees. Good parallel work includes independent RCA hypotheses,
architecture reviews, oracle reviews, documentation projections and separate
delivery segments whose dependencies are explicit. Never parallelize two
writers over the same authority or an implementation before its oracle exists.

## Compose boundaries as a segment tree

For ordered boundaries `A -> B -> C -> D`, validate disjoint pairs in parallel:

```text
(A+B) || (C+D)
        ->
   (A+B+C+D)
```

Each pair returns a compact certificate containing input/output identities,
preserved obligations, terminal observations and verdict. Compose certificates
associatively only when identities join. `PASS` is identity, `FAIL` is
absorbing and `INDETERMINATE` prevents global PASS. Pairwise PASS never implies
global PASS without the composition check.

## Delivery scheduling

1. Find the nearest measurable constraint and its shortest falsifier.
2. Run several independent candidate probes when they answer the same question
   without sharing mutable files or the heavy box.
3. Stop losing candidates early; integrate only the best falsified survivor.
4. Serialize exact command execution, release-shaped installation and other
   heavy box work.
5. Run one whole-delivery source-blind EXAMINE and one finalize after the
   composed candidate, not once per internal segment.
6. Record wall, processed tokens and cost from terminal telemetry. Setup,
   waiting and retries are friction evidence but do not replace end-to-end
   delivery time.

## Long-session loops

Loops are opt-in and off by default. Explain WHAT they monitor, WHY the long
session benefits and HOW to stop them before asking consent. Arm only after
explicit acceptance and verify the scheduler actually registered them. Use
event-driven or sparse checks; never inject a large recurring prompt. A loop
suggests the next falsifier and consolidates evidence but cannot override the
durable authority or `DeliveryContract`.

## Hygiene

An idle agent is not a completed artifact. Verify diff and terminal evidence,
then integrate or explicitly reject it. At each convergence point inventory
worktrees, reconcile every valuable diff, remove completed temporary worktrees
and leave no unowned WIP. Never trade disk/process hygiene for apparent lane
count.
