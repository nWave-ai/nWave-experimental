---
description: Compiles permanent architecture and value authority into one minimal executable oracle and one validated DeliveryContract for a RED_TO_GREEN or GREEN_TO_GREEN route.
argument-hint: '[delivery-id]'
---

# NW-DISTILL

## Overview

Load `~/.claude/skills/nw-distill/SKILL.md`; it is the sole methodology owner.
ADR-SSOT-002 owns the delivery algebra. Do not reproduce either authority in
this task.

## Invocation

Resolve the permanent architecture locator and every Seeded fact explicit and
discoverable at their canonical owner — never inferred, never reconstructed
from a delivery workspace: `CONTRACT-LOCATOR`, `DELIVERY-ID`, `OUTCOME`,
`ROOT`, `BASE-REVISION`, `DELIVERY-ROUTE` (`RED_TO_GREEN|GREEN_TO_GREEN`),
`EXAMINE`, `INDEPENDENT-REVIEW`, `BUDGET-TOKEN-LIMIT`,
`BUDGET-WALL-CLOCK-MINUTES` and `VALUE-SEED`. A missing or malformed fact
returns to its canonical owner as `EVIDENCE_GAP` before dispatch.

Consume the `CONTRACT-SCHEMA` absolute path emitted by
`des prepare-ordinary-request`, which resolves the schema beside its own
installed runtime. Never search the host, infer a profile directory or ask the
user/root for that internal path. It is ephemeral dispatch context only, never
a contract field or persistent output.

Dispatch one `nw-acceptance-designer` with the architecture locator on its own
line, `CONTRACT-SCHEMA` immediately after `CONTRACT-LOCATOR`, followed by
every remaining Seeded fact above. Human and Auto use the same input and
route contract. Human interaction may resolve an upstream ambiguity, but it
does not select another workflow.

## Completion

Accept only a terminal handoff containing exactly this three-line block:

```text
DISTILL-RESULT: CONTRACT_READY
REPO-ROOT: <absolute physical repository root>
DELIVERY-CONTRACT: <repo-relative locator>
```

`REPO-ROOT` is the same explicit physical root used for resolution; it is
ephemeral handoff context, not a contract field or inferred cwd. The
acceptance designer never executes, hashes, validates or classifies the
contract or oracle itself — the single dispatch boundary immediately after
`CONTRACT_READY` (`des dispatch --repo-root ROOT --delivery-contract PATH`)
performs that validation, resolution and hashing once, and the crafter's own
BASELINE step classifies RED, GREEN or BROKEN. A timeout, partial response or
nonterminal process result is `INDETERMINATE` and cannot dispatch a crafter.

The route outputs only the oracle and one complete DeliveryContract. It does
not author a charter, narrative workspace, ledger, receipt or compatibility
carrier.

## Success Criteria

- one terminal `CONTRACT_READY` result and one complete schema-valid
  DeliveryContract, assembled by the acceptance designer from the Seeded
  facts and durable DESIGN facts;
- validation, resolution and hashing happen exactly once, at the single
  `des dispatch` boundary — never hand-authored by DISTILL;
- RED is attributable or GREEN is complete-scope preservation, established by
  the crafter's own BASELINE, never by DISTILL;
- no legacy carrier, partial handoff or inferred test substrate.
