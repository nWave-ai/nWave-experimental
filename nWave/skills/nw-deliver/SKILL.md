---
name: nw-deliver
description: "Use for DELIVER wave orchestration from one validated DeliveryContract to one examined candidate and one whole-delivery finalization."
user-invocable: true
argument-hint: '--repo-root <ROOT> --delivery-contract <repository-relative-json>'
---

> **Code facts** — resolve structural facts through `des code-fact`; degrade LOUD when its provider-neutral adapters cannot answer.

<!-- gates-ref: deliver -->
<!-- outputs-ref: deliver -->

# NW-DELIVER

## Overview

Turn exactly one immutable, DISTILL-produced `DeliveryContract` value vertical
into a terminal candidate. The contract owns route, target, oracle, boundary, obligation,
verification-command, applicability and budget facts. This skill coordinates;
it never repairs production code or tests itself.

The discoverable invocation is:

```text
/nw-deliver --repo-root <ROOT> --delivery-contract <PATH>
```

`PATH` is relative to `ROOT`, never to the current directory. The terminal
DISTILL result supplies both values; DELIVER never creates or edits the
contract. When entered directly (not already holding root's forwarded
`THIN-DELIVERY-CONTRACT`/`THIN-DELIVERY-CONTRACT-DIGEST` pair), invoke the
same single `des dispatch --repo-root ROOT --delivery-contract PATH` boundary
root uses and bind the returned contract+oracle closure digest before
dispatch; never call `des validate-delivery-contract` a second time when that
verification already happened upstream. This no-duplicate rule binds
root/orchestrator only: the selected crafter's own entry and terminal
`des validate-delivery-contract` calls (`nw-crafter-discipline-delivery-contract`,
"Point-of-use contract verification") are consumer-boundary checks against
the already-produced digest, never a second producer validation, and remain
required regardless of how root reached this dispatch. Missing, stale,
escaping, ambiguous or invalid input returns WHAT/WHY/HOW and stops. There is
no alternate carrier or textual bypass, and no second schema implementation.

## Core Principles

1. **One authority.** Hand every downstream role the same contract locator and
   digest; never restate its facts in prose.
2. **One value vertical.** A dispatch owns one observable outcome or one
   explicitly behavior-preserving transformation, not a multi-slice queue.
3. **Tests remain ATD-owned.** The crafter may read and run the immutable oracle
   but never edit it.
4. **Implementation-first.** Orientation is bounded. For a production-changing
   route, the selected crafter's own first-mutation bound is diagnostic, never
   itself a stop condition: exceeding it to recover one fact the contract
   already named imprecisely is reported as `contract-fact-gap`, not
   `INDETERMINATE`. Only authority the contract never named at all stops as
   `INDETERMINATE`, at any tool-call number. Root never spends turn budget
   re-reading the repository on the crafter's behalf.
5. **Terminal evidence only.** A stopped process, timeout, partial narration or
   zero-diff run is not delivery completion.
6. **Independent observations.** Technical review and EXAMINE remain distinct
   from the crafter's own result.
7. **One heavy box.** Cloud reasoning may overlap; locally expensive builds and
   suites run one at a time.

## Workflow

1. **VALIDATE** — invoke the single dispatch boundary above exactly once
   (never a second time when root already forwarded its stdout), then verify
   the returned contract+oracle closure digest, repository revision, targets,
   command vectors and positive wall/token budgets.
2. **SELECT** — choose `nw-software-crafter` for `object_oriented` or
   `nw-functional-software-crafter` for `functional`. Any other value blocks.
3. **E2 AT REVIEW** — dispatch the AT reviewer foreground against C before
   the selected crafter. Project the validated input as the first bytes of the
   reviewer prompt: exactly the two thin headers
   `THIN-DELIVERY-CONTRACT: <PATH>` and
   `THIN-DELIVERY-CONTRACT-DIGEST: sha256:<digest>`, then one blank line, then
   `REPO-ROOT: <absolute physical root>`. Nothing precedes the pair.
   `REPO-ROOT` is forwarded context, never a third header or carrier. Only a
   bare exact `APPROVE` or `APPROVED` permits craft. `NEEDS_REVISION` routes
   to ATD; `APPROVED WITH CONDITIONS`, any condition, `INDETERMINATE`, malformed,
   contradictory or unknown output stops.
4. **E3 DISPATCH** — only after E2 approval, project the same bound input to
   the selected crafter. The selected crafter owns production targets and
   returns one terminal `CRAFTER-RESULT`. Root never fills in a missing
   implementation.
5. **VALIDATE RESULT** — require the crafter result's contract/oracle identities to
   match input, its `execution-root` to equal the integration root,
   `changed-targets` to be non-empty and contained by contract targets, and
   every verification command to have a terminal result. A complete
   `CRAFTER-RESULT PASS` has no `candidate:` field. The first
   implementation-reviewer/Examiner/finalize consumer performs E4: it validates
   the result and current Git state, then seals or replays K and injects the
   existing separate `candidate` K plus `execution-root` fields. This E4
   readback, never crafter authority, is the only downstream candidate input.
   Any missing, malformed or mismatched evidence is `INDETERMINATE`. Carry a
   non-`none` `contract-fact-gap` from the crafter result unchanged into the
   terminal `DELIVERY-RESULT`; it is friction evidence for ATD's next contract
   on this delivery-id class, never a join input and never itself cause for
   `INDETERMINATE`.
6. **JOIN REVIEW** — when `applicability.independent-review=true`, require an
   independent actual-diff verdict on E4-injected K. Only bare `APPROVE` or
   `APPROVED` advances to finalization; `NEEDS_REVISION` with any ATD-owned
   finding routes to ATD, while an all-crafter finding set routes to the
   selected crafter. `APPROVED WITH CONDITIONS`, any condition, mixed,
   malformed or unknown ownership stops as `INDETERMINATE`; correction ranks
   remain bounded by §4f.
7. **EXAMINE** — when `applicability.examine=true`, give Vera every validated
   charter in deterministic order plus its start recipe and E4's root-injected
   existing `candidate` K plus `execution-root`. Send no changed-targets,
   source, tests or producer claims. Vera echoes the fields unchanged; it
   never derives them with Git/source. When false, record only that the axis
   was not applicable.
8. **HAND OFF** — join applicable verdicts with `PASS` as identity, `FAIL` as
   absorbing and `INDETERMINATE` preventing `PASS`. A terminal candidate exists
   only when required crafter, review and EXAMINE evidence joins without stale
   identities. Invoke the `nw-finalize` Skill exactly once after the whole
   delivery, never per internal implementation segment. Consume its one typed
   final F result — its one exact B-derived `PreservationVector`, including
   authorized verification argv, already passed in its fresh clean checkout —
   before reporting `PASS`. Then root releases the existing owner marker with
   `des worktree-release --repo <root> --worktree <execution-root>` and runs
   `des verify-worktree-cleanup --repo <root> --target-branch <target-ref>
   --worktree <execution-root>` without `--check-only`. The target ref is
   explicit delivery/integration authority. A non-primary execution root
   closes only when the scoped report contains its matching `CLEANUP_DUE`
   entry with `removed=true`; the Git-primary root may yield an empty scoped
   report and remain. Any nonzero, mismatched or other result is
   `INDETERMINATE`. Never release before F, run unscoped ACT, or substitute raw
   Git. Root never
   commits or calls a finalize CLI as a fallback. Installed/CI closure facts
   remain independently applicable evidence; they never cause a second finalize.

## Terminal Contract

Return exactly one concise block:

```text
DELIVERY-RESULT
verdict: PASS | FAIL | INDETERMINATE
contract: <locator>@sha256:<closure-digest>
candidate: git-<algorithm>:<candidate-revision>
execution-root: <absolute-execution-root>
oracle: <locator>
mutation: <first production mutation tool-call, or none>
contract-fact-gap: <none | one line forwarded unchanged from the crafter result>
changed-targets: <non-empty repository-relative paths>
verification: <executed command identities and terminal results>
review: PASS | FAIL | INDETERMINATE | NOT_APPLICABLE
examine: PASS | FAIL | INDETERMINATE | NOT_APPLICABLE
```

`contract` carries the single contract+oracle closure digest; there is no
separate oracle digest field. E4 injects the existing `candidate` K and
`execution-root` from Git readback after crafter PASS. They are never emitted
by the crafter, merged, split or re-derived; `candidate` is K, never B. Final
`Commit` remains F and never relabels K.

`PASS` is reported only after the finalize result says `Commit: git-<algorithm>:<F>`
and `Clean-checkout: true`, and the scoped cleanup satisfies the HAND OFF
postcondition. Installed host parity and CI, when applicable, are
separate closure facts joined into this same delivery result; neither repeats
finalization nor changes F.

`PASS` requires an accepted terminal result from every applicable owner.
`FAIL` is absorbing. Missing, nonterminal, stale or identity-mismatched evidence
is `INDETERMINATE` and cannot advance to finalization.

## Success Criteria

- one validated contract and one value vertical;
- production mutation inside the orientation bound when production must change;
- immutable oracle and architecture boundaries preserved;
- literal command vectors executed without a shell;
- independent review/EXAMINE applied exactly when their independent axes say so;
- terminal result identities join, with no root-authored repair;
- no persistent progress artifact created.

## Constraints

- Language and test-framework conventions come from the contract and repository.
- Never run a raw shell command from contract data; execute
  `[executable, *arguments]` literally.
- Never weaken a failing oracle, fabricate a verdict or resume a spent agent
  context as if it were a fresh delivery unit.
- Parallelize only independent children with disjoint files after their shared
  interface is frozen; otherwise keep the causal dependency ordered.
