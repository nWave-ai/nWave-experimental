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
