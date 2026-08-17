---
name: nw-buddy-command-catalog
description: Current nWave command map for routing users without teaching retired workflow ceremony.
user-invocable: false
disable-model-invocation: true
---

# Command Catalog

| Need | Command | Owner |
|---|---|---|
| Validate a problem | `/nw-discover` | product discoverer |
| Compare solution directions | `/nw-diverge` | diverger |
| Clarify jobs, journeys and outcomes | `/nw-discuss` | product owner |
| Establish architecture, reuse and boundaries | `/nw-design` | architect selected by scope |
| Establish deployment and operational constraints | `/nw-devops` | platform architect |
| Compile the executable oracle and `DeliveryContract` | `/nw-distill` | acceptance designer |
| Deliver one validated contract | `/nw-deliver --repo-root ROOT --delivery-contract PATH` | selected crafter plus independent observers |
| Diagnose and correct one defect | `/nw-bugfix --repo-root ROOT --delivery-contract PATH` | troubleshooter, ATD and crafter |
| Review an artifact or diff | `/nw-review` | matching reviewer |
| Reduce a noisy test portfolio | `/nw-optimize-tests` | test optimizer |
| Run an explicit mutation probe | `/nw-mutation-test` | project test tooling |

`PATH` is supplied by the producing DISTILL result and resolves only relative
to `ROOT`. No command requires a feature workspace, workflow mode, slice token
or progress ledger.
