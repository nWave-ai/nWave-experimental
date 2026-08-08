---
name: nw-auto
description: "Thin prompt-level router for explicitly authorized Auto M/L work: reuse the acceptance-designer, paradigm crafter, independent examiner, and Git evidence without creating another controller."
---

# nw-auto — thin Auto M/L router

**Requires explicit Auto and explicit M/L** (per `nw-mode-select`). Human mode
and direct S work keep their existing routes.

This skill is prompt-level routing, not a workflow runtime. Root dispatches the
existing roles, preserves their ownership boundaries, and reports evidence. It
does not author the contract, acceptance tests, implementation, or examiner
verdict itself.

## Bounded context lookup

Root and the dispatched technical roles may issue bounded
`des code-fact query.* SUBJECT --root ROOT` commands when a structural code
fact is needed. Replace the capability, subject, and root with the one fact
required for the current slice. The CodeFactPort chooses the provider; raw
repository searches are not a substitute for code facts.

## Deterministic crafter selection

Read and validate the thin contract's `DeliveryContract.paradigm` before any
crafter dispatch:

| `DeliveryContract.paradigm` | Crafter |
|---|---|
| `functional` | `nw-functional-software-crafter` |
| `object_oriented` | `nw-software-crafter` |

If `paradigm` is missing or has any other value, return the contract to
`nw-acceptance-designer` as a blocker. Root never guesses or selects by target
language.

## M route — direct reuse floor

Dispatch, in order and without a second controller:

1. `nw-acceptance-designer` authors the minimal thin `DeliveryContract`, the
   acceptance tests, an expectation charter, and a user-surface start recipe.
   The contract must carry `paradigm`.
2. After the validation above, dispatch exactly one crafter selected by the
   deterministic mapping. That crafter implements the contract to green
   without rewriting the acceptance-designer's tests.
3. One independent `nw-user-examiner` examines the running product.
4. Root reports the role verdicts, focused evidence, and Git diff/status.

## L route — bounded serial gap resolution, then the same floor

Before the M route, resolve gaps independently and in this order:

1. If an intent gap exists, dispatch DISCUSS once, then re-evaluate intent. If
   the gap remains, refuse with a concise intent blocker.
2. After intent is resolved, if an architecture gap exists, dispatch DESIGN
   once, then re-evaluate architecture. If the gap remains, refuse with a
   concise architecture blocker.

An architecture gap triggers exactly one DESIGN consult after intent is
resolved.

The consult bound is two total: at most one DISCUSS followed by at most one
DESIGN. They are conditional, independent, and serial — never parallel. Skip
either consult when its gap is absent. Once both gaps are resolved, run the
same acceptance-designer → selected crafter → independent examiner → Git
evidence floor defined for M.

## Examiner input isolation

The examiner receives exactly two inputs from the acceptance-designer:

- the expectation charter; and
- the user-surface start recipe.

Never send the examiner code facts, acceptance tests, a test command, source
paths, implementation claims, or a source-reading fallback. The examiner
derives probes from the expectation and observes only the shipped user surface.

## Route boundaries

- Direct S and Human-on-the-loop routes are unchanged.
- No `TaskCreate` bookkeeping, new hook, schema, CLI verb, or duplicate
  sequencer/controller is introduced by this skill.
- Auto ends with one of these terminal Git outcomes; no ledger or seal is
  created:
  - **PASS** — verify the current branch is neither `main` nor `master`, commit
    the accepted diff on that current branch, then report the clean status and
    exact commit SHA. Refuse to commit PASS on `main`/`master`.
  - **FAIL** — follow Vera's failure rule: report the concrete observation for
    acceptance-designer re-entry and preserve the current WIP exactly as-is;
    do not commit, reset, clean, or claim completion.
  - **INDETERMINATE** — do not commit or claim completion; report the exact
    current branch plus `git status` so the WIP has an explicit recovery
    pointer.
- Root stops and reports a concise blocker when a required role or user surface
  is unavailable; it does not silently replace that role.
