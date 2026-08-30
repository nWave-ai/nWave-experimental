---
description: Delivers one validated DeliveryContract through the selected paradigm crafter, independent review, source-blind EXAMINE when applicable, and one terminal finalization.
argument-hint: --repo-root <ROOT> --delivery-contract <repository-relative-json>
---

<!-- gates-ref: deliver -->
<!-- outputs-ref: deliver -->

# NW-DELIVER

## Overview

Load `~/.claude/skills/nw-deliver/SKILL.md`; it is the sole orchestration owner.
Do not reproduce or improvise its route in this task.

## Invocation

Require explicit `--repo-root <ROOT>` and `--delivery-contract <PATH>`. Resolve
`PATH` only relative to `ROOT`, then invoke
`des dispatch --repo-root ROOT --delivery-contract PATH` exactly once and bind
its returned two-line contract+oracle closure digest. A missing, stale,
ambiguous or unsafe locator returns
WHAT/WHY/HOW and stops; do not reproduce the schema here.

After dispatch seals C, dispatch the AT reviewer foreground before the selected
paradigm crafter. Only exact `APPROVE` or `APPROVED` permits craft;
`NEEDS_REVISION` routes to ATD, while `APPROVED WITH CONDITIONS`, any condition,
`INDETERMINATE` or malformed output stops. Accept only the crafter's terminal `CRAFTER-RESULT`, which has no
`candidate:` field; process exit, timeout, partial narration and zero-diff
exploration are `INDETERMINATE`. The first implementation-reviewer, Examiner
or finalize consumer performs E4, seals or replays K from Git readback, and
injects the existing candidate/root fields. Root never implements or repairs
the candidate.

Join independent review and one source-blind EXAMINE pass exactly when their
independent applicability axes require them. Forward E4's existing candidate
identity and execution root verbatim to EXAMINE; never send changed-targets or
ask Vera to derive identity from Git/source. For implementation review of K,
only bare `APPROVE` or `APPROVED` advances to finalize; ATD-owned findings
route to ATD, crafter-only findings to the selected crafter, and
`APPROVED WITH CONDITIONS`, any condition, mixed/malformed/unknown findings or
`INDETERMINATE` stop.
Invoke the `nw-finalize` Skill once for the whole delivery after all applicable
evidence joins. It creates the single terminal commit; root never commits or
calls the finalize CLI as a fallback.
Global PASS requires clean-checkout closure on that exact SHA.

## Completion

Return the `DELIVERY-RESULT` block defined by `nw-deliver`, including contract,
candidate and oracle identities, first production mutation, terminal command
results, review and EXAMINE verdicts. Missing or stale evidence cannot become
`PASS`.

## Success Criteria

- exactly one validated DeliveryContract and one value vertical;
- production mutation within the bounded orientation window when required;
- immutable oracle and declared architecture/reuse obligations preserved;
- terminal verification, review and EXAMINE evidence joined by identity;
- no root-authored repair or persistent progress artifact;
- finalization invoked once at whole-delivery completion.
