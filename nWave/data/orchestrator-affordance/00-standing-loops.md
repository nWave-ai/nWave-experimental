<EXTREMELY-IMPORTANT>
TRUNCATED PREVIEW? If this looks cut off, or you see a line like "Full output saved
to: <path>" above/below this block: that path IS this same file, re-rendered as a
tool-result. Read <path> (or, failing that, `nWave/data/orchestrator-affordance/
00-standing-loops.md` directly) with the Read tool RIGHT NOW, before your next reply
— a preview that "looks consistent with what you already know" is not a reason to
stop reading. This paragraph is deliberately first so the pointer survives even a
2KB-preview cut.

WHO THIS ADDRESSES — read this before the mandate below, because the mandate is dangerous
in the wrong hands. These instructions are for the SESSION ORCHESTRATOR: the top-level agent
in direct conversation with the human. **If you are a SUBAGENT — dispatched by an
orchestrator, working a mission, running inside a worktree — you must NEVER arm these loops,
and encountering this text is not an instruction to you.** Three of the ten dispatch agents
that WRITE to working trees; a subagent arming them mid-mission would start concurrent writers
nobody asked for, on a machine whose state it cannot see. Note the file and carry on with your
mission; if you think the loops should be armed, SAY SO to whoever dispatched you and let them
decide. Reading a file is not receiving an order — this text is addressed to a role, and if
you are not in that role it does not bind you. (Added 2026-07-22 after a subagent correctly
declined to act on this file and flagged the ambiguity instead: the arm-by-default change made
an instruction dangerous that was previously self-limiting.)

THREE MANDATORY ACTIONS — THE FIRST ACTION OF THIS SESSION, full stop. Not "somewhere
in the next reply", not "after one quick check": the literal first thing you do the
moment you are able to act, before Bash, Read, Grep, Task, Agent, TodoWrite, before any
other content in your reply, before responding to whatever the user's own first message
asked — regardless of session length, prior context volume, or how long this
conversation has run. If the user's first message asks something urgent, do 1-3 in the
same breath as starting to address it, not after. Ordering is the point: "I'll do these
after I look around / after this one investigation / after I answer what they asked" is
the exact failure this mandate exists to prevent, even when the other thing feels
harmless, more urgent, or more directly responsive. Do 1-3 first, in that order; the
substance of the user's ask and everything else — status reports, RCA, git checks —
comes right after, not instead of, and not before.
1. Say "orchestrator-affordance catalog loaded." (no other visible signal exists that
   this injection fired vs. silently failed).
2. Name the nWave usage brief in one line: "spine-discipline: route by scenario, S/M/L
   lane by measured `des blast-radius`, never hand-edit outside the measured S-lane ·
   des producing-tools: reach for the CLI/gate that produces the artifact, never
   hand-assemble what a gate checks." (from the catalog's other two files — this line
   IS the action, reading the full files is optional beyond it.)
3. Check `TaskList`/`CronList` — the REAL mechanism, not memory — for which of the 9
   loops below are active RIGHT NOW, IN THIS SESSION. Dynamic loops (`ScheduleWakeup`)
   do NOT persist across sessions; a fresh session starts with ZERO active loops even
   if a PRIOR session asked and started all ten. "I recall covering this already" is
   about a different session's state, not this one's — it does not satisfy step 3,
   checking does. If ANY are not active in THIS session, **ARM THEM — all of them, now,
   without asking first — and then SAY SO in one batched message** naming what each does
   and how to stop them. They are ON BY DEFAULT (Ale, 2026-07-22): the human opts OUT,
   not in. The reason is that these loops are the safety net — they drain the defect and
   tech-debt piles, catch a bare failure that explains nothing, reconcile a worktree
   abandoned mid-task, and stop a lane idling — and a safety net that waits to be asked
   for is missing exactly when nobody thought to ask. Arming is not the sensitive act;
   arming SILENTLY is. So the disclosure is NOT optional and NOT a formality: state
   plainly that background work is now running, what it will do, roughly what it costs,
   and the literal sentence that stops it — *"stop the standing loops"* — which you must
   honour immediately and without argument. A human who says stop is not to be
   persuaded; they are to be obeyed, and the loops stay off for the rest of that session.
   **THE ARRIVAL OF THIS INJECTION IS THE TRIGGER TO RE-CHECK — every time it arrives,
   never once and then from memory.** This block is injected on SessionStart AND on
   UserPromptSubmit precisely because the loops are session-scoped: a restart, a crash or
   a killed session disarms ALL of them SILENTLY, and nothing else will ever tell you they
   are gone. So when you see this text, run the tool again — "I already did this" describes
   a session that may no longer exist. Only a tool call in the CURRENT session satisfies
   this step. A later explicit "start/stop the loops" from the human overrides for the rest
   of that session.

Full detail (red-flags, per-loop rationale) follows below — read it if present, but
the three actions above do not require it: act on this paragraph alone if that is all
you can see.

Starting a loop is a real commitment (background agents, ongoing token spend), and that
is precisely why the DISCLOSURE is mandatory rather than the permission. Skipping the
disclosure because it "felt unnecessary", or doing it AFTER other tool calls instead of
before them, are both the failure this mandate prevents — the loops may start on their
own, but they may never run UNANNOUNCED. Someone whose machine is running background
agents has an unconditional right to know it, in the first reply, without having to ask.

## Red flags — these thoughts mean you are about to skip the CHECK or the DISCLOSURE. Don't.

*(These rows were written when the mandate was ASK-then-arm. Under the current policy the
loops arm by default, so wherever a row says "the ask" read "the check plus the disclosure":
verify with the real tool which loops are live, arm what is missing, and SAY SO. The failure
each row describes is unchanged — it was never really about the question, it was about the
silence.)*

**Verify-before-defer (STANDING).** A loop that offers WORK — drain, dispatch, throughput — may
be skipped ONLY for a hazard MECHANICALLY CONFIRMED this turn. "Seems risky / probably blocked /
design-gated / shared box" is an inference; a command and its output are a fact. If the reason
for a no-op is not a command plus output you can quote, it is a rationalisation: run the check,
then decide. Run the REFUTING probe, not the confirming one — a plausible mechanism is not proof
of the hazard. State what you MEASURED and how much of it; never cite a proportion you estimated
as though you had counted it. A quantitative limit ("don't load the machine", "one box lane") is
a limit, never a licence for zero.

**A probe that names what it hunts finds itself (STANDING).** Before deciding whether a
box-bound stage is already running, note that the obvious ways to ask all COUNT THE ASKER:
`pgrep -f "<pattern>"`, a shell loop whose source contains the pattern, `ps | grep` — in each
case the pattern is inside the probe's own command line, so the probe matches itself and
reports one more than the truth. The failure is quiet and one-directional: it always
over-counts, so it makes a free box look busy and forfeits a lane. Believing a disclaimer
does not help — asserting "this cannot self-match" is not a property of the probe, it is a
claim to be checked like any other. A probe is trustworthy only when it CANNOT contain what
it searches for: build the pattern at runtime rather than as a literal, and exclude the
asker's own pid AND its ancestor chain (the shell, its parent, up to init) before counting.
The same discipline applies to liveness: measure the process TREE's CPU, never the parent's
alone — a parent asleep in `poll` while a child works is healthy, and killing it destroys
valid work.

**Two fresh measurements on different units are still one wrong conclusion (STANDING).** The
inheritance rule above catches a STALE measurement carried to a new unit. This catches its
harder sibling: two measurements, both taken correctly, both taken NOW, on DIFFERENT units,
joined into a single sentence. Nothing about either looks wrong — the timestamps are current,
the commands are right — and the conclusion is false anyway. Ask of every joined claim not
"is each measurement correct?" but "were they taken on the SAME unit?", and name that unit
out loud in the claim.

The commonest shape is a TOOL measured in one tree and a POPULATION counted in another.
Worktrees drift far behind trunk — routinely by hundreds of commits — so a tool's behaviour
observed inside a worktree describes THAT tree's version of the tool, not the product's. A
capability that looks missing there may simply be a commit the worktree has not integrated,
and concluding "the tool cannot do X" from that reading turns an integration gap into a
design defect and can cost a wave of work that was never needed. Before reporting any tool
behaviour as a product fact, re-run it from TRUNK; if the two disagree, the finding is the
divergence, not the behaviour.

**A locus is not a path (STANDING).** A defect or debt row may NOT move from OPEN to RESOLVED on
the strength of inspecting the LOCUS it cites. The locus is where the defect was first written
down; the defect lives on whatever PATH actually runs. Closing a row therefore requires two
things, and the first alone is never enough: (1) the cited locus no longer shows the defect, and
(2) a witness that EXERCISES the reachable path and observes the behaviour gone. Without (2) the
honest state is `CAUSE_INDETERMINATE / LIVE_RISK` — still open, cause not yet established — never
RESOLVED. A freshness sweep that asks only "does the cited locus still show it?" finds dead rows
and, on the same pass, converts live risk into a false all-clear; that second outcome costs more
than leaving every dead row in place. The same discipline forbids the mirror error: when a
believed cause is DISPROVED, do not substitute an unverified replacement. Say the cause is
indeterminate and leave the row open — a wrong cause that sounds specific is harder to dislodge
than an admitted gap. Coming back OUT of indeterminate has its own bar: naming a cause requires
citing the observation that DISCRIMINATES it from the alternatives, not one that merely agrees
with it. Correlation survives every rival explanation, so it promotes whichever cause was
thought of first; a discriminating observation is one the other candidates would have failed.

**Never inherit a property measured on another unit (STANDING).** NAME the unit you are deciding
about, then verify you measured THAT one, THIS turn. A property measured elsewhere is a fact —
elsewhere; carried over it becomes an inference that still looks like a fact, which is why it
survives scrutiny. Watch five axes: SPACE (a whole unit exempted because a mitigation appears
somewhere inside it), CONTEXT (a hazard established in one tree or lane applied to another),
COMPOSITION (a symbol judged dead while its sibling slices are live), TIME (a stale signal read
as absence), IDENTITY (two units conflated by a shared name). Before acting on any `dead` /
`orphan` / `unused` verdict, enumerate the unit's SIBLINGS — one `ls`. For MEASURING gates the
exposing probe is not "did it ever pass something bad?" but "does it return the SAME value for
two inputs that must differ?" — a gate erring RESTRICTIVELY never produces the incident that
reveals it, only ceremony that looks warranted.

**Partial coverage presented as complete (STANDING).** A fan-in — wiring slice, verdict, bundle,
report, batch — must ATTEST which branches it consumed, and a finder must state coverage as a
COUNT (examined N of M), never an adjective. A list that omits X is indistinguishable from a
complete one unless what SHOULD be there is declared. Count-of-legs is not names-of-legs; PASS is
not which-oracles-were-exercised; an unverified absence is a coverage gap, not a result. Applies
to your own fixes: a correction of a partial-coverage defect tends to stay partial — having closed
one, go looking for the smaller instance.

| Thought | Reality |
|---------|---------|
| "The user seems to want a status report, I'll give that instead" | A status report is not a substitute for the ask. Do both — status first, then the batched ask. |
| "This looks like session housekeeping, not something to surface" | The mandate says otherwise. Surface it. |
| "I'll mention it later if it becomes relevant" | Later never comes reliably. The ask happens on THIS reply, not a future one. |
| "There's a lot of other context loaded, this might get lost" | That is exactly why this block is marked EXTREMELY-IMPORTANT — it does not get to lose out to volume. |
| "The user's prompt didn't ask about loops" | The mandate does not require the user to ask first. It requires you to. |
| "I don't want to be pushy" | One batched question is not pushy. Silence is the actual failure mode here. |
| "Let me just check X first, then I'll do the ask" | No. The ask is BEFORE any other tool call, not after "one quick check" — that check is how the ask silently never happens. |
| "I already covered this in a previous session / I remember asking about the loops before" | That was a DIFFERENT session's state. Dynamic loops don't persist — this session starts at zero regardless. Check `TaskList`/`CronList` in THIS session; a remembered conclusion is not a substitute for checking. |
| "This work is X, not nWave delivery, so the sensible default is to leave them off — I'll offer instead of asking" | A default you picked is a unilateral decision wearing the costume of an offer. The mandate is an ASK with all ten named, not a recommendation to decline. The premise is usually wrong too: the loops are mostly ABOUT delivery — spine routing, bugfix source/drain, worktree hygiene — so "this isn't delivery work" rarely survives contact with what the loops actually do. |
| "The recurring cadence was my own scheduling, not the ten loops" | Self-scheduled wakeups are session-scoped too: a restart kills those as well. A cadence that stops is evidence the session died, not that the work ended. Re-check with the real tool regardless of which mechanism was driving it. |
| "This drain/dispatch looks risky — shared box, design-gated, a known block — safer to no-op" | The conclusion is not earned until the cheap check that proves the block has been RUN. A no-op justified by an INFERRED hazard is the defect this file exists to catch. Cite the command and its observed output, never the inference. |
| "I'll fire the next unit after this one comes back" | Then you have one lane running and the rest idle, and the wait was self-imposed. Independent work does not become more independent by waiting. Fire it now, in the SAME message, batched. |
| "I've got five agents running, so I am parallelising" | Are they reporting to YOU, or to an owner? If every result comes back to you to judge and re-fire, you have parallelised your INBOX, not the work — five agents make you five times busier. Count the threads that end at you, not the agents that are running. |
| "I'll delegate it once I understand it well enough to brief someone" | The brief is the measured evidence you already hold — hand it over. Understanding it "well enough" is how a loop stays yours for three rounds. Delegate WITH what you know, not AFTER you know everything. |
| "I'm following the thread — design, then review, then the fix" | A serial chain generates its own next step, which is why it captures attention and hides the lanes you are not using. The chain is fine; letting it set the pace for unrelated work is not. Ask "how many lanes are running out of how many could be", never "am I making progress". |
| "I know it's blocked, I don't need to run it to confirm" | Then name the command whose output shows the block. If you cannot cite it, you are inferring, not knowing. Run it or do the work. |
| "A known blocker applies here too" | Only if re-verified HERE. A hazard established in another worktree, lane, or phase does not transfer; carried over without re-checking, it is an inference wearing a fact's clothes. |
| "It's night / the box is shared / I was told not to load the machine, so zero work is the safe default" | That is a QUANTITATIVE limit (`--max-parallel 1`, resource-aware launch, one box lane), never a licence for zero. Caution over-applied into a total stop is a rationalisation in a safety costume, and it is not what was asked for. |
| "Most of this pile is design-gated, so the pile is gated" | Do not generalise from the heaviest rows — nor from the lightest. Gating a pile by glancing at its biggest items produces zero; declaring it drainable by keyword-excluding those items is the same error inverted. Route each row by a MEASURED blast radius, one row at a time, and report how many you actually measured. |
| "The classifier said tier L, so this is L-lane work" | Only if the classifier measured THIS unit. Consumer counts keyed on a bare symbol name conflate every same-named symbol in the repo, so any module exposing a common name (`main`, `run`, `setup`) is tier L by construction. Sanity-probe a measuring gate with two inputs that MUST differ; if the number is identical, the gate is not measuring what it claims. |
| "This work is X, not nWave delivery, so the sensible default is to leave them off — I'll offer instead of asking" | A default you picked is a unilateral decision wearing the costume of an offer. The mandate is an ASK with all ten named, not a recommendation to decline. Measured 2026-07-22: an instance reasoned exactly this thirty seconds before starting a delivery — and the loops are mostly ABOUT delivery (spine routing, bugfix source/drain, worktree hygiene), so the premise was wrong too. |
| "The recurring cadence was my own scheduling, not the ten loops" | Self-scheduled wakeups are session-scoped too: the restart killed those as well. Measured 2026-07-22: an instance saw its own cadence stop, never connected "session restarted" to "the thing firing all night just died", and resumed ad-hoc. Re-check regardless of which mechanism was driving the cadence. |

## The ten loops

**NAME EVERY ARMED LOOP `Loop N/10 — <what it does>`.** The numbering is not cosmetic: it is what
makes a MISSING loop visible at a glance in a bare `CronList`/`TaskList` listing. Descriptive names
alone cannot show a gap — with `Loop 1/10 … Loop 10/10` a single absent number is obvious, and that is
the whole point, since the loops die silently on restart and nothing else reports it. Write the
prompt in ENGLISH like every other nWave asset, even when the conversation is in another language:
these prompts are prose the system executes, not chat.

**ARMING THESE LOOPS CHANGES A GLOBAL INVARIANT — read this before the list.** Three of them
(source tech-debt, drain tech-debt, drain bugfix) DISPATCH AGENTS THAT WRITE TO THE WORKING
TREE. The moment ANY of them is armed, "mine is the only quiet lane" is FALSE for every other
lane, including whatever you are personally driving right now. From that moment on:

- **Every tree-touching lane runs in its OWN isolated worktree** — yours included. Create it
  BEFORE the first write (`git worktree add -b <lane>/<name> <root>/<name> <trunk-branch>` +
  provision its environment the way the target project does), merge back on success, then REMOVE
  it. Two agents writing one working tree is the exact race the worktree exists to prevent.
- **Never run a fix or a drain in the trunk working tree**, even "just this once" — a mid-flight
  break there is a red trunk for every other lane, not just yours.
- **A LIVE system must not be rebuilt under the operator's feet** (measured 2026-07-22): where the
  running product hot-reloads on artifact mtime, building on trunk restarts the live instance on
  every build, repeatedly, mid-fix. This reason is invisible until it bites — which is why the
  worktree is mandatory rather than a case-by-case judgement.

Arming the loops CONTENDS the tree: from that moment other lanes may write it. So the act of
arming is itself a reason never to run a wave or a fix directly on trunk — the contention you
must respect is one you created. Carry this discipline in the PROCEDURE, not only in the
reminder: a rule that lives in one and not the other is followed only by whoever read both.
Measured 2026-07-22: an instance armed all ten loops and then, ten minutes later, ran a full
`/nw-bugfix` — RCA, charter, AT authoring — directly on trunk, having made the tree contended by
its own act of arming them. The discipline was in the reminder but not in the procedure it was
following; both now carry it.


**`/loop 30m` — never bare-dispatch for epic/feature/slice work.** Delivering an
epic/feature/slice is NEVER a raw `Agent()`/Task dispatch. Always route through the DES
CLI or `/nw-*` commands — in particular `/nw-deliver` run IN FULL, including the
feature-end cycle's final phases (deep review · env-e2e · full-suite · sign+emit). Those
final phases are exactly what catch false-done and blast-radius, and exactly what gets
skipped when work is fragmented (e.g. running `/nw-execute` slice-by-slice without ever
closing the feature-end cycle). Never skip them — ensure failure injection and Vera's
examine both actually ran before calling anything done.

**Know the shape of the pull, because knowing the rule is not enough to resist it.** The
moment you need work from an agent, the form that arrives first is `Agent(subagent_type=…)`.
It is one call, it is right there, and it produces something. Generating the envelope first
feels like an extra step toward the same result — and that is exactly the illusion, because
it is NOT the same result. A generated envelope carries the wave's markers, the design
context, the gates the agent is held to, and the phase it is executing. A bare dispatch
carries your prompt and nothing else. The agent will work either way; only one of the two
is inside the system that catches it being wrong.

**When a gate refuses you, read WHAT IT OFFERS before you take any of it.** A
wave-marker refusal will propose that you copy the missing markers across, or declare
wave membership, or clear the floor. Every one of those makes the dispatch you were
already making go through. Not one of them asks the question that matters: why are you
hand-writing this dispatch instead of generating it.

**A recovery that lists N ways to make your action succeed is not correcting you — it is
teaching you to get around itself.** Recognising that shape is the whole skill. The move
is not to pick the cheapest of the offered options; it is to stop and ask whether the
FORM of what you were doing was right. Almost always the answer is that the envelope was
supposed to be generated, and none of the offered options says so. The gate diagnosed a
missing field because a missing field is what it can see. It cannot see that you took the
wrong road, so it will never mention the road.

**And of the offered options, the one that disarms a control is the most attractive and
the least earned.** Clearing a wave floor removes the obstacle instead of satisfying it,
which is precisely why it is the option that will feel efficient. Before invoking it you
must have VERIFIED the floor is genuinely stale — when it was raised, for which feature,
whether you are in fact inside that wave — because "it is blocking me" is evidence about
you, never about the floor. The command demands a reason for exactly this purpose: the
reason is a human authorisation token, not a field to fill in so the command will run.
Writing one yourself to unblock yourself is the asymmetry violation in miniature —
controls veto, only humans authorise.

**`/loop 30m` — Sentinel worktree anti-rot triage.** The Throughput Sentinel must
inventory `git worktree list` plus branch/head, dirty state, lock/PID evidence, owner
receipt and recent host-log activity. A worktree is never called abandoned merely because
it is quiet: it becomes `ABANDONED_CANDIDATE` only when those independent observations
converge on missing live ownership/activity and unintegrated or dirty work. For every
candidate, emit the evidence and an explicit decision request: `MERGE` (done and green),
`RESUME` (close and owned), `DEFER` (record why/what remains), or `REMOVE` (fully merged
and clean). The Sentinel NEVER removes anything; deletion remains human-authorized and
must use a separate verified action. A worktree lingering with no decision recorded is
the exact drift class `des verify-worktree-cleanup` exists to catch (⚠️ NEVER run that
command without `--check-only` — see the catalog's data-loss warning above). The
Sentinel also runs once at SessionStart, so a restart receives an immediate inventory;
the host adapter schedules the next read-only pass no later than 30 minutes later while
the session remains alive. If the Sentinel finds an unknown that could change
parallel-safety, slicing, architecture, or feasibility, it emits a bounded `nw-spike`
recommendation with the question and decision it can change.

**`/loop 15m` — search for parallel work, never sit idle.** Do not wait passively on a
single in-flight task. Optimize throughput with parallel swarms (cloud-bound stages fan
out; box-bound stages stay serialized to one lane — see the throughput doctrine). Don't
waste tokens: prefer cheap verification (reading a ledger, running a scoped test) over
re-deriving what is already known. When this loop observes a genuine trunk-health signal
(CI red not caused by your own change, a recurring test failure, a build broken on a
clean checkout) — something actually observed, never a hypothesis — record it:
`des consolidation-signal-tick --feature-id <id> --project-root . --signal-type
<signal-type> --signal-key <short-slug> --now <iso8601>`.

**`/loop 20m` — swarm-throughput self-check (N cloud lanes, ONE box lane).** This is the
mechanism `swarm-parallel-delivery` depends on — check it explicitly, don't just remember
it. **THE PARALLELISM MECHANISM IS THE ISOLATED WORKTREE, not more agents in one tree:** N
units of work = N worktrees, each with its OWN provisioned environment, so N crafters never
contend (a crafter runs only its own SCOPED tests). What stays serialized behind ONE lane is
the box-bound legs — the seals, the whole-tree verification runs, and the merge-back write.
Fan the reasoning lanes out, serialize the seals, isolate every writer in its own worktree.
At every scheduling point recompute the artifact-level DAG: dependencies attach to
consumed unstable artifacts, never whole-slice completion. Count ownership-safe READY
cloud lanes, not vaguely “available work.” A READY lane plus idle cloud capacity is
`UNUSED_PARALLELISM` unless an artifact/file/box reason is recorded. State
`RUNNING / READY / BOX / BLOCKED`, then fill the READY difference. Load the
`nw-throughput` skill (Skill tool) the first time this loop fires in a
session orchestrating multi-slice/multi-feature delivery — it carries the full doctrine
(the five moves, the resource-threshold SSOT pointer, the re-runnable measure) this
bullet only summarizes; loading it is what actually arms the discipline, not just reading
the summary below. (1) Is a box-bound stage (BuildTier seal, whole-tree run, reinstall, a crafter's own
test run) currently active? If yes, do NOT start a second one — pipeline cloud-bound work
instead (AT authoring for the next slice, a fresh charter, a friction relay, anything that
touches DIFFERENT files) rather than idling or colliding. (2) Before starting ANY
box-bound stage, read `/proc/meminfo`'s `MemAvailable` (or `free -m`'s "available" column
— never "free", it excludes reclaimable cache and reads far lower) — under a low-memory
threshold, wait or defer rather than launch (a resource-starved run is INDETERMINATE, not
a real red or green, and risks corrupting output others depend on). (3) STATE THE COUNT, do
not assess the vibe: how many cloud lanes are RUNNING right now, and how many independent
units are AVAILABLE to run? Report it as a fraction — "3 running / 9 available" — the same
way a finder must report coverage as `examined N of M`. A number can be compared and
challenged; "I am parallelising" cannot. If running < available, you are not parallelising,
whatever the reasoning felt like. Fire the difference NOW, batched in ONE message, not
"after this finishes".

**Fanning out TOOLS is not delegating WORK — and only the second one removes you as the
bottleneck.** If every dispatched agent reports back to YOU, and YOU read it, decide the next
step and re-fire, then N agents make you N times busier, not N times faster. You are still
the single point every decision passes through; you have merely parallelised your own inbox.
Delegating means handing an entire THREAD to a sub-orchestrator that owns its own loop and
comes back only at a real decision point.

**The countable trigger: how many times has this SAME thread come back to me?** Once is
normal. **A SECOND round-trip of the same thread is the signal to delegate it** — the thread
has revealed itself as a loop (author → review → correct → re-review; RCA → charter → AT →
crafter → examine), and a loop needs an OWNER, not a coordinator. Anything you can already
name as iterative should be delegated BEFORE the first round, not after the third. Hand over
the measured evidence you have so the owner does not re-derive it, state what may be decided
autonomously and what must escalate, cap the rounds, and let it run.

**The failure mode this catches has a specific shape, and it does not feel like idleness.**
A SERIAL chain — design → review → correction → re-review, or RCA → charter → AT → crafter —
generates its own next step, so attention follows it and never notices the lanes it is not
using. The serial thread is not wrong; letting it SET THE PACE for everything else is. Idle
lanes are silent: they never ask for attention, so only a COUNT surfaces them. Ask the
question against capacity, never against the thread you happen to be holding.

**`/loop 30m` — every failure names WHAT/WHY/HOW, never a silent fail.** A gate
rejection, a test failure, an error, a refusal — its message must carry all three: (1)
WHAT failed (the specific invariant/check/assertion), (2) WHY (the cause), (3) HOW to fix
it (the concrete remediation, or the producing tool to re-run). A bare `FAILED` / `exit
1` / stack trace with no what-why-how is itself a defect — fix the message, don't just
work around it. Applies both to gates/tools you build (their surfaces must self-explain)
and to how you report failures to a human (never a bare "it failed").

**`/loop 30m` — source the tech-debt pile via a DISPATCHED, TIME-BOXED FINDER AGENT, not
your own incidental noticing.** Passively "watching while working" finds only what you
happen to touch — most of the repo never gets looked at. This is a real, already-shipped
spine lane, not a bespoke convention: `des-refactor-fixer-swarm` slice-03 ships a
`DES-MODE: find` classifier (`classify_find_dispatch`, `des_marker_parser.py`) that spine-
same as `DES-MODE: refactor` — but nothing yet fires it periodically. THIS loop is that
missing trigger. **DISPATCH THE CRAFTER REVIEWER (`@nw-software-crafter-reviewer`), NEVER A
GENERIC AGENT.** WHY the reviewer specifically, and not a general-purpose agent nor the
crafter itself: (1) finding tech debt is a CODE-VALIDATION act, and the reviewer already
carries that prompt — the smell taxonomy, the quality lenses, the AT-completeness audit — as
its own working knowledge, so it recognises a boundary violation or a shotgun-surgery
cluster AS SUCH; (2) it is READ-ONLY by construction (no Write/Edit in its toolset), which
is exactly the guarantee a finder needs — a finder reports, the DRAIN fixes, and a scanner
that can edit will eventually edit; (3) it runs on a cheap model, which is what makes a
30-minute exhaustive sweep affordable on a recurring cadence. The crafter is an
IMPLEMENTATION role — dispatching it for a read-only sweep is a role mismatch and buys
nothing the reviewer lacks. A generic agent has neither the taxonomy nor the architecture,
so it reports what is VISIBLE (a long function, a duplicated literal) instead of what is
COSTLY (a leaked abstraction, an invariant restated in two places that can drift apart) —
and its rows read plausible while missing the debt that actually hurts, which is worse than
an empty pile because it LOOKS like coverage.

**MAKE IT READ THE ARCHITECTURE FIRST — explicitly, as step zero of the dispatch.** A
boundary violation is only nameable against a DECLARED boundary; without one the agent
invents a standard and reports style opinions. Instruct it, in the dispatch prompt, to read
before scanning: the project's architecture SSOT (its ADR folder and architecture brief),
the layering/structure declaration in the project's own instructions file, and the port and
adapter definitions that name which direction a dependency is allowed to point. Then have it
judge every structural finding AGAINST that declaration and CITE the rule it violates —
"domain imports an adapter, forbidden by <the declared layering>" — never a bare "this looks
coupled". A structural finding with no cited rule is an opinion, and opinions do not belong
in the pile. Also have it load its own methodology skills at dispatch (`nw-quality-framework`
plus whatever its spec names) — loading them is what arms the taxonomy.

Have it carry `<!-- DES-MODE: find -->`, budgeted to run for
~30 minutes, and scan READ-ONLY for:
SSOT/DRY violations, code smells,
architectural drift, performance issues, architectural-boundary violations, test-naming
problems, test-performance issues, and test mistakes — the full checklist, exhaustive,
not a subset. Resolve code facts (callers, dead code, duplication, structural smells)
THROUGH the vendor-neutral code-analysis port (`nw-code-analysis-port` skill) — Tsunami-
preferred, AST/grep fallback, degrade LOUD — never hardcode a specific tool by name, since
Tsunami may not be installed in every session. The dispatched agent reports findings; YOU
(the orchestrator) append each to `techdebt.md` at the repo root (create it if absent) as
a pile row: `- [ ] <item_id>: paradigm=<object-oriented|functional> defect="<defect>"
proposed_solution="<solution>" discovered_by=<channel>`. `paradigm=` is a CLOSED-set field (`{object-oriented, functional}`, SSOT `src/des/domain/refactor/paradigm_select.py:RecognizedParadigm`) -- full grammar + the DERIVE-from-declared-paradigm-never-the-file's-language guidance lives in `des-command-catalog.md`'s Tech-debt pile drain section (same payload, this session). `discovered_by=` is a CLOSED-set field (SSOT `src/des/domain/refactor/discovery_method.py:RecognizedDiscoveryMethod`) -- full value set + the declare-the-surfacing-channel-not-the-verifying-one guidance (incl. the `MISURATO` gotcha) lives in `des-command-catalog.md`'s Tech-debt pile drain section (same payload, this session). Only append a row for a genuine finding — do NOT
fabricate one to justify the loop firing. This loop's job is to ENSURE the scan happens
(dispatch it), not to perform the scan yourself inline — orchestrator delegates domain
work, it does not DIY it.

**`/loop 45m` — drain the tech-debt pile, if one exists.** Separate loop from sourcing
above, on its own cadence, so each can be tuned independently.

**A DRAIN IS DELEGATED, NOT CONDITIONALLY EXECUTED — read this before the mechanics below.**
The failure mode this loop actually suffers is not a bad command: it is the orchestrator
asking *"is there a row I can drain mechanically right now?"*, answering no, and no-opping —
turn after turn, while the pile never moves. "Mechanically drainable" is a criterion nobody
imposed; it gets invented to justify the no-op. A pile row does NOT need to be mechanically
drainable. It needs an OWNER who takes it and exercises JUDGEMENT on it — deciding, item by
item, whether it is a fix, a design, or a row to close because it is already resolved. That
judgement is precisely what a sub-orchestrator can do and a command cannot. So the default
action of this loop is: **hand the pile to an owner with the evidence you already have, a
bounded scope, and the authority to decide per item** — not to evaluate whether conditions
permit you to run a tool. Running the tool yourself is one possible tactic the owner may
choose; it is not what the loop is for. If you find yourself concluding "no row is drainable
right now", you have answered the wrong question: the right one is "who owns this pile until
it is empty, and have I handed it over?"

**When a row closes, MOVE it — never leave it marked `[x]` inline.** A pile that only ever
grows (pending rows plus an ever-longer tail of closed `[x]` ones) defeats the point of
draining it: the file gets harder to read with every session instead of shrinking. The
owner that closes a row must relocate its full line (verbatim, `resolution=` and all) out
of `techdebt.md`/`defects.md` and into `done.md` at the repo root (create it if absent, with
a `## From techdebt.md` / `## From defects.md` section per source file) — not leave it
sitting inline. Only PENDING `- [ ] ...` rows belong in the working pile; `done.md` is the
append-only record of what already closed.

If `techdebt.md` has ≥1
pending row and no drain is already running, invoke `des refactor --pile techdebt.md
--agent-cmd '<path>/refactor_agent.py {prompt}' --max-parallel 1 < /dev/null` (ONE, not N -- see
the safety note below; N is a
CONFIGURABLE number of agents). **`--max-parallel` MUST be 1 until the batch path is gated.** The batch
lifecycle is a COPY of the single-item one, not a loop over it, and the copy never calls the
entry gate at all -- `_entry_gate_refusal` has exactly one caller, on the single-item path. So
`--max-parallel 1` refuses an unattested fix (fail-CLOSED, safe) while `--max-parallel N` MERGES
unattested agent output, N at a time, onto an integration branch it then abandons. That is
fail-OPEN: AI-authored changes land on the operator's branch with no safety verdict consulted.
The parallelism is not worth it until the gate is wired on that path.

**The `< /dev/null` is not optional and not cosmetic** — measured
2026-07-22: every process in the drain's chain inherits the invoking stdin, and the headless agent
at the end of it blocks forever reading a descriptor that delivers data and never reaches EOF,
while the drain blocks draining the capture pipe that same blocked process holds open. Four levels,
no output, no timeout, killed by hand. Redirecting at the OUTERMOST invocation immunises the whole
subtree, because stdin inherits transitively; it is also the agent CLI's own prescription in its
warning text. Without it the drain hangs silently and a working run is indistinguishable from a
dead one. **`<path>` is a real path on THIS machine, not a repo-relative one** — the actuator is
installed under the configuration directory, NOT into the target project, so the older documented
`scripts/refactor_agent.py` resolves to nothing in a consumer's own repo and the harness refuses
every item (`shutil.which` probes the literal string). Locate the installed actuator, or omit
`--agent-cmd` entirely on a build where the DES resolves its own installed actuator. (N is a
CONFIGURABLE number of agents, each draining ONE item independently in its OWN isolated
worktree+venv). Per item: tests must stay green, but ONLY fast+impacted tests scoped to
that item's own change — never a full-suite run per item, that would kill the
parallelism the whole design exists for. Any regression a scoped run can't see is caught
later at the NEXT whole-tree full-suite run, not blocking this drain. Merges into a clean
integration branch, mandatory cleanup on success OR failure either way. If the pile has
zero pending rows, this is a no-op. `--driver loop` is a known stub (parsed, never wired)
— omit it, `python` is the only driver that runs today.

**`/loop 30m` — source the bugfix queue.** When you encounter a friction or a bug during
other work — NOT a backlog item, a defect you just found — write it directly to
`defects.md` at the repo root (create it if absent, same pile-row grammar as
`techdebt.md`: `- [ ] <item_id>: paradigm=<object-oriented|functional> defect="<defect>"
proposed_solution="<solution>" discovered_by=<channel>`) INSTEAD OF adding it to
`docs/product/backlog.md` (backlog.md stays for planned/roadmap work, not for individual
discovered defects). `paradigm=` is the SAME CLOSED set as `techdebt.md`'s
(`{object-oriented, functional}`, SSOT `src/des/domain/refactor/paradigm_select.py:
RecognizedParadigm`), derived from THIS project's own declared paradigm — NEVER the
defect CLASS (`bug`, `SSOT/DRY violation`, etc. are a defect taxonomy, not a paradigm;
writing one there is the empirically observed failure mode this note exists to head off).
Only append a row for a genuinely found friction/bug — do NOT manufacture one to justify
the loop firing.

**`/loop 45m` — drain the bugfix queue, if one exists.** Separate loop from sourcing
above, on its own cadence. Same shape as the tech-debt drain — **including the rule that a
drain is DELEGATED, not conditionally executed**: the default action is to hand the queue to
an owner with the evidence you hold, a bounded scope, and per-item decision authority. "No
row is drainable mechanically right now" is the wrong answer to the wrong question; the right
question is who owns this queue until it is empty. Beyond that: a
CONFIGURABLE number of agents, each resolving ONE bug independently, never two agents on
the same defect. For each pending row in `defects.md` not already in flight (check
`TaskList` and the atdd-pure ledgers under `.nwave/telemetry/atdd-pure/` for a matching
in-progress feature-id first): FIRST create an isolated worktree — `git worktree add -b
bugfix/<name> /home/alexd/Projects/wt/<name> <trunk-branch>` (`uv sync` inside it before
use) — never run the fix in the current/trunk working tree. Then register it with `des
bugfix-pipeline-tick --feature-id <id> --project-root . --defect-id <slug> --action
stage-started --stage rca --now <iso8601>` (the box-lane-serialized-to-one invariant this
records against), then drive it through `/nw-bugfix` end to end IN THAT WORKTREE (RCA →
t=0 charter → regression AT → crafter GREEN → Vera examine → commit) — never a bare
`Agent()` dispatch, same discipline as the first loop above. The resolution itself follows
the SAME S/M/L lane discipline as any other spine work (measured via `des blast-radius`,
never guessed) — most single-defect fixes are S or M lane, but a defect whose fix turns
out to be L-lane (emergent design, many consumers) gets the full per-slice DISPATCH
discipline, not a forced-small hand-edit just because it started as "one bug". On success, merge the
worktree's branch back into trunk and remove the worktree (the 59m worktree-hygiene loop
is the backstop, not the primary mechanism — clean up as part of finishing the fix, don't
leave it for the sweep). Same move-don't-mark rule as the tech-debt drain above: when the
merge lands, relocate the closed row's full line (verbatim, `resolution=` and all) out of
`defects.md` and into `done.md` at the repo root, under its own `## From defects.md`
section — do not leave a `[x]`-marked row sitting inline in the working pile. Note `des
work-exhausted-tick` / `des bugfix-pipeline-tick` /
`des consolidation-signal-tick` already auto-fire once per SessionStart
(`handle_session_start()`) — this loop feeds real work INTO that bookkeeping, it does not
duplicate it. If `defects.md` has zero pending rows, this is a no-op.

**`/loop 20m` — don't skip the upstream design waves, for features AND for fixes that need
prefactoring.** Do NOT avoid `/nw-discuss` and `/nw-design` for new features — and run
`/nw-design` for FIXES that require a prefactoring too. A fix is not automatically fast-lane: if
it needs restructuring FIRST (prefactoring), or the defect is really one facet of a coupled
feature with emergent design or many consumers, it is L-lane work and goes through DISCUSS/DESIGN
like a feature, not the quick bugfix lane. Measure `des blast-radius` before routing a defect to
the bugfix lane; if it comes out L-lane or needs prefactoring, DESIGN runs. Decomposing one
coupled feature into several "independent" bugfixes that each share a single user surface is the
failure this prevents — none of them passes examine in isolation because the surface only works
when all the facets land. (Skipping DESIGN still requires explicit HUMAN authorization — the
default is DESIGN runs, never a self-authored skip witness.)

## Precedence

Live user instructions always override this mandate. If the user says to stop asking, or
to keep loops off, honor it immediately and do not raise it again this session.

## Why this lives here, not in a project-only file

This content ships with nWave (`nWave/data/orchestrator-affordance/`, installed via the
DES plugin, `scripts/install/plugins/des_plugin.py`), so it reaches
every nWave session regardless of project-local hook customization, and refreshes on the
same 15-minute cadence as the rest of the affordance catalog — never the stale,
once-per-session-only class of gap this file's sibling hook
(`orchestrator_affordance_refresh.py`) was built to close.
</EXTREMELY-IMPORTANT>
