<EXTREMELY-IMPORTANT>
TRUNCATED PREVIEW? If this looks cut off, or you see a line like "Full output saved
to: <path>" above/below this block: that path IS this same file, re-rendered as a
tool-result. Read <path> (or, failing that, `nWave/data/orchestrator-affordance/
00-standing-loops.md` directly) with the Read tool RIGHT NOW, before your next reply
— a preview that "looks consistent with what you already know" is not a reason to
stop reading. This paragraph is deliberately first so the pointer survives even a
2KB-preview cut.

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
   if a PRIOR session asked and started all nine. "I recall covering this already" is
   about a different session's state, not this one's — it does not satisfy step 3,
   checking does. If ANY are not active in THIS session, ASK about ALL of them together
   in ONE batched message (not one per loop), naming what each does.
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

Starting a loop is a real commitment (background agents, ongoing token spend) — you
ASK, you do not self-start. Skipping the ask because it "felt unnecessary", or doing
it AFTER other tool calls instead of before them, are both the failure this mandate
prevents.

## Red flags — these thoughts mean you are about to skip the ask. Don't.

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
| "This work is X, not nWave delivery, so the sensible default is to leave them off — I'll offer instead of asking" | A default you picked is a unilateral decision wearing the costume of an offer. The mandate is an ASK with all nine named, not a recommendation to decline. Measured 2026-07-22: an instance reasoned exactly this thirty seconds before starting a delivery — and the loops are mostly ABOUT delivery (spine routing, bugfix source/drain, worktree hygiene), so the premise was wrong too. |
| "The recurring cadence was my own scheduling, not the nine loops" | Self-scheduled wakeups are session-scoped too: the restart killed those as well. Measured 2026-07-22: an instance saw its own cadence stop, never connected "session restarted" to "the thing firing all night just died", and resumed ad-hoc. Re-check regardless of which mechanism was driving the cadence. |

## The nine loops

**NAME EVERY ARMED LOOP `Loop N/9 — <what it does>`.** The numbering is not cosmetic: it is what
makes a MISSING loop visible at a glance in a bare `CronList`/`TaskList` listing. Descriptive names
alone cannot show a gap — with `Loop 1/9 … Loop 9/9` a single absent number is obvious, and that is
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

Measured 2026-07-22: an instance armed all nine loops and then, ten minutes later, ran a full
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

**`/loop 59m` — reconcile abandoned worktrees.** Run `git worktree list`. For each
worktree not actively owned by a live dispatch, decide: merge it back (if the work is
done and green), remove it (if fully merged and clean, or abandoned with nothing worth
keeping), finish its implementation now (if close and unblocked), or defer it — updating
the backlog with why and what's left, so it is not silently lost. A worktree lingering
with no decision recorded is the exact drift class `des verify-worktree-cleanup` exists
to catch (⚠️ NEVER run that command without `--check-only` — see the catalog's data-loss
warning above); deciding explicitly here is the cheap alternative to ever needing that
tool's risky ACT mode.

**`/loop 15m` — search for parallel work, never sit idle.** Do not wait passively on a
single in-flight task. Optimize throughput with parallel swarms (cloud-bound stages fan
out; box-bound stages stay serialized to one lane — see the throughput doctrine). Don't
waste tokens: prefer cheap verification (reading a ledger, running a scoped test) over
re-deriving what is already known. When this loop observes a genuine trunk-health signal
(CI red not caused by your own change, a recurring test failure, a build broken on a
clean checkout) — something actually observed, never a hypothesis — record it:
`des consolidation-signal-tick --feature-id <id> --project-root . --signal-type
<drift|unmerged-work|stale-branch|failing-gate> --signal-key <short-slug> --now
<iso8601>`.

**`/loop 20m` — swarm-throughput self-check (N cloud lanes, ONE box lane).** This is the
mechanism `swarm-parallel-delivery` depends on — check it explicitly, don't just remember
it. **THE PARALLELISM MECHANISM IS THE ISOLATED WORKTREE, not more agents in one tree:** N
units of work = N worktrees, each with its OWN provisioned environment, so N crafters never
contend (a crafter runs only its own SCOPED tests). What stays serialized behind ONE lane is
the box-bound legs — the seals, the whole-tree verification runs, and the merge-back write.
Fan the reasoning lanes out, serialize the seals, isolate every writer in its own worktree. Load the `nw-throughput` skill (Skill tool) the first time this loop fires in a
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
a real red or green, and risks corrupting output others depend on). (3) While a dispatched
agent runs, ask: what ELSE is running? "Nothing" is the failure state this loop exists to
catch — name the next independent unit and fire it now, not "after."

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
recognizes a finder dispatch — exempt from the classic TDD-dispatch completeness check,
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
proposed_solution="<solution>"`. `paradigm=` MUST be one of the CLOSED set `{object-oriented, functional}` -- the code-refactoring RPP lenses `des refactor` recognises (SSOT `src/des/domain/refactor/paradigm_select.py:RecognizedParadigm`). DERIVE it from the TARGET project's DECLARED development paradigm (its `## Development Paradigm` section, or the equivalent declaration the project ships) -- NEVER infer it from the file's language (a language is not a paradigm) and NEVER put the defect CLASS there (`SSOT`, `code`, `duplication` are defect taxonomy, not paradigms; that is what `defect=` is for). An unrecognised value makes the drain REFUSE the row. Only append a row for a genuine finding — do NOT
fabricate one to justify the loop firing. This loop's job is to ENSURE the scan happens
(dispatch it), not to perform the scan yourself inline — orchestrator delegates domain
work, it does not DIY it.

**`/loop 45m` — drain the tech-debt pile, if one exists.** Separate loop from sourcing
above, on its own cadence, so each can be tuned independently. If `techdebt.md` has ≥1
pending row and no drain is already running, invoke `des refactor --pile techdebt.md
--agent-cmd 'scripts/refactor_agent.py {prompt}' --max-parallel N` -- that script is the SHIPPED ACTUATOR; `--agent-cmd` must name a real
executable (the harness probes it with `shutil.which`), so there is nothing to invent here (N is a
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
`techdebt.md`) INSTEAD OF adding it to `docs/product/backlog.md` (backlog.md stays for
planned/roadmap work, not for individual discovered defects). Only append a row for a
genuinely found friction/bug — do NOT manufacture one to justify the loop firing.

**`/loop 45m` — drain the bugfix queue, if one exists.** Separate loop from sourcing
above, on its own cadence. Same shape as the tech-debt drain: a
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
leave it for the sweep). Note `des work-exhausted-tick` / `des bugfix-pipeline-tick` /
`des consolidation-signal-tick` already auto-fire once per SessionStart
(`handle_session_start()`) — this loop feeds real work INTO that bookkeeping, it does not
duplicate it. If `defects.md` has zero pending rows, this is a no-op.

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
