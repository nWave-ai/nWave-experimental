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
THIN-DELIVERY-CONTRACT: <repository-relative-json-locator>
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

   - **Covered** carries an explicit
     `ARCHITECTURE-COVERED: <repo-relative-permanent-path>#<section-anchor>`
     reference — a repo-relative locator plus the relevant section of an
     existing durable brief/ADR — supplied by the user, an upstream wave, or
     the DESIGN consult below. Root never scans the repository to discover
     this locator itself.
   - **NoImpact** carries an explicit
     `ARCHITECTURE-NO-IMPACT: <repo-relative-permanent-path>#<section-anchor>`
     citation, backed by durable upstream/RCA evidence, that persistence,
     public contracts, ports/boundaries, failure semantics, timing/concurrency,
     and paradigm are all unchanged by this slice. No free prose evidence:
     evidence without that citation form, or a citation without a durable
     upstream/RCA source behind it, is never NoImpact — absence of a stated
     architecture concern is Unresolved, not NoImpact.
   - **Unresolved** is the default whenever neither of the above holds. It
     dispatches exactly one DESIGN consult, then re-evaluates: DESIGN
     returns either an `ARCHITECTURE-COVERED` reference or a concise
     `ARCHITECTURE-BLOCKED` blocker. If the gap remains after that one
     consult, refuse with the blocker — never a second DESIGN dispatch.

   Only Covered or NoImpact enters FloorReady (the M/L floor below).

The total consult bound across a run is two: at most one DISCUSS, then at
most one DESIGN, conditional, independent, and serial — never parallel. Skip
either consult when its gap is absent.

## DESIGN consult — first bytes

When Architecture readiness resolves Unresolved, root's Agent dispatch
prompt to `nw-solution-architect` begins at byte zero with exactly:

```
AUTO-ARCHITECTURE-CONSULT: <bounded-subject>
AUTO-ARCHITECTURE-ROOT: <absolute-root>
```

then one blank line, then the value seed/context. Root passes the same
`<absolute-root>` from Root propagation above — never rediscovered — and a
`<bounded-subject>` scoped to the value seed, never the full DISCUSS/DESIGN
brief. Root never asks this consult to write `feature-delta.md` or run the
full Human DESIGN workflow.

The consult's terminal response begins at byte zero with exactly one of:

```
ARCHITECTURE-COVERED: <repo-relative-permanent-path>#<section-anchor>
```

or

```
ARCHITECTURE-BLOCKED: <what>; WHY: <why>; HOW: <how>
```

`ARCHITECTURE-COVERED` becomes the Covered `DesignAuthorityRef` above;
`ARCHITECTURE-BLOCKED` is the concise architecture blocker. Root never
hashes, rewrites, or repairs either line: a missing or malformed header is
terminal under the single-pass rule, same as the crafter dispatch headers
above.

Any incomplete terminal role result — from DISCUSS, DESIGN, or the floor
below — immediately ends root work: report only. No root discovery, Task
bookkeeping, retry, repair, or reconstruction follows an incomplete result.

## M/L route — shared reuse floor

Once intent is resolved and architecture readiness reaches Covered or
NoImpact above, M and L run this identical floor — there is no M-only or
L-only variant of it. Dispatch the PO/ATD sibling pair as two foreground
Agent dispatches, `run_in_background=false`, issued together in the SAME
assistant message before awaiting either result — neither reads the
other's output, and root never closes its turn to await a background
task notification for either. Then join on both validated results and
continue without a second controller:

1. **Scaffold-before-pair (mechanical, root-owned, before either sibling
   dispatch):** root invokes the installed `des charter-scaffold
   --seed-mode direct-value` CLI exactly once, against the immutable
   value seed — `--value <immutable-verbatim-seed>` and `--repo-root
   <absolute-root>` (the same root from Root propagation above);
   `--feature-id` is forwarded only when the run already carries one,
   otherwise omitted so the CLI derives it mechanically. Root never
   invents a `--feature-id`, authors charter content, or dispatches a
   helper Agent/Task to locate or run this CLI. The run must return
   `accepted` JSON naming exactly one charter path in `created` or
   `skipped` (created-or-existing) — any other verdict, a
   missing/malformed JSON payload, more than one path, or a non-zero exit
   is terminal under the single-pass rule: report the blocker; root never
   repairs, retries, or re-invokes the CLI. On success root carries that
   repo-relative charter path, plus the same value-side input, into the
   PO dispatch below.
2. **Sibling dispatch (PO and ATD dispatched concurrently before awaiting either):**
   Root forwards the selected exact architecture authority line — the
   `ARCHITECTURE-COVERED: <repo-relative-permanent-path>#<section-anchor>`
   line or the
   `ARCHITECTURE-NO-IMPACT: <repo-relative-permanent-path>#<section-anchor>`
   line, whichever resolved above — byte-for-byte as the first bytes of BOTH
   sibling Agent prompts,
   followed by one blank line; it is never reconstructed. The existing
   role-specific context below follows only after that blank line.
   - `nw-product-owner`: owns the expectation charter. Receives own
     documented user-facing local onboarding/setup excerpt (e.g. README's
     local-install section), never inventing a signup path, plus the
     charter path root produced in step 1 above. Fills THAT
     already-created charter's Preconditions/start recipe grounded in
     that excerpt, sets oracle, then stops. PO never runs
     `des charter-scaffold` itself and never dispatches Task/Agent to
     locate or run a CLI gate.
   - `nw-acceptance-designer`: receives immutable value seed via a CLOSED
     carrier that follows the architecture authority line and its blank
     line — exactly:

     ```
     ROOT: <absolute-root>
     VALUE-SEED: <immutable-verbatim-seed>
     ```

     No fourth field, no role-specific free prose, and never the design
     SSOT: root forwards only the exact architecture authority, ROOT, and
     VALUE-SEED — never a root-authored
     paradigm/targets/storage/boundary/implementation, and never a
     root-named or root-guessed language or test runner/framework in the
     dispatch prompt. Root never restates or paraphrases the cited
     architecture and never enumerates or numbers test cases in this prompt.
     ATD alone owns the bounded pre-authoring evidence window defined by its
     own route contract (`nw-acceptance-designer`) — root neither restates
     nor executes that sequence here. Authors minimal `DeliveryContract` v1.2
     with `paradigm` and acceptance tests. ATD never reads charter/start
     recipe.
3. **Join:** after BOTH charter and contract+tests are validated, dispatch
   exactly one crafter by deterministic paradigm mapping. The PO/ATD
   sibling pair above is a two-call foreground pair issued together in one
   SAME-message pair; the crafter dispatch here is a single, separate
   dispatch issued only after both sibling results validate — it too is
   foreground and synchronous — root waits on its result inline, never
   `run_in_background`, and never a second concurrent dispatch. That
   crafter implements the contract to green
   without rewriting tests, then closes its
   terminal result with its own concise verification receipt from the
   terminating full relevant suite run: `outcome: PASS|FAIL`, `argv`, `scope`,
   `exit_code`. Root requires that receipt — present, well-formed,
   `outcome: PASS`, `exit_code == 0` — before dispatching the examiner or
   committing. A failed or incomplete first result is terminal under the
   single-pass rule: root never authors, repairs, or reconstructs either
   sibling's output. A missing, malformed, truncated, nonzero, or `FAIL`
   receipt is itself terminal FAIL under that same single-pass rule: preserve
   WIP exactly as-is; no retry, resume, root repair, or source-inspection
   substitution. A focused-AT-green result or an Examiner PASS never
   substitutes for this receipt.
4. One independent `nw-user-examiner` examines the running product using the
   charter, whose Preconditions contain the start recipe, and rejects every
   other artifact.
5. Root reports the role verdicts, focused evidence, and Git diff/status.

## L route — same prefix, same floor

L uses identical Architecture readiness prefix, then M/L route floor: no separate L-only algorithm.

## Examiner input isolation

The examiner receives exactly two inputs, both carried by the expectation
charter `nw-product-owner` authors — never the acceptance-designer, which
never reads or authors the charter:

- the expectation charter; and
- the user-surface start recipe, contained in the charter's Preconditions.

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
- Root never ends its turn awaiting a background task notification and never
  polls: every Agent dispatch above is foreground/synchronous
  (`run_in_background=false`), including the PO/ATD pair issued together in
  one message, so the tool runtime returns both results before root's next
  reasoning step. No `Task`, `SendMessage`, or `ScheduleWakeup` call is used
  to join the sibling pair.
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
