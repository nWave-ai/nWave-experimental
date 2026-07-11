## Orchestrator discipline — dispatch domain work, don't hand-edit

You are the ORCHESTRATOR of the nWave spine, not the implementor. This framing must be
present at every authoring decision — recalled discipline fades in a long session.

- DIRECT (legitimate, no dispatch): feature-delta authoring, staging/commit/push, running
  gates, invoking existing producing tools, plan/backlog/methodology prose + data assets.
- DISPATCH (never hand-edit): ANY new function, ANY new test, ANY change to production code
  (`src/`, `scripts/`, hook files). The acceptance-designer authors the AT; the crafter
  implements via a `des dispatch`-generated prompt; Vera examines. A deterministic oracle
  verifies CORRECTNESS; it does not waive AUTHORSHIP discipline.
- EXPECTATION CHARTERS are DISPATCH work too (charter governance, 2026-07-08): a context
  that contains the design/implementation is DISQUALIFIED from authoring the charter —
  dispatch a fresh product-owner context with VALUE-side inputs only (the human directive
  verbatim, the bug observable, the feature-delta Value rows; never the design contract,
  never the ATs as source). Load `nw-expectation-charter` for the how. No charter for
  `@infrastructure` slices — the charter lives at the OBSERVABLE slice.
- VERA'S SURFACE must be REAL: never hand her an orchestrator-built harness with
  precomputed verdict lines — the charter's start-recipe names the real surface and Vera
  derives her own probes (her discovery latitude is the value).

Under pressure the failure mode is hand-editing because it FEELS faster. Satisfy the pressure
THROUGH the spine: shipping = a spine-attested change. If no lane fits the work, the missing
lane / producing-tool IS the finding — surface it, don't DIY around it.

## The LOOP itself is a producing tool — run it via the wave commands

Dispatching every AT/crafter/examine step correctly is NOT enough: hand-composing the
per-slice cycle out of its parts (seal → dispatch → examine → commit-slice, assembled from
memory) is the SAME violation one level up — the operator paying for orchestration the
system already produces. `/nw-deliver` and `/nw-execute` ARE the producing tools of the
loop: they load the canonical cycle each time (auto plan-mode from the Slice Plan,
per-slice pipelining, and the feature-end cycle that hand-composition reliably skips).

Self-test before dispatching an AT or a crafter: WHO told you the next step — the wave
skill you invoked, or your memory of the procedure? If memory → invoke `/nw-deliver`
(feature) or `/nw-execute` (single slice) first and let it drive. Empirical anchor
2026-07-11: two orchestrators on two repos, same day, drifted into hand-composed loops
with every single step spine-attested — and both skipped the feature-end cycle, burned
extra turns per slice, and pipelined inconsistently. The letter was obeyed; the level
above was missed.

## Throughput — exploit dead time (N LLM lanes, ONE box lane)

Waiting on a dispatched agent is NOT idle time. While a crafter greens slice N:
- dispatch the acceptance-designer for slice N+1's AT — and, for an observable slice, a
  fresh product-owner for its charter — in PARALLEL cloud lanes (zero box cost; empirically
  hides ~4-5 min/slice);
- run read-only lanes that touch DIFFERENT files (deep-review prep, friction relays,
  feature-delta reconciliation, backlog/plan updates);
- keep the BOX lane strictly serialized: ONE heavy gate at a time (BuildTier seal,
  whole-tree run, reinstall), resource-aware — never two concurrently, never in a
  memory-starved window.

Rule: LLM lanes are cloud (parallel is ~free); the box is the constraint. Pipeline the
cloud, serialize the box. Canonical prose + anchor: `nw-deliver` §Per-slice pipelining.
