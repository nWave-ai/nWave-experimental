---
name: nw-mutation-test
description: "Run an explicit mutation probe over the validated delivery delta, or support the project-level nightly-delta policy. Disabled by default."
user-invocable: true
argument-hint: '[--delivery-contract <path> | --nightly-delta] [--threshold 80]'
---

# Mutation Test

Mutation testing is **disabled by default**. This skill runs only after an
explicit on-demand invocation or when the project itself declares
`Mutation Testing Strategy: nightly-delta`.

It is a standalone diagnostic outer loop, not a DELIVER phase, rigor knob, completion
gate, workflow state or substitute for semantic acceptance tests.

## Input authority

- Explicit probe: validate the named DeliveryContract, then intersect its
  production targets with the terminal candidate diff.
- Nightly delta: use production files changed since the last successful
  mutation run.
- Never infer targets from `docs/feature/`, feature-delta, a progress ledger,
  filenames alone or the implementation agent's claims.

If the intersection is empty, report `not-applicable` and stop. If a target is
missing, outside the repository or not production code, fail loudly before
starting a mutation tool.

## Execution

1. Detect the project's language and existing mutation runner. Do not impose a
   Python-specific tool on another language.
2. Prove the target's ordinary tests pass with the project's declared runner.
3. Snapshot the user's worktree status.
4. Create a dedicated disposable worktree or copy and run all mutations there.
   Never mutate, reset or restore the user's worktree.
5. Compare the user's status with the snapshot and discard only the disposable
   target.

No supported runner is an honest `indeterminate`, not a fabricated PASS.

## Result

Default threshold: 80% killed mutants.

- `pass`: kill rate >= threshold.
- `fail`: kill rate < threshold; name surviving mutants by production file,
  line or symbol and the smallest missing observable.
- `indeterminate`: runner unavailable, baseline tests fail, execution is
  interrupted or evidence cannot be attributed to the validated delta.
- `not-applicable`: validated delta contains no mutable production target.

Keep the interactive report concise: verdict, numerator/denominator, per-file
survivor count, and a bounded list of actionable survivors. Do not create a
per-delivery markdown report or another persistent progress artifact.

For `nightly-delta`, CI owns persistence: create or update one deduplicated
issue containing the same bounded report and the exact comparison range. A
later green run closes that issue. The nightly job must not expand to the
whole repository when its baseline is missing; establish a new baseline
explicitly instead.
