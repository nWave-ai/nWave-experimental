---
name: nw-at-completeness-check
description: Canonical AT completeness gate (lean core) — composes a Tier-1 coverage taxonomy (C1-C7 + 15-item checklist), a Tier-2 structural-invariants gate (S-family), gap routing, and taxonomy lifecycle. Paradigm-neutral. Drives the acceptance-designer reviewer verdict deterministically.
user-invocable: false
disable-model-invocation: true
---

# AT Completeness Check — Canonical Gate (core)

Mechanical gate for acceptance-test completeness. Runs against any candidate AT set. Verdict deterministic by count, not judgment. This core is a lean dispatcher: the knowledge lives in four composed modules, each loaded by its own trigger.

**Provenance**: research-anchored 7-category taxonomy, paradigm-neutral. See `docs/research/at-edge-case-taxonomy-2026-05-19.md` for the full literature review. Plan v3 §6 (ATDD-pure restructure) is the canonical specification.

**Runtime note** (Ale 2026-05-24): nwave-dev has no sequencer / no engine — only hooks. This is a **contract document** loaded by acceptance-designer + reviewer agents at dispatch time. Enforcement is "the agent MUST run both gates before issuing AT verdict", not a runtime hook.

## Two-tier gate

Reviewer runs **both** gates before issuing verdict; they are independent and additive:

1. **Tier-1 Coverage Gate** — the canonical 7-category C1-C7 taxonomy + 15-item mechanical checklist + deterministic verdict thresholds. Audits **what the AT set covers** of the SUT's input/state/mode/error/env space. Module: `nw-at-completeness-check-coverage-taxonomy`.
2. **Tier-2 Structural Invariants Gate** — the S-family (S1 step-text uniqueness, S2 driving-port-only boundary / no direct-domain testing per Mandate-13, S3 dormant-seam reconciliation per D11, S4 declared-runtime-contract conformance). S4 is mandatory whenever DESIGN declares a typed driven-port request, receipt or authority: an AT must observe the concrete production boundary and reject a field-compatible lookalike. Audits **how the AT set itself is structured** — SSOT/boundary/seam-witnessing invariants on the test code, not SUT coverage. A Tier-2 failure is independent of the Tier-1 score and BLOCKS regardless of coverage band. Module: `nw-at-completeness-check-structural-invariants`.

The 15-item count, IDs, and verdict thresholds in Tier-1 are **unchanged** by Tier-2 additions; the S-family lives in its own namespace.

**ZERO-obligation override** (Tier-1 C3): **Absence of an explicit Zero scenario for any iterative surface ⇒ INCOMPLETE verdict regardless of total checklist score.** The Zero gap is a hard block, not a documentable gap — enforced at the nWave hook spine (PreToolUse/SubagentStop — Python + filesystem, git-free). Full definition in the coverage-taxonomy module.

## Composition — module → trigger

| Module | KIND | Trigger (when to load) |
|--------|------|------------------------|
| `nw-at-completeness-check-coverage-taxonomy` | KNOWLEDGE | Auditing whether the AT set COVERS the SUT's input/state/mode/error/env space (Tier-1: C1-C7, 15-item checklist, thresholds, PBT signatures, ZERO-obligation). |
| `nw-at-completeness-check-structural-invariants` | KNOWLEDGE | Auditing whether the AT set itself is STRUCTURALLY sound (Tier-2: S1 step-text uniqueness, S2 driving-port-only, S3 dormant-seam; independent BLOCK). |
| `nw-at-completeness-check-gap-routing` | KNOWLEDGE | A gap has been FOUND — emit the typed `ATGap` verdict (kind + severity) and route to the owning wave (SPECIFICATION_AMBIGUITY upstream vs AT_GAP_IN_DELIVERY_SCOPE loop-DISTILL). |
| `nw-at-completeness-check-taxonomy-lifecycle` | KNOWLEDGE | Adapting the taxonomy itself — authoring/opting-in a `domain-extension` overlay, or a falsifier-gate prune/escalate decision from telemetry. |

Machine-readable Tier-1 form: `checklist-15-item.yaml` (this dir). Domain overlays: `domain-extensions/*.yaml` (this dir; lifecycle module).

## How the reviewer uses this core

1. Run **Tier-1** (load `nw-at-completeness-check-coverage-taxonomy`) → coverage count + ZERO-obligation check → Tier-1 verdict band.
2. Run **Tier-2** (load `nw-at-completeness-check-structural-invariants`) → S1/S2/S3 → Tier-2 verdict (BLOCK overrides Tier-1 on any S-failure).
3. For each gap found in step 1 or 2, route it (load `nw-at-completeness-check-gap-routing`) → typed `ATGap` + owning wave.
4. Taxonomy evolution (overlays, falsifier prune) is out-of-band config/telemetry work (load `nw-at-completeness-check-taxonomy-lifecycle`), not part of a single AT-set run.

Tier-2 (S-family) is MANDATORY and not subject to the falsifier-prune; the 7 C-categories default active and are empirically falsifiable per the lifecycle module.
