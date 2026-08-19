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

Is root about to dispatch a crafter directly with a prose task description,
before `des dispatch` has emitted `THIN-DELIVERY-CONTRACT`? That dispatch is
cryptographically gated and refused every time — never attempt it; the only
path from `CONTRACT_READY` to a crafter is the exact sequence below.

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

**Root verification discipline.** Is root about to `Read` an implementation
or test file to fact-check the returned brief/ADR, or to hand-edit
`brief.md`/an ADR itself? Both are off-route and never happen: the architect
already self-verified every citation before returning `COVERED`
(`nw-solution-architect`, "Citation self-verification"), and durable
authority belongs to the architect alone. If root still wants a spot-check,
the only one it ever runs is one bounded `des code-fact` call against the
exact cited symbol/file — never a broad `Read`:

```
des code-fact query.atoms-in-file --root <cited-file-path>
```

Verified against this repository's own installed CLI (`--root` takes the
FILE for this one capability). For any other `des code-fact` capability, use
the subject-before-`--root` shape every time (see `nw-solution-architect`,
"Citation self-verification" for the verified working shapes) — the
reordered form (`--root <value>` before the subject) is unreliable, not
merely unrecommended: argparse's handling of a positional trailing an
already-satisfied `--root` differs across CPython 3.12.x patch releases, so
it must never be relied on even where it happens to parse today. A mismatch
is a real architecture defect:
refuse with WHAT/WHY/HOW and re-dispatch the architect naming the exact
mismatch — never repair it by reading further source or editing the
authority directly.

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

**Deciding `--examine`, before it is ever passed to `des
prepare-ordinary-request`:** does the VALUE-SEED name a user-observable
surface the request drives — an API endpoint, a CLI, a UI, a workflow a
human or an external client exercises? Then `--examine true`. Does it name
only an internal-only refactor with no new or changed user-observable
surface? Then `--examine false` (ADR-SSOT-002 Section 5: "A pure internal
prefactoring can set `examine=false`... A user-observable UI/CLI/API/
workflow prefactoring can set `examine=true`"). This is root's own closed
evidence rule, resolved from the seed text alone before the producer call —
`des prepare-ordinary-request` deliberately never infers, defaults or
guesses `examine` itself (its own docstring: "every semantic decision...
is consumed as an explicit already-closed-rule-resolved argv fact, never
inferred, defaulted or guessed here"), so `--examine` stays required and
explicit at the CLI boundary; the criterion above is what root applies to
supply it, never a flip-a-coin or copy-the-last-run's value.

**Before the first `des prepare-ordinary-request` call, when `examine=true`:**
does the VALUE-SEED already carry the literal public start recipe (exact
method+path+example body) PO's `## Preconditions` requires — or are you about
to pass the abstract feature text alone and let PO discover the gap for you?
PO is Write-only (no Read access, by design, source-blind) and can only
project a recipe already present in the seed; root is not. Read the project's
own API/README docs (docs only — never source, tests or architecture) and
complete the seed with the exact recipe those docs already state BEFORE the
first producer call, not after an `INDETERMINATE` reports it missing.

1. Run exactly once, with VALUE-SEED bytes on stdin. The Auto-root Bash
   allowlist permits exactly one stdin shape for this one producer — the
   `des prepare-ordinary-request` call header ending in a QUOTED heredoc
   redirect, all as a single Bash invocation:

   ```
   des prepare-ordinary-request \
     --size <M|L> --repo-root <absolute physical root> \
     --architecture-authority "ARCHITECTURE-COVERED: path.md#anchor" \
     --delivery-route <RED_TO_GREEN|GREEN_TO_GREEN> --examine <true|false> \
     --independent-review <true|false> [numeric budget overrides] <<'NW_SEED'
   <exact value-seed text, byte-for-byte, over as many lines as it needs>
   NW_SEED
   ```

   The delimiter (`NW_SEED`) MUST be quoted — `<<'NW_SEED'` or
   `<<"NW_SEED"` — never bare `<<NW_SEED`: an unquoted heredoc lets the
   shell expand `$(...)`/backticks/variables inside the body, which would
   silently corrupt the seed. Quoted, the body between the header and the
   closing `NW_SEED` line is opaque to the shell — copy the seed in
   verbatim, no escaping, no re-typing, no paraphrase, and it tolerates
   quotes, `|`, blank lines and any other byte. The closing line must be
   exactly `NW_SEED` with nothing else on it, and nothing may follow that
   line — no other pipe/heredoc/composition shape is permitted, and the
   header line before `<<` accepts only the flags shown above, nothing
   else. Do not precede it with `des --help`, `which des`,
   `des validate-delivery-contract`, hashing, recounting or another
   producer probe. VALUE-SEED is never argv/env/temp/transcript data.
   Nonzero is the terminal `Blocked` WHAT/WHY/HOW; root never repairs or
   retries.

2. On `Prepared(SeededAuthority)`, run exactly one command:

   ```
   des resolve-charters --repo-root <root> --delivery-id <producer id> --examine <true|false> <<'NW_SEED'
   <the SAME VALUE-SEED bytes already piped to prepare-ordinary-request, byte-for-byte>
   NW_SEED
   ```

   Route only by its closed `status`: `SKIP` omits PO and Vera; `AUTHOR`
   prints one ready-to-paste `envelope` field alongside `namespace` and
   dispatches PO with THAT envelope, verbatim, as its entire prompt — root
   never authors, reconstructs or augments a PO prompt by hand, the exact
   Run 6 defect (hand-composed PO envelopes rejected twice for a malformed
   header, then a hand-added architecture anchor forwarded into PO's own
   context, `CHARTER-AUTHOR-DISQUALIFIED`, ~8 minutes lost); `REUSE` omits
   PO and retains the returned charter paths only for source-blind Vera;
   `BLOCK` is terminal WHAT/WHY/HOW. Root never runs `find`, a global
   search, or any ad-hoc filesystem inference in its place.

3. Then, still before dispatching ATD, run exactly one more command — the
   mechanical skeleton compiler (ADR-SSOT-002 Section 4/4b item 1). It
   derives `targets`/`verification-scope`/`obligations`/the acceptance-
   oracle locator from the SAME architecture authority, so ATD fills a
   skeleton instead of authoring one from scratch:

   ```
   des compile-contract --repo-root <root> --delivery-id <producer id> \
     --architecture-authority "ARCHITECTURE-COVERED: path.md#anchor" \
     --route <RED_TO_GREEN|GREEN_TO_GREEN> --examine <true|false> \
     --independent-review <true|false>
   ```

   `--architecture-authority`, `--route`, `--examine` and
   `--independent-review` are the SAME already-resolved Seeded values this
   step already carries from prepare-ordinary-request's own inputs — never
   re-derived, re-typed or paraphrased a second time. `--independent-
   review` is mandatory here specifically so this producer's own citation-
   only proxy (an `ARCHITECTURE_BOUNDARY_CHANGE` obligation) never silently
   disagrees with root's already-resolved Seeded fact. Nonzero is the
   terminal `Blocked` WHAT/WHY/HOW (e.g. no discoverable test-directory
   convention) — root never repairs, retries or falls back to dispatching
   ATD without a compiled skeleton; report the refusal and stop. On
   success, this producer's own printed `DELIVERY-CONTRACT-SKELETON`/
   `ORACLE-LOCATOR` lines are root's own confirmation only — they carry no
   new fact ATD needs, since `CONTRACT-LOCATOR` (already in the unchanged
   fourteen-line envelope below) now resolves to a real file ATD reads
   first, and that file already states its own oracle locator.

   Then emit one **AB batch in the same assistant
   message**, foreground (`run_in_background=false`):
   - ATD always receives the original fourteen-line producer stdout
     verbatim, unchanged by this step — never hand-authored, never
     reconstructed, never re-augmented with compile-contract's own output.
     `CONTRACT-LOCATOR` now already resolves to the skeleton this step just
     wrote; ATD fills it (`nw-acceptance-designer.md`, "Compiled skeleton")
     rather than authoring from scratch, and alone owns writing the oracle
     at the skeleton's own given locator; it returns
     `DISTILL-RESULT: CONTRACT_READY`.
   - For `examine=true, Author`, PO concurrently receives only the
     producer-emitted DeliveryId, namespace, root and VALUE-SEED — never the
     architecture-authority anchor, which remains a DESIGN/ATD readiness
     input PO's own role logic disqualifies itself over the instant its
     context carries one; it alone writes the charter. These are
     `resolve-charters`' printed `envelope` field, pasted verbatim as PO's
     entire prompt — root never authors, reconstructs or augments it by
     hand. For Reuse/Skip, omit PO.

   Neither call observes the other result or shares a write target. Join every
   terminal batch result before any dependent action; a partial/non-PASS batch
   stops without retry. Did that role's own response end with its own
   terminal result block (`DISTILL-RESULT:`, `CHARTER-RESULT:`, ...), or does
   its absence make a subagent killed mid-turn (budget exhaustion, timeout,
   an interrupted process) indistinguishable from one still working? A
   response carrying NO terminal result line is `INDETERMINATE` for that
   role, never a nonterminal batch to retry: report the missing terminal
   receipt in one sentence and stop — never re-dispatch the same role
   blindly on the unproven assumption that a second try will simply finish
   what silence already refused to confirm. Before reporting, check
   `.nwave/des/subagent-results/<the dispatched agent-id>.txt` -- the
   SubagentStop hook (stable-design report 2026-08-19 section 1.1) writes a
   synthesized `<ROLE>-RESULT: verdict INDETERMINATE reason: ...` there the
   instant that role's own turn ended with no terminal line; if present,
   quote it verbatim instead of inferring the cause.

   `CHARTER-RESULT` `INDETERMINATE` citing a missing/vague `PublicStartRecipe`
   or any other value-side authority gap (`CLARIFICATION_NEEDED` — PO's own
   scope) is a PO-scope gap, never a DISTILL/ATD defect: never route it to ATD
   via `REVISE-CONTRACT` (Run 8's own mistake — ATD correctly bounces it back
   `EVIDENCE_GAP`, costing a full wasted dispatch). `DeliveryId` is `auto-`
   plus the first 16 hex characters of the SHA-256 digest over the exact
   VALUE-SEED bytes (ADR-SSOT-002); completing the seed with the missing
   recipe changes those bytes, so it is a DIFFERENT `DeliveryId` — restart
   from step 1 with the corrected seed (a fresh `des prepare-ordinary-request`
   / `resolve-charters` / AB batch), never reuse the old id, locator or any
   already-authored contract/charter under it. If instead the SAME
   `DeliveryId`'s contract already exists and only the charter needed a fix
   (no seed-byte change — e.g. a charter citation error caught downstream),
   dispatch ATD via `REVISE-CONTRACT` exactly as the crafter-citing-contract
   row below, never a fresh re-author: the contract's targets/oracle did not
   change, only the charter did.

4. Validate the charter when applicable, then run the one `des dispatch`
   command from “CLI dispatch” above. Forward its two lines verbatim to the
   paradigm crafter. Require terminal `CRAFTER-RESULT` with matching contract,
   opaque candidate identity, oracle, changed targets, first-mutation bound and
   terminal zero-exit results for every declared verification command. A PASS
   opens the single-writer causal window: until the terminal commit, no actor
   may mutate production targets, contract, oracle or charters.

   Route by `verdict` — each row is a question the router answers honestly
   before acting, paired with the imperative for the honest-no case:

   | `CRAFTER-RESULT` verdict | Root routes to |
   |---|---|
   | `PASS` | the examiner pass below (`examine=true`) or step 5 finalize |
   | `FAIL` | Is this a genuine terminal FAIL, not a timeout/partial narration (those are `INDETERMINATE` — nw-crafter-discipline-delivery-contract)? A real FAIL is terminal: report the FAIL evidence verbatim and stop — never redispatch hoping a second attempt succeeds where the evidence already says it cannot |
   | `INDETERMINATE` citing the contract/oracle itself (an invented import, a self-referential obligation, a self-flagged coverage/oracle gap, or any other defect the crafter names IN the delivered contract/oracle — nw-crafter-discipline-delivery-contract item 6, "return an oracle defect to DISTILL"; a self-flagged gap is never `PASS` with the gap only noted in `residuals`) | Does the citation name a real defect IN the contract/oracle, not just an inability to satisfy it? If so, run `des revise-contract-round --repo-root <root> --contract-locator <the SAME CONTRACT-LOCATOR already produced> --citation <the crafter's citation text>` (stable-design report 2026-08-19 section 1.2 -- the bounded producer of the three-line revision body, REVISE-CONTRACT/REVISE-ROUND/CITATION; a durable per-DeliveryId counter refuses once the round would exceed its declared bound, terminal WHAT/WHY/HOW, never an unbounded redispatch loop). Send its exact stdout verbatim as `nw-acceptance-designer`'s dispatch body -- never a fresh `des prepare-ordinary-request` run and never a hand-typed revision body. If the producer refuses (bound exhausted), report `DELIVER-RESULT: INDETERMINATE` citing the exhausted revision budget and stop -- never dispatch ATD again for this DeliveryId. Its stdout is exactly `REVISE-CONTRACT: <locator>` then `REVISE-ROUND: <n>/<N>` then `CITATION: <json-string>`, each on its own line. On the returned `DISTILL-RESULT: CONTRACT_READY`, run `des dispatch` again and redispatch the crafter fresh; `des resolve-charters`/PO are NOT rerun — the charter's validity did not change |
   | `INDETERMINATE` citing environment/tooling/sandbox (nw-crafter-discipline-delivery-contract item 9, "terminal INDETERMINATE after the first failed attempt") | Is this actually a harness gap no contract revision can fix? If so it is terminal: report the INDETERMINATE evidence and stop — never redispatch ATD, the crafter, or restart the cycle hoping the environment resolves itself |
   | No terminal `CRAFTER-RESULT` block at all | Same rule as the batch-join above: `INDETERMINATE`, report the missing terminal receipt, stop — never re-dispatch blindly |

   A non-`none` `contract-fact-gap` (`first-production-mutation-tool-call` past
   15) never changes the row above — it is friction evidence for ATD's next
   contract on this delivery-id class, not a gate on this one. Report it in
   one line alongside the routed outcome and take no other action on it.

   Then, only when examine=true, dispatch one source-blind Vera pass with the
   validated charter sequence, execution root and the candidate identity
   forwarded byte-for-byte. Never send changed-targets to Vera and never ask
   Vera to derive identity from Git/source. Require Vera to echo that identity
   unchanged. Missing, stale, malformed, nonzero or nonterminal evidence
   stops; root never repairs or repeats Vera's public observation.

5. Invoke the `nw-finalize` Skill exactly once with the C/D evidence and
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
