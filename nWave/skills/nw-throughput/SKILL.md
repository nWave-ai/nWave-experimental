---
name: nw-throughput
description: How to maximize delivery throughput while driving the nWave spine — the Theory-of-Constraints insight (the box, not the agents), the N-cloud-ONE-box resource-aware pipeline, and the re-runnable measure. Load when orchestrating multi-slice/multi-feature delivery.
user-invocable: true
---

# nw-throughput — maximize delivery throughput on the nWave spine

Ledger-measured methodology for keeping the delivery pipeline full without tripping the
local machine. Load this when you are the ORCHESTRATOR fanning wave/gate work across
slices or features.

## Standing loops arm by default — and they route DRAINS, not just delivery

The standing consolidation loops are ON by default (the human opts OUT). They are session-scoped:
a restart, crash, or killed session disarms ALL of them SILENTLY, so re-check with the real tool
(`CronList`/`TaskList`) on every SessionStart and re-arm what is missing — a remembered "I armed
them" describes a session that may no longer exist.

Throughput is NOT only parallel swarm delivery. The loops also route the two DRAINS, and both are
first-class throughput work, not a side chore:
- **tech-debt drain** — `des refactor --pile techdebt.md`, one item per isolated worktree+venv.
- **bugfix drain** — each pending `defects.md` row driven through `/nw-bugfix` end-to-end in its
  own isolated worktree (RCA → t=0 charter → regression AT → GREEN → Vera examine → commit).

Same box discipline applies: N cloud lanes fan out, ONE box lane serialized, resource-aware. A
drain is a tree-writing lane — it MUST run in its own worktree, never in trunk.

## Default: parallel, in the background, unless the user says otherwise

Dispatch agents and commands in the BACKGROUND by default, and maximize how much runs
concurrently — never dispatch-then-wait-then-dispatch-next when the work is genuinely
independent. Only serialize when there is a real reason to (see below): a shared box
resource, or two lanes that touch the same files. Absent one of those, more parallelism
is always the default, not something you ask permission for — the user opts OUT of
parallelism explicitly if they want serial/foreground work, not the other way round.

### Fan-out is a scheduling invariant, not an optional optimization

After every phase transition, completion, refusal, new artifact or changed dependency,
the orchestrator MUST recompute the feature's slice/lane DAG and immediately dispatch
every ownership-safe READY cloud lane until cloud capacity is full or no READY lane
remains. Waiting for the current slice to finish while an independent charter, DISTILL,
JIT-analysis, review or downstream-preparation lane is READY is
`UNUSED_PARALLELISM` — an orchestration defect, not a conservative choice.

**Dependencies attach to consumed artifacts, not whole-slice completion.** A
`depends-on slice-N` declaration blocks only work that consumes an unstable output of
slice N. It MUST NOT become a whole-slice barrier for work whose inputs are already
stable: charter authoring from accepted product intent, DISTILL from stable contracts,
source inventory/JIT analysis, independent intra-slice lanes, or generation of later
DES dispatches. A slice boundary is not a synchronization barrier; only an unmet
artifact dependency, explicit file conflict or box constraint is.

At each scheduling point:

1. Mark every lane `READY`, `BLOCKED_BY_ARTIFACT`, `BLOCKED_BY_FILE`, `RUNNING`, or
   `DONE`.
2. Partition READY work into cloud lanes and the single box lane.
3. Dispatch READY cloud lanes in dependency order until all cloud slots are occupied.
4. Queue — never overlap — box-lane work.
5. Pipeline slice N+1 charter/DISTILL while slice N is in `A_GREEN` or EXAMINE.
6. Recompute immediately when any lane emits an artifact or finding.

The target is a **saturated dependency-safe pipeline**:
`running_cloud = min(available_cloud_slots, ready_cloud_lanes)`, with at most one
running box lane. If a cloud slot remains idle while READY work exists, record the
specific reason; silence is a defect. Before dispatch, surface a compact snapshot:

```text
RUNNING: slice-00/A_GREEN
READY:   slice-01/H0-DISTILL, slice-01/R0-DISTILL, slice-04/charter
BOX:     idle
BLOCKED: slice-02/A_GREEN <- slice-01/preservation-contract
```

Then fill every READY cloud slot. Fan out both **between slices** and **inside a
slice** when sub-lanes have disjoint ownership and stable inputs.

## The constraint (Theory of Constraints): the BOX, not the agents

- **LLM-bound stages run in the CLOUD, parallel almost for free**: RCA, charter (PO),
  AT-authoring (acceptance-designer), crafter A_GREEN, Vera examine, review. Maximize
  these — dispatch every independent one in a single batched call, in the background.
- **Box-bound stages contend for CPU/RAM on the local machine**: `des commit-slice`,
  BuildTier, whole-tree suite, wheel-build, env-e2e. Under memory pressure they emit
  **FALSE-RED** — a subprocess OOM-killed (SIGKILL/137/143) reported as a test failure.
  This is the ONE class of work you isolate to one-at-a-time — the bottleneck is the
  box, never the agent count.

**THE RULE: N cloud LLM lanes, ONE box lane, resource-aware. Parallelize everything
else by default.**

## Move 0: one sub-orchestrator per worktree — parallelize, don't BE the bottleneck

Before the five moves below: the main orchestrator itself is a serial resource. Personally
driving each worktree's slice-by-slice loop (reading files, dispatching one phase, waiting,
dispatching the next) turns the orchestrator into exactly the bottleneck ToC says to route
around. For EVERY active worktree carrying multi-slice feature work, dispatch ONE
sub-orchestrator agent (background, full tool access including further dispatch) that owns
the ENTIRE per-slice spine for its feature (DISTILL → entry-gate → A_GREEN → EXAMINE →
COMMIT, repeated per slice) PLUS its worktree's mechanical cleanup once merge-back succeeds
— dispatching its OWN crafter/acceptance-designer/examiner agents via `des dispatch`, never
a passthrough. **It does NOT run its own feature-end cycle** — a slice's cleanup ends at
merge-back; feature-end is a SEPARATE, LATER decision (possibly batched across several
ready features, to pay the full-suite/deep-review/env-e2e cost once instead of once per
feature). A sub-orchestrator finishes at "all slices committed and verified, worktree
cleaned" and reports that — the main orchestrator decides when to close feature-end for one
feature or a batch together. It reports back only at genuine decision points (ambiguous
design call, gate refusal needing human judgment, a defect in an upstream-wave artifact),
not after every mechanical step. **Trunk-writing is consolidated under exactly ONE
sub-orchestrator at a time** — two peers independently mutating the same shared tree race
each other and can corrupt an in-flight whole-tree gate; when several features' remaining
work all lands on trunk, bundle them under one trunk-completion sub-orchestrator instead of
one per feature. Features with their own isolated worktree (no trunk dependency yet) get
independent sub-orchestrators freely — dispatched BATCHED in one message when independent
(true parallel fan-out, in the background), never dispatch-then-wait-then-dispatch-next.
The main orchestrator's job narrows to: identify which worktrees need a sub-orchestrator,
fan them ALL out at once, and synthesize/triage what they escalate.

## The five moves (ordered by ToC leverage)

1. **Serialize the box, fan out the cloud.** At most ONE box-bound gate runs at a time.
   Run every LLM stage (RCA ∥ charter, AT-authoring, crafter, Vera, review) concurrently.
   A swarm never multiplies the box — it only multiplies the cloud.

2. **Pipeline the cloud across slices (C2).** Author AT(N+1) + charter(N+1) in the cloud
   WHILE the crafter greens slice N. ~4-5' hidden per slice. Never block slice N+1's cloud
   work on slice N's box work. This is mandatory whenever those lanes are READY, not a
   discretionary speed-up.

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
   (Haiku ∥ per-lens + adversarial verify), not a running crafter↔review loop — cheap
   per-slice verification, expensive deep review only once at the end.

## Avoid the ceremony tax (C6)

Rejection roundtrips are measurable ceremony (~3 rejections/day ≈ 20' + lost context).
Surface the affordance (accepted tokens, WHERE an annotation goes) INLINE at the authoring
surface (GDP-2), not only in the gate's rejection message. GENERATE the checked artifact with
its producing tool (`des dispatch` for the crafter envelope, `des feature-delta-doctor` before
DISTILL) — never hand-assemble what a gate will check (GDP-5, cost on the system).

## Tool-output discipline in dispatch prompts (C7)

A dispatched agent defaults to reading whatever a command prints straight into its own
context — a long-running whole-tree suite, a large file, a wide grep — unless its dispatch
prompt explicitly tells it otherwise. A handful of large dumps in an otherwise-small
transcript can dominate its total size; the same information a `tail -N` / `grep` pass
would have delivered in a fraction of the size gets carried forward and re-billed on every
subsequent turn once it enters context.

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

## The measure (re-runnable)

`SliceCommitVerified` events from `.nwave/telemetry/atdd-pure/*.jsonl`; gaps between
consecutive timestamps per feature give the spacing distribution. **Verify the event name
against the ledger before trusting an empty result** — this line named `SliceCommitted` for a
long time, an event those ledgers do not carry, so the measure silently returned nothing and
looked like a repo with no history rather than a query with no subject. A distribution of
zero is a claim about your instrument first.

Look at the TAIL (p90), not just the median. A long tail means occasional collisions or
starvation, not a steady bottleneck — and that reading holds whether the median is slow OR
fast: a fast median with a p90 several times larger is the signature of contention, not of
speed.

**This measures CALENDAR SPACING, not slice cost, and the difference is not a footnote.**
The gap between two verified slices contains every minute nobody was working — nights,
breaks, waiting on a human. Filtering out gaps over some threshold removes session
boundaries and nothing subtler, so a long pause in the middle of the night still counts as
slice time. The median therefore overstates true per-slice work by an unknown amount and the
tail overstates it enormously. Two consequences worth stating before anyone quotes a number:

- a comparison against a baseline is only meaningful if the baseline was computed the SAME
  way; if that has not been checked, "X versus Y" is not yet a claim;
- turning this into a performance result requires a per-slice `started_at` recorded beside
  the verification timestamp. Without it, a quiet week and a fast week are indistinguishable
  in this distribution, and reporting the first as the second is the easiest false claim in
  the whole methodology.

Re-run after applying the moves above to confirm they moved the number — and re-state the
caveat every time the number is quoted, because a figure travels further than its footnote.

## When NOT to optimize

Speed is a means, not the goal: quality is superhuman, velocity human-competitive. Never
trade a real gate (execution-observing floors, Vera examine, the seal) for speed — those are
the fixed floor. Optimize the CEREMONY around them (hand-assembly, whole-tree-per-slice,
false-red retries, roundtrips), never the substance.
