---
name: nw-spike
description: "Runs a timeboxed PROBE to validate one core assumption, then optionally PROMOTES the probe into a walking skeleton committed to the repository. Use when the feature involves a new mechanism, performance requirement, or external integration."
user-invocable: true
argument-hint: '[feature-description]'
---

> **Code facts** -- resolve structural facts about code through `des code-fact`
> (vendor-neutral, bundled adapters: AST then TextSearch). Degrade LOUD. Never
> ad-hoc grep.

# NW-SPIKE

> **Deprecated wave slot**: SPIKE was a canonical wave phase prior to v3.16.0
> and is now folded into DESIGN's analysis pass. Retained for backward
> compatibility.

## Authority

A spike is an ephemeral probe, never a durable decision carrier. It produces
throwaway code and a findings result; it authors no permanent per-wave
ledger. Every lasting fact a spike surfaces belongs to an existing durable
owner, not to the spike itself:

- **Promote** -- the probe becomes a walking skeleton (real code, one
  acceptance test, committed). Its design implication is written directly
  into `docs/product/architecture/brief.md` or the relevant ADR by DESIGN,
  which reads `findings.md` before starting.
- **Discard** -- `findings.md` is returned as the result. No permanent
  decision record is created.
- **Pivot** -- the assumption was wrong; the corrected question returns to
  DISCUSS or spawns a second probe. Nothing is promoted.

## Required Pass

1. **Skip check** -- run only if the feature needs a new mechanism, an
   unverifiable performance requirement, or an integration with unknown
   behavior. Otherwise skip straight to DESIGN.
2. **Probe** -- validate exactly one assumption. Code lives in `/tmp/`, never
   in `src/`. Max 1 hour, no tests/types/error-handling/abstractions, one to
   two files, timed with `time.perf_counter()`. Write the binary verdict
   (WORKS / DOESN'T WORK), timing and edge cases to `findings.md`.
3. **Promotion gate (interactive)** -- present PROMOTE / DISCARD / PIVOT to
   the user. Do not self-select.
4. **Walking skeleton (only if PROMOTE)** -- refactor the probe into a real
   end-to-end slice: a real user-facing entry point through to a real
   user-visible output, no mocked layer except a costly external service
   (fake/contract pattern), exactly one `@walking_skeleton @driving_port`
   acceptance test, code under `src/`, committed as
   `feat({feature-id}): walking skeleton -- {description}`. Delete the probe
   directory from `/tmp/` after promotion.

## Handoff

Return the verdict and disposition; do not author a `wave-decisions.md` or
any other per-wave ledger. DESIGN reads `findings.md` (and the walking
skeleton, if promoted) before starting and designs the remainder around it.
DISTILL later adds scenarios and integration tests on top of an already
promoted skeleton rather than writing it from scratch.

```text
SPIKE-RESULT
verdict: WORKS | DOESNT_WORK
disposition: PROMOTE | DISCARD | PIVOT
findings: docs/feature/{feature-id}/spike/findings.md
skeleton: <commit sha + acceptance test path, only if PROMOTE>
propagated-to: <brief.md / ADR path, only if a lasting fact was promoted>
```
