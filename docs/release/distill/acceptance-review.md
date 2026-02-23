# Acceptance Review: Release Train Tag Auto-Discovery

**Date**: 2026-02-23
**Test file**: `tests/release/test_discover_tag.py`
**Conftest**: `tests/release/conftest.py`

## Success Criteria Checklist

| Criterion | Status | Evidence |
|-----------|--------|----------|
| All user stories covered | PASS | US-1: scenarios 1-3, 6-8, 10-11; US-2: scenarios 4-5, 9 |
| Walking skeleton identified | PASS | TestWalkingSkeleton::test_auto_discover_highest_dev_tag |
| Error path ratio >= 40% | PASS | 6 error/edge out of 15 = 40% |
| Business language in test names | PASS | No HTTP codes, no class names, no SQL in test names |
| One test enabled, rest skipped | PASS | 1 FAILED (no script yet), 14 SKIPPED |
| Driving port only (subprocess CLI) | PASS | All tests invoke via subprocess, zero internal imports |
| Fixtures match architecture spec | PASS | 4 fixtures from arch section 5.3, digit transition has 11 entries |
| Existing tests unaffected | PASS | conftest additions are new fixtures, no existing fixture modified |

## Mandate Compliance Evidence

### CM-A: Driving Port Usage

All tests invoke `discover_tag.py` through subprocess (the driving port). Zero imports from production code.

```
run_discover_tag() -> subprocess.run([sys.executable, SCRIPT, *args])
_run_discover_in_repo() -> subprocess.run([sys.executable, script_path, *args])
```

### CM-B: Zero Technical Terms in Test Names

Test names use domain language exclusively:
- "auto discover highest dev tag"
- "mixed base versions returns globally highest"
- "digit transition dev11 beats dev9"
- "no dev tags returns stage 1 guidance"
- "tag at head shows zero commits behind"

No HTTP codes, no API endpoints, no database terms.

### CM-C: Scenario Counts

- Walking skeletons: 1
- Focused scenarios: 14 (all with @skip)
- Total: 15

## Architecture Alignment

| Architecture Spec | Test Coverage |
|-------------------|---------------|
| --pattern dev/rc | Scenarios 1-5, 8-9 |
| --validate TAG | Scenarios 6-7 |
| --tag-list | All unit scenarios (1-11, 14-15) |
| JSON output: tag, version, found | All scenarios assert these fields |
| JSON output: commits_behind | Scenarios 12-14 |
| Exit code 0 = found | Scenarios 1-6, 11 |
| Exit code 1 = not-found | Scenarios 7-9, 15 |
| Exit code 2 = invalid input | Scenario 10 |
| packaging.Version sort | Scenarios 3, 5 (digit transition) |

## Gaps and Notes

- Workflow integration (Roadmap Step 3) is outside test scope;
  covered by workflow YAML changes, not by this test file.
- The `_run_discover_in_repo` helper resolves the script path
  from `Path(__file__).parents[2]`, making it portable across
  environments without hardcoded paths.
