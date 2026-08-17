---
name: nw-buddy-wave-knowledge
description: Current wave authority and handoff map for answering where product, design, delivery, and feedback facts belong.
---

# Wave Authority Map

```text
DISCOVER -> DIVERGE? -> DISCUSS -> DESIGN -> DEVOPS -> DISTILL -> DELIVER -> FINALIZE
                              ^          ^          ^          ^
                              +----------+----------+----------+
                         downstream conflict returns to its owner
```

| Wave | Owns | Passes forward |
|---|---|---|
| DISCOVER | evidence that a problem exists | validated opportunity and uncertainty |
| DIVERGE | materially different directions | selected direction and rejected alternatives |
| DISCUSS | durable jobs, journeys, value and KPIs | stable product identities and observations |
| DESIGN | architecture, reuse, ports, boundaries, residual stress decisions | durable design identities and obligations |
| DEVOPS | environment, deployment, recovery and observability constraints | executable operational obligations |
| DISTILL | acceptance oracle and one immutable `DeliveryContract` | locator plus digest |
| DELIVER | implementation against that contract | terminal candidate/review/EXAMINE evidence |
| FINALIZE | whole-delivery hygiene and durable back-propagation | clean tree and closure result |

Not every change needs every upstream conversation. A small defect can start at
RCA and reuse existing product/design authority; a new product outcome may need
the full path. Skipping an owner is valid only when its facts already exist and
remain unchanged.

The handoff mechanism is identity plus projection, not copied narrative. A
downstream discovery updates the durable upstream authority, then DISTILL emits
a new immutable contract. No dual-write or compatibility fallback.
