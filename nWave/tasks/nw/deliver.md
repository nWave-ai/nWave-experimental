---
description: Delivers feature-delta Slice Plan slices through AT-first implementation, review/EXAMINE, and finalize. Use when prior waves are complete and the feature is ready for implementation.
argument-hint: '[feature-description] - Example: "Implement user authentication with JWT"'
---

<!-- gates-ref: deliver -->
<!-- outputs-ref: deliver -->

The DELIVER gate stack and output contract live ONCE in the wave-contract registry
`nWave/waves/deliver.yaml` — the `gates-ref` / `outputs-ref` pointers above name it.
This prose does not re-enumerate the gate stack inline; it POINTS at the registry.

# NW-DELIVER: Complete DELIVER Wave Orchestrator

**Wave**: DELIVER (wave 6 of 6)|**Agent**: Main Instance (orchestrator)|**Command**: `/nw-deliver "{feature-description}"`

## Overview

Orchestrates complete DELIVER wave: feature description → production-ready code with mandatory quality gates. You (main Claude instance) coordinate by delegating to specialized agents via Task tool. Final wave (DISCOVER > DIVERGE > DISCUSS > DESIGN > DEVOPS > DISTILL > DELIVER).

Sub-agents cannot use Skill tool or `/nw:*` commands. You MUST:
- Read the relevant command file and embed instructions in the Task prompt
- Remind the crafter to load its skills as needed for the task (skill files are at `~/.claude/skills/nw/{agent-name}/`)

## CRITICAL BOUNDARY RULES

1. **NEVER implement steps directly.** ALL implementation MUST be delegated to the selected crafter (@nw-software-crafter or @nw-functional-software-crafter per step 1.5) via Task tool with DES markers. You are ORCHESTRATOR — coordinate, not implement.
2. **Do not create retrospective phase records.** Current `atdd_pure` delivery uses the AT-completion ledger and mechanically stamped commit trailers.
3. **Use the selected current workflow's declared inputs only.** The feature delta and its acceptance tests are the delivery specification; do not derive work from retired planning assets.

**DES monitoring is non-negotiable.** Circumventing DES — faking step IDs, omitting markers, or writing log entries manually — is a **violation that invalidates the delivery**. DES detects unmonitored steps and flags them; finalize **blocks** until every flagged step is re-executed through a properly instrumented Task. There is no workaround: unverified steps cannot pass integrity verification, and the delivery cannot be finalized. Without DES monitoring, nWave cannot **verify** TDD phase compliance. For non-deliver tasks (docs, research, one-off edits): `<!-- DES-ENFORCEMENT : exempt -->`.


Before any phase work, read `.nwave/config.yaml` key `workflow.mode`. The active `atdd_pure` execution path is described below; its DELIVER phase shape is projected from the mode registry, never hand-written here: <!-- mode-ref-ok -->

<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice AT-first loop; AT-completion ledger + commit trailers are the authority.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
<!-- GENERATED:mode-descriptor END -->


## Current Delivery Routing

1. **Select mode** — Read `.nwave/config.yaml` and the mode registry. Gate: a current workflow mode is resolved before dispatch.
2. **Read the delivery contract** — Read the feature delta, DISTILL acceptance tests, and current DESIGN artifacts named by the selected mode. Gate: delivery inputs are consistent.
3. **Run the selected spine** — Follow the selected mode's registry projection and its mode-owned skill instructions. For `atdd_pure`, use the per-slice spine above. Gate: every required phase records its declared evidence.
4. **Maintain living documentation** — Emit the selected mode's required `[REF]` outcome sections and update only the authoritative feature artifacts. Gate: implementation, test, and evolution evidence agree.
5. **Close the feature** — Run the selected mode's feature-end verification and report its evidence. Gate: the mode's completion contract passes.
