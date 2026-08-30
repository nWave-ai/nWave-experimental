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
Require exit code `0` and stdout that is exactly these two identity lines and
nothing else:

```
THIN-DELIVERY-CONTRACT: <repository-relative-json-locator>
THIN-DELIVERY-CONTRACT-DIGEST: sha256:<64-lowercase-hex>
```

Root forwards that stdout verbatim as the first bytes of the E2 AT-review
prompt: no prose, no root line, no JSON paste and no code fence precede them. Exactly
one blank line follows the two dispatch lines, then
`REPO-ROOT: <absolute physical root>` as private forwarded context — never a
public dispatch line or a new carrier. Only bare `APPROVE` or `APPROVED`
advances to E3 craft; `APPROVED WITH CONDITIONS`, any condition, malformed or
`INDETERMINATE` result stops. Root never calls `des dispatch` a second time or
calls `des validate-delivery-contract` itself.

A nonzero exit, missing, malformed or non-two-line stdout is terminal under
the single-pass rule: root never hashes, never reconstructs, never repairs,
never retries, and never re-invokes `nw-auto`; it never dispatches a helper
agent or substitutes a generic writer.

## Worktree ownership — before role dispatch

Two cwd-local observation probes — never `git -C`/`cd`/compound
shell/substitution:

1. `git rev-parse --show-toplevel` → root
2. `git rev-parse --abbrev-ref HEAD` → attachment

| Attachment | Action |
|---|---|
| `HEAD` | run `des worktree-admit --repo <root> --lane auto` from cwd. Its sole stdout path is the execution root: the same cwd when measured durable, otherwise a frozen copy → byte-verify → switch rescue. Nonzero is terminal. |
| branch name | run the identical `des worktree-admit --repo <root> --lane auto`. Its sole stdout path is the new admitted execution root; occupied/registered/unprovable residence refuses fail-closed. |

Root never authors a destination or invokes raw `git worktree add`; the CLI is
the only constructor and writes the positive owner assertion. Never
delete/reset/clean/stash/force/adopt. Rescue leaves the source present and
byte-verifies WIP before the returned execution root changes.

**Root propagation:** the CLI's stdout execution root becomes this root; this root is an immutable dispatch input. Every Agent dispatch (DISCUSS, DESIGN,
PO, ATD, crafter, examiner) must
receive that exact absolute root and treat it as target repository — never rediscovered via global find, nearest-repo, transcript inference, or another
clone.

## Architecture readiness — shared M/L prefix

Before PO or ATD, close this prefix once for the vertical/node. Root does not
hand it to a downstream role unresolved.

| Size | Route |
|---|---|
| M | One independently deliverable vertical. If it is not one, promote to L. |
| L | DISCUSS maps observable ready/blocked value nodes. Every ready node is one independently deliverable vertical; every blocked node names its missing owner/fact. Apply the M prefix to each ready node. |

For an intent gap, dispatch DISCUSS exactly once. If it remains, refuse; never
substitute a root interpretation. Covered readiness is one valid
`ARCHITECTURE-COVERED: <repo-relative-permanent-path>#<section-anchor>` line.
Absent architecture SSOT, a missing additive/no-pattern opinion, or a proof dependency
with `declared=false` or `present=false` is unresolved, never a root-inferred
no-impact shortcut. Dispatch one DESIGN consult for an unresolved M boundary or
for a technical boundary in a ready or blocked L node. It returns
`ARCHITECTURE-COVERED` or `ARCHITECTURE-BLOCKED`; otherwise stop. Root never
installs or repairs dependencies: DESIGN owns readiness, never PO, ATD, or a
crafter. Then run `DISTILL -> DELIVER`; FINALIZE runs once inside that DELIVER,
never as an epic cycle.

For that unresolved technical boundary, dispatch to `nw-solution-architect`:

```
AUTO-ARCHITECTURE-CONSULT: <bounded-subject>
AUTO-ARCHITECTURE-ROOT: <absolute-root>
AUTO-DELIVERY-ROUTE: <RED_TO_GREEN|GREEN_TO_GREEN>
```

These are the entire base prompt. The route is resolved upstream; the
architect consumes it and never infers or defaults it.

Response must be exactly one of:

```
ARCHITECTURE-COVERED: <repo-relative-permanent-path>#<section-anchor>
ARCHITECTURE-BLOCKED: <what>; WHY: <why>; HOW: <how>
```

Missing/malformed header → terminal (single-pass rule). Any incomplete result → report only, stop.

**Repair re-consult — after `des compile-contract` rejects the brief this
same architect authored** (e.g. a target-declaration-table problem): add
ONE more field to the same three-line header, carrying the producer's own
BLOCKED stdout verbatim — the SAME discipline this skill already applies
to the PO/ATD envelopes below (verbatim, never hand-authored, never
paraphrased), never affixed here before now:

```
AUTO-ARCHITECTURE-CONSULT: <bounded-subject>
AUTO-ARCHITECTURE-ROOT: <absolute-root>
AUTO-DELIVERY-ROUTE: <RED_TO_GREEN|GREEN_TO_GREEN>
AUTO-ARCHITECTURE-REJECTION: <<'NW_REJECTION'
<the producer's exact BLOCKED stdout, byte-for-byte>
NW_REJECTION
```

Is the fourth field the exact BLOCKED text `des compile-contract` printed,
or a hand-written summary meant to save a line? Only the former is
admitted — the hook enforcing this envelope (`pre_tool_use_handler.py`,
"Auto-root architect envelope malformed") rejects anything else,
including a summary with the header quoted but the body paraphrased.
Never hand-summarize the rejection before forwarding it: paste it whole,
between the quoted heredoc header and its bare `NW_REJECTION` terminator,
exactly as the `NW_SEED` carrier below already requires for a VALUE-SEED
(K4 camp7 2026-08-23: a hand-paraphrase omitted the Target-cell detail
entirely, three dispatches to converge on a shape the compiler had
already named in full on the first rejection).

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
   des prepare-ordinary-request --size <M|L> --repo-root <absolute physical root> --architecture-authority "ARCHITECTURE-COVERED: path.md#anchor" --delivery-route <RED_TO_GREEN|GREEN_TO_GREEN> --examine <true|false> --independent-review <true|false> [numeric budget overrides] <<'NW_SEED'
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
   des compile-contract --repo-root <root> --delivery-id <producer id> --architecture-authority "ARCHITECTURE-COVERED: path.md#anchor" --route <RED_TO_GREEN|GREEN_TO_GREEN> --examine <true|false> --independent-review <true|false>
   ```

   `--architecture-authority`, `--route`, `--examine` and
   `--independent-review` are the SAME already-resolved Seeded values this
   step already carries from prepare-ordinary-request's own inputs — never
   re-derived, re-typed or paraphrased a second time. `--independent-
   review` is mandatory here specifically so this producer's own citation-
   only proxy (an `ARCHITECTURE_BOUNDARY_CHANGE` obligation) never silently
   disagrees with root's already-resolved Seeded fact. A nonzero is the
   terminal `Blocked` WHAT/WHY/HOW (e.g. no discoverable test-directory
   convention) — root never repairs, retries or falls back to dispatching
   ATD without a compiled skeleton; report the refusal and stop. There is
   exactly one typed continuation for a destination-exists refusal: only
   when the exact stderr carries `WHAT: existing-contract:` (the compiler's
   machine-readable `Blocked.kind` rendered by `_blocked_from`), the
   DeliveryId, physical repository root, base revision, route, examine,
   paradigm, size, budget-token-limit, budget-wall-clock-minutes and
   independent-review compile-input facts are unchanged byte-for-byte, and
   a FRESH architect re-consult has returned a repaired
   `ARCHITECTURE-COVERED` authority may root invoke `des recompile-contract`
   once. The original compile flags are copied byte-identically except for
   `--architecture-authority`, which is replaced only by that fresh repaired
   authority. An `existing-non-file` collision is a distinct terminal
   refusal and never enters this continuation. This is a
   session/router `CompileRejected(existing-contract, identity) ->
   RecompilePermit(same identity + fresh repaired authority) -> Recompiled`
   transition, not a generic retry; the CLI does not persist or enforce the
   permit/counter. A generic rejection, identity mismatch, absent fresh
   repaired authority, second recompile, or nonzero recompile remains
   terminal. On
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
   result in one sentence and stop — never re-dispatch the same role blindly
   on the unproven assumption that a second try will simply finish what
   silence already refused to confirm.

   `CHARTER-RESULT` `INDETERMINATE` citing a missing/vague `PublicStartRecipe`
   or any other value-side authority gap (`CLARIFICATION_NEEDED` — PO's own
   scope) is a PO-scope gap, never a DISTILL/ATD defect: never route it to ATD
   via a contract/oracle correction (Run 8's own mistake — ATD correctly bounces it back
   `EVIDENCE_GAP`, costing a full wasted dispatch). `DeliveryId` is `auto-`
   plus the first 16 hex characters of the SHA-256 digest over the exact
   VALUE-SEED bytes (ADR-SSOT-002); completing the seed with the missing
   recipe changes those bytes, so it is a DIFFERENT `DeliveryId` — restart
   from step 1 with the corrected seed (a fresh `des prepare-ordinary-request`
   / `resolve-charters` / AB batch), never reuse the old id, locator or any
   already-authored contract/charter under it. If instead the SAME
   `DeliveryId`'s charter carries a VALUE-side defect cited by an
   independent reviewer (no seed-byte change — e.g. a wrong
   `PublicStartRecipe` faulted after authoring), run
   `des revise-charter-round --repo-root <root> --delivery-id <id>
   --citation <the reviewer's exact citation text>` and dispatch
   `nw-product-owner` with its exact eight-line stdout verbatim (the
   `DISCOVER: ExistingNeedsRevision` envelope, `CHARTER-CURRENT` carrying
   the existing text as data so the Write-only PO rewrites it in place
   without reading it) — never a hand-composed PO prompt (correctly
   `CHARTER-AUTHOR-DISQUALIFIED`) and never a fresh re-author. If the
   producer refuses (bound exhausted), report `INDETERMINATE` citing the
   exhausted charter revision budget and stop. Contract/oracle correction
   instead starts from the last approved closure and newer native AT review;
   it never mutates a scalar carrier.

4. Validate the charter when applicable, then run the one `des dispatch`
   command from “CLI dispatch” above. Dispatch the AT reviewer foreground
   against C before the selected paradigm crafter. Only exact bare `APPROVE`
   or `APPROVED` permits that crafter. `NEEDS_REVISION` routes to ATD;
   `APPROVED WITH CONDITIONS`, any condition, `INDETERMINATE`, malformed,
   contradictory or unknown output stops. The reviewer is the only route to
   the crafter.

   Require terminal `CRAFTER-RESULT` with matching contract, execution-root,
   oracle, changed targets, first-mutation bound and terminal zero-exit results
   for every declared verification command. The result has no `candidate:`
   field. After PASS, the first implementation-reviewer/Examiner/finalize
   consumer performs E4: it validates the result and Git state, seals or
   replays K, then injects the existing candidate K and execution-root fields
   from Git readback. A PASS opens the single-writer causal window: until the
   terminal commit, no actor may mutate production targets, contract, oracle or
   charters.

   | `CRAFTER-RESULT` verdict | Root routes to |
   |---|---|
   | `PASS` | E4 at the first implementation-reviewer/Examiner/finalize consumer |
   | `FAIL` | Report the terminal FAIL and stop. |
   | `INDETERMINATE` citing a defect in the contract/oracle | Start one strict closure child from the cited approved closure; never mutate a scalar carrier or reuse the rejected closure. |
   | `INDETERMINATE` citing environment/tooling/sandbox | Report the exact executable, argv and observed failure, then stop. Environment admission belongs before delivery; Auto never infers a language, provisions a tool-specific substrate or substitutes a command. |
   | Any other `INDETERMINATE` | Report it and stop. |
   | No complete terminal block | `INDETERMINATE`; report the missing evidence and stop. |

   For implementation review of E4-injected K, only bare `APPROVE` or
   `APPROVED` advances to finalize. `NEEDS_REVISION` with any ATD-owned finding
   routes to ATD; an all-crafter finding set routes to the selected crafter.
   `APPROVED WITH CONDITIONS`, any condition, mixed ownership, malformed or
   unknown findings, and `INDETERMINATE` stop.

   The contract/oracle-citing `INDETERMINATE` row's producer call, root's own
   command (SF friction report 2026-08-20 item 5: this exact invocation was
   previously blocked by the Auto-root Bash allowlist despite this row
   mandating it -- a deadlock resolved only by relaying through a second
   agent; strict-child correction is the only supported replacement
   every other root-run `des` subcommand on this page is):

   ```
   strict closure child from the cited approved closure
   ```

   A non-`none` `contract-fact-gap` (`first-production-mutation-tool-call` past
   15) never changes the row above — it is friction evidence for ATD's next
   contract on this delivery-id class, not a gate on this one. Report it in
   one line alongside the routed outcome and take no other action on it.

   Then, only when examine=true, dispatch one source-blind Vera pass with the
   validated charter sequence and E4-injected K/root fields forwarded
   byte-for-byte. Never send changed-targets to Vera or ask it to derive either
   field from Git/source. Missing, stale, malformed, nonzero or nonterminal
   evidence stops; root never repairs or repeats Vera's public observation.

5. Invoke the `nw-finalize` Skill exactly once with the C/D evidence and
   changed-targets; never dispatch an Agent named `nw-finalize`, call a
   fallback finalization CLI, or commit directly. Finalize performs only its
   verified scope projection and returns its one typed final F result only
   after its fresh clean checkout runs its one exact B-derived
   `PreservationVector` (including authorized verification argv) and remains
   clean. Consume `Commit: git-<algorithm>:<F>`
   and `Clean-checkout: true` before reporting PASS. Installed/CI closure facts
   remain separately applicable evidence; neither repeats finalization. Complete
   only when the original VALUE-SEED is observed; create no receipt, ledger or
   progress artifact. After finalize returns F, satisfy `nw-deliver`'s HAND OFF
   cleanup postcondition exactly; do not restate or weaken it here.

## Examiner input isolation

Dispatched only when Axis 2 resolves `Reuse`/`Author` above (`examine=true`);
never for `Skip`. The examiner receives exactly two inputs — never the
acceptance-designer, which never reads or authors the charter:

- the deterministic non-empty sequence of validated expectation charters,
  each already containing its public `PublicStartRecipe` in Preconditions
  (CLI argv, public library import+setup+call, endpoint+request, or
  URL+ordered UI actions — ADR-SSOT-002 §4b); and
- the admitted K candidate identity and execution-root required to start that
  surface, forwarded byte-for-byte as separate fields (the candidate identity
  and execution root are never combined).

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
  no retry/resume correction of that dispatch. Role
  identity is not run or feature identity: a canonical role may be freshly
  dispatched again for a distinct DeliveryContract/value input, including a
  later vertical needed to close the original VALUE-SEED. Never disguise an
  identical retry as a new slice.
- **Foreground/sync only**: every dispatch `run_in_background=false`. The
  independent calls inside one spatial batch (the AB batch above) may be
  issued together in the same assistant message and run concurrently; root
  joins every call in that batch before starting any dependent step.
- **No infrastructure**: no `TaskCreate`, hook, schema, CLI verb, sequencer/controller.
- **Terminal Git outcomes** (isolated worktree, no ledger): only `nw-finalize`
  creates and verifies the single terminal F. Root never duplicates it. Its
  finalize result contains F and `Clean-checkout: true`; missing either is
  INDETERMINATE. Installed/CI closure stays separate, with no duplicate finalize.
- **Missing/unavailable roles**: stop, report blocker (no silent substitution).
