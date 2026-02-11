# APEX-002: Improve Installation Script Environment Detection and Error Handling

**Type:** Developer Experience Improvement
**Priority:** MEDIUM
**Assigned To:** software-crafter
**Created:** 2026-01-29
**Status:** PARKING LOT

---

## Executive Summary

During smoke testing of the nWave installation on a clean machine, the installation script failed with an unhelpful error when dependencies were missing. The script should detect environment issues before attempting the build and provide actionable guidance.

---

## Current State Analysis

### Failure Scenario

```bash
$ python3 scripts/install/install_nwave.py

[ERROR] Build failed
[ERROR] Traceback (most recent call last):
  ...
  ModuleNotFoundError: No module named 'yaml'
```

### Root Cause

The `build_framework()` method in `scripts/install/install_nwave.py` (lines 86-103):

```python
result = subprocess.run(
    [sys.executable, str(build_script)],
    ...
)

if result.returncode == 0:
    self.logger.info("Build completed successfully")
    return True
else:
    self.logger.error("Build failed")
    self.logger.error(result.stderr)  # Raw traceback dumped
    return False
```

### Identified Gaps

| Gap | Impact |
|-----|--------|
| No pre-flight environment check | Script starts then fails mid-way |
| No virtual environment detection | Users may pollute global Python |
| Raw traceback as error message | Not actionable for users |
| No dependency check before build | Build fails instead of install failing gracefully |
| No Pipfile/venv guidance | Users don't know the fix |

---

## Proposed Solution

### 1. Pre-flight Environment Check

Add method to verify environment before starting:

```python
def _check_environment(self) -> bool:
    """Verify Python environment is properly configured."""
    # Check if running in virtual environment
    in_venv = sys.prefix != sys.base_prefix

    if not in_venv:
        self.logger.warn("Not running in a virtual environment")
        self.logger.info("Recommended: pipenv install && pipenv run python install_nwave.py")

    # Check for required dependencies
    required_modules = ['yaml', 'pathlib']
    missing = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)

    if missing:
        self.logger.error(f"Missing required modules: {', '.join(missing)}")
        self.logger.info("Install dependencies first:")
        self.logger.info("  pipenv install && pipenv shell")
        self.logger.info("  # OR")
        self.logger.info("  pip install -r requirements.txt")
        return False

    return True
```

### 2. Intelligent Error Parsing

Parse stderr for common patterns and provide guidance:

```python
def _parse_build_error(self, stderr: str) -> str:
    """Parse build error and return actionable message."""
    if "ModuleNotFoundError" in stderr:
        module = re.search(r"No module named '(\w+)'", stderr)
        module_name = module.group(1) if module else "unknown"
        return (
            f"Missing Python module: {module_name}\n"
            f"Fix: Activate virtual environment first\n"
            f"  pipenv install && pipenv run python install_nwave.py"
        )
    if "PermissionError" in stderr:
        return "Permission denied. Check file permissions or run with appropriate access."
    return stderr  # Fallback to raw error
```

### 3. Integration Points

Call pre-flight check at start of `main()`:

```python
def main():
    installer = NWaveInstaller(...)

    # Pre-flight checks
    if not installer._check_environment():
        return 1

    # Continue with normal flow...
```

---

## Acceptance Criteria

- [ ] Script detects when not running in virtual environment and warns
- [ ] Script checks for required dependencies before build attempt
- [ ] Missing module errors provide actionable "pipenv" guidance
- [ ] Permission errors provide clear message
- [ ] Pre-flight check can be skipped with `--skip-checks` flag
- [ ] All checks logged to install log for debugging

---

## Related Files

- `scripts/install/install_nwave.py` - Main installation script (lines 86-103)
- `scripts/install/install_utils.py` - Shared utilities
- `Pipfile` - Project dependencies
- `docs/installation/installation-guide.md` - User documentation

---

## Discovery Context

This gap was identified during smoke testing of the nWave installation on a clean machine:
1. Ran `python3 scripts/install/install_nwave.py` without virtual environment
2. Build failed with raw `ModuleNotFoundError: No module named 'yaml'`
3. No guidance provided on how to fix

**Reporter:** Vera (orchestrator)
**Discovery Date:** 2026-01-29

---

## Additional Issues Discovered

### Issue #2: Installation Guide Missing Prerequisites

**File:** `docs/installation/installation-guide.md`

**Current State (line 18):**
```
**Prerequisites**: Python 3.11 or higher
```

**Problems:**
1. Does not mention pipenv is required
2. Does not mention virtual environment setup
3. Does not mention dependencies must be installed first
4. Python version claim is inaccurate (Pipfile allows Python 3.x, tested working on 3.10.11)

**Proposed Update:**
```markdown
**Prerequisites**:
- Python 3.8 or higher
- pipenv (`pip install pipenv`)

**Setup:**
```bash
pipenv install --dev    # Create virtual environment and install dependencies
```
```

### Issue #3: Quick Start Section Misleading

**Current State (lines 9-16):**
```bash
# From repository root
python3 scripts/install/install_nwave.py
```

**Problem:** Running without virtual environment causes `ModuleNotFoundError: No module named 'yaml'`

**Proposed Update:**
```bash
# From repository root
pipenv install --dev                                    # First time only
pipenv run python scripts/install/install_nwave.py     # Run installer
```

---

## Correct Installation Steps (Verified)

The following steps were tested on a clean macOS machine:

```bash
# 1. Prerequisites (if pipenv not installed)
pip3 install pipenv

# 2. Setup virtual environment and dependencies
cd crafter-ai
pipenv install --dev

# 3. Run installation
pipenv run python scripts/install/install_nwave.py

# 4. Verify installation
ls ~/.claude/agents/nw/       # Should show 28+ agent files
ls ~/.claude/commands/nw/     # Should show 23 command files
cat ~/.claude/nwave-manifest.txt
```

---

## Scope Expansion

This parking lot item now covers:

1. **Script improvement:** Pre-flight environment checks and actionable error messages
2. **Documentation fix:** Update installation guide with correct prerequisites
3. **Documentation fix:** Update quick start with pipenv commands
4. **Documentation fix:** Correct Python version requirement (3.8+, not 3.11+)
