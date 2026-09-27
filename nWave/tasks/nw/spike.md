---
description: 'Runs a bounded probe of one product, visual-experience or technical uncertainty inside DISCUSS/DESIGN; returns evidence to its owner without creating wave authority.'
argument-hint: '[question or uncertain experience]'
---


# NW-SPIKE: Bounded Decision Probe

**Wave**: DISCUSS/DESIGN technique, not an extra phase | **Command**: `/nw-spike`

## Overview

Probe one uncertainty only when its answer can change a product or design decision. This is not a required step before DESIGN. Reuse relevant context and preserve useful evidence in the caller-owned persistent workspace; do not create a feature-wave findings document or promote probe code automatically.

## Skip Check

Skip when existing evidence already answers the question, or the result cannot affect a decision. Honor the caller's existing delegation or stop boundary; do not introduce a permission checkpoint. When a probe is useful, read the relevant product or design context already available to the caller, including prior DISCUSS or DIVERGE results if present.

## Probe Scope

### Decision 1: Probe Question
State the ONE uncertainty, the evidence that could change the decision, and a bounded scope/time budget. For a visual question, identify the actor, journey and feedback question; select a sketch, wireframe or navigable prototype appropriate to the uncertainty. For a technical question, name the mechanism, integration or performance threshold that needs observation.

## Specialist Invocation

Keep ownership with the calling PO or architect. For visual uncertainty, consult `nw-ux-designer`; for technical uncertainty, select the applicable technical specialist. Supply the question, relevant context, scope and evidence sought. Do not route every probe to `nw-software-crafter` as a managed implementation batch.

**Probe rules**:
- Keep artifacts and findings in the caller-owned persistent workspace outside production paths; do not rely on `/tmp` for valuable work or require a feature-wave authority artifact.
- Use the project's native toolchain and implement only enough to answer the question. Clearly distinguish simulated data, mocked effects and absent integration.
- Observe the result. Show a visual prototype to the human and distinguish actual feedback from model inference; pending feedback remains unresolved, not a binary verdict.
- Return evidence, limitations and the remaining decision to the PO or architect. They supply semantic inputs to the relevant DES constructor; the probe does not write authority or handover documents.

## Success Criteria

- [ ] One decision-relevant uncertainty probed within a bounded scope
- [ ] Evidence and limitations retained in the caller-owned persistent workspace
- [ ] Actual feedback distinguished from inference where human evaluation matters
- [ ] Findings returned to the decision owner without requiring a binary verdict

## Handoff and Retention

Return the findings and remaining decision to the calling PO or architect. If a design implication matters, DESIGN incorporates the returned fact through its existing authority-writing constructor; the probe itself does not author a parallel ledger. No automatic promotion, commit or cleanup: separately selected implementation may reuse prototype code after normal design, oracle and review work. Preserve useful evidence before any explicitly selected disposal; meaningful prototype changes need renewed feedback.

## Examples

### Example 1: Performance probe
```
/nw-spike "Can wave-matrix derive feature status from pytest + filesystem within five seconds?"
```
The technical specialist measures the relevant collection path, retains the command, result and limitations in the caller-owned workspace, and returns whether the timing evidence changes the design decision.

### Example 2: Integration probe
```
/nw-spike "Can cel-python evaluate 100 policy expressions in under one second?"
```
The specialist measures a representative evaluation and returns its timing and observed expression-syntax limitations. The architect decides whether that evidence changes the expression schema.

### Example 3: Visual-experience probe
```
/nw-spike "Can the target user locate the policy override in the proposed screen?"
```
The PO supplies actor, journey and feedback question; the UX designer builds the smallest useful prototype. The caller presents it to the human and retains actual feedback separately from predictions. Until feedback arrives, the preference remains unresolved.
