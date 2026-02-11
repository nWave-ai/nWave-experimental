# Outside-In TDD: Step-to-Scenario Mapping Principle

**Version**: 1.0
**Date**: 2026-01-24
**Status**: Mandatory for all nWave DEVELOP waves

---

## Core Principle

**1 Acceptance Test Scenario = 1 Step File = 1 Complete 14-Phase TDD Cycle**

This is a **hard constraint** for Outside-In TDD, not a suggestion.

---

## The Rule

```
DISTILL Wave Output:
  tests/acceptance/test_us00X_*.py
    ├─ test_scenario_001_*  ← Scenario 1
    ├─ test_scenario_002_*  ← Scenario 2
    ├─ test_scenario_003_*  ← Scenario 3
    └─ test_scenario_004_*  ← Scenario 4

DEVELOP Wave Roadmap (MUST match):
  docs/feature/{project}/steps/
    ├─ 01-01.json  → Makes Scenario 1 pass (RED → GREEN)
    ├─ 01-02.json  → Makes Scenario 2 pass (RED → GREEN)
    ├─ 01-03.json  → Makes Scenario 3 pass (RED → GREEN)
    └─ 01-04.json  → Makes Scenario 4 pass (RED → GREEN)

VALIDATION:
  num_step_files == num_acceptance_test_scenarios  ✅ REQUIRED
```

---

## Why This Matters

### ❌ **WRONG Approach** (Architectural Steps)

```yaml
# Roadmap with "architectural" thinking:
steps:
  - 01-01: Create orchestrator class
  - 01-02: Implement marker injection
  - 01-03: Add command filtering
  - 01-04: Integration testing
```

**Problem**:
- No clear RED → GREEN progression
- Tests pass all at once in step 01-04
- Violates Outside-In TDD discipline
- Can't track which scenario is implemented

### ✅ **CORRECT Approach** (Scenario-Driven Steps)

```yaml
# Roadmap with "scenario" thinking:
steps:
  - 01-01: Make test_execute_command_includes_des_validation_marker pass
  - 01-02: Make test_ad_hoc_task_bypasses_des_validation pass
  - 01-03: Make test_research_command_skips_full_validation pass
  - 01-04: Make test_develop_command_includes_des_validation_marker pass
```

**Benefits**:
- Clear RED → GREEN per step
- Each step has measurable completion (1 test passes)
- Follows Outside-In TDD strictly
- Traceability: scenario → step → commit

---

## Implementation Requirements

### For `@solution-architect` (Roadmap Creation)

**BEFORE creating roadmap**:
1. Read acceptance test file: `tests/acceptance/test_us00X_*.py`
2. Count scenarios: `grep 'def test_' | wc -l`
3. Create exactly N steps for N scenarios

**Roadmap structure**:
```yaml
steps:
  - step_id: "01-01"
    name: "Make Scenario 1 pass"
    acceptance_test_scenario: "test_scenario_001_execute_command"  # ← REQUIRED
    acceptance_test_file: "tests/acceptance/test_us001_*.py"       # ← REQUIRED
    description: "Implement code to make test_scenario_001 pass (RED → GREEN)"
```

### For `/nw:split` (Step File Generation)

**BEFORE generating step files**:
1. Read roadmap step count
2. Read acceptance test scenario count
3. **ENFORCE**: `assert num_steps == num_scenarios`

**Step file template**:
```json
{
  "task_specification": {
    "task_id": "01-01",
    "acceptance_test_scenario": "test_scenario_001_*",
    "acceptance_test_file": "tests/acceptance/test_us001_*.py",
    "description": "Make test_scenario_001 pass (RED → GREEN)",
    ...
  }
}
```

### For `@software-crafter` (Step Execution)

**Each step MUST**:
1. Start with exactly 1 acceptance test RED
2. End with exactly 1 acceptance test GREEN
3. All other tests remain in current state (no regression)

**Phase 2 (RED_ACCEPTANCE)**:
```python
# Run ONLY the scenario for this step
pytest tests/acceptance/test_us001_*.py::test_scenario_001_* -v
# Expected: FAIL (RED state)
```

**Phase 6 (GREEN_ACCEPTANCE)**:
```python
# Run the same scenario again
pytest tests/acceptance/test_us001_*.py::test_scenario_001_* -v
# Expected: PASS (GREEN state)

# Verify no regression
pytest tests/acceptance/ -v
# Expected: All previously passing tests still pass
```

---

## Validation Script

```python
#!/usr/bin/env python3
"""Enforce 1:1 mapping between acceptance scenarios and step files."""

import sys
import yaml
import re
from pathlib import Path

def count_acceptance_scenarios(test_file):
    """Count test scenarios in acceptance test file."""
    content = Path(test_file).read_text()
    # Match: def test_scenario_NNN_* or def test_*
    scenarios = re.findall(r'^\s+def test_\w+\(', content, re.MULTILINE)
    return len(scenarios)

def count_roadmap_steps(roadmap_file):
    """Count total steps in roadmap."""
    roadmap = yaml.safe_load(Path(roadmap_file).read_text())
    return sum(len(phase['steps']) for phase in roadmap['roadmap']['phases'])

def validate_mapping(project_id, user_story_id):
    """Enforce 1:1 mapping."""
    test_file = f"tests/acceptance/test_{user_story_id}_*.py"
    roadmap_file = f"docs/feature/{project_id}/roadmap.yaml"

    num_scenarios = count_acceptance_scenarios(test_file)
    num_steps = count_roadmap_steps(roadmap_file)

    if num_steps != num_scenarios:
        print(f"❌ VALIDATION FAILED: 1:1 Mapping Violated")
        print(f"   Acceptance scenarios: {num_scenarios}")
        print(f"   Roadmap steps: {num_steps}")
        print(f"   REQUIRED: num_steps == num_scenarios")
        print(f"\n   Outside-In TDD requires 1 step per scenario.")
        print(f"   Fix roadmap to match acceptance test count.")
        sys.exit(1)

    print(f"✅ VALIDATION PASSED: 1:1 Mapping Enforced")
    print(f"   {num_scenarios} scenarios → {num_steps} steps")

if __name__ == "__main__":
    validate_mapping("des", "us001")
```

**Usage**:
```bash
# Run before /nw:develop
python3 scripts/validation/validate_step_mapping.py

# Add to pre-commit hook or roadmap review
```

---

## Exception Cases

**When can you violate this rule?**

**NEVER** for feature development with acceptance tests.

**Only exception**: Infrastructure setup steps (no acceptance tests):
- Database migrations
- Environment configuration
- Third-party service provisioning

These use different workflow (US-INF-* stories with manual verification).

---

## CM-B: Integration Step Requirement (v1.1 Addition)

### The Missing Constraint

The 1:1 step-to-scenario mapping validates **COUNT** but not **BOUNDARY**.

A roadmap can have:
- 6 scenarios → 6 steps ✅ (count matches)
- All 6 steps test internal component ❌ (wrong boundary)
- No step integrates component into entry point ❌ (missing integration)

### Extended Validation Rule

```
VALIDATION (v1.0):
  num_step_files == num_acceptance_test_scenarios  ✅ REQUIRED

NEW VALIDATION (v1.1):
  num_step_files == num_acceptance_test_scenarios  ✅ REQUIRED
  at_least_one_step.targets_entry_point == true    ✅ REQUIRED
  at_least_one_test.imports_entry_point == true    ✅ REQUIRED
```

### Step Types

Each step in the roadmap should specify its type:

```yaml
step_types:
  feature:        # Normal feature step with acceptance test
  integration:    # REQUIRED: Wires component into entry point
  research:       # Investigation (no acceptance test)
  infrastructure: # Setup/config (no acceptance test)

validation_rule: |
  count(steps.step_type == "integration") >= 1  # At least 1 integration step
```

### Boundary Validation

**Acceptance tests must be at the correct boundary**:

```yaml
boundary_check:
  correct: "Tests import entry-point module (driving port)"
  violation: "Tests import internal component directly"

  examples:
    correct:
      - "from des.orchestrator import DESOrchestrator"
      - "from api.client import FeatureClient"

    violation:
      - "from des.validator import TemplateValidator"
      - "from internal.service import BusinessLogic"
```

### Extended Validation Script (v1.1)

```python
def validate_integration_boundary(project_id, test_file):
    """Validate at least one test invokes through entry point."""
    content = Path(test_file).read_text()

    # Check imports
    imports = re.findall(r'^(?:from|import)\s+(\S+)', content, re.MULTILINE)

    entry_point_imports = [i for i in imports if
                          'orchestrator' in i.lower() or
                          'entry_point' in i.lower() or
                          'api.client' in i.lower()]

    internal_only_imports = [i for i in imports if
                            'validator' in i.lower() or
                            'internal.' in i.lower()]

    if not entry_point_imports and internal_only_imports:
        print(f"❌ BOUNDARY VIOLATION: Tests import internal components only")
        print(f"   Found: {internal_only_imports}")
        print(f"   Missing: Entry point imports (orchestrator, api, etc.)")
        print(f"\n   At least one acceptance test must invoke through entry point.")
        sys.exit(1)

    print(f"✅ BOUNDARY CHECK: Entry point import found")
    print(f"   Entry point imports: {entry_point_imports}")
```

---

## Lessons Learned

### Case Study: DES US-001 (Anti-Pattern)

**What happened**:
- DISTILL created 4 acceptance tests (4 scenarios)
- DEVELOP roadmap created 11 steps (architectural approach)
- Step 01-01 made all 4 tests pass at once
- Violated Outside-In TDD discipline

**Impact**:
- Lost granularity in RED → GREEN progression
- Can't trace which scenario drove which implementation
- Harder to review incremental progress
- Mixed refactoring with feature implementation

**Correct approach** (should have been):
- DISTILL: 4 acceptance tests (4 scenarios)
- DEVELOP: 4 steps (01-01 through 01-04)
- Each step: 1 scenario RED → GREEN
- Result: Clean, traceable TDD progression

---

## Summary

**This is a HARD CONSTRAINT, not a guideline.**

- ✅ **DO**: Create 1 step per acceptance test scenario
- ✅ **DO**: Make each step focus on 1 scenario RED → GREEN
- ✅ **DO**: Enforce with validation scripts
- ❌ **DON'T**: Create "architectural" or "technical layer" steps
- ❌ **DON'T**: Make multiple scenarios pass in 1 step
- ❌ **DON'T**: Skip validation enforcement

**Enforcement**: Add validation to `/nw:roadmap` and `/nw:split` commands.

---

**Document Owner**: AI-Craft Team
**Review Cycle**: After each DEVELOP wave
**Next Review**: After DES US-002 completion
