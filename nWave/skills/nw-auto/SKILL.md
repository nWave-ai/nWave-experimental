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

Root does not run `des code-fact query.* SUBJECT --root ROOT` itself. Root
delegates the bounded brief — capability, subject, and root — to
`nw-acceptance-designer`, which owns the one bounded CodeFactPort query per
slice and returns its reuse/architecture facts in the existing
`DeliveryContract`. Raw `find`, `grep`, or `cat`-style repository discovery is
never a substitute for a code fact and must not be used for structural
lookup, by root or by the dispatched role.

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

## Worktree ownership — before role dispatch

Two cwd-local probes only — never `git -C`/`cd`/compound shell/substitution:

1. `git rev-parse --show-toplevel` → root
2. `git rev-parse --abbrev-ref HEAD` → attachment

| Attachment | Action |
|---|---|
| `HEAD` | reuse cwd as-is, dirt or clean; zero `git worktree add`, zero relocation; no session heuristic |
| branch name | sibling = root + `.nwave-auto`; `git worktree list --porcelain`; registered, or `git worktree add --detach <sibling> HEAD` fails occupied → refuse fail-closed (WHAT: path registered/occupied; WHY: ownership/cleanliness unprovable; HOW: reconcile/remove, retry) — never adopt; else run that add |

Never branch, or delete/reset/clean/stash/force/adopt. WIP stays bit-identical.

**Root propagation:** this root is an immutable dispatch input. Every Agent
dispatch (DISCUSS, DESIGN, PO, ATD, crafter, examiner) must receive that exact
absolute root and treat it as sole repository — never rediscovered via global
find, nearest-repo, transcript inference, or another clone.

## Architecture readiness — shared M/L prefix

Before either route dispatches PO/ATD, root resolves intent and architecture
readiness through this ordered, bounded sequence. It is explanatory
prompt-level algebra only — never persisted, never a schema, never a
controller state — and it is the ONE prefix both M and L run; there is no
separate M/L architecture-gap split and no duplicated per-route algorithm.

1. **Intent**, conditional: if an intent gap exists, dispatch DISCUSS once,
   then re-evaluate intent. If the gap remains, refuse with a concise intent
   blocker.
2. **Architecture readiness**, conditional, evaluated only after intent is
   resolved:

   ```
   ArchitectureReadiness =
     Covered(DesignAuthorityRef) | NoImpact(Evidence) | Unresolved
   ```

   - **Covered** carries an explicit repo-relative locator plus the relevant
     section of an existing durable brief/ADR, supplied by the user, an
     upstream wave, or the DESIGN consult below. Root never scans the
     repository to discover this locator itself.
   - **NoImpact** carries explicit upstream/RCA evidence that persistence,
     public contracts, ports/boundaries, failure semantics,
     timing/concurrency, and paradigm are all unchanged by this slice.
     Missing evidence is never NoImpact — absence of a stated architecture
     concern is Unresolved, not NoImpact.
   - **Unresolved** is the default whenever neither of the above holds. It
     dispatches exactly one DESIGN consult, then re-evaluates: DESIGN
     returns either a Covered reference or a concise architecture blocker.
     If the gap remains after that one consult, refuse with the blocker —
     never a second DESIGN dispatch.

   Only Covered or NoImpact enters FloorReady (the M/L floor below).

The total consult bound across a run is two: at most one DISCUSS, then at
most one DESIGN, conditional, independent, and serial — never parallel. Skip
either consult when its gap is absent.

Any incomplete terminal role result — from DISCUSS, DESIGN, or the floor
below — immediately ends root work: report only. No root discovery, Task
bookkeeping, retry, repair, or reconstruction follows an incomplete result.

## M/L route — shared reuse floor

Once intent is resolved and architecture readiness reaches Covered or
NoImpact above, M and L run this identical floor — there is no M-only or
L-only variant of it. Dispatch the PO/ATD sibling pair as two background
Agent dispatches, issuing both before waiting on either result — neither
reads the other's output. Then join on both validated results and continue
without a second controller:

1. **Sibling dispatch (PO and ATD dispatched in the background before either
   result is awaited):**
   - `nw-product-owner` (value-side inputs only) additionally receives, as
     part of its seed, the target repository's own documented user-facing
     local onboarding/setup excerpt (e.g. its README's local-install/quick-start
     section). It runs `des charter-scaffold`, fills the expectation charter's
     Preconditions/start recipe by grounding it in that excerpt — never
     inventing a signup path — sets the oracle, then stops before the Human
     workflow.
   - `nw-acceptance-designer` receives the same immutable value seed as the PO,
     plus the design SSOT, and, when architecture readiness resolved as
     Covered or NoImpact, the exact Covered reference or NoImpact evidence —
     never a root-authored paradigm/targets/storage/boundary/implementation
     guess or open design choice. It authors the minimal thin
     `DeliveryContract` v1.1 and acceptance tests. The contract must carry
     `paradigm`; the ATD never authors or reads the charter/start recipe.
2. **Join:** after BOTH the charter is verified and contract+tests are
   validated, dispatch exactly one crafter selected by the deterministic
   paradigm mapping. That crafter implements the contract to green without
   rewriting the acceptance-designer's tests. Root never authors, repairs, or
   reconstructs either sibling's output: a failed or incomplete first result
   is terminal under the single-pass rule, never a root-side patch-up.
3. One independent `nw-user-examiner` examines the running product using the
   charter, whose Preconditions contain the start recipe, and rejects every
   other artifact.
4. Root reports the role verdicts, focused evidence, and Git diff/status.

## L route — same prefix, same floor

L runs the identical Architecture readiness prefix above, then the identical
M/L route floor above. There is no separate L-only algorithm: L differs from
M only in which gaps `nw-mode-select` observed before dispatching into this
skill, never in a distinct in-skill procedure.

## Examiner input isolation

The examiner receives exactly two inputs from the acceptance-designer:

- the expectation charter; and
- the user-surface start recipe.

Never send the examiner code facts, acceptance tests, a test command, source
paths, implementation claims, or a source-reading fallback. The examiner
derives probes from the expectation and observes only the shipped user surface.

## Route boundaries

- Auto roles are single-pass: the first result of each dispatched role
  (acceptance-designer, crafter, examiner) is terminal. No `SendMessage`,
  resume, retry, or correction within the same Auto run. A later retry is a
  separately measured new run, issued only after the upstream gap that
  caused the first result is corrected.
- Direct S and Human-on-the-loop routes are unchanged.
- No `TaskCreate` bookkeeping, new hook, schema, CLI verb, or duplicate
  sequencer/controller is introduced by this skill.
- Auto ends with one of these terminal Git outcomes in the isolated worktree
  decided above; no ledger or seal is created:
  - **PASS** — the current checkout must be neither `main` nor `master` (the
    worktree-ownership step above guarantees this by construction); remove
    only ephemeral artifacts the run itself created (e.g. `__pycache__/`,
    lock files regenerated by tooling) or ensure they are properly ignored,
    without touching any pre-existing user WIP, then commit the accepted diff
    as a normal commit on the isolated worktree's detached HEAD (no push,
    hooks run normally) and report the clean status and exact commit SHA.
    Refuse to commit PASS on `main`/`master`.
  - **FAIL** — follow Vera's failure rule: report the concrete observation for
    acceptance-designer re-entry and preserve the current WIP exactly as-is;
    do not commit, reset, clean, or claim completion.
  - **INDETERMINATE** — do not commit or claim completion; report the exact
    worktree path, current branch plus `git status`, and commit SHA so the
    WIP has an explicit recovery pointer.
- Root stops and reports a concise blocker when a required role or user surface
  is unavailable; it does not silently replace that role.
