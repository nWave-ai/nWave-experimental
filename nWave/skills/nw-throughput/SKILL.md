---
name: nw-throughput
description: How to maximize delivery throughput while driving the nWave spine — the Theory-of-Constraints insight (the box, not the agents), the N-cloud-ONE-box resource-aware pipeline, and the re-runnable measure. Load when orchestrating multi-slice/multi-feature delivery.
user-invocable: true
---

# nw-throughput — maximize delivery throughput on the nWave spine

Operational distillation of the empirical throughput study
`docs/analysis/throughput-and-gate-design-insights-2026-07-10.md` (SSOT + evidence:
n=214 consecutive `SliceCommitted` intervals across 71 features, ledger-measured, not
estimated). Load this when you are the ORCHESTRATOR fanning wave/gate work across
slices or features — it is how you keep the pipeline full without tripping the box.

## The constraint (Theory of Constraints): the BOX, not the agents

- **LLM-bound stages run in the CLOUD, parallel almost for free**: RCA, charter (PO),
  AT-authoring (acceptance-designer), crafter A_GREEN, Vera examine, review.
- **Box-bound stages contend for CPU/RAM on the local cores**: `des commit-slice`,
  BuildTier, whole-tree suite, wheel-build, env-e2e. Under memory pressure they emit
  **FALSE-RED** — a subprocess OOM/earlyoom-killed (SIGKILL/137/143) reported as a
  test failure. The bottleneck is the box, never the agent count.

**THE RULE: N cloud LLM lanes, ONE box lane, resource-aware.**

## The five moves (ordered by ToC leverage)

1. **Serialize the box, fan out the cloud.** At most ONE box-bound gate runs at a time.
   Run every LLM stage (RCA ∥ charter, AT-authoring, crafter, Vera, review) concurrently.
   A swarm never multiplies the box — it only multiplies the cloud.

2. **Pipeline the cloud across slices (C2).** Author AT(N+1) + charter(N+1) in the cloud
   WHILE the crafter greens slice N. ~4-5' hidden per slice. Never block slice N+1's cloud
   work on slice N's box work.

3. **Scope the box per-slice (C1).** The per-slice seal digests only the ENTERING slice's
   regression test + light always-on invariants; the whole-tree tier defers to feature-end.
   Running the whole tree per-slice is the JIT poison that forbids pipelining. Seal 3-10' → 1-2'.

4. **Resource-aware box launch (C3 / GDP-6 starvation-class).** BEFORE a heavy box gate,
   check resources (free RAM > ~700 MB ∧ load < ~cores×2); if not, wait a bounded window
   with progress. A gate killed by resources is **INDETERMINATE-with-retry, NEVER a red** —
   distinguish a resource kill (137/143, aborted run) from a genuine failure. **The trigger
   is RAM, not load.**

5. **Verify per-slice with Vera-Haiku (C4), not a continuous review loop.** Vera-Haiku
   examines each slice's charter at Haiku cost; the deep review is a feature-end panel
   (Haiku ∥ per-lens + adversarial verify), not a running crafter↔review loop. −40-60%
   verification tokens at scale (baseline: 93 PASS / 11 FAIL / 2 IND over 60 features).

## Avoid the ceremony tax (C6)

Rejection roundtrips are measurable ceremony (~3 rejections/day ≈ 20' + lost context).
Surface the affordance (accepted tokens, WHERE an annotation goes) INLINE at the authoring
surface (GDP-2), not only in the gate's rejection message. GENERATE the checked artifact with
its producing tool (`des dispatch` for the crafter envelope, `des feature-delta-doctor` before
DISTILL) — never hand-assemble what a gate will check (GDP-5, cost on the system).

## The measure (re-runnable, identical)

`SliceCommitted` events from `.nwave/telemetry/atdd-pure/*.jsonl`; gaps between consecutive
timestamps per feature; window 1'–10h; post-fix comparison uses only intervals after the tag.
Baseline 2026-07-10: **median 35'/slice · p25 14' · p75 78' · p90 159'** — the TAIL is the
problem, not the median. Target after the C1–C7 corrections: median ~12-14', p90 ~20',
throughput ~2.5×.

## When NOT to optimize

Speed is a means, not the goal: quality is superhuman, velocity human-competitive. Never
trade a real gate (execution-observing floors, Vera examine, the seal) for speed — those are
the fixed floor. Optimize the CEREMONY around them (hand-assembly, whole-tree-per-slice,
false-red retries, roundtrips), never the substance.
