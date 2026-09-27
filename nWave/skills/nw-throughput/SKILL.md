---
name: nw-throughput
description: Evidence-led orchestration for maximizing delivery throughput with independent fan-out, one heavy local box, and concise whole-value evidence.
user-invocable: true
---

# nw-throughput

Before diagnosing or assigning corrections, load `nw-cross-cutting-invariants`
and apply `delivery:trustworthy-baseline-and-repair-scope`. A blocking observation
requires attention; it does not alone authorize an independent repair.


## Constraint

The bottleneck is usually the shared machine or a causal boundary, not the
number of available agents. Keep cloud reasoning busy while allowing at most
one heavy local build/test/install workload. Measure load and stop adding lanes
when contention increases end-to-end wall time.

## Strategy

1. Select the nearest measurable constraint and shortest falsifier.
2. Fan out only independent work with disjoint ownership in detached worktrees;
   apply the worktree lifecycle below when creating or inheriting a lane.
3. Keep one heavy local build/test/install box; serialize its use.
4. Fan in on the whole delivered value. Keep required review, EXAMINE,
   integration, observation and cleanup; the orchestrating LLM chooses and
   invokes them, while DES persists typed facts and advisory `NEXT` data.
5. Measure wall time, cost, tokens, retries, tool calls, and human
   intervention against the outcome.

## Bounded observed correction context

For a bounded correction with an observed counterexample, targeted context may
be used when it supplies the observation/counterexample, requested delta, exact
candidate, and references to the applicable authorities. Fetch further context
when a required fact is missing; do not repeat the entire narrative handoff.
Preserve semantic decisions and declared quality, then return the commands
actually performed, their evidence, and any facts still missing. This is a
conditional context choice, not a blanket removal of guidance.

## P2: diagnose a changed interface surface once

When the first failure reveals an interface migration, the orchestrating LLM
chooses the related property x consumer test-file scope and runs that complete
scope through the repository's native test executor before paying for the next
broad run. Collect all failures in the selected scope, repair the coherent
contract within the shared repair-scope clause, then run the required broad verification.
Diagnosing an interface migration does not itself authorize that migration. Selected files are evidence
about that scope only; they do not establish whole-project coverage.

Use the repository's own affected-test selector when it exists. In this Python
repository, `python3 scripts/hooks/pytest_touched_files.py --diagnose PATH ...`
is available: it launches every selected runnable file within the normal
bounded ceiling without early stopping, clears ambient `PYTEST_ADDOPTS`
selection filters, and prints the exact argv plus deferred and uncovered paths.
Repository collection configuration still applies. It returns nonzero for
failures, zero collection, an oversized scope, or a scope left incomplete by
deferred/uncovered paths. The ordinary pre-commit command remains fail-fast and
bounded. This example is not a
cross-language requirement: another repository uses its native executor and
must report the corresponding selected, deferred, and uncovered scope loudly.

The LLM selects the scope and the next commands from the observed failures. Do
not add a controller, automatic retry, phase transition, or gate for this
workflow.

## Worktree lifecycle

Use at lane creation, inheritance, finalization and resumed cleanup. Scope:
the Request's owned or explicitly inherited lanes, including temporary build
and evidence copies. Preserve other owners' work; this is no machine-wide sweep.

- **Creation** — In existing task context, name the checkout's purpose, owner
  and condition under which it is no longer needed. Keep one named scope per
  lane; place discovered work under its actual owner in the existing disposition.
- **Reconciliation** — Does the current inventory cover every owned/inherited
  lane and useful residual, or only the accepted feature? Refresh it from current
  bytes and assign each residual a disposition below before claiming closure.

| Disposition | Required basis in existing task context |
|---|---|
| Integrated | Destination and integration evidence for the exact revision. |
| Superseded | Legitimate replacement reference and verified retained replacement bytes. |
| Transferred | Named backlog item plus a verified recoverable artifact outside the checkout, bound to the exact revision. Transfer leaves the work unfinished. |
| Unfinished | Concrete residual, owner and next action; keep required checkout bytes until a verified destination exists. |

- **Cleanup** — Have all useful current revisions survived outside the checkout,
  and has active use ended, or are you relying on an old archive receipt? Verify
  actual destination bytes for current work, including dirty/untracked work and
  needed evidence, or its legitimate retained replacement, immediately before
  removal. Bind that observation to the current revision. Edits invalidate
  verification for the changed revision; refresh preservation and verification.
  Establish no active users/writers and keep the checkout quiescent through
  removal; if this cannot be established, retain it and state the next action.
- **Removal** — Evidence retention needs recoverable bytes, not a live checkout.
  Once reconciliation and no active use are established, invoke existing
  `des lane finalize --repo-root ROOT --worktree PATH` for clean reachable
  lanes. For archive-only temporary copies or dirty/superseded historical
  lanes, use explicitly authorized caller cleanup after verified preservation;
  report the archive disposition, never an invented integration. Report any
  remaining checkout with its purpose and concrete next action.
- **Resume** — After interruption, resume the existing inventory/dispositions;
  reobserve bytes, destinations and active use before the next cleanup action.
  Report feature acceptance separately from residual completion and checkout
  removal. Use existing task context; no new ledger, document or runtime gate.

Incident anchor: `docs/analysis/2026-09-26-worktree-reconciliation.md` — selected
integration left mixed residual work; evidence copies had separate retention
purposes. Feature closure alone did not reconcile those checkouts.

## Feature evolution before cleanup

After the LLM has completed whole-feature review and required evidence, it runs
`des lane integrate --repo-root ROOT --worktree PATH --keep-worktree`; after
that whole-feature integration it invokes `des evolution --repo-root ROOT
--input -` once on destination `ROOT` before cleanup. Never invoke it per slice;
DES does not impose a completion gate. The
closed v1 JSON carries `schema_version`, explicit `date` (`YYYY-MM-DD`) and
`feature_id`, `purpose`, `key_decisions`, `delivered_work`,
`verification_results`, `problems`, `lessons`, and `durable_artifacts`.
Problems and lessons use explicit applicability plus a nonblank reason; use
`not_applicable` rather than invented content. Destinations default to
`docs/evolution/YYYY-MM-DD-{feature-id}.md` and use
`documents.evolution.destination` from unified global configuration with a
project override. On resumed finalization retry the exact same input; it is
idempotent. This command invokes no provider and does not choose a phase,
feature size or cleanup action.

Example shape: `{"schema_version":1,"date":"2026-09-09","feature_id":"feature-id","purpose":"...","key_decisions":["..."],"delivered_work":["..."],"verification_results":["..."],"problems":{"applicability":"not_applicable","reason":"...","items":[]},"lessons":{"applicability":"applicable","reason":"...","items":["..."]},"durable_artifacts":[{"label":"evidence","path":"docs/evidence.md"}]}`. Artifact paths are repository-relative or HTTPS.

Preserve and commit the generated evolution document and its evidence on `ROOT`
before cleanup, then apply the worktree lifecycle above and explicitly run
`des lane finalize --repo-root ROOT --worktree PATH` for this integrated lane.
Finalize only removes a clean lane whose tip is already
reachable from `ROOT`; it never merges or reintegrates. The destination may have
advanced with the evolution-document commit after integration. LLM chooses these
commands; `NEXT` remains advisory.

For features and bugfixes alike, the orchestrating LLM evaluates and revises
S/M/L from current evidence, selects applicable waves and upstream corrections,
and may ignore `NEXT`. DES does not use a size label to route or execute work.
