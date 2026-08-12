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

Root delegates the bounded brief — capability, subject, and root — to
`nw-acceptance-designer`, which owns the one bounded CodeFactPort query per
slice. Root does not run `des code-fact query.* SUBJECT --root ROOT` itself.

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

## Crafter dispatch — first bytes

ATD returns a ready-to-forward authority block. Its first two lines,
byte-for-byte, are exactly:

```
THIN-DELIVERY-CONTRACT: <repo-relative-json-locator>
THIN-DELIVERY-CONTRACT-DIGEST: sha256:<64-lowercase-hex>
```

Root forwards those two ATD-authored lines as the first bytes of the
selected crafter's Agent prompt: no prose, no root line, no JSON paste, and
no code fence precede them. Optional context follows only after one blank
line.

A missing or malformed header is terminal under the single-pass rule: root never hashes, never reconstructs, never repairs, never retries, and never re-invokes `nw-auto`; it never dispatches a helper agent or substitutes a generic writer.

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
absolute root and treat it as target repository — never rediscovered via global
find, nearest-repo, transcript inference, or another clone.

## Architecture readiness — shared M/L prefix

Before dispatching PO/ATD, root resolves intent and architecture readiness
through this ordered, bounded sequence. It is the ONE prefix both M and L
run; there is no separate M/L architecture-gap split. Explanatory
prompt-level algebra only — never persisted, never a schema, never controller
state.

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

1. **Sibling dispatch (PO and ATD dispatched concurrently before awaiting either):**
   - `nw-product-owner`: receives own documented user-facing local
     onboarding/setup excerpt (e.g. README's local-install section), never inventing a signup path. Runs
     `des charter-scaffold`, fills Preconditions/start recipe grounded in that
     excerpt, sets oracle, then stops.
   - `nw-acceptance-designer`: receives immutable value seed, design SSOT,
     and architecture evidence (Covered reference or NoImpact only — never a
     root-authored paradigm/targets/storage/boundary/implementation, and
     never a root-named or root-guessed language or test runner/framework in
     the dispatch prompt). ATD alone detects language and separately
     discovers the project-native test command from repository-owned
     evidence. Authors minimal `DeliveryContract` v1.1 with `paradigm` and
     acceptance tests. ATD never reads charter/start recipe.
2. **Join:** after BOTH charter and contract+tests are validated, dispatch
   exactly one crafter by deterministic paradigm mapping. That crafter
   implements the contract to green without rewriting tests. A failed or
   incomplete first result is terminal under the single-pass rule: root never authors,
   repairs, or reconstructs either sibling's output.
3. One independent `nw-user-examiner` examines the running product using the
   charter, whose Preconditions contain the start recipe, and rejects every
   other artifact.
4. Root reports the role verdicts, focused evidence, and Git diff/status.

## L route — same prefix, same floor

L uses identical Architecture readiness prefix, then M/L route floor: no separate L-only algorithm.

## Examiner input isolation

The examiner receives exactly two inputs from the acceptance-designer:

- the expectation charter; and
- the user-surface start recipe.

Never send the examiner code facts, acceptance tests, a test command, source
paths, implementation claims, or a source-reading fallback. The examiner
derives probes from the expectation and observes only the shipped user surface.

## Route boundaries

- Auto roles are single-pass: the first result of each dispatched role
  (acceptance-designer, crafter, examiner) is terminal and never repeated —
  no retry, resume, or correction within the same run via `SendMessage`. Only
  a separately measured new run, begun after correcting the upstream gap that
  caused the first failure, may proceed.
- Direct S and Human-on-the-loop routes are unchanged.
- No `TaskCreate`, new hook, schema, CLI verb, or duplicate sequencer/controller
  is introduced.
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
