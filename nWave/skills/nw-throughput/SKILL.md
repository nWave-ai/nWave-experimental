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

## Move 0: one sub-orchestrator per worktree — don't BE the bottleneck (ratified 2026-07-19)

Before the five moves below: the main orchestrator itself is a serial resource. Personally
driving each worktree's slice-by-slice loop (reading files, dispatching one phase, waiting,
dispatching the next) turns the orchestrator into exactly the bottleneck ToC says to route
around. For EVERY active worktree carrying multi-slice feature work, dispatch ONE
sub-orchestrator agent (`general-purpose`, full tool access including `Agent`/`SendMessage`) that
owns the ENTIRE per-slice spine for its feature (DISTILL → entry-gate → A_GREEN → EXAMINE →
COMMIT, repeated per slice) PLUS its worktree's mechanical cleanup once merge-back succeeds —
dispatching its OWN crafter/acceptance-designer/examiner agents via `des dispatch`, never a
passthrough. **It does NOT run its own feature-end cycle.** Per `parallel-work-cleans-up-after-
merge-back`'s own design: a slice's cleanup ends at merge-back; feature-end is decided
SEPARATELY, LATER, POSSIBLY BATCHED across several ready features
(`many-features-close-for-one-full-suite`, epic-delta.md row 6 — status `pending`, the
N-feature-id batched CLI does not exist yet). Paying the full-suite/deep-review/env-e2e cost once
per sub-orchestrator instead of once per BATCH is exactly the waste row 6 exists to eliminate. A
sub-orchestrator finishes at "all slices SliceCommitVerified, worktree cleaned" and reports that —
the main orchestrator decides WHEN to close the feature-end for one feature or a batch of several
together (today: N separate `des feature-end run` calls, run back-to-back in the SAME decided
window since the batched CLI isn't built — still one deliberate closing decision, not N
independent ones). It reports back only at genuine decision points (ambiguous design call, gate
refusal needing human judgment, a defect in a DISTILL-owned artifact), not after every mechanical
step. **Trunk-writing
is consolidated under exactly ONE sub-orchestrator at a time** — two peers independently mutating
the same shared tree race each other and can corrupt an in-flight whole-tree gate; when several
features' remaining work all lands on trunk, bundle them under one trunk-completion
sub-orchestrator instead of one per feature. Features with their own isolated worktree (no trunk
dependency yet) get independent sub-orchestrators freely — dispatched BATCHED in one message when
independent (true parallel fan-out), never dispatch-then-wait-then-dispatch-next. The main
orchestrator's job narrows to: identify which worktrees need a sub-orchestrator, fan them out, and
synthesize/triage what they escalate. Full canonical writeup:
`docs/epic/swarm-parallel-delivery/epic-delta.md` §Operating model.

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
   check resources (**MemAvailable** above the gate's own floor ∧ load < ~cores×2); if not,
   wait a bounded window with progress. **The SSOT for the exact threshold is the code, not
   this line**: `run_contract_gate._read_mem_available_mib` / `_DEFAULT_MIN_MEM_AVAILABLE_MIB`
   (~700 MiB today, and `NWAVE_BUILD_TIER_MIN_MEM_AVAILABLE_MIB` overrides it) — do NOT copy
   that number here, POINT to it, so a threshold change never leaves this doc lying. Threshold
   on **MemAvailable** — the figure earlyoom watches and the gate already uses — **NOT MemFree /
   the `free -m` "free" column**, which excludes reclaimable page cache and reads ~5x lower: a
   box at 270 MB "free" but 6.7 GB MemAvailable is NOT starved, and holding it there is
   throughput lost to a wrong number. Read `MemAvailable:` from `/proc/meminfo` (or `free -m`
   **"available"** column), never "free". A gate killed by
   resources is **INDETERMINATE-with-retry, NEVER a red** — distinguish a resource kill
   (137/143, aborted run) from a genuine failure. **The trigger is MemAvailable, not load.**

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

## Tool-output discipline in dispatch prompts (C7)

A dispatched agent defaults to reading whatever a command prints straight into its own
context — a 33-minute whole-tree suite, a large file, a wide grep — unless its dispatch
prompt explicitly tells it otherwise. Measured on a live orchestration (2026-07-20): one
long-running gate-owning agent's transcript held 275KB of raw `tool_result` content across
123 calls, median 745 bytes but a ~20-item tail of 5-45KB dumps — the same information a
`tail -N` / `grep` pass would have delivered in a fraction of the size, carried forward and
re-billed on every subsequent turn once it enters context (conversation length compounds
this — it is not a one-time cost).

**THE RULE: never let a dispatched agent `cat`/read a large or long-running command's raw
output. Redirect to a file, read back only the tail/grep/summary.** This is GDP-2 (inline
guidance at the authoring surface, not a reactive fix after the fact) applied to dispatch
prompts specifically — the orchestrator states the redirect-and-tail pattern IN the prompt,
every time it hands off a command that could produce more than a screenful:

```
NWAVE_GATE_JOBS=serial uv run des run-contract-gate --repo . >> gate.out 2>&1 &
# then poll with: tail -30 gate.out   (never `cat gate.out`)
```

Applies to: whole-tree/full-suite gate output, `pytest`/build logs, `find`/`grep` over a
large tree, reading an entire source file when only one function is relevant (use
line-ranged Read or a targeted grep instead). Does not apply to short, bounded outputs
(`--help`, a single ledger record, a small diff) — the rule is about UNBOUNDED or
LARGE-BY-CONSTRUCTION output, not every tool call.

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
