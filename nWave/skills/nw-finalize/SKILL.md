---
name: nw-finalize
description: "Finalize one whole delivery by joining terminal evidence and returning one verified final commit F."
user-invocable: false
---

# NW-FINALIZE: whole-delivery closure

**Wave**: CROSS_WAVE

Finalize runs once for a whole delivery, called by `/nw-deliver`; a rerun
reverifies its exact final commit rather than creating a second one. Its
authority is ADR-SSOT-002 Section 8. It owns no progress record, staging tree
or second delivery model.

## Inputs and completion floor

Consume existing terminal evidence only:

- every immutable DeliveryContract belonging to `delivery-id`;
- the recognized `candidate: git-<algorithm>:<K>` and separate
  `execution-root`, injected by E4 from Git readback, whose HEAD is exactly K,
  plus its `changed-targets` and terminal verification results. These are never
  crafter authority;
- independent technical review;
- one source-blind Examiner verdict for every validated charter when
  `applicability.examine=true`, including the byte-identical candidate echo;
- the current base revision and complete pending Git path set.

Reject missing, stale, contradictory or nonterminal evidence as
`INDETERMINATE`; reject a known failed obligation as `FAIL`. Never infer
completion from a planning document, filename, status label or prior run.
Caller-supplied vectors or metadata are non-authoritative.

## `AuthorizedDeliveryPaths`

Finalize authors no paths. `AuthorizedDeliveryPaths` is the admitted
`Diff(B,K)`, computed from Git objects; it is never persisted or supplied by a
separate role result.

## Procedure

1. Join contract, candidate, oracle, review and applicable EXAMINE identities.
   A partial or non-PASS join stops without retry or repair.
   `candidate` is admitted K and `execution-root` is separate: mechanically
   require root HEAD=K before any projection. Never translate K into B or use
   a combined candidate/worktree form; derive B only from K's admitted
   closure ancestry. F is the final terminal Commit, never a relabelled K.
2. Compute the complete pending Git path set, including formerly-untracked paths, and verify it equals exactly `AuthorizedDeliveryPaths` above and nothing else. An unaccounted extra or missing path blocks as `FAIL`/`INDETERMINATE` rather than being silently included or dropped.
3. Verify that no production target, the contract, the oracle or a charter
   mutated after K's terminal `PASS`. Derive B only from K's admitted strict
   parent closure ancestry; do not accept a base from prose, a candidate
   translation, or the current worktree.
4. Verify no retired per-delivery root or nWave-owned session artifact (a
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
5. Invoke the private final projection constructor with K, derived B, the
   symbolic target ref read from the original user root, and exactly
   `AuthorizedDeliveryPaths`. It uses a fresh detached root/private index.
   Stage exactly the verified path set, `AuthorizedDeliveryPaths`, and nothing
   else. It records the projection tree, runs normal commit hooks exactly once
   through one ordinary commit with canonical deterministic final metadata and
   reads back F. Resolve one exact
   B-derived `PreservationVector` internally from the admitted C contract over
   B; it contains the authorized verification argv. In a fresh clean checkout
   of F, run that vector; the checkout must remain clean.
   Only then perform `git update-ref <target-ref> <F> <admitted-predecessor>`
   where the admitted predecessor is B or K, and return the typed final F.
   Hook, tree, path, verification, cleanliness or CAS disagreement is
   `INDETERMINATE`; it never redispatches. F is the single whole-delivery commit.

A scope or identity mismatch at step 2 or 3 blocks the commit as `FAIL`/
`INDETERMINATE` rather than committing a partial or drifted diff.

Report `PASS`, `FAIL` or `INDETERMINATE` with WHAT/WHY/HOW. Finalize persists
no state of its own.

## Idempotence law

A rerun may return `PASS` only for the exact F previously constructed for this
delivery. It recomputes `AuthorizedDeliveryPaths`, reconstructs the exact
B-derived `PreservationVector`, checks F's committed path set, then reruns it
in a fresh clean checkout of F. It performs no second commit or state-changing
CAS; its only CAS is an atomic same-object no-op. It never infers success from
a merely clean tree. A foreign, stale or mismatched F is
`INDETERMINATE` (or `FAIL` for a known contradiction).

Installed host parity, CI and EXAMINE are separate delivery-closure facts.
EXAMINE is joined before F; installed/CI evidence is consumed after this one
finalize result and does not invoke finalization again.

## Invariants

- One finalization and one commit per whole delivery; never per slice and
  never invoked a second time by a downstream consumer such as `/nw-bugfix`.
- No temporary feature root, promotion plan or cleanup runtime.
- No new schema field, persisted verdict, receipt, ledger or controller.
- No mutation of production, contract, charter or executable oracle after C.
- Exact `AuthorizedDeliveryPaths` equality, fresh-clean-checkout verification
  and idempotence are mandatory falsifiers.

## Expected result

```text
Commit: git-<algorithm>:<F>
Clean-checkout: true
Verdict: PASS | FAIL | INDETERMINATE
```
