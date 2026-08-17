---
name: nw-finalize
description: "Finalize one whole delivery by joining terminal evidence, proving exact AuthorizedDeliveryPaths scope, and creating the single commit used for clean-checkout closure."
user-invocable: false
---

# NW-FINALIZE: whole-delivery closure

**Wave**: CROSS_WAVE

Finalize runs exactly once, called by `/nw-deliver` after the entire whole
delivery, never per slice and never invoked a second time by a downstream
consumer such as `/nw-bugfix`. Its authority is ADR-SSOT-002 Section 8. It
owns documentary, filesystem and scoped Git hygiene; it creates no progress
record, staging tree or second delivery model.

## Inputs and completion floor

Consume existing terminal evidence only:

- every immutable DeliveryContract belonging to `delivery-id`;
- the crafter's opaque candidate identity, `changed-targets` and terminal
  verification results;
- independent technical review;
- one source-blind Examiner verdict for every validated charter when
  `applicability.examine=true`, including the byte-identical candidate echo;
- the current base revision and complete pending Git path set.

Reject missing, stale, contradictory or nonterminal evidence as
`INDETERMINATE`; reject a known failed obligation as `FAIL`. Never infer
completion from a planning document, filename, status label or prior run.

## `AuthorizedDeliveryPaths`

Finalize computes one prompt-local, ephemeral union of pending
repository-relative paths from already-existing terminal role results only —
never a persisted set, registry or second carrier:

- any pending charter path the PO authored under `Resolve = Author(...)`
  (Section 4b Axis 2) for this delivery;
- ATD's authored acceptance/integration oracle path plus the
  `DeliveryContract` path it wrote together (Section 4b item 1), for a
  `RED_TO_GREEN` slice only — a `GREEN_TO_GREEN` slice binds an existing,
  already-committed locator and contributes no pending path for either;
- any permanent DESIGN authority path (architecture brief section or ADR)
  DESIGN actually changed for this delivery;
- `C`'s reported `changed-targets`;
- this procedure's own explicitly authorized evolution/ADR-link updates
  (step 2 below).

A reused, already-committed artifact — a bound `GREEN_TO_GREEN` oracle, a
`Reuse`d charter, an unchanged architecture page — contributes no pending
path to this union: reuse is read-only. `AuthorizedDeliveryPaths` is
recomputed fresh at each finalize attempt; it is never written to disk.

## Procedure

1. Join contract, candidate, oracle, review and applicable EXAMINE identities.
   A partial or non-PASS join stops without retry or repair.
2. Write or complete exactly the explicitly enumerated authorized
   durable-document updates for this delivery directly to their permanent
   owners — the evolution record and any architecture-brief/ADR link, the
   fifth member of `AuthorizedDeliveryPaths` above. Never a copy, a staging
   file or a second carrier, and never a charter or executable-oracle
   rewrite.
3. Compute the complete pending Git path set, including formerly-untracked paths, and verify it equals exactly `AuthorizedDeliveryPaths` above and nothing else. An unaccounted extra or missing path blocks as `FAIL`/`INDETERMINATE` rather than being silently included or dropped.
4. Verify that no production target, the contract, the oracle or a charter
   mutated after `C`'s terminal `PASS`, and that the current parent/base
   revision still matches the base revision `C` (and, when dispatched, `D`)
   reported.
5. Verify no retired per-delivery root or nWave-owned session artifact (a
   `docs/feature/` tree member, or another file/directory this step
   positively identifies as nWave-owned delivery residue) is newly created
   or changed in the pending diff computed at step 3. A path already
   present, byte-for-byte unchanged, in `C`'s base revision is preexisting
   user-owned state: it is preserved, excluded from this check by
   construction, and is never a finalize input, defect classification target
   or deletion candidate. Only a path that is new or modified in the pending
   diff and positively matches the retired family is reported as a defect;
   this step never deletes, promotes or classifies user-owned state, and
   finalize never deletes any path outside its own verified
   `AuthorizedDeliveryPaths` commit scope.
6. Stage exactly the verified path set, run the normal commit hooks exactly once and create the single whole-delivery commit. Return its immutable SHA. Root must not create another commit.

A scope or identity mismatch at step 3 or 4 blocks the commit as `FAIL`/
`INDETERMINATE` rather than committing a partial or drifted diff.

Report `PASS`, `FAIL` or `INDETERMINATE` with WHAT/WHY/HOW. Finalize persists
no state of its own.

## Clean-tree idempotence law

A rerun against a clean working tree is `PASS` only when both hold against
the current HEAD: its parent equals the exact base revision `C` (and, when
dispatched, `D`) reported for this delivery, AND the committed path set at
that HEAD equals exactly this delivery's recomputed `AuthorizedDeliveryPaths`.
A clean HEAD that fails either equality — a foreign delivery's commit, a
stale base, or a committed path set that has drifted from the expected
union — is `INDETERMINATE` (or `FAIL` when the mismatch is a known
contradiction), never a reused `PASS`. Finalize never infers success from a
merely clean tree alone.

## Global closure

Finalize PASS is local evidence for the commit it created. Global `F` uses a
clean checkout of that exact SHA and reruns the DeliveryContract verification vectors,
then proves installed Claude/Codex parity plus CI, Git and filesystem closure.
Missing or failed `F` is not PASS.

## Invariants

- One finalization and one commit per whole delivery; never per slice and
  never invoked a second time by a downstream consumer such as `/nw-bugfix`.
- Durable facts are written directly to their permanent owners.
- No temporary feature root, promotion plan or cleanup runtime.
- No new schema field, persisted verdict, receipt, ledger or controller.
- No mutation of production, contract, charter or executable oracle after C.
- Exact `AuthorizedDeliveryPaths` equality, clean-checkout replay and
  idempotence are mandatory falsifiers.

## Expected result

```text
Validated: contract + candidate + oracle + review + applicable EXAMINE
Committed: exact AuthorizedDeliveryPaths
Commit: git-<algorithm>:<immutable-revision>
Verdict: PASS | FAIL | INDETERMINATE
```
