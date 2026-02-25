---
name: tdd-review-enforcement
description: Test design mandate enforcement, test budget validation, 5-phase TDD validation, and external validity checks for the software crafter reviewer
---

# TDD Review Enforcement

Domain knowledge for reviewing TDD implementations against 5 test design mandates, test budget, 5-phase validation, and external validity.

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

Violations: test_valid_email_1/test_valid_email_2 | copy-pasted tests with only inputs changed
Severity: High. Consolidate into @pytest.mark.parametrize.

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

## 5-Phase TDD Validation

Verify all 5 phases in execution-log.yaml: PREPARE, RED_ACCEPTANCE, RED_UNIT, GREEN, COMMIT.

### Phase Checks
- Completeness: all 5 present (Blocker if missing) | Outcomes: all PASS (Blocker if FAIL)
- Sequential execution: correct order by timestamps | Test discipline: 100% green after GREEN, COMMIT

### Quality Gates

| Gate | Description | Phase |
|------|-------------|-------|
| G1 | Exactly one acceptance test active | PREPARE |
| G2 | Acceptance test fails for valid reason | RED_ACCEPTANCE |
| G3 | Unit test fails on assertion | RED_UNIT |
| G4 | No mocks inside hexagon | RED_UNIT |
| G5 | Business language in tests | GREEN |
| G6 | All tests green | GREEN |
| G7 | 100% passing before commit | COMMIT |
| G8 | Test count within budget | RED_UNIT |

Gates G2, G4, G7, G8 are Blockers if not verified.

Note: Review/refactoring quality verified at deliver-level Phase 4 (Adversarial Review).

### Walking Skeleton Override
When `is_walking_skeleton: true`: don't flag missing unit tests | verify exactly one E2E test | thinnest slice OK (hardcoded values) | RED_UNIT and GREEN may be SKIPPED with "NOT_APPLICABLE: walking skeleton"

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

Issue: All 6 acceptance tests import des.validator.TemplateValidator directly.
No test imports des.orchestrator.DESOrchestrator (the entry point).

Consequence: Tests pass, coverage is 100%, but TemplateValidator is never
called in production because DESOrchestrator doesn't use it.

Required: update acceptance test to invoke through entry point, wire component.
```

---

## Approval Decision Logic

### Approved
All 5 phases present, all PASS, all gates satisfied, zero defects, budget met, no internal class tests.

### Rejected
Missing phases | any FAIL | any defect | budget exceeded | internal class tested. Zero tolerance.

### Escalation
>2 review iterations | persistent gate failures | unresolved architectural violations. Escalate to tech lead.
