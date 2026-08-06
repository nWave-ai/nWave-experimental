---
name: nw-tdd-review-enforcement
description: Test design mandate enforcement, test budget validation, active-workflow slice-evidence validation, and external validity checks for the software crafter reviewer
user-invocable: false
disable-model-invocation: true
---

# TDD Review Enforcement

Domain knowledge for reviewing TDD implementations against 5 test design mandates, test budget, active-workflow slice evidence, and external validity.

---

## Language-Agnostic Application

These mandates apply to every implementation language and test framework. Test names, assertion syntax, and framework mechanisms shown below are illustrative examples, not required forms; use the repository's native data-driven or parameterization mechanism.

---

## 5 Test Design Mandates

### Mandate 1: Observable Behavioral Outcomes
All assertions validate observable outcomes, never internal structure.

Observable: return values from driving ports | state changes via queries | side effects at driven port boundaries | exceptions from public API | business invariants

Violations: asserting private fields | verifying internal method call order | inspecting intermediate calculations | checking internal class instantiation

Severity: Blocker. Rewrite to assert observable outcomes only.

### Mandate 2: No Domain Layer Unit Tests
Zero unit tests of domain entities/value objects/services directly. Test indirectly through application service (driving port) tests.

Violations: imports domain entity (Order, Customer) | instantiates value object (Money, Email) | invokes domain service method

Exception: complex standalone algorithm with stable public interface (rare).
Severity: Blocker. Delete domain tests, add application service test.

### Mandate 3: Test Through Driving Ports
All unit tests enter through driving ports (application services, controllers, CLI handlers, event handlers). Never internal classes.

Detection: grep for internal imports (`from domain.entity`, `from internal.validator`).
Severity: Blocker. Rewrite through driving port.

### Mandate 4: Integration Tests for Adapters
Adapters have integration tests with real infrastructure (testcontainers, test servers). No mocked unit tests.

Violations: mocking IDbConnection | mocking SMTP client | stubs instead of real infrastructure
Acceptable: in-memory implementations if behavior-complete.
Severity: Blocker. Convert to integration test.

### Mandate 5: Parametrized Input Variations
Input variations of same behavior use parametrized tests, not duplicates.

Violations: separately named tests that differ only in input data | copy-pasted tests with only inputs changed
Severity: High. Consolidate using the framework's data-driven or parameterized-test mechanism.

---

## Test Budget Validation

Formula: `max_unit_tests = 2 x number_of_distinct_behaviors`

A behavior = ONE observable outcome from a driving port action. Edge cases of same behavior = ONE (use parametrized).

### Counting Rules
One behavior: happy path for one operation | error handling for one error type | validation for one rule
Not a behavior: testing internal class | same behavior different inputs | testing getters/setters | testing framework code

### Enforcement Steps
1. Count distinct behaviors in AC | 2. Calculate `budget = 2 x count`
3. Count actual test methods (parametrized cases don't add) | 4. Pass: actual <= budget. Fail: actual > budget (Blocker)

### Example Finding

```
TEST BUDGET VALIDATION: FAILED

Acceptance Criteria Analysis:
- "User can register with valid email" = 1 behavior
- "Invalid email format rejected" = 1 behavior
- "Duplicate email rejected" = 1 behavior

Budget: 3 behaviors x 2 = 6 unit tests maximum
Actual: 14 unit tests

Violations:
1. Budget exceeded: 14 > 6 (Blocker)
2. Internal class testing: test_user_validator.py tests UserValidator directly (Blocker)
3. Parameterization missing: 5 separate tests for valid email variations

Required: delete internal tests, consolidate via parametrize, re-submit
```

---

## Active-Workflow Slice Evidence Validation



<!-- GENERATED:mode-descriptor START — source of truth: nWave/flavors/*.yaml; do not hand-edit (docgen renders this region) -->
- `atdd_pure` — Per-slice AT-first loop; AT-completion ledger + commit trailers are the authority.
  Deliver phase shape: `A_GREEN -> EXAMINE -> COMMIT`
<!-- GENERATED:mode-descriptor END -->



### Evidence Checks

| Evidence | Reviewer checks | Failure |
|----------|-----------------|---------|
| Feature Delta Slice Plan | Active row declares the slice's value and target paths | BLOCKER |
| Executable ATs | Slice-owned ATs are executable and green through their declared driving surface | BLOCKER |
| Parent-to-commit diff | Changed production paths stay within the Slice Plan; test changes retain behavioral assertions | BLOCKER |
| Commit attestation | The accepted slice commit carries its valid trailer and completion attestation | BLOCKER |
| EXAMINE outcome | Apply the route-specific requirement below when the charter gate is armed | BLOCKER |

### Attestation Routes

No universal three-record checklist exists. Select the route from the Slice Plan and AT kind; do not demand evidence that its guard does not produce.

| Route | Entry evidence | Completion evidence |
|-------|----------------|---------------------|
| Ordinary AT review | Approved, current `ATReviewVerdict` for the slice's executable AT set | Valid accepted commit and `SliceCommitVerified` |
| `pytest-regression` mechanical seal | Fresh, content-bound `RedObserved` plus satisfied negative-AT mandate for the declared regression file; an approved `ATReviewVerdict` remains an alternative | Valid accepted commit and `SliceCommitVerified` |
| `GREEN_TO_GREEN` prefactoring | Guard proves suite green before and after the accepted commit and no test path changed; it bypasses AT-review evidence | Valid accepted commit and `SliceCommitVerified` |

`CarpaccioGateCleared` is gate output when applicable, not a universal reviewer-record requirement.

### EXAMINE Routes

When the charter gate is armed, an ordinary observable slice requires a fresh PASS `ExamineVerdictRecorded` bound to the current charter. `@coupled` is distinct: record or verify `ExamineDeferredToFeatureEnd`; it owes feature-end examination, not a per-slice PASS. `@infrastructure` and `@prefactoring` are distinct permanent exemptions: record or verify `ExamineExemptNonObservableSlice`; they are not deferred. If the gate is unarmed, report `UNARMED`, never invent an EXAMINE obligation.

### Quality Gates

| Gate | Description | Evidence surface |
|------|-------------|------------------|
| G1 | Slice-owned ATs are declared by the active Slice Plan | Feature Delta + executable ATs |
| G2 | AT outcomes validate the declared value through a driving surface | Executable ATs |
| G3 | Assertions validate observable outcomes | Executable ATs + diff |
| G4 | No mocks inside the hexagon | Tests + diff |
| G5 | Tests use business language | Tests |
| G6 | Required ATs and relevant tests are green | Executable runs |
| G7 | Applicable entry route and accepted commit are attested for this slice | Gate-defined route evidence + accepted-commit attestation |
| G8 | Test count is within budget | AC + tests |
| G9 | Existing test assertions were not weakened to fit implementation | Parent-to-commit diff |

Gates G2, G4, G7, G8, G9 are Blockers if not verified.

Note: Review/refactoring quality verified at deliver-level Phase 4 (Adversarial Review).

### Walking Skeleton Override
When the active Slice Plan identifies the walking skeleton: don't flag missing unit tests | verify the declared E2E AT proves installed wiring | use the Slice Plan's declared target paths, applicable attestation route, commit evidence, and EXAMINE outcome.

---

## External Validity Check

Verify features are invocable through entry points, not just existing in code.

Question: "If I follow these steps, will the feature WORK or just EXIST?"

### Criteria
1. Acceptance tests import entry point modules, not internals (Blocker)
2. At least one test invokes through user-facing entry point (High)
3. Component wired into system entry point (Blocker)

### Example Finding

```
EXTERNAL VALIDITY CHECK: FAILED

Issue: All 6 acceptance tests import an internal validator directly.
No test uses the declared application entry point.

Consequence: Tests pass, coverage is 100%, but the validator is never
called in production because the application entry point does not use it.

Required: update the acceptance test to invoke through the entry point, then wire the component.
```

---

## Test Modification Detection (ALWAYS BLOCKER)

The single worst TDD violation: modifying a test to make it pass instead of fixing the implementation. This inverts the TDD feedback loop -- the test no longer protects behavior. Instant rejection, no exceptions, no conditional approval.

### Detection Signals

| Signal | How to Detect | Severity |
|--------|---------------|----------|
| Test + implementation changed in one slice | Parent-to-commit diff contains both classes | Inspect |
| Assertion weakened | A specific outcome assertion becomes a weaker predicate; syntax shown is illustrative, not exhaustive | BLOCKER |
| Expectations reduced | Same behavioral claim retains materially less checked outcome | BLOCKER |
| Test deleted or skipped | Any skip/xfail/disable mechanism or removed behavioral case; syntax varies by framework | BLOCKER |
| Deferred-fix rationale | Comment or metadata admits a temporary relaxation | BLOCKER |
| Assertion count decreased | Fewer assertions for the same behavioral claim; inspect semantics, not count alone | BLOCKER |

### Review Procedure

1. Compare the slice commit with its parent; scope the diff to the active Feature Delta Slice Plan.
2. If an existing test changed with production code, flag it for detailed inspection.
3. Check each modification against the signals table above
4. If modification is purely additive (new assertions, new test methods): PASS
5. If modification weakens, removes, or relaxes any existing assertion: BLOCKER -- reject immediately

### Legitimate Test Changes (Not Violations)

- Renaming test methods for clarity (no assertion changes)
- Adding new assertions to existing tests (strengthening, not weakening)
- Correcting an AT defect only after the owning DISTILL/requirements authority updates the Feature Delta and AT contract; the reviewer records NEEDS_REVISION, never treats an implementation review as approval to rewrite the contract
- Parametrization refactoring that preserves all original assertions

### Example Finding

```
TEST MODIFICATION DETECTION: BLOCKER

File: tests/unit/test_order_service.py
Commit: accepted slice commit `abc123`

Parent commit:
  assert result.total == Decimal("150.00")
  assert result.tax == Decimal("15.00")
  assert result.items == 3
  assert result.status == OrderStatus.CONFIRMED

Accepted slice commit:
  assert result is not None  # <-- weakened from 4 specific assertions to existence check

Verdict: REJECTED. Implementation could not satisfy the original assertions.
The crafter modified the test instead of fixing the implementation.
Required: restore the behavioral assertion, then fix the implementation to satisfy it.
```

---

## Fixture Theater Detection (ALWAYS BLOCKER)

Acceptance tests pass because fixtures implement the expected behavior directly, rather than exercising production code through the driving port. The tests verify the correct outcome from the wrong source.

### Detection Signals

| Signal | How to Detect | Severity |
|--------|---------------|----------|
| No production files in scoped diff | Parent-to-commit diff contains only test/fixture paths while direct inspection shows fixtures create the outcome | BLOCKER |
| Given steps create end-state | Test Given/Arrange steps construct the expected output directly instead of setting up preconditions for production code | BLOCKER |
| Fixture implements behavior | Test helper/fixture contains domain logic that should live in production code | BLOCKER |
| Outcome produced by fixture | Driving-surface observation fails when fixture behavior is removed | BLOCKER |

### Review Procedure

1. Compare the commit's diff with the active Feature Delta Slice Plan declared target paths.
2. Every changed production path MUST be declared there. A declared target that is untouched is investigation evidence, not by itself a blocker.
3. Apply the **deletion test**: "If I revert ALL changes to test files and fixtures, does the acceptance test still pass with ONLY the production code changes?" If yes: production code is doing the work (PASS). If the test cannot pass without fixture changes: BLOCKER
4. Inspect test Given/Arrange sections for domain logic that belongs in production code

### Legitimate Exceptions (Not Violations)

- A Slice Plan row whose declared target paths are test-only
- Documentation-only steps where no production code is expected
- Hash update steps where the production change is a constant update in a test file

### Example Finding

```
FIXTURE THEATER DETECTION: BLOCKER

Slice Plan target paths: [src/application/adapters/plugin_installer]

Parent-to-accepted-commit diff:
  tests/acceptance/test_plugin_installation  (fixture modified)
  tests/conftest.py                               (helper added)

Untouched declared target: src/application/adapters/plugin_installer

Verdict: REJECTED. Agent modified test fixtures to produce expected state
instead of implementing production code in the declared adapter.
The acceptance test passes because the fixture creates the expected output,
not because the declared driving port produces it.
Required: revert fixture changes, implement production code in the declared adapter.
```

---

## Escalation Verification

When a crafter gets stuck, the correct action is to escalate -- not to silently weaken tests. The reviewer verifies proper escalation protocol was followed.

### What to Check

1. **Contract mismatch**: an AT or requirement appears wrong/incomplete for the Feature Delta Slice Plan. Return `NEEDS_REVISION` to the owning DISTILL/requirements authority; do not accept a test rewrite as implementation evidence.
2. **Implementation mismatch**: the declared AT is executable but fails. Return `NEEDS_REVISION` with the failing AT, diff, and Slice Plan row; retain the AT contract.
3. **Attestation mismatch**: gate-defined route evidence, accepted-commit attestation, or charter-armed EXAMINE outcome is missing or invalid. Return `NEEDS_REVISION`; the slice remains unattested.

### Escalation Failures

| Failure | Detection | Severity |
|---------|-----------|----------|
| Silent test modification | Parent-to-commit diff weakens an existing assertion | BLOCKER |
| Contract mismatch | Test change lacks a matching Feature Delta and AT-contract revision by its owner | BLOCKER |
| Attestation mismatch | Required route evidence, accepted-commit attestation, or armed EXAMINE PASS is absent or invalid | BLOCKER |
| Proper escalation | `NEEDS_REVISION` identifies the owning authority and the concrete Slice Plan, AT, diff, or attestation defect | PASS |

---

## Approval Decision Logic

### Approved
The active-workflow Slice Plan is coherent with executable ATs; required ATs are green; the parent-to-accepted-commit diff is within declared scope and free of test weakening or fixture theater; G1-G9 pass; the declared attestation route and accepted-commit evidence attest the slice; a charter-armed observable slice has current EXAMINE PASS.

### Rejected
Missing or incoherent Slice Plan evidence | failing executable AT | undeclared production path | invalid route or accepted-commit attestation | missing armed EXAMINE PASS | any defect | budget exceeded | internal class tested | test modified to accommodate implementation (G9) | testing theater detected.

### Escalation
Persistent implementation failure | unresolved architectural violation | a contract mismatch that requires the owning requirements authority | an attestation failure that cannot be repaired by the slice owner. Escalate with the concrete Slice Plan row, AT result, diff, route evidence, accepted-commit attestation, or EXAMINE evidence.
