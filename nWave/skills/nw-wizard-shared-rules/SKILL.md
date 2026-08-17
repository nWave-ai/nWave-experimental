---
name: nw-wizard-shared-rules
description: Shared routing rules for discovering the earliest missing nWave authority without persistent wizard state.
user-invocable: false
disable-model-invocation: true
---

# Wizard Shared Rules

Use stable identifiers already present in durable product/design authorities.
When a new identifier is necessary, derive a short lowercase kebab-case name
from the observable outcome and let its owning authority persist it.

Detection order is evidence-based: product evidence, selected direction,
durable product meaning, durable design, operational constraints, executable
oracle/contract, terminal delivery evidence. Stop at the first missing owner.

Never create progress state, feature workspaces or archive copies. Never treat
a directory name as proof that a wave ran.
