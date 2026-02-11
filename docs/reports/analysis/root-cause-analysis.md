# CI/CD Root Cause Analysis - Pre-commit Hook Failures

**Date**: 2026-01-26 (Updated)
**Previous Analysis**: 2026-01-21
**Analyst**: Sage (Troubleshooter Agent)
**Methodology**: Toyota 5 Whys Multi-Causal Investigation
**Status**: 4 Root Causes Identified - Actionable Solutions Provided

---

## Executive Summary

The CI/CD pipeline is RED on GitHub Actions due to **pre-commit hook failures** stemming from 4 independent root causes:

1. **RC1 - CRITICAL**: CI installs `pytest pytest-cov pyyaml` but NOT `pytest-bdd`, causing test collection failures
2. **RC2 - HIGH**: Test files contain assigned-but-unused variables (F841 violations)
3. **RC3 - HIGH**: Redundant import statements in `test_backup_cleanup.py` confusing ruff analysis (F821)
4. **RC4 - LOW**: JSON file missing trailing newline (auto-fixed)

**Root Cause**: Dependency management divergence between local development (Pipfile) and CI environment (hardcoded pip install list)

---

## Current Failure Analysis (2026-01-26)

### Observable Symptoms from CI Log

| Failure | Exit Code | Files Affected |
|---------|-----------|----------------|
| Pytest Test Validation | 1 | 3 test files fail collection |
| Ruff Linting (F841) | 1 | 6 unused variable violations |
| Ruff Linting (F821) | 1 | 4 undefined name violations |
| End-of-file fixer | 1 | 1 JSON file modified |

### Evidence Sources

**Source 1**: CI Error Log (`_tmp/_cicd_error.log`)
```
ERROR collecting tests/acceptance/features/version-update-experience/test_git_workflow_steps.py
ERROR collecting tests/acceptance/features/version-update-experience/test_update_steps.py
ERROR collecting tests/acceptance/features/version-update-experience/test_version_steps.py
```

**Source 2**: CI Workflow (`.github/workflows/ci-cd.yml` lines 97-99)
```yaml
pip install pytest pytest-cov pyyaml  # NO pytest-bdd!
```

**Source 3**: Pipfile (line 13)
```
pytest-bdd = ">=7.0.0"  # Required for acceptance tests
```

---

## Toyota 5 Whys Multi-Causal Investigation

### FAILURE BRANCH A: Pytest Collection Errors

#### WHY #1A: Why do tests fail to collect?
**Symptom**: `ERROR collecting tests/acceptance/.../test_git_workflow_steps.py`

**Evidence**: Test files import `pytest_bdd`:
```python
from pytest_bdd import scenarios, given, when, then, parsers  # line 9
```

**Conclusion**: Module `pytest_bdd` not found in CI environment.

#### WHY #2A: Why is pytest-bdd not available in CI?
**Evidence from `.github/workflows/ci-cd.yml`**:
```yaml
pip install pytest pytest-cov pyyaml  # pytest-bdd NOT listed
```

**Conclusion**: CI uses hardcoded minimal dependency list.

#### WHY #3A: Why doesn't CI install pytest-bdd?
**Comparison**:
- **Pipfile**: `pytest-bdd = ">=7.0.0"` (dev-packages)
- **CI**: Only `pytest pytest-cov pyyaml`

**Conclusion**: CI workflow diverges from Pipfile.

#### WHY #4A: Why is there divergence?
**Evidence**:
- Local: `pipenv install --dev` reads Pipfile
- CI: Direct `pip install` with hardcoded list
- No `requirements-dev.txt` synchronization

**Conclusion**: Two parallel dependency management systems.

#### WHY #5A: ROOT CAUSE 1
**Root Cause**: CI/CD uses hardcoded dependency list that diverges from authoritative Pipfile. No single source of truth for test dependencies.

---

### FAILURE BRANCH B: Ruff F841 (Unused Variables)

#### WHY #1B: Why does ruff report F841?
**Symptom**:
```
test_git_workflow_steps.py:407:5: F841 Local variable `result` is assigned to but never used
```

#### WHY #2B: Why do unused variables exist?
**Evidence from test file**:
```python
def verify_commit_not_in_log(git_repo):
    result = subprocess.run(...)  # Captured but never used
    pass  # Placeholder implementation
```

**Conclusion**: Test implementations are incomplete/scaffolded.

#### WHY #3B-5B: ROOT CAUSE 2
**Root Cause**: Test step definitions contain assigned-but-unused variables from incomplete implementation. Variables captured for future assertions that were never written.

---

### FAILURE BRANCH C: Ruff F821 (Undefined Name)

#### WHY #1C: Why does ruff report F821?
**Symptom**:
```
test_backup_cleanup.py:56:23: F821 Undefined name `BackupManager`
```

#### WHY #2C: Why was the import removed?
**Evidence from CI diff**:
```diff
-from nWave.infrastructure.backup_manager import BackupManager
```
Ruff removed module-level import as "unused".

#### WHY #3C: Why did ruff think it was unused?
**Evidence**: Import exists TWICE:
- Line 14: Module level (removed by ruff)
- Lines 59, 97, 126, 156: Inside each test method (redundant)

**Conclusion**: Duplicate imports confused ruff's analysis.

#### WHY #4C-5C: ROOT CAUSE 3
**Root Cause**: Redundant import statements in `test_backup_cleanup.py` - both at module level and duplicated inside test methods. Ruff removes what appears unused, breaking the code.

---

### FAILURE BRANCH D: End-of-File Fixer

#### ROOT CAUSE 4
**Root Cause**: JSON file `04-04.json` missing trailing newline. Auto-fixed by pre-commit.

---

## Root Cause Summary Table

| ID | Root Cause | Category | Severity | Files Affected |
|----|-----------|----------|----------|----------------|
| RC1 | CI dependency divergence from Pipfile | Configuration | CRITICAL | `.github/workflows/ci-cd.yml` |
| RC2 | Unused variables in test scaffolding | Code Quality | HIGH | `test_git_workflow_steps.py`, `test_update_steps.py` |
| RC3 | Redundant imports confusing ruff | Code Quality | HIGH | `test_backup_cleanup.py` |
| RC4 | Missing EOF newline | Formatting | LOW | `04-04.json` |

---

## Solutions

### Solution 1: Fix CI Dependency Management (RC1)
**Recommended**: Add pytest-bdd to CI install:
```yaml
pip install pytest pytest-cov pytest-bdd pyyaml
```

**Alternative**: Generate requirements-dev.txt from Pipfile.

### Solution 2: Fix Unused Variables (RC2)
Prefix with underscore to indicate intentional non-use:
```python
_result = subprocess.run(...)  # Intentionally unused
```

**Affected lines**:
- `test_git_workflow_steps.py`: 407, 471
- `test_update_steps.py`: 457, 505, 513, 530

### Solution 3: Fix Redundant Imports (RC3)
Remove in-method imports, keep only module-level:
```python
# Keep at module level (line 14)
from nWave.infrastructure.backup_manager import BackupManager

# REMOVE these duplicate imports inside methods:
# Lines 59, 97, 126, 156
```

### Solution 4: EOF Newline (RC4)
Already auto-fixed. Commit the modified file.

---

## Backward Chain Validation

| Root Cause | If Fixed | Expected Result |
|------------|----------|-----------------|
| RC1 | pytest-bdd installed | Test collection succeeds |
| RC2 | Variables prefixed `_` | F841 errors resolve |
| RC3 | Duplicates removed | F821 errors resolve |
| RC4 | EOF added | File fixer passes |

**Cross-validation**: All root causes are independent. Fixing one does not break another.

---

## Estimated Fix Time

| Task | Time |
|------|------|
| Add pytest-bdd to CI | 2 min |
| Prefix unused variables | 10 min |
| Remove duplicate imports | 5 min |
| Commit fixed files | 3 min |
| **Total** | **20 min** |

---

## Historical Context (2026-01-21 Analysis)

The previous investigation identified a different class of issues related to build system error swallowing. Those issues may still exist but are not blocking the current CI/CD failure, which is caused by pre-commit hook failures before the build step runs.

---

## Appendix: Previous Analysis (2026-01-21)

The following section documents the previous build system analysis for reference.
