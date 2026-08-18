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
   route, no production mutation by tool-call 15 yields `INDETERMINATE`; do not
   spend the remaining turn budget re-reading the repository.
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
3. **DISPATCH** — project the validated input as the first bytes of the
   selected crafter's Agent prompt: exactly the two thin headers
   `THIN-DELIVERY-CONTRACT: <PATH>` and
   `THIN-DELIVERY-CONTRACT-DIGEST: sha256:<digest>`, then one blank line, then
   `REPO-ROOT: <absolute physical root>`. Nothing precedes the pair.
   `REPO-ROOT` is forwarded context for the crafter's consumer-boundary check,
   never a third header or carrier. The selected crafter owns production
   targets and returns one terminal `CRAFTER-RESULT`. Root never fills in a
   missing implementation.
4. **VALIDATE CANDIDATE** — require the crafter result's contract/oracle
   identities to match input, its opaque `candidate` identity to carry the
   validated base revision, and its separate `execution-root` field to equal
   the crafter's exclusive worktree root. Never decompose or parse `candidate`
   to recover the root; the two fields are independent and both required.
   Require `changed-targets` to be non-empty and contained by contract
   targets, and every verification command to have a terminal result.
   Otherwise the candidate is `INDETERMINATE`. This PASS opens the
   no-mutation causal window through the single terminal commit.
5. **JOIN REVIEW** — when `applicability.independent-review=true`, require an
   independent actual-diff verdict on the same contract and candidate identity.
6. **EXAMINE** — when `applicability.examine=true`, give Vera every validated
   charter in deterministic order plus its start recipe, the crafter's
   `execution-root` field and its `candidate` identity, both forwarded
   verbatim as the two distinct fields the crafter emitted. Send no
   changed-targets, source, tests or producer claims. Vera performs one
   source-blind pass and echoes the candidate identity unchanged; it never
   derives it with Git/source. When false, record only that the axis was not
   applicable.
7. **HAND OFF** — join applicable verdicts with `PASS` as identity, `FAIL` as
   absorbing and `INDETERMINATE` preventing `PASS`. A terminal candidate exists
   only when required crafter, review and EXAMINE evidence joins without stale
   identities. Invoke the `nw-finalize` Skill exactly once after the whole
   delivery, never per internal implementation segment; it validates scope and
   creates the one terminal commit. Root never commits or calls the finalize
   CLI as a fallback. Global PASS additionally requires clean-checkout `F` on
   that exact immutable SHA.

## Terminal Contract

Return exactly one concise block:

```text
DELIVERY-RESULT
verdict: PASS | FAIL | INDETERMINATE
contract: <locator>@sha256:<closure-digest>
candidate: git-<algorithm>:<base-revision>
execution-root: <absolute-execution-root>
oracle: <locator>
mutation: <first production mutation tool-call, or none>
changed-targets: <non-empty repository-relative paths>
verification: <executed command identities and terminal results>
review: PASS | FAIL | INDETERMINATE | NOT_APPLICABLE
examine: PASS | FAIL | INDETERMINATE | NOT_APPLICABLE
```

`contract` carries the single contract+oracle closure digest; there is no
separate oracle digest field. `candidate` and `execution-root` are the two
distinct fields the selected crafter emitted, forwarded here verbatim as a
product, never merged, split or re-derived from one another.

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
