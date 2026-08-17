---
name: nw-distill-prior-wave-reading
description: "Reads and reconciles the durable product, architecture, platform, and delivery authorities before DISTILL compiles an executable oracle and DeliveryContract."
user-invocable: false
disable-model-invocation: true
---

# DISTILL Prior-Authority Reconciliation

Run before authoring or binding an acceptance oracle.

1. Read the value seed and only the durable product authorities it names:
   vision, job, journey and KPI identities.
2. Read the relevant architecture brief/ADRs, including reuse, route,
   prefactoring, paradigm, targets, ports/boundaries, cross-layer laws,
   residual stress decisions and test substrate.
3. Read platform/environment authorities only when the delivery has an
   operational obligation.
4. If an existing `DeliveryContract` is being completed, validate its schema
   and ownership state. Do not trust incomplete facts outside the field's
   owning stage.
5. Reconcile contradictions by stable identity. A contradiction blocks and is
   returned to the durable authority that owns the fact; do not write an
   upstream-issues file or copy the dispute into a second document.
6. Missing design required for an executable oracle blocks with WHAT/WHY/HOW.
   A genuinely unaffected optional lens is `NOT_APPLICABLE`, not a fabricated
   section.
7. Record the reconciliation only in the terminal DISTILL result and the
   resulting immutable contract. No wave log, delta or progress ledger.

The output is the minimum verified input map needed by `nw-distill`: product
identities, design decision ids, route, oracle choice, targets, boundaries,
obligations, applicability, command vectors and budgets.
