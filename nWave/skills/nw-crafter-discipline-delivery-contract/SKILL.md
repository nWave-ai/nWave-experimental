---
name: nw-crafter-discipline-delivery-contract
description: Crafter discipline for implementing one immutable DeliveryContract with minimal production change, reuse, boundary integrity, and terminal evidence.
user-invocable: false
---

# Crafter Discipline — DeliveryContract

## Boundary

Receive exactly:

```text
THIN-DELIVERY-CONTRACT: <repository-relative path>
THIN-DELIVERY-CONTRACT-DIGEST: sha256:<digest>
```

Resolve the path relative to the supplied repository root and validate it once.
Do not accept copied contract facts, a feature workspace, prose prompt markers
or an alternate carrier. The acceptance oracle named by the contract is
immutable and owned by the acceptance designer.

## Point-of-use contract verification

`des dispatch` (run once, upstream, by root/orchestrator) is the sole
producer of the contract+oracle closure digest; this discipline never
re-invokes it and never reimplements its algorithm. The crafter is a
consumer of that digest and runs exactly one verification command, at
exactly two points — once before BASELINE, and again immediately before
PASS/REPORT:

```text
des validate-delivery-contract --repo-root <absolute-current-repository-root> --delivery-contract <locator>
```

At both call sites, require exit code `0`, a JSON `verdict` of `VALID`, and
its returned `digest` to equal the dispatched `THIN-DELIVERY-CONTRACT-DIGEST`
exactly. A nonzero exit, a non-`VALID` verdict, malformed output or a digest
mismatch at either call is `INDETERMINATE`. Never guess, hand-hash or
reimplement the closure algorithm, and never restate this rule's prose
elsewhere — `des validate-delivery-contract` is the one point-of-use
authority, and these two calls are consumer-boundary checks, not a duplicate
of the producer's `des dispatch` validation.

## Discipline

### Mandatory lens resolution

After validating and reading the contract, but before BASELINE or production
mutation, invoke every matching lens below through the native Skill tool. This
table is the sole normative routing authority; agent bodies and the build-time
catalog never restate its mapping.

| Contract fact | Required Skill |
|---|---|
| `paradigm == object_oriented` | `nw-code-design-oo` |
| `paradigm == functional` | `nw-fp-principles`, then `nw-code-design-fp` |
| `CONTESTED_LAW` or `REPRESENTATION_CHANGE` | `nw-algebraic-design-protocol`; also `nw-fp-algebra-driven-design` on a functional route |
| `INVALID_STATE` or `PRESERVATION` | `nw-certainty-by-construction` |
| `REUSE_CANDIDATE`, `ARCHITECTURE_BOUNDARY_CHANGE`, target `EXTEND`, or `GREEN_TO_GREEN` | `nw-refactor` |
| a required structural fact is absent from the validated contract | `nw-code-analysis-port` |
| verification explicitly selects scoped mutation testing | `nw-mutation-test` |

No matched row is optional. Skill calls count toward the first-mutation bound.
If a matched skill is unavailable or cannot be invoked, return
`INDETERMINATE` before BASELINE. Record the exact invoked names in the terminal
result. Never load PBT/test-authoring skills: ATD owns the immutable oracle.

1. Read the validated contract, immutable oracle and declared target files.
   Bound orientation; when production must change, make the first production
   edit by tool-call 15 or return `INDETERMINATE`.
2. Before creating a responsibility, use `des code-fact` and the repository's
   durable design authority to find an existing port, type or implementation to
   extend. Degrade LOUD if structural facts are approximate.
3. Implement the smallest coherent production change that satisfies the
   oracle. Do not add speculative configuration, defensive branches or
   abstractions without a declared state/failure law.
4. Preserve architectural boundaries, dependency direction and public
   observations. A required boundary change belongs upstream in DESIGN; do not
   smuggle it into implementation.
5. Model domain, application/port, adapter/integration and
   infrastructure/recovery failures through the repository's native language
   so required handling is explicit. Keep the design language-agnostic.
6. Never author, edit, weaken or replace an acceptance test. Return an oracle
   defect to DISTILL.
7. Run the contract's literal verification command vectors through the exact
   declared interpreter. Never substitute an ambient `.venv`, shell string or
   guessed command.
8. Refactor only after GREEN and preserve observations. Batch coherent
   transformations, then execute one terminating relevant suite. Prefer
   deletion and reuse; reject architectural drift.
9. A tool, sandbox or permission refusal is terminal `INDETERMINATE` after the
   first failed attempt. Do not retry the command and do not probe the same
   unavailable substrate with `echo`, `pwd`, `true` or substitute commands.

## Terminal Result

```text
CRAFTER-RESULT
verdict: PASS | FAIL | INDETERMINATE
contract: <locator>@sha256:<digest>
candidate: git-<algorithm>:<base-revision>+worktree:<absolute-execution-root>
oracle: <locator>
mutation: <first production mutation tool-call, or none>
skills-invoked: <ordered names | none>
changed-targets: <repository-relative paths>
verification: <literal command identities and terminal results>
```

`contract` carries the single contract+oracle closure digest; there is no
separate persisted oracle-digest field or duplicate oracle identity line.
`candidate` is an opaque causal identity for the exclusive worktree, not a
content digest. Root forwards it byte-for-byte to the Examiner and finalize;
neither consumer derives or recomputes it.

Timeout, partial narration, zero-diff exploration, identity mismatch or an
unexecuted command is `INDETERMINATE`. Only terminal evidence can be `PASS`.
