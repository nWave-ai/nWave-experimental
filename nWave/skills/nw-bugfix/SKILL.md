---
name: nw-bugfix
description: "Resolve one observed defect through evidence-led RCA, an ATD-owned regression oracle, direct delivery, source-blind EXAMINE when applicable, and one finalization."
user-invocable: true
argument-hint: '--repo-root <ROOT> --delivery-contract <repository-relative-json>'
---

> **Code facts** — resolve structural facts through `des code-fact`; degrade
> LOUD when its provider-neutral adapters cannot answer.

# NW-BUGFIX

## Purpose

Correct one observable defect without creating a second workflow. The
`DeliveryContract` is the delivery authority; durable product/design SSOTs
remain upstream authorities. There is no compatibility workflow, per-delivery
narrative, progress ledger or per-segment command.

The discoverable invocation is:

```text
/nw-bugfix --repo-root <ROOT> --delivery-contract <PATH>
```

`PATH` is repository-relative and is supplied by the terminal DISTILL result.
Validate it exactly as `/nw-deliver` does; never reconstruct or search for it
from the current directory.

## Flow

1. **RCA** — dispatch `nw-troubleshooter` over the observed defect. Require an
   evidence chain from the nearest manifestation outward, one falsifiable root
   cause and the smallest correction boundary. Do not start from a broad repo
   theory when the local failure can discriminate candidates.
2. **Architecture decision** — compare the proposed correction with existing
   ports, responsibilities and durable design authority. Prefer reuse; reject
   duplication, boundary erosion and architectural drift. If the defect reveals
   a new design decision, return it to DESIGN before implementation.
3. **Human oracle when applicable** — when the validated contract has
   `applicability.examine=true`, run total charter discovery for its
   `delivery-id`. Dispatch a fresh `nw-product-owner` only for `Missing` or
   `Empty`; any invalid present member blocks. Keep the PO source-blind.
4. **Regression oracle** — dispatch `nw-acceptance-designer` to author the
   smallest executable oracle that fails for the diagnosed reason. The ATD,
   never the crafter, owns it. Seal its immutable locator and digest in the
   `DeliveryContract` before DELIVER.
5. **Deliver** — invoke `/nw-deliver --repo-root ROOT --delivery-contract PATH`.
   The selected OO or FP crafter implements only the minimal correction and
   may not edit the oracle. Review, EXAMINE and terminal command evidence follow
   the contract's independent applicability axes. `/nw-deliver` already calls
   the internal `nw-finalize` Skill once as its own terminal step.
6. **Consume the returned finalize result** — take the commit SHA and `F`
   result `/nw-deliver` already returned from its one internal finalization.
   Never invoke the `nw-finalize` Skill a second time for this delivery; a
   repeated finalize call is a defect, not an alternate path.

RCA and a fresh value-side charter derivation may overlap because neither
depends on the other. AT authoring depends on the accepted diagnosis; the
crafter depends on the immutable oracle. Heavy local verification remains a
single box. Parallelism never changes these causal edges.

## Success

- root cause falsified against alternatives;
- existing responsibility reused or an explicit design decision owns change;
- immutable regression oracle fails then passes for the right reason;
- production diff stays inside declared targets and boundaries;
- applicable review and source-blind EXAMINE join on matching identities;
- exactly one whole-delivery finalization, consumed from `/nw-deliver` and
  never invoked a second time by this flow; and
- no compatibility fallback or progress artifact survives.
