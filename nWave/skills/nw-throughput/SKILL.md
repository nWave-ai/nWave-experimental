---
name: nw-throughput
description: How to maximize delivery throughput while driving the nWave spine — the Theory-of-Constraints insight (the box, not the agents), the N-cloud-ONE-box resource-aware pipeline, and the re-runnable measure. Load when orchestrating multi-slice/multi-feature delivery.
user-invocable: true
---

# nw-throughput — maximize delivery throughput on the nWave spine

Ledger-measured methodology for keeping the delivery pipeline full without tripping the
local machine. Load this when you are the ORCHESTRATOR fanning wave/gate work across
slices or features. Each section below is a question to put to yourself before and during
that fan-out — answer it from evidence, not from memory of having answered it before.

## Are the standing loops actually armed right now — and are they routing the DRAINS too?

The standing consolidation loops are ON by default (the human opts OUT). They are session-scoped:
a restart, crash, or killed session disarms ALL of them SILENTLY, so re-check with the real tool
(`CronList`/`TaskList`) on every SessionStart and re-arm what is missing — a remembered "I armed
them" describes a session that may no longer exist.

Is throughput only parallel swarm delivery? No — the loops also route the two DRAINS, and both are
first-class throughput work, not a side chore:
- **tech-debt drain** — `des refactor --pile techdebt.md`, one item per isolated worktree+venv.
- **bugfix drain** — each pending `defects.md` row driven through `/nw-bugfix` end-to-end in its
  own isolated worktree (RCA → t=0 charter → regression AT → GREEN → Vera examine → commit).

Same box discipline applies: N cloud lanes fan out, ONE box lane serialized, resource-aware. A
drain is a tree-writing lane — it MUST run in its own worktree, never in trunk.

## Are you dispatching in the background, in parallel, by default?

Dispatch agents and commands in the BACKGROUND by default, and maximize how much runs
concurrently — never dispatch-then-wait-then-dispatch-next when the work is genuinely
independent. Only serialize when there is a real reason to (see below): a shared box
resource, or two lanes that touch the same files. Absent one of those, is more parallelism
the default? Yes — the user opts OUT of parallelism explicitly if they want serial/foreground
work, not the other way round.

### After this event, did you recompute the DAG and dispatch every READY lane — or is something idle that shouldn't be?

After every phase transition, completion, refusal, new artifact or changed dependency, ask
this. Waiting for the current slice to finish while an independent charter, DISTILL,
JIT-analysis, review or downstream-preparation lane is READY is `UNUSED_PARALLELISM` — an
orchestration defect, not a conservative choice.

Does a `depends-on slice-N` declaration really block this work, or only its whole-slice
COMPLETION? **Dependencies attach to consumed artifacts, not whole-slice completion.** It
MUST NOT become a whole-slice barrier for work whose inputs are already stable: charter
authoring from accepted product intent, DISTILL from stable contracts, source
inventory/JIT analysis, independent intra-slice lanes, or generation of later DES
dispatches. A slice boundary is not a synchronization barrier; only an unmet artifact
dependency, explicit file conflict or box constraint is.

At each scheduling point, ask:

1. Is every lane correctly marked `READY`, `BLOCKED_BY_ARTIFACT`, `BLOCKED_BY_FILE`,
   `RUNNING`, or `DONE`?
2. Which READY work is cloud, and which is the single box lane?
3. Have all READY cloud lanes been dispatched, in dependency order, until cloud capacity
   is full?
4. Is box-lane work queued, never overlapped?
5. Is slice N+1's charter/DISTILL pipelining WHILE slice N is in `A_GREEN` or EXAMINE?
6. Did the DAG get recomputed the instant any lane emitted an artifact or finding?

Is the pipeline actually saturated and dependency-safe —
`running_cloud = min(available_cloud_slots, ready_cloud_lanes)`, at most one running box
lane? If a cloud slot sits idle while READY work exists, do you have the specific reason
recorded? Silence is a defect. Before dispatch, surface a compact snapshot:

```text
RUNNING: slice-00/A_GREEN
READY:   slice-01/H0-DISTILL, slice-01/R0-DISTILL, slice-04/charter
BOX:     idle
BLOCKED: slice-02/A_GREEN <- slice-01/preservation-contract
```

Then fill every READY cloud slot. Are you fanning out BOTH between slices AND inside a
slice, wherever sub-lanes have disjoint ownership and stable inputs?

### Would a read-only Throughput Sentinel pass find parallelism you left on the table?

The **Throughput Sentinel** is a small, read-only control loop inspired by
[Relay](https://github.com/andrealaforgia/relay-agentic-model). It is not another
delivery orchestrator and it never writes code, changes a ledger, approves a gate,
dispatches an agent, merges, deletes, or starts a box-bound command. Its deterministic
pass reads the current delivery DAG, declared ownership facts, local worktree metadata,
host-log freshness, and box occupancy, then emits the compact
`RUNNING / READY / BOX / BLOCKED` snapshot above.

Do you actually have a host receipt for the capacity claim you're about to act on? When a
Claude or Codex adapter has one, the Sentinel may report that receipt's capacity state.
When it has no such receipt, it reports `UNAVAILABLE`/`UNKNOWN` — it must never infer a
free cloud slot from silence, a worktree, or an old transcript. `UNUSED_PARALLELISM` is
therefore emitted only when the declared ready lane and the relevant capacity evidence
are both present; otherwise the receipt asks the orchestrator to measure or declare the
missing fact before scheduling.

**Does a dispatched agent's `idle` mean the WORK is done, or only that the PROCESS is?**
`idle` attests a process state, never that the work is done. `idle` is a designation; "the
artifact exists" is the property, and the two diverge. Before reporting a dispatched
agent's work as complete, have you verified the ARTIFACT it was told to produce — the
commit, the file, the ledger record — rather than trusting its status?

Does a quiet channel mean a stalled agent, or could it just as easily mean one about to
report? The asymmetry runs BOTH ways, and the second direction is the one that burns
tokens. Status notifications and agent messages arrive out of order with respect to the
work itself: an `idle` ping can precede a report already in flight, and a tree snapshot
can catch an agent mid-run. So is a quiet channel evidence of a stalled agent any more
than it is evidence of a finished one? No. Read the artifact, and let the ARTIFACT — not
the elapsed silence — decide whether to nudge. A nudge sent on silence alone is a paid
roundtrip against an agent that was already working, and it teaches nothing; a nudge sent
because the artifact is absent is diagnosis. Note also what a nudge cannot prove
afterwards: once the work lands, the ordering no longer shows whether the nudge caused
it, so do not record the recovery as evidence for its own necessity.

**Did you write the completion contract into THIS dispatch prompt — or are you assuming
the final message is automatic?** A dispatched agent's result reaches you only if it
sends it, so write the instruction in: *your final message IS the return value; send it
with SendMessage when done*. Measured over 4 dispatches in one session: delivered on 2 of
2 where the sentence was present, while the dispatch that omitted it sat idle holding a
finished report nobody received. A nudge recovers the report, but a nudge is a paid
roundtrip — one sentence in the prompt is cheaper than the recovery, every time.

Does every pass include worktree anti-rot triage? It inventories each linked worktree and
its branch/head, dirty state, lock/PID evidence, owner receipt and recent host-log
activity. A worktree becomes `ABANDONED_CANDIDATE` only when convergent evidence shows no
live ownership/activity together with unintegrated or dirty work. The receipt names the
evidence and offers exactly `MERGE`, `RESUME`, `DEFER`, or `REMOVE`. It never removes a
worktree automatically — is deletion staying human-authorized and separately verified?

**Did the Sentinel read the orchestrator's declared active-lane ledger BEFORE inferring
anything from git/mtime/telemetry — or did it re-derive "which worktrees are live lanes"
from ambiguous signals, the way every prior pass in the session already got wrong?** A
worktree's dirty-file count, its last-commit age, and a ledger row it happens to contain
are properties of the FILE TREE, not evidence of orchestrator intent — a worktree can be
dirty and old because a lane is genuinely mid-`commit-slice` deliberation, or because it
is five days of undisturbed backlog, and nothing in `git status`/`git log` alone tells
these apart. Inferring liveness from those signals is exactly the class GDP-8 names:
deciding on a DESIGNATION (looks busy, looks stale) instead of the PROPERTY (is the
orchestrator actually driving this worktree right now). Measured repeatedly in one
overnight session (2026-08-02): eight consecutive Sentinel passes each re-derived the
same three-lane RUNNING set from scratch, and each time conflated total worktree COUNT
with dispatched-lane count ("10/6 capacity" for 3 real lanes among 10 existing
worktrees), read a stale ledger row as current state, or — once — recommended REMOVE on
two worktrees carrying live uncommitted bugfix work because their last-named COMMIT
happened to already be an ancestor of trunk, which said nothing about the UNCOMMITTED
diff sitting on top of it. Every one of those had to be caught and corrected by hand,
after the fact, on the SAME facts a declared ledger would have made unambiguous up front.

**Does the orchestrator maintain a small declared-lanes file BEFORE dispatching the next
Sentinel pass — one row per worktree it has itself dispatched and is actively driving,
written and updated on every REAL confirmation (a genuine status message, a verdict, a
seal — never a Sentinel's own inference, which would make the ledger self-referential)?**
Is its filename prefixed with the orchestrator's own lane name per the shared-scratchpad
rule elsewhere in this skill (`team-lead-active-lanes.md`, or the equivalent for whichever
lane is doing the dispatching)? Does every Sentinel dispatch prompt then name that exact
path and say, verbatim in substance, *read this file first; treat it as the primary
source for which worktrees are live dispatched lanes; corroborate it against
git/mtime/ledger evidence and surface a named discrepancy if something disagrees, but do
not silently reclassify a declared lane as abandoned, or an undeclared worktree as
running, on your own inference*? A worktree absent from that ledger is backlog, not
urgent, regardless of how many files are dirty or how fresh the last commit is — is "how
many corsie are actually in flight" answerable from one read of that file, rather than
reconstructed from ambiguous git state on every single pass?

Is the agent classifying an ambiguous dependency actually Luna — Vera's economical model
tier — and only when deterministic facts are insufficient? She may not invent work,
liveness, capacity, or override the snapshot. Has the Sentinel run at SessionStart and at
least every 30 minutes while the host session is alive? The periodic pass is observation
only — has it stayed that way, never turning missing host scheduling into a hidden
resident process? When an unknown could change a lane's safety, slicing, architecture, or
feasibility, has the Sentinel named the unknown and routed it to a bounded `nw-spike`
before scheduling? The spike answers `SUPPORTED`, `REFUTED`, or `INDETERMINATE`; it is not
generic research.

## Is this dispatch riding the spine's discipline, or hand-assembled? — and does fan-out multiply that answer?

The routing rules — which command drives which situation, what is DIRECT vs DISPATCH, why the
envelope is generated and never hand-assembled, the wave-floor markers — are owned by the
**orchestrator spine-discipline affordance**, which the DES runtime injects at session start (and
refreshes on prompt). This skill does not restate them: find that injected block and read its
scenario table. If it is not in your context, the affordance is not being injected and THAT is the
finding — a routing rule you cannot see is a routing rule you will guess.

What belongs HERE is the interaction with parallelism, which that file does not cover:

- **Does this swarm multiply discipline, or drift?** N lanes on a spine-generated envelope
  multiply throughput; N lanes hand-assembled multiply drift, and the drift arrives N times
  faster than a single lane would have shown it. Fan-out is worth having ON TOP of a disciplined
  dispatch, never instead of one.
- **Is the sub-orchestrator running `des dispatch` ITSELF** for the agents it dispatches inside
  its worktree, rather than forwarding an envelope you generated for it? Yours names your slice,
  not its.
- **Is this WAVE/PRODUCTION work, or a research/measurement/triage/read-only scout?** The rule
  binds only the former. Stating the boundary is what keeps the rule enforceable: a rule read as
  "never dispatch anything directly" gets discarded wholesale the first time it is obviously
  wrong.

## Is the constraint the BOX, or the agent count?

- **Are these stages LLM-bound?** RCA, charter (PO), AT-authoring (acceptance-designer), crafter
  A_GREEN, Vera examine, review all run in the CLOUD, parallel almost for free — maximize these,
  dispatch every independent one in a single batched call, in the background.
- **Are these stages box-bound?** `des commit-slice`, BuildTier, whole-tree suite, wheel-build,
  env-e2e contend for CPU/RAM on the local machine. Under memory pressure they emit **FALSE-RED**
  — a subprocess OOM-killed (SIGKILL/137/143) reported as a test failure. This is the ONE class of
  work you isolate to one-at-a-time — the bottleneck is the box, never the agent count.

**THE RULE: N cloud LLM lanes, ONE box lane, resource-aware. Parallelize everything
else by default.**

## Move 0: are YOU the bottleneck — one worktree, one sub-orchestrator?

Before the five moves below, ask this first. Personally driving each worktree's
slice-by-slice loop (reading files, dispatching one phase, waiting, dispatching the next)
turns the orchestrator into exactly the bottleneck ToC says to route around. For EVERY
active worktree carrying multi-slice feature work: has a sub-orchestrator agent been
dispatched (background, full tool access including further dispatch) that owns the ENTIRE
per-slice spine for its feature (DISTILL → entry-gate → A_GREEN → EXAMINE → COMMIT,
repeated per slice) PLUS its worktree's mechanical cleanup once merge-back succeeds —
dispatching its OWN crafter/acceptance-designer/examiner agents via `des dispatch`, never
a passthrough?

**Does it also run its own feature-end cycle?** It should NOT — a slice's cleanup ends at
merge-back; feature-end is a SEPARATE, LATER decision (possibly batched across several
ready features, to pay the full-suite/deep-review/env-e2e cost once instead of once per
feature). A sub-orchestrator finishes at "all slices committed and verified, worktree
cleaned" and reports that — the main orchestrator decides when to close feature-end for
one feature or a batch together. Does it report back only at genuine decision points
(ambiguous design call, gate refusal needing human judgment, a defect in an upstream-wave
artifact), not after every mechanical step?

**Is trunk-writing consolidated under exactly ONE sub-orchestrator at a time?** Two peers
independently mutating the same shared tree race each other and can corrupt an in-flight
whole-tree gate; when several features' remaining work all lands on trunk, bundle them
under one trunk-completion sub-orchestrator instead of one per feature. Do features with
their own isolated worktree (no trunk dependency yet) get independent sub-orchestrators
freely — dispatched BATCHED in one message when independent (true parallel fan-out, in
the background), never dispatch-then-wait-then-dispatch-next? The main orchestrator's job
narrows to: identify which worktrees need a sub-orchestrator, fan them ALL out at once,
and synthesize/triage what they escalate.

**Have you declared `--swarm-isolated` BEFORE hitting the refusal, not after?**
Parallelizing a LATER slice of the SAME feature in a second worktree needs one extra
flag. Opening a second isolated worktree from an earlier slice's sealed tip (per the
"parallelize a node's own slices" loop) so slice N+1 can run its own DISTILL/GREEN while
slice N is still sealing elsewhere is exactly right — but `des dispatch`'s own
carpaccio-ordering check will otherwise BLOCK slice N+1 with `CarpaccioSliceOutOfOrder`
the moment it can't find a `SliceCommitVerified` ledger record for slice N (it cannot see
one: slice N is sealing in a DIFFERENT worktree). The designed escape hatch already
exists — pass BOTH `--swarm-isolated` and `--swarm-justification "<which worktree, which
predecessor slice, and that it will fold into the shared line at integration>"` to the
`des dispatch` call for slice N+1 (and again to its eventual `des commit-slice`, which
re-checks ordering independently). This exempts ONLY the order check, nothing else — true
ordering is still verified later, at integration, when the parallel branch folds back onto
the shared line. Have you named this UP FRONT whenever planning a second worktree for a
later slice of an in-flight feature, so the dispatch succeeds the first time instead of
failing, being diagnosed, and being re-issued?

## Is every idle cloud slot filled — or is the CONSTRAINT actually advancing?

Filling every idle cloud slot LOOKS like throughput but is it the same objective as
advancing the actual constraint? No — the two diverge more often than they align. A
swarm can run six lanes at full occupancy for hours while the ONE node that everything
else depends on (the Mikado/ToC constraint — the node the fan-out tally names as blocking
the most other work) sits stalled on a single external dependency: every "busy" lane is
genuinely working, and the metric that matters (constraint nodes closed) still reads
zero. Measured 2026-07-31: a session ran 5-6 concurrent lanes for several hours, all doing
real DESIGN/DISTILL/bugfix work, and closed zero tree nodes in that window — because the
orchestrator kept asking "is there idle capacity to fill?" and never "does the
constraint's own critical path already have everything it needs?".

**Before opening or parallelizing ANY new front, does the constraint's own critical path
already have every lane it can productively use?** If NOT, that is where the next dispatch
goes — not into a fresh, independent front just because a cloud slot is free. Only once
the constraint's path is maximally resourced (every parallelizable piece of it already
has a lane) does spare capacity legitimately go to a second front. A second front opened
while the constraint itself is under-resourced is throughput spent on the wrong node,
however busy it looks.

This does not contradict Move 0/the five moves below — it orders them: saturate the
constraint's own lanes first, THEN apply the same fan-out discipline to whatever
capacity remains.

## The five moves (ordered by ToC leverage) — which of these is not yet true?

1. **Is the box serialized while the cloud fans out?** At most ONE box-bound gate runs at
   a time. Run every LLM stage (RCA ∥ charter, AT-authoring, crafter, Vera, review)
   concurrently. A swarm never multiplies the box — it only multiplies the cloud.

2. **Is the cloud pipelining across slices (C2)?** Author AT(N+1) + charter(N+1) in the
   cloud WHILE the crafter greens slice N. ~4-5' hidden per slice. Never block slice
   N+1's cloud work on slice N's box work. This is mandatory whenever those lanes are
   READY, not a discretionary speed-up.

3. **Is the box scoped per-slice (C1)?** The per-slice seal EXECUTES only the ENTERING
   slice's regression test + light always-on invariants; the whole-tree tier defers to
   feature-end. This governs which architectural invariants RUN per-slice — it is a
   DIFFERENT axis from the `Gate-Scope:` commit trailer, which is a whole-tree SET
   FINGERPRINT (sha256 over every collected test node-id) and is legitimately whole-tree
   by design: it detects the test population itself drifting between gate-run and
   commit-land, including files OUTSIDE the entering slice — a scoped collect cannot see
   that delta structurally. Running the whole tree per-slice is the JIT poison that forbids
   pipelining. Seal 3-10' → 1-2'.

4. **Is the box launch resource-aware (C3 / GDP-6 starvation-class)?** BEFORE a heavy box
   gate, check resources (**MemAvailable** above the gate's own floor ∧ load < ~cores×2);
   if not, wait a bounded window with progress. **The SSOT for the exact threshold is the
   code, not this line**: `run_contract_gate._read_mem_available_mib` /
   `_DEFAULT_MIN_MEM_AVAILABLE_MIB` (~700 MiB today, and
   `NWAVE_BUILD_TIER_MIN_MEM_AVAILABLE_MIB` overrides it) — do NOT copy that number here,
   POINT to it, so a threshold change never leaves this doc lying. Is the threshold on
   **MemAvailable** — the figure earlyoom watches and the gate already uses — **NOT
   MemFree / the `free -m` "free" column**, which excludes reclaimable page cache and
   reads ~5x lower? A box at 270 MB "free" but 6.7 GB MemAvailable is NOT starved, and
   holding it there is throughput lost to a wrong number. Read `MemAvailable:` from
   `/proc/meminfo` (or `free -m` **"available"** column), never "free". Is a gate killed
   by resources being recorded as **INDETERMINATE-with-retry, NEVER a red**? Distinguish
   a resource kill (137/143, aborted run) from a genuine failure. **The trigger is
   MemAvailable, not load.**

5. **Is verification per-slice with Vera-Haiku (C4), not a continuous review loop?**
   Vera-Haiku examines each slice's charter at Haiku cost; the deep review is a
   feature-end panel (Haiku ∥ per-lens + adversarial verify), not a running
   crafter↔review loop — cheap per-slice verification, expensive deep review only once
   at the end.

## Is the ceremony tax (C6) creeping in?

Rejection roundtrips are measurable ceremony (~3 rejections/day ≈ 20' + lost context). Is
the affordance (accepted tokens, WHERE an annotation goes) surfaced INLINE at the
authoring surface (GDP-2), not only in the gate's rejection message? Is the checked
artifact GENERATED with its producing tool (`des dispatch` for the crafter envelope, `des
feature-delta-doctor` before DISTILL) rather than hand-assembled to match what a gate will
check (GDP-5, cost on the system)?

## Tool-output discipline in dispatch prompts (C7) — did you tell the dispatched agent NOT to read the raw dump?

A dispatched agent defaults to reading whatever a command prints straight into its own
context — a long-running whole-tree suite, a large file, a wide grep — unless its dispatch
prompt explicitly tells it otherwise. A handful of large dumps in an otherwise-small
transcript can dominate its total size; the same information a `tail -N` / `grep` pass
would have delivered in a fraction of the size gets carried forward and re-billed on every
subsequent turn once it enters context.

**THE RULE: never let a dispatched agent `cat`/read a large or long-running command's raw
output. Redirect to a file, read back only the tail/grep/summary.** This is GDP-2 (inline
guidance at the authoring surface, not a reactive fix after the fact) applied to dispatch
prompts specifically — state the redirect-and-tail pattern IN the prompt, every time you
hand off a command that could produce more than a screenful:

```
NWAVE_GATE_JOBS=serial uv run des run-contract-gate --repo . >> gate.out 2>&1 &
# then poll with: tail -30 gate.out   (never `cat gate.out`)
```

Applies to: whole-tree/full-suite gate output, `pytest`/build logs, `find`/`grep` over a
large tree, reading an entire source file when only one function is relevant (use
line-ranged Read or a targeted grep instead). Does not apply to short, bounded outputs
(`--help`, a single ledger record, a small diff) — the rule is about UNBOUNDED or
LARGE-BY-CONSTRUCTION output, not every tool call.

### Is the redirect target actually a SHARED namespace — did you name it per-lane?

**All dispatched lanes share ONE scratchpad directory**, despite the per-session UUID in
its path suggesting otherwise. The redirect-to-file rule above therefore creates its own
hazard: two lanes writing `gate.out` silently overwrite each other. No error, no git
conflict — the content changes underfoot, and a lane can read another lane's gate result
and report it as its own. The orchestrator then integrates on a false fact with no way to
notice.

**THE RULE: every scratch file gets the lane name in it** — `gate-<lane>.out`,
`msg-<lane>.txt` — or, better, lives inside the lane's own worktree, which is isolated by
construction. State this IN the dispatch prompt, next to the redirect instruction: a lane
cannot infer that a path it was handed is shared.

Are you applying this hardest to shell redirects? The `Write` tool refuses to overwrite a
file it has not read — that guardrail is what caught the collisions below. `> file` in
Bash has NO such guardrail and destroys silently. Gate output is written with `>`, so the
least protected write path is exactly the one carrying the results lanes report on.

### Is `git stash` about to be used while a swarm is live? Don't — `refs/stash` is shared

`refs/stash` lives in the common dir, NOT per-worktree. Every lane pushes onto the SAME
stack, and `git stash pop` takes the top entry — whoever pushed last, not the caller.
Measured 2026-07-28: two lanes stashed nine seconds apart and the first lane's `pop`
took and dropped the second lane's work. Recovered from the dangling commit
(`git stash store -m "<label>" <sha>`), but by luck, not by design — one `gc` earlier and
it would have been gone.

To set work aside in a swarm, is it going to a temporary branch in YOUR OWN worktree, or
a file copy — never the stash? Note also that untracked files are not in a stash at all,
so a lane recovering one still has to check its untracked test directories separately.

Measured 2026-07-28 with 8 parallel lanes: at least three collisions in one evening
(`distill_prompt.md`, `carpaccio.txt`, `msg.txt`), reported independently by three lanes.
One lane was stopped from overwriting another's dispatch envelope only by the Write
guardrail, and initially read the refusal as a local inconvenience rather than the
systemic symptom it was.

## The measure (re-runnable) — does your number actually query the right event?

`SliceCommitVerified` events from `.nwave/telemetry/atdd-pure/*.jsonl`; gaps between
consecutive timestamps per feature give the spacing distribution. **Have you verified the
event name against the ledger before trusting an empty result?** This line named
`SliceCommitted` for a long time, an event those ledgers do not carry, so the measure
silently returned nothing and looked like a repo with no history rather than a query with
no subject. A distribution of zero is a claim about your instrument first.

Are you looking at the TAIL (p90), not just the median? A long tail means occasional
collisions or starvation, not a steady bottleneck — and that reading holds whether the
median is slow OR fast: a fast median with a p90 several times larger is the signature of
contention, not of speed.

**Does this number measure CALENDAR SPACING, or slice cost — and have you kept the two
apart?** The gap between two verified slices contains every minute nobody was working —
nights, breaks, waiting on a human. Filtering out gaps over some threshold removes session
boundaries and nothing subtler, so a long pause in the middle of the night still counts as
slice time. The median therefore overstates true per-slice work by an unknown amount and
the tail overstates it enormously. Two questions worth asking before anyone quotes a
number:

- was the baseline you're comparing against computed the SAME way? If that has not been
  checked, "X versus Y" is not yet a claim;
- do you have a per-slice `started_at` recorded beside the verification timestamp? Without
  it, a quiet week and a fast week are indistinguishable in this distribution, and
  reporting the first as the second is the easiest false claim in the whole methodology.

Re-run after applying the moves above to confirm they moved the number — and re-state the
caveat every time the number is quoted, because a figure travels further than its footnote.

## Is this optimization trading away a real gate — or only the ceremony around it?

Speed is a means, not the goal: quality is superhuman, velocity human-competitive. Is a
real gate (execution-observing floors, Vera examine, the seal) ever being traded for
speed? It must not be — those are the fixed floor. Optimize the CEREMONY around them
(hand-assembly, whole-tree-per-slice, false-red retries, roundtrips), never the substance.
