---
description: Designs system architecture with C4 diagrams and technology selection. Use when defining component boundaries, choosing tech stacks, or creating architecture documents.
argument-hint: '[component-name] - Optional: --residuality --paradigm=[auto|oop|fp]'
---


# NW-DESIGN: bounded architecture dispatcher

**Wave**: DESIGN | **Command**: `*design-architecture`

DESIGN is not a mandatory phase. ADR-SSOT-002 §5 invokes it only when current
authority does not settle a technical boundary, reuse decision, proof
dependency, or semantic obligation. It owns that decision at its durable
source; it does not manufacture scope, task plans, diagrams, a paradigm, or a
DEVOPS handoff.

## Route

1. **Locate the gap** — Does the authority just read leave a technical boundary
   unresolved, rather than merely making DESIGN the habitual next phase?
   Read only the product/design authority and evidence needed to answer.
   If it already settles the boundary, return to the Request in flight without
   creating a skip record; if evidence is missing, name that uncertainty.
2. **Select the owner** — Scale/distribution → `@nw-system-designer`;
   domain/bounded-context → `@nw-ddd-architect`; application/reuse/component
   boundary → `@nw-solution-architect`; deployment/infrastructure →
   `@nw-platform-architect`. Does this owner match the evidenced gap rather
   than a generic architect designation? If not, resolve the responsibility
   from current authority before dispatch or return the unresolved ownership.
3. **Clarify only a real choice** — Is product scope or a trade-off actually
   undecided, rather than a fact authority already supplies? If yes, ask the
   human that choice; otherwise proceed from the existing authority.
4. **Dispatch the bounded consultation** — Follow `nw-design` and
   `nw-role-invocation`: invoke the exact installed role natively, never a
   generic architect persona. The host then supplies its closed semantic JSON
   to `des design --repo-root ROOT --value N --input -`; DES does not invoke
   the role. Include the exact boundary, cited authority, affected layers,
   original actors and constraints. Honor the shared-before-delta rule in
   `nw-design` when common feature decisions are needed.
   The selected architect applies its design obligations and reachable
   trigger-specific skills. Optional pattern/style, DDD, system, diagram or
   expanded stress analysis follows its own trigger; it does not waive the
   selected architect's required design obligations.

5. **Return the smallest decision as one typed design** — In a managed
   invocation the architect writes no repository file and no durable authority;
   it may write scratch or probe files only outside the repository, where its
   tools allow. It returns paradigm, ordered targets
   with `EXTEND`/`CREATE_NEW`, obligations, oracle locator and supports, native
   verification argv vectors and the public contract, and SOFTWARE renders the
   canonical section at the configured destination for the persisted scope. In a human-driven
   consultation, send the same smallest durable decision to `des design
   --repo-root ROOT --value N --input -`, which constructs that brief or the affected ADR. Produce
   diagrams, specialist handoffs, or readiness facts only when this boundary
   needs them. Does the result carry downstream typed facts or a cited
   constructor-produced authority, rather than only a promised side artifact?
   If not, retain the missing semantic input or projection as an explicit gap
   and return it to its producing owner; do not substitute a side authority.
6. **Correct at the owner** — Does the result contradict a prior authoritative
   fact? If yes, route the correction to that product/design SSOT owner under
   ADR-SSOT-002 §7 and supply the amended semantic input to its constructor.
   If not, continue the Request without a delta ledger or copied correction
   narrative.

## Success criteria

- [ ] The trigger was an unresolved technical boundary, not a habitual phase.
- [ ] Exactly one architect owned the bounded question, or the real unresolved
  product choice was returned for human decision.
- [ ] The durable architecture authority contains only the decision and
  downstream facts the boundary requires.
- [ ] The Request in flight resumes; DESIGN has not created implementation
  plans, mandatory diagrams, or a DEVOPS handoff.
