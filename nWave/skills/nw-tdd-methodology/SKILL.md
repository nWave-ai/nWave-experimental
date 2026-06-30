---
name: nw-tdd-methodology
description: Deep knowledge for Outside-In TDD - double-loop architecture, ATDD integration, port-to-port testing, walking skeletons, and test doubles policy
user-invocable: false
disable-model-invocation: true
---

# Outside-In TDD Methodology

Lean composing core. The deep knowledge is decomposed into seven one-job-one-trigger modules under the `nw-tdd-methodology-*` prefix. This core keeps the name (shared — the crafters, acceptance-designer, distill, and the test-optimizer all reference it) and routes to the module whose trigger fires. Load the module(s) for the job in play; do not re-inline their content here.

## Composition — module → trigger

| Module | Job | Trigger (when to load) |
|--------|-----|------------------------|
| `nw-tdd-methodology-cycle` | the DELIVER cycle | running RED→GREEN→COMMIT — phase boundaries, fail-for-right-reason gate, GREEN-matches-public-contract, no-code-without-a-requiring-test, post-GREEN wiring check, language-detection frame |
| `nw-tdd-methodology-outside-in` | workflow shape | deciding the development-workflow shape — double-loop, Outside-In vs Inside-Out, lightweight ATDD, BDD, Bache workflow, unit-of-behavior framing |
| `nw-tdd-methodology-port-to-port` | test boundary | deciding what a test enters/asserts on — port-to-port discipline, the layer-specific Universe, refactoring-resilience, hexagonal per-layer strategy |
| `nw-tdd-methodology-test-doubles` | choose a double | choosing/building a test double — Meszaros taxonomy, classical-vs-mockist, mock-only-at-port-boundaries policy, doubles-must-validate-inputs contract |
| `nw-tdd-methodology-walking-skeleton` | build a WS | building/validating a walking skeleton — WS protocol, per-slice JIT E2E, Mandate 5 adapter-strategy decision tree, Mandate 6 adapter real-I/O, adapter-integration RED-phase semantics |
| `nw-tdd-methodology-paradigm` | write a unit/acceptance test | writing a unit or acceptance test — property-based + state-delta mandate, applicability matrix, debt-payoff curve, delta-first trigger/bypass |
| `nw-tdd-methodology-pbt-deep` | write a PBT (deep) | writing a property-based test needing deep mechanics — A13/P6 stateful preconditions, four property-finding strategies, two shrinking mechanisms, targeted/search-based PBT |

## How to use

1. Identify the job in play (which trigger fires).
2. Read `~/.claude/skills/nw-tdd-methodology-{module}/SKILL.md` for that job.
3. For a full DELIVER cycle you will typically load `-cycle` + `-paradigm`; add `-port-to-port`, `-test-doubles`, `-walking-skeleton`, or `-pbt-deep` as the boundary/double/WS/PBT decision arises.

The seven modules together cover everything this skill held before decomposition — zero knowledge lost. <!-- mode-ref-ok -->

<!-- SCAFFOLD-MARKER section start — DISTILL slice-02 of fix-mandate-9-v2-rollout.
     This section is intentionally empty; A_GREEN_ATS populates the RED-phase
     mode distinction + the distinguishing-token contract per the spike.
     Source spec: docs/feature/fix-mandate-9-v2-rollout/spike/spike-v2.md
     section 6. Adapter-integration RED-phase semantics now live in
     nw-tdd-methodology-walking-skeleton. -->
