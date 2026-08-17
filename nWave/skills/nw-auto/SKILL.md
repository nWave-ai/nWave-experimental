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

## Deterministic crafter selection

Read and validate the dispatched contract's `DeliveryContract.paradigm`
before any crafter dispatch:

| `DeliveryContract.paradigm` | Crafter |
|---|---|
| `functional` | `nw-functional-software-crafter` |
| `object_oriented` | `nw-software-crafter` |

If `paradigm` is missing or has any other value, return the contract to
`nw-acceptance-designer` as a blocker. Root never guesses or selects by target
language.

## CLI dispatch — the only bridge from CONTRACT_READY to a crafter

ATD returns exactly:

```
DISTILL-RESULT: CONTRACT_READY
REPO-ROOT: <absolute physical root>
DELIVERY-CONTRACT: <repo-relative locator>
```

Root never hand-hashes, hand-validates or hand-repairs the contract or oracle.
After `CONTRACT_READY`, root runs exactly one command:

```
des dispatch --repo-root ROOT --delivery-contract PATH
```

This is the single execution/hash/validation step between DISTILL and DELIVER.
Require exit code `0` and stdout that is exactly these two lines and nothing
else:

```
THIN-DELIVERY-CONTRACT: <repository-relative-json-locator>
THIN-DELIVERY-CONTRACT-DIGEST: sha256:<64-lowercase-hex>
```

Root forwards that stdout verbatim as the first bytes of the selected
crafter's Agent prompt: no prose, no root line, no JSON paste, and no code
fence precede them. Exactly one blank line follows the two dispatch lines,
then `REPO-ROOT: <absolute physical root>` as forwarded context — this is
context for the crafter's own consumer-boundary check, never a third header
or a new carrier. Root never calls `des dispatch` a second time and never
calls `des validate-delivery-contract` itself — that consumer-boundary check
belongs to the selected crafter, not to root.

A nonzero exit, missing, malformed or non-two-line stdout is terminal under
the single-pass rule: root never hashes, never reconstructs, never repairs,
never retries, and never re-invokes `nw-auto`; it never dispatches a helper
agent or substitutes a generic writer.

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

Before PO/ATD dispatch, root resolves (ADR-SSOT-002 §4b): one prefix for M and L, no split.

- **Intent**: Gap? Dispatch DISCUSS once. Gap remains → refuse blocker.
- **Readiness**: Covered means root already holds a valid architecture
  authority line with a repo-relative permanent `.md#anchor`; enter the floor.
  Absence of an architecture SSOT, a root opinion that the change is additive,
  "no new pattern", or any proof dependency an obligation names with
  declared=false or present=false is Unresolved, never a root-inferred no-impact shortcut. Dispatch one
  DESIGN consult immediately. It returns `ARCHITECTURE-COVERED` or
  `ARCHITECTURE-BLOCKED`; a remaining gap is refused. Root never installs or
  repairs a dependency itself — that readiness work belongs to the DESIGN
  consult, never to ATD or the crafter.

For Unresolved, dispatch to `nw-solution-architect`:

```
AUTO-ARCHITECTURE-CONSULT: <bounded-subject>
AUTO-ARCHITECTURE-ROOT: <absolute-root>
AUTO-DELIVERY-ROUTE: <RED_TO_GREEN|GREEN_TO_GREEN>
```

These are the entire prompt. The route is already resolved upstream; the
architect consumes it and never infers or defaults it.

Response must be exactly one of:

```
ARCHITECTURE-COVERED: <repo-relative-permanent-path>#<section-anchor>
ARCHITECTURE-BLOCKED: <what>; WHY: <why>; HOW: <how>
```

Missing/malformed header → terminal (single-pass rule). Any incomplete result → report only, stop.

## Root inputs and spatial AB batch

Root resolves only explicit/direct inputs: Auto size, immutable VALUE-SEED,
physical root and HEAD, architecture authority, route,
examine, independent-review and optional numeric budget overrides. Ambiguous
semantic facts block with WHAT/WHY/HOW. `des prepare-ordinary-request`
exclusively resolves the installed schema and computes/validates DeliveryId,
locator, base revision and default budget; root never searches for or supplies
the schema and never recomputes, revalidates or restates those formulas.

Examine is independent of route: `false` skips PO/Vera; `true` reuses every
valid charter, authors exactly one through PO for a Missing/Empty namespace,
and blocks on Invalid. A RED contract must observe every VALUE-SEED clause at
its real port; internal proxies and later-slice promises are `EVIDENCE_GAP`.

1. Run exactly once, with VALUE-SEED bytes on stdin:

   ```
     des prepare-ordinary-request --size <M|L> --repo-root <absolute physical root>
     --architecture-authority "ARCHITECTURE-COVERED: path.md#anchor"
     --delivery-route <RED_TO_GREEN|GREEN_TO_GREEN> --examine <true|false>
     --independent-review <true|false> [numeric budget overrides]
   ```

   Do not precede it with `des --help`, `which des`,
   `des validate-delivery-contract`, hashing, recounting or another producer
   probe. VALUE-SEED is never argv/env/temp/transcript data. Nonzero is the
   terminal `Blocked` WHAT/WHY/HOW; root never repairs or retries.

2. On `Prepared(SeededAuthority)`, run exactly one command:

   ```
   des resolve-charters --repo-root <root> --delivery-id <producer id> --examine <true|false>
   ```

   Route only by its closed `status`: `SKIP` omits PO and Vera; `AUTHOR`
   dispatches PO with the returned namespace; `REUSE` omits PO and retains
   the returned charter paths only for source-blind Vera; `BLOCK` is terminal
   WHAT/WHY/HOW. Root never runs `find`, a global search, or any ad-hoc
   filesystem inference in its place. ATD always receives only the original
   fourteen-line producer stdout verbatim.

   Then emit one **AB batch in the same assistant
   message**, foreground (`run_in_background=false`):
   - ATD always receives producer stdout verbatim and alone owns oracle plus
     complete contract; it returns `DISTILL-RESULT: CONTRACT_READY`.
   - For `examine=true, Author`, PO concurrently receives only the
     producer-emitted DeliveryId, namespace, root and VALUE-SEED — never the
     architecture-authority anchor, which remains a DESIGN/ATD readiness
     input; it alone writes the charter. For Reuse/Skip, omit PO.

   Neither call observes the other result or shares a write target. Join every
   terminal batch result before any dependent action; a partial/non-PASS batch
   stops without retry.

3. Validate the charter when applicable, then run the one `des dispatch`
   command from “CLI dispatch” above. Forward its two lines verbatim to the
   paradigm crafter. Require terminal `CRAFTER-RESULT` with matching contract,
   opaque candidate identity, oracle, changed targets, first-mutation bound and
   terminal zero-exit results for every declared verification command. A PASS
   opens the single-writer causal window: until the terminal commit, no actor
   may mutate production targets, contract, oracle or charters.
   Then, only when examine=true, dispatch one source-blind Vera pass with the
   validated charter sequence, execution root and the candidate identity
   forwarded byte-for-byte. Never send changed-targets to Vera and never ask
   Vera to derive identity from Git/source. Require Vera to echo that identity
   unchanged. Missing, stale, malformed, nonzero or nonterminal evidence
   stops; root never repairs or repeats Vera's public observation.

4. Invoke the `nw-finalize` Skill exactly once with the C/D evidence and
   changed-targets; never dispatch an Agent named `nw-finalize`, call a
   fallback finalization CLI, or commit directly. Finalize performs only its
   authorized direct durable-owner updates, validates the complete commit
   scope and creates the one terminal commit. Global PASS follows only
   after `F` reruns the contract verification vectors on a clean checkout of
   that exact commit and proves installed/Git/filesystem closure. Report role
   verdicts and immutable SHA only then. Complete only when the original
   VALUE-SEED is observed; create no receipt, ledger or progress artifact.

## Examiner input isolation

Dispatched only when Axis 2 resolves `Reuse`/`Author` above (`examine=true`);
never for `Skip`. The examiner receives exactly two inputs — never the
acceptance-designer, which never reads or authors the charter:

- the deterministic non-empty sequence of validated expectation charters,
  each already containing its public `PublicStartRecipe` in Preconditions
  (CLI argv, public library import+setup+call, endpoint+request, or
  URL+ordered UI actions — ADR-SSOT-002 §4b); and
- the candidate identity and execution root required to start that surface.

Never send the examiner code facts, acceptance tests, a test command, source
paths, implementation claims, or a source-reading fallback. The examiner
derives probes from the expectation and observes only the shipped user
surface. `des verify-charter-filled` is a structural gate only (non-empty
sections, no scaffold residue, >=1 negative observation); it never judges
whether the recipe is genuinely public-surface. That semantic judgment is
never root's or a regex's to make: the examiner's own START step is the
actual semantic check — an internal/application-port "recipe" fails to start
the real public surface and yields `FAIL`/`INDETERMINATE`, never a silent
`PASS`.

## Route boundaries

- **Single-pass dispatches, reusable roles**: each individual Agent result is terminal —
  no retry/resume/`SendMessage` correction of that dispatch. Role
  identity is not run or feature identity: a canonical role may be freshly
  dispatched again for a distinct DeliveryContract/value input, including a
  later vertical needed to close the original VALUE-SEED. Never disguise an
  identical retry as a new slice.
- **Foreground/sync only**: every dispatch `run_in_background=false`. The
  independent calls inside one spatial batch (the AB batch above) may be
  issued together in the same assistant message and run concurrently; root
  joins every call in that batch before starting any dependent step. No
  `Task`/`SendMessage`/`ScheduleWakeup`.
- **No infrastructure**: no `TaskCreate`, hook, schema, CLI verb, sequencer/controller.
- **Terminal Git outcomes** (isolated worktree, no ledger): only `nw-finalize`
  creates the single terminal commit. Root never duplicates it. Global PASS
  additionally requires `F` on a clean checkout of that exact SHA; FAIL
  preserves WIP and reports the observation; missing `F` is INDETERMINATE.
- **Missing/unavailable roles**: stop, report blocker (no silent substitution).
