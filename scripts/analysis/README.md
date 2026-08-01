# Context-cost measurement instruments

Fifteen probes plus a reducer, salvaged 2026-07-29 from a session-scoped
scratchpad that would not have survived. They answer *where the tokens go*.

> **`ctxprobe_reduce.py` is NOT the canonical reducer.** The canonical one is
> `scripts/telemetry/context_consumption_reduce.py` (chartered by ADR-D71,
> AT-covered). The two write filenames ONE CHARACTER apart into the SAME
> directory -- `context_consumption.jsonl` (underscore, this one) vs
> `context-consumption.jsonl` (hyphen, canonical) -- so tell their records
> apart by `reducer_version` (`"d71-reducer-1.0.0"` here, `"1"` canonical),
> never by the filename you believe you opened. See the feature-delta section
> "Which reducer is CANONICAL, and the one-character collision".

| script | answers |
|---|---|
| `ctxprobe_reduce.py` | a reducer -- NOT canonical, see the note above: streams transcripts, emits `context_consumption` records |
| `ctxprobe_account.py` | requestId dedup + the cache-chain accounting law |
| `ctxprobe_fleet.py` | per-agent census across the dispatch fleet |
| `ctxprobe_decompose.py` | fixed admission prefix vs task-accrued re-reads |
| `ctxprobe_attrib.py` | byte attribution by tool and by file |
| `ctxprobe_byteturns.py` | the byte-turn ranking (bytes x residency) |
| `ctxprobe_byteturn_categories.py` | the same charge bucketed by CATEGORY, so competing cut proposals share one denominator |
| `ctxprobe_orchestrator_byteturns.py` | byte-turns on the ORCHESTRATOR's own session -- the hook-injected ledger no subagent probe can see |
| `ctxprobe_affordance_admission.py` | which affordance asset owns the admitted window, and whether the runtime serves the revision you are reading |
| `ctxprobe_bashclass2.py` | Bash byte-turns by command class |
| `ctxprobe_bashtarget.py` | search-class targets + the harness output-ceiling probe |
| `ctxprobe_calls.py` | calls per agent, lifetime concentration |
| `ctxprobe_capping2.py` | counterfactual split replay (the capping refutation) |
| `ctxprobe_skills.py` | skill cores, path (a): explicit Read |
| `ctxprobe_skillpathb.py` | skill cores, path (b): Skill tool / invoked_skills |
| `ctxprobe_prefix.py` | admission-prefix residual band |
| `ctxprobe_pairgap.py` | offered-vs-admitted pairing population |
| `ctxprobe_joinkeys.py` | join-key shape conformance |
| `ctxprobe_heading_drift.py` | cross-tree heading-drift control (designed + falsified, NOT wired) |

## The caveats travel with the numbers

Re-measuring without these reproduces the numbers and loses their meaning.

1. **The corpus is MULTI-VERSION.** It spans several Claude Code binaries, so a
   property measured on it is an average over binaries, not a property of
   today's product. Concretely: the ~30 KB Bash-output ceiling is HISTORICAL.
   The current binary persists oversized output to a file and DECLARES it
   (`Output too large (NN KB). Full output saved to: <path>`). Re-establish
   the harness behaviour before inheriting any figure here.
2. **Every byte figure is ADMITTED, not PRODUCED.** Hooks and tool results
   both cross a harness-side admission boundary the emitter cannot observe.
   "Bash produced 18 MB" would be false; it DELIVERED 18 MB after the cut.
3. **The offered-vs-admitted ratio rests on 55 pairable injections of 277.**
   The unpaired population is NOT homogeneous - it holds the largest
   injections in the corpus. The error direction UNDERSTATES the unpaired
   mass. The per-hook persona figure (0.020, ten consistent pairings) is
   solid; the aggregate was withdrawn.
4. **`tool_use_id` is not unique.** The literal `SessionStart` recurs across
   11 records in a field otherwise 99.99% well-formed, and one ordinary value
   is shared by four hook commands in a single firing - it identifies the
   FIRING, not the hook. Pair on a locally minted `correlation_id`.
5. **Bytes-to-tokens is the one ESTIMATE.** Reported as a band (3.2-4.2
   B/token); every derived figure inherits that width. It is not a
   measurement.
6. **`des skill-normative-gate` bare invocation reads an INSTALLED manifest**,
   not the repo's. Pass `--manifest` and `--root` explicitly or it validates a
   tree you are not working on, and passes.
7. **A byte-turn figure means nothing until it names its LEDGER.** The same
   orchestrator-affordance payload measures **0.18%** of tool-admitted byte-turns
   on the subagent corpus and **72.6%** of hook-injected byte-turns on the
   orchestrator's own session, because the hooks fire only on the orchestrator
   lifecycle and their bytes never enter a subagent transcript. A percentage
   quoted without its denominator is not a small number, it is an unmeasured
   one -- the tree once retired the affordance as "efficacy, not cost" on the
   strength of the first figure alone.
8. **The ~2 KB affordance cut is NOT truncation any more.** The current binary
   persists the oversized payload to a file and declares it
   (`Output too large (NN KB). Full output saved to: <path>` + `Preview (first
   2KB)`), so the body costs zero byte-turns unless something reads the path.
   Prose in the tree that reasons about an in-place cut is describing an older
   harness -- same shape as caveat 1.

## The method rule these earned

The first pass of a measuring instrument is suspect BY CONSTRUCTION, because
it is the only version built before its author has seen the data. Six
instances in one day: a Bash classifier putting 84.6% in the residual bucket;
a join-key metric flagging every scope field; a cost model promising to save
556% of the total; a gate certifying a clause it was not looking at; and two
confident predictions - that the memory index was derivable, that the
CLAUDE.md duplication was enormous - both false.

Each was caught by a check costing seconds. Each would have driven a real
decision the wrong way. The corollary that made the difference: **the check
that matters is the one that could embarrass you.** Make the gate fail, look
for the value that contradicts you, compute the counterfactual that might say
your recommendation was wrong. A check you expect to pass tells you nothing.
