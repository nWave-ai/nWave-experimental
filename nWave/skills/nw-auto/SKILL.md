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

Before PO/ATD dispatch, root resolves (ADR-SSOT-002 §4b): one prefix for M and L, no split.

- **Intent**: Gap? Dispatch DISCUSS once. Gap remains → refuse blocker.
- **Readiness**: Covered/NoImpact? Enter floor. Unresolved? Dispatch one DESIGN consult. Returns `ARCHITECTURE-COVERED` or `ARCHITECTURE-BLOCKED`. Gap remains → refuse.

For Unresolved, dispatch to `nw-solution-architect`:

```
AUTO-ARCHITECTURE-CONSULT: <bounded-subject>
AUTO-ARCHITECTURE-ROOT: <absolute-root>
```

Response must be exactly one of:

```
ARCHITECTURE-COVERED: <repo-relative-permanent-path>#<section-anchor>
ARCHITECTURE-BLOCKED: <what>; WHY: <why>; HOW: <how>
```

Missing/malformed header → terminal (single-pass rule). Any incomplete result → report only, stop.

## M/L route — shared reuse floor

M and L share one floor. Root resolves (ADR-SSOT-002 §4b):

| Axis | Source | Contract |
|---|---|---|
| `delivery-route` | ATD | `RED_TO_GREEN` or `GREEN_TO_GREEN`; never infer/default. Missing → blocker. |
| `applicability.examine` | charter/PO/Vera | Per table below. No new carrier/controller/field beyond schema. |

**Examine resolution:**

| State | Trigger | Action |
|---|---|---|
| `Skip` | `examine=false` | No charter/PO/Vera this run. |
| `Reuse` | `examine=true`, Valid | Carry `ValidatedCharter`s to Vera, no scaffold/PO dispatch. |
| `Author` | `examine=true`, Missing/Empty | Run `des charter-scaffold --seed-mode direct-value --value <seed> --repo-root <root>` once; return `accepted` JSON with exactly one path in `created`/`skipped`. Non-zero exit or malformed → blocker (single-pass rule). On success carry charter path + value-side input to PO. |
| `Block` | `examine=true`, Invalid | Refuse before any role dispatch. |

**Dispatch sequence (foreground, `run_in_background=false`, issued together, root waits inline):**

1. `nw-acceptance-designer` (every run): Forwards architecture authority line + ROOT/VALUE-SEED/DELIVERY-ROUTE (four lines only, no design SSOT/language/framework). Authors `DeliveryContract` v1.2 + acceptance tests (new RED oracle for `RED_TO_GREEN`, or bound existing for `GREEN_TO_GREEN`).
2. `nw-product-owner` (only if `examine=true, Author(Namespace)`): Receives architecture line + charter path. Fills Preconditions/start recipe from documented user-facing excerpt, sets oracle, stops.
3. **Join**: After both validate (ATD always; PO only when dispatched), dispatch crafter by paradigm. Crafter implements to green and returns the ephemeral receipt `outcome: PASS|FAIL`, `argv`, `scope`, `exit_code`. PASS requires `argv` to equal the contract's projected `verification-scope.commands`, `scope` to cover them, and every exit code to be zero. Missing/malformed/truncated/mismatched/nonzero/FAIL → terminal FAIL (single-pass rule), preserve WIP; focused-AT green or Examiner PASS never substitutes. No receipt ledger/artifact.
4. `nw-user-examiner` (only if `examine=true`): Examines using `ValidatedCharter`s + start recipe. One terminal pass.
5. Report role verdicts + Git diff/status.

## Examiner input isolation

Dispatched only when Axis 2 resolves `Reuse`/`Author` above (`examine=true`);
never for `Skip`. The examiner receives exactly two inputs, both carried by
the expectation charter — never the acceptance-designer, which never reads
or authors the charter:

- the expectation charter; and
- the user-surface start recipe, contained in the charter's Preconditions.

Never send the examiner code facts, acceptance tests, a test command, source
paths, implementation claims, or a source-reading fallback. The examiner
derives probes from the expectation and observes only the shipped user surface.

## Route boundaries

- **Single-pass roles**: first result of each (ATD, PO, crafter, examiner) is terminal. No retry/resume/`SendMessage`-correction within run. New run only after upstream gap fixed.
- **Foreground/sync only**: every dispatch `run_in_background=false`, results returned before root's next step. No `Task`/`SendMessage`/`ScheduleWakeup`.
- **No infrastructure**: no `TaskCreate`, hook, schema, CLI verb, sequencer/controller.
- **Terminal Git outcomes** (isolated worktree, no ledger): PASS = clean diff on non-`main`/`master` branch, commit with normal hooks; FAIL = preserve WIP, report observation; INDETERMINATE = report worktree + status + SHA.
- **Missing/unavailable roles**: stop, report blocker (no silent substitution).
