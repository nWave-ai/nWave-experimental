---
description: Designs system architecture with C4 diagrams and technology selection. Use when defining component boundaries, choosing tech stacks, or creating architecture documents.
argument-hint: "[component-name] - Optional: --residuality --paradigm=[auto|oop|fp]"
---


# NW-DESIGN: bounded architecture dispatcher

**Wave**: DESIGN | **Command**: `*design-architecture`

DESIGN is not a mandatory phase. ADR-SSOT-002 §5 invokes it only when current
authority does not settle a technical boundary, reuse decision, proof
dependency, or semantic obligation. It owns that decision at its durable
source; it does not manufacture scope, task plans, diagrams, a paradigm, or a
DEVOPS handoff.

## Route

1. **Locate the gap** — Read only the product/design authority and evidence
   needed to name the unresolved boundary. Gate: authority already settles it
   → return to the active M/L route; do not create a skip record.
2. **Select the owner** — System/infrastructure → `@nw-system-designer`;
   domain/bounded-context → `@nw-ddd-architect`; application/reuse/component
   boundary → `@nw-solution-architect`. Gate: one owner matches the observed
   gap.
3. **Clarify only a real choice** — Ask the human only where product scope or
   a trade-off remains genuinely undecided. Gate: no question is emitted for
   a fact authority already decides.
4. **Dispatch the bounded consultation** — Include the marker below and the
   exact boundary, cited authority, affected layer, and any known constraints.
   The selected architect loads its trigger-specific skills and chooses
   optional formal, DDD, system, diagram, or residuality work only when their
   trigger fires. Gate: no universal architecture style or tool ritual.

<!-- DES-WAVE: design -->

5. **Write the smallest durable decision** — Update `docs/product/architecture/brief.md`
   or the affected ADR with the boundary, decision, constraints, and the
   exact downstream facts DISTILL needs. Produce diagrams, ADRs, specialist
   handoffs, or readiness facts only when this boundary needs them. Gate:
   downstream receives a cited durable authority, not a new side artifact.
6. **Correct at the owner** — If the result contradicts a prior fact, correct
   that product/design SSOT under ADR-SSOT-002 §7. Gate: no delta ledger or
   copied correction narrative.

## Success criteria

- [ ] The trigger was an unresolved technical boundary, not a habitual phase.
- [ ] Exactly one architect owned the bounded question, or the real unresolved
  product choice was returned for human decision.
- [ ] The durable architecture authority contains only the decision and
  downstream facts the boundary requires.
- [ ] The M/L delivery route resumes; DESIGN has not created implementation
  plans, mandatory diagrams, or a DEVOPS handoff.
