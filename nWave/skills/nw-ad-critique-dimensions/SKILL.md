---
name: nw-ad-critique-dimensions
description: Review dimensions for acceptance test quality - happy path bias, GWT compliance, business language purity, coverage completeness, walking skeleton user-centricity, priority validation, observable behavior assertions, traceability coverage, and walking skeleton boundary proof
user-invocable: false
disable-model-invocation: true
---

# Acceptance Test Critique Dimensions

Load when performing peer review of acceptance tests (during *handoff-develop).

## Dimension 1: Happy Path Bias

**Pattern**: Only successful scenarios, error paths missing.

Detection: compare promised distinguishable failure/recovery outcomes with actual falsifiers. No universal error-scenario percentage; missing a promised decline/timeout/refusal/preservation outcome is the defect.

Severity: blocker (production error handling untested).

## Dimension 2: Business observation structure

Verify admitted context, business stimulus and observable outcome/falsifier.
Given-When-Then is useful vocabulary, not mandatory Gherkin syntax or a required
framework. Stateful journeys may involve multiple operations when the transition
contract needs them. Severity follows a concrete ambiguous or absent observation.

## Dimension 3: Business Language Purity

**Pattern**: Incidental implementation choices replace business observations.
Flag private classes, representations or plumbing asserted without a deliberate
contract. Native business helpers hide technical drivers where helpful.
HTTP/JSON/storage terms are valid when they are the user's actual public
protocol or promised domain, not merely forbidden words. Severity: high for
real coupling that prevents an equivalent implementation.

## Dimension 4: Coverage Completeness

**Pattern**: User stories lack acceptance test coverage.

Validation: Map each story to scenarios | Verify all AC have corresponding tests | Confirm edge cases and boundaries tested.

Severity: blocker (unverified requirements).

## Dimension 5: Walking Skeleton User-Centricity

**Pattern**: Walking skeletons describe technical layer connectivity instead of user value.

Detection litmus test for `@walking_skeleton` scenarios:
- Title describes user goal or technical flow?
- Then steps describe user observations or internal side effects?
- Could non-technical stakeholder confirm "yes, that is what users need"?

Violations: "End-to-end order flow through all layers" (technical framing) | Then "order row inserted in database" (internal side effects) | Given "database contains user record" instead of "customer has an account"

Severity: high (skeletons that only prove wiring miss the point -- first skeleton should be demo-able to stakeholder).

## Dimension 6: Priority Validation

**Pattern**: Tests address secondary concerns while larger gaps exist.

Questions: 1. Is this the largest bottleneck? (timing data or gap analysis) | 2. Simpler alternatives considered? | 3. Constraint prioritization correct? | 4. Test design decisions data-justified?

Severity: blocker if wrong problem addressed, high if no measurement data.

## Dimension 7: Observable Behavior Assertions

**Pattern**: Tests assert internal state or method calls instead of observable behavior.

For EVERY Then step in EVERY scenario, apply this mechanical checklist:

1. Does the assertion check a return value from a driving port call? YES = pass, NO = flag.
2. Does the assertion check an observable outcome (user sees X, system produces Y)? YES = pass, NO = flag.
3. Does the assertion check internal state, private fields, or method call counts? YES = REJECT the scenario.

**Concrete violations to flag**:
- `assert mock_repo.save.called` — asserts method call, not observable outcome
- `assert len(db.query(Order).all()) == 1` — asserts internal DB state
- `assert obj._internal_field == "value"` — asserts private state
- `assert os.path.exists("output.json")` — asserts file existence (implementation detail)

**Concrete passing assertions**:
- `assert result.is_confirmed()` — observable business outcome
- `assert result.order_number is not None` — return value from driving port
- `assert "confirmation" in customer_notification.subject` — observable user outcome

**Relationship to Dim 5 (Walking Skeleton User-Centricity)**:
- Dim 5 validates walking skeleton SCOPE (user goal framing vs technical layer framing)
- Dim 7 validates ASSERTION TYPE for ALL scenarios (walking skeletons AND focused scenarios)
- A scenario can pass Dim 5 (good user-centric framing) and fail Dim 7 (internal state assertions)

Severity: high (tests coupled to implementation break on refactoring).

## Dimension 8: Traceability Coverage

**Pattern**: Scenarios exist without traceability to upstream wave artifacts.

Map the original agreed value and authorized scope amendments to selected
criteria, native tests/properties and falsifiers per `nw-at-completeness-check`.
Use actual configured authority destinations and bound headings, not hardcoded
story/environment filenames, tags or guessed defaults. Environments matter
only when selected authority promises a distinguishable observation there.
Do not infer missing coverage from absent tags; inspect the actual behavior.

**What this dimension does NOT cover**:
- KPI measurability — that is PO-reviewer scope during DELIVER post-merge gate
- Scenario quality — covered by Dims 1-7

Severity: blocker for Check A (untraceable requirements), high for Check B (untested environments).

## Review Output Format

```yaml
review_id: "accept_rev_{timestamp}"
reviewer: "acceptance-designer (review mode)"

strengths:
  - "{positive test design aspect with example}"

issues_identified:
  happy_path_bias:
    - issue: "Feature {name} only tests success"
      severity: "blocker"
      recommendation: "Add error scenarios: invalid input, timeout, service failure"

  gwt_format:
    - issue: "Scenario has multiple When actions"
      severity: "high"
      recommendation: "Split into separate scenarios"

  business_language:
    - issue: "Technical term '{term}' in scenario"
      severity: "high"
      recommendation: "Replace with: '{business alternative}'"

  coverage_gaps:
    - issue: "User story {US-ID} has no acceptance tests"
      severity: "blocker"
      recommendation: "Create scenarios for all AC of {US-ID}"

  walking_skeleton_centricity:
    - issue: "Walking skeleton '{name}' describes technical flow, not user goal"
      severity: "high"
      recommendation: "Reframe: title as user goal, Then steps as observable user outcomes"

  observable_behavior:
    - issue: "Scenario '{name}' Then step asserts internal state: {assertion}"
      severity: "high"
      recommendation: "Replace with observable outcome assertion: {alternative}"

  traceability_coverage:
    - issue: "Story {US-ID} has no matching scenario"
      severity: "blocker"
      recommendation: "Create at least one scenario tagged @{US-ID}"
    - issue: "Environment '{env}' has no matching Given clause in walking skeletons"
      severity: "high"
      recommendation: "Add walking skeleton with Given clause: 'Given a {env} environment with {preconditions}'"

  walking_skeleton_boundary:
    - issue: "WS uses @in-memory for a driven-internal/local resource adapter"
      severity: "blocker"
      recommendation: "Replace InMemory with real adapter (tmp_path, real subprocess) per the Architecture of Reference"
    - issue: "Driven adapter '{name}' has no real I/O integration test"
      severity: "blocker"
      recommendation: "Add integration test with real I/O for this adapter"

approval_status: "approved|rejected_pending_revisions|conditionally_approved"
```

## Reviewer Scope Boundaries

The acceptance-designer-reviewer (Sentinel) owns Dimensions 1-9 during DISTILL.

Responsibilities that belong to OTHER reviewers (do NOT evaluate these):
- **KPI measurability**: PO-reviewer validates during DELIVER post-merge gate
- **Infrastructure readiness**: PA-reviewer validates during DEVOPS-to-DISTILL handoff
- **Code quality**: Software-crafter-reviewer validates during DELIVER Phase 4

If a finding touches KPI measurement or infrastructure readiness, tag it `@escalate:{reviewer}` in the review output and move on. Do NOT attempt to evaluate it.

## Dimension 9: Walking Skeleton Boundary Proof

For walking skeleton scenarios, validate that the WS actually proves adapter wiring with real I/O.

### 9a: Port-Class Treatment Match

Does the WS implementation match the port-class defaults from the Architecture of Reference (`nw-distill-port-treatment-policy`)?
- Driven-internal/local-resource port uses @in-memory: BLOCKER
- Driven-external/costly port has no @requires_external marker: HIGH

### 9b: Adapter Integration Coverage

Require real I/O integration for the promised adapter boundary/law when a fake
cannot distinguish it. Do not demand a separate test for every adapter merely
by inventory count; reuse adequate real observations.

### 9c: Walking Skeleton Fixture Tier

Walking skeleton fixtures — what adapter tier do they use?
- Litmus test: "If I deleted the real adapter, would this WS still pass?"
- If YES for a driven-internal/local-resource port: WS is testing InMemory, not wiring, and cannot observe the declared failure. REJECT.

### 9d: Fake-Cannot-Observe-Failure Detection

Grep for @in-memory on walking skeleton scenarios that exercise a driven-internal/local-resource port.
- If found: HIGH — WS claims real-I/O boundary proof but uses a fake that cannot observe the promised failure
