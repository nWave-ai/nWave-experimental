# Local CI/CD Validation

This document describes how to run CI/CD validation checks locally before pushing code, ensuring that issues are caught early.

## Overview

The local validation environment mirrors the GitHub Actions CI/CD pipeline, allowing you to catch errors before they reach the remote repository.

**Benefits:**
- Catch YAML syntax errors before commit
- Validate tests pass locally
- Ensure build succeeds
- Check security issues
- Faster feedback loop
- Avoid failed CI/CD runs

## Prerequisites

**Required:**
- Python 3.11 or 3.12
- pipenv (`pip install pipenv`)

**Optional (for enhanced validation):**
- shellcheck (shell script linting)
- pre-commit (`pip install pre-commit`)

## Quick Start

### 1. Install Dependencies

```bash
# Install pipenv (if not already installed)
pip install pipenv

# Install all dependencies (runtime + dev)
pipenv install --dev
```

### 2. Run Full Local CI Validation

**Recommended - Python version** (cross-platform):
```bash
pipenv run validate
# or directly:
python scripts/local_ci.py
```

**Alternative - Shell version** (Unix only):
```bash
./scripts/local-ci.sh
```

This runs all the same checks as GitHub Actions CI/CD:
1. YAML file validation
2. Pipenv dependency validation
3. Python test suite (pytest)
4. Build process validation
5. Shell script syntax checks
6. Shellcheck linting
7. Python linting (Ruff)
8. Python formatting check (Ruff)
9. Security validation (no hardcoded credentials)
10. nWave framework validation
11. Documentation checks

### 3. Fast Mode (Skip Build)

For quicker validation during development:

**Python**:
```bash
pipenv run validate-fast
# or:
python scripts/local_ci.py --fast
```

**Shell**:
```bash
./scripts/local-ci.sh --fast
```

### 4. Verbose Output

For detailed debugging information:

**Python**:
```bash
python scripts/local_ci.py --verbose
```

**Shell**:
```bash
./scripts/local-ci.sh --verbose
```

## Available Pipenv Scripts

All CI/CD commands are centralized in the Pipfile:

| Command | Description |
|---------|-------------|
| `pipenv run test` | Run pytest test suite |
| `pipenv run build` | Run build process |
| `pipenv run lint` | Run Ruff linting |
| `pipenv run format` | Run Ruff formatting |
| `pipenv run format-check` | Check formatting without modifying |
| `pipenv run validate` | Run full local CI validation |
| `pipenv run validate-fast` | Run fast validation (skip build) |
| `pipenv run validate-yaml` | Validate YAML files only |

## Individual Validation Scripts

### YAML Validation

Validates all YAML files in the repository:

```bash
pipenv run validate-yaml
# or:
python scripts/validation/validate_yaml_files.py
```

**Verbose mode:**
```bash
python scripts/validation/validate_yaml_files.py --verbose
```

This checks:
- YAML syntax correctness
- Proper structure (no mixed list/dict indentation)
- Valid multi-document YAML files
- Template files (nWave/templates/)

**Exit codes:**
- `0`: All YAML files valid
- `1`: One or more files have errors

### Run Tests Only

```bash
pipenv run test
```

Runs the full pytest test suite.

### Run Build Only

```bash
pipenv run build
```

Builds the nWave IDE bundle from source files.

## Pre-Commit Hooks

Pre-commit hooks automatically run validation before each commit.

### Install Pre-Commit Hooks

```bash
# Install pre-commit (if not already installed)
pip install pre-commit

# Install hooks for this repository
pre-commit install
```

### Pre-Commit Validation Includes:

1. **nWave Version Auto-Increment** - Auto-bumps version when nWave files change
2. **Pytest Test Validation** - Runs all tests
3. **Documentation Version Validation** - Checks doc versions are synchronized
4. **Conflict Detection** - Detects conflicts between related files
5. **Code Formatter Check** - Ensures ruff/mypy are available
6. **YAML File Validation** - Validates all YAML syntax
7. **Shell Syntax Check** - Validates shell script syntax (bash -n)
8. **Shellcheck Linting** - Lints shell scripts for best practices
9. **Ruff Linting** - Python code linting
10. **Ruff Formatting** - Python code formatting check
11. **Standard Checks** - Trailing whitespace, EOF, merge conflicts, private keys

### Run Pre-Commit Manually

```bash
# Run on all files
pre-commit run --all-files

# Run on staged files only
pre-commit run

# Run specific hook
pre-commit run yaml-validation
```

### Bypass Pre-Commit (Emergency Only)

**NOT RECOMMENDED** - Only use in emergencies:

```bash
git commit --no-verify
```

This will be logged in `.git/hooks/pre-commit.log` for audit.

## CI/CD Alignment Matrix - 100% Parity

| Check | Local Script | Pre-Commit | CI/CD | Notes |
|-------|-------------|------------|-------|-------|
| Pipenv Dependencies | `pipenv install --dev` | - | `pipenv install --deploy --dev` | **100% parity** |
| YAML Validation | `pipenv run validate-yaml` | yaml-validation hook | quality-gates | **100% parity** |
| Python Tests | `pipenv run test` | pytest-validation | build-and-test | **100% parity** |
| Build Process | `pipenv run build` | (too slow) | build-and-test | Pre-commit skips (slow) |
| Shell Syntax | local-ci.sh | bash -n hook | quality-gates | **100% parity** |
| Shellcheck | local-ci.sh | shellcheck hook | quality-gates | **100% parity** |
| Ruff Linting | `pipenv run lint` | ruff hook | quality-gates | **100% parity** |
| Ruff Formatting | `pipenv run format-check` | ruff-format hook | quality-gates | **100% parity** |
| Security Scan | local-ci.py | (security context) | quality-gates | Pre-commit skips |
| Agent Count | local-ci.py | (informational) | quality-gates | Pre-commit skips |
| Documentation | local-ci.py | (informational) | documentation-check | Pre-commit skips |

**Key Achievement**: Every CI check now has a local equivalent - zero gaps!

## Common Issues and Solutions

### Issue: YAML Validation Fails

```
YAML syntax: File.yaml
  Line 2043, Col 11: while parsing a block collection, expected <block end>, but found '?'
```

**Cause:** Mixed list items (`-`) with dictionary keys at the same indentation level.

**Solution:**
```yaml
# WRONG - dictionary key at same level as list items
section:
  - item1
  - item2
  validation: "text"

# CORRECT - wrap list with 'items:' key
section:
  items:
    - item1
    - item2
  validation: "text"
```

### Issue: Multiple YAML Documents Error

```
expected a single document in the stream but found another document
```

**Cause:** Multiple `---` separators in a file that should be single-document YAML.

**Solution:** Remove extra `---` separators or ensure multi-document YAML is intentional.

### Issue: Tests Pass Locally But Fail in CI

**Cause:** Environment differences between local and CI.

**Solution:**
1. Run `pipenv run validate` to ensure all checks pass
2. Verify Python version matches CI (Python 3.11 or 3.12)
3. Check that all dependencies are installed: `pipenv install --dev`
4. Review `.github/workflows/ci.yml` for any CI-specific configuration

### Issue: Pipenv Lock Issues

**Cause:** Pipfile.lock out of sync with Pipfile.

**Solution:**
```bash
# Regenerate lock file
pipenv lock

# Then install
pipenv install --dev
```

### Issue: Pre-Commit is Slow

**Solution:**
```bash
# Skip slow hooks for quick commits
SKIP=pytest-validation git commit -m "quick fix"

# Or use local-ci.py in fast mode instead
pipenv run validate-fast
```

## Workflow Integration

### Recommended Development Workflow

1. **Make changes** to code/configuration
2. **Run quick validation**:
   ```bash
   pipenv run validate-fast
   ```
3. **Fix any issues** identified
4. **Run full validation** before commit:
   ```bash
   pipenv run validate
   ```
5. **Commit** (pre-commit hooks run automatically)
6. **Push** to remote (CI/CD runs automatically)

### CI/CD Failure Recovery

If CI/CD fails after push:

1. **Check GitHub Actions logs** for specific error
2. **Run local validation**:
   ```bash
   python scripts/local_ci.py --verbose
   ```
3. **Reproduce the error locally**
4. **Fix the issue**
5. **Verify fix with local validation**
6. **Commit and push** again

## Consolidated Workflow Architecture

**Single Unified CI Workflow**: `.github/workflows/ci.yml`

The workflow uses pipenv for all Python operations with these jobs:

1. **build-and-test** - Matrix build (3 OS x 2 Python versions = 6 builds total)
2. **quality-gates** - YAML, shellcheck, ruff linting, security, agent/command validation
3. **documentation-check** - Required documentation validation
4. **unix-installer-test** - Dry-run installer tests (Ubuntu + macOS)
5. **windows-installer-test** - Dry-run installer test (Windows)
6. **release** - Automated release on version tags
7. **ci-summary** - Final status report

**Zero Duplication**: Matrix builds run once across 6 configurations.

## Adding New Validation Checks

To add a new validation check that mirrors CI/CD:

1. **Add to CI workflow** (`.github/workflows/ci.yml` -> `quality-gates` job)
2. **Add to Pipfile** `[scripts]` section (if applicable)
3. **Add to local_ci.py** script
4. **Add to pre-commit** (if fast enough - typically <2 seconds)
5. **Update this documentation**

Example:
```toml
# In Pipfile [scripts] section
new-check = "python scripts/new_check.py"
```

```python
# In scripts/local_ci.py
def validate_new_check(self) -> None:
    """Run new validation check."""
    self.print_header("11. New Validation Check")
    self.run_command(["pipenv", "run", "new-check"], "New check passed")
```

## Maintenance

### Update Pre-Commit Hooks

```bash
# Update to latest versions
pre-commit autoupdate

# Re-install hooks
pre-commit install --install-hooks
```

### Clean Pre-Commit Cache

```bash
pre-commit clean
```

### Update Dependencies

```bash
# Update all dependencies
pipenv update

# Update specific package
pipenv update ruff
```

## References

- GitHub Actions Workflows: `.github/workflows/`
- Local CI Script: `scripts/local_ci.py`
- YAML Validator: `scripts/validation/validate_yaml_files.py`
- Pre-Commit Config: `.pre-commit-config.yaml`
- Pipenv Configuration: `Pipfile`
- CI/CD Documentation: `docs/ci-cd/`
