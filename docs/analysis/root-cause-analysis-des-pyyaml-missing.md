# Root Cause Analysis: DES Hooks Fail with Missing PyYAML on macOS/pipx

**Date**: 2026-02-15
**Severity**: Critical (blocks deliver phase entirely)
**Affected**: All pipx-installed users on any platform
**GitHub Issue**: https://github.com/nWave-ai/nWave/issues/1

---

## Problem Statement

When nWave is installed via `pipx install nwave-ai`, DES hooks fail at runtime with `ModuleNotFoundError: No module named 'yaml'`. This specifically blocks Phase 6 (Deliver Integrity Verification) but affects all DES hook invocations that transitively import PyYAML.

**Environment**: macOS Tahoe 26.3, Python 3.14.2 (Homebrew), pipx installation.

---

## Toyota 5 Whys Analysis

### Branch A: Direct `import yaml` Failure in DES CLI

**WHY 1 (Symptom)**: `des.cli.verify_deliver_integrity` fails with `ModuleNotFoundError: No module named 'yaml'`.

- **Evidence**: User report: "The DES CLI requires PyYAML which isn't installed." Six files in `src/des/` contain `import yaml` at module level:
  - `src/des/cli/verify_deliver_integrity.py:21`
  - `src/des/cli/log_phase.py:30`
  - `src/des/cli/roadmap.py:19`
  - `src/des/domain/roadmap_schema.py:15`
  - `src/des/application/subagent_stop_service.py:277` (lazy import)
  - `src/des/adapters/driven/hooks/yaml_execution_log_reader.py:16`

**WHY 2 (Context)**: PyYAML is not available to the Python interpreter that executes these files.

- **Evidence**: The hook command in `~/.claude/settings.json` is:
  ```
  PYTHONPATH=$HOME/.claude/lib/python python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter <action>
  ```
  This uses `python3` from system PATH (Homebrew Python 3.14.2). The `PYTHONPATH` adds `~/.claude/lib/python` which contains the DES module source, but PyYAML is NOT in that directory.

**WHY 3 (System)**: The installer copies DES Python source to `~/.claude/lib/python/des/` but does NOT copy or install any of DES's third-party dependencies (PyYAML, pydantic, etc.) alongside it.

- **Evidence**: `scripts/install/plugins/des_plugin.py` method `_install_des_module()` (lines 184-243) copies the `src/des/` tree to `~/.claude/lib/python/des/` and rewrites imports from `src.des.` to `des.`, but performs no dependency resolution. No `pip install` is invoked. No vendored dependencies are included.

**WHY 4 (Design)**: The installation architecture assumes DES will run under a Python environment that already has PyYAML available, but this assumption is violated by the pipx isolation model.

- **Evidence**: `pyproject.toml` line 49 declares `pyyaml>=6.0` as a project dependency. When installed via `pipx install nwave-ai`, pipx creates an isolated venv at `~/.local/pipx/venvs/nwave-ai/` containing PyYAML. But the hook command uses `python3` (system Python), NOT the pipx venv's Python. The installer (`des_plugin.py` line 419-421) explicitly hardcodes:
  ```python
  lib_path = "$HOME/.claude/lib/python"
  python_path = "python3"
  ```

**WHY 5 (Root Cause)**: **The DES runtime deployment model conflates "source distribution" with "runnable installation."** The installer copies Python source files (a source distribution pattern) but expects them to run as a standalone application. It does not bundle, vendor, or install runtime dependencies. The hook invocation uses system Python which has no mechanism to access pipx's isolated dependencies.

---

### Branch B: Architectural Boundary Violation -- Two Runtimes, One Dependency Set

**WHY 1 (Symptom)**: nWave CLI commands work fine, but DES hooks fail.

- **Evidence**: `pipx install nwave-ai` works. `nwave install` runs successfully (it executes in the pipx venv). But hooks registered in `settings.json` fail because they are executed by Claude Code using system Python.

**WHY 2 (Context)**: There are two distinct runtime contexts: (1) the nwave CLI (runs inside pipx venv), and (2) DES hooks (run by Claude Code using system shell).

- **Evidence**: The hook commands in `settings.json` are shell commands. Claude Code executes them via `sh -c "..."`. The shell resolves `python3` to the system Python, not the pipx venv Python.

**WHY 3 (System)**: The installer does not account for the runtime boundary between "installer context" and "hook execution context."

- **Evidence**: `des_plugin.py` line 421 uses `python_path = "python3"` -- a generic system lookup. The installer runs inside the pipx venv where `sys.executable` would point to `~/.local/pipx/venvs/nwave-ai/bin/python`, but this path is never captured or used for hook commands.

**WHY 4 (Design)**: The hook command template was designed for portability (`$HOME`, `python3`) across machines where `~/.claude/` might be synced, but this portability goal conflicts with dependency resolution.

- **Evidence**: Comment in `des_plugin.py` line 39: "Uses $HOME for portability: settings.json is shared across machines via ~/.claude synced directory, so paths must resolve per-machine." This design explicitly avoids absolute paths, which means it cannot point to the pipx venv.

**WHY 5 (Root Cause)**: **The system has no dependency deployment strategy for the hook execution context.** The portability requirement (generic `python3`) and the dependency isolation model (pipx venv) are fundamentally incompatible. No mechanism exists to bridge these two worlds.

---

### Branch C: PyYAML is a Hard Dependency at Module Import Time

**WHY 1 (Symptom)**: Even hooks that don't directly use YAML features fail, because transitive imports trigger `import yaml`.

- **Evidence**: `claude_code_hook_adapter.py` imports `YamlExecutionLogReader` (line 42-44), which has `import yaml` at module level (line 16). This means ANY hook invocation (PreToolUse, SubagentStop, PostToolUse) will fail if PyYAML is missing, even for non-YAML operations.

**WHY 2 (Context)**: The DES module uses eager (top-level) imports throughout, with no lazy loading or graceful degradation for missing dependencies.

- **Evidence**: `yaml_execution_log_reader.py` line 16: `import yaml` is at module scope. `verify_deliver_integrity.py` line 21: `import yaml` at module scope. No `try/except ImportError` guards exist in any of these files.

**WHY 3 (System)**: The DES module was developed in a monorepo context where all dependencies are always available via the dev venv.

- **Evidence**: `pyproject.toml` lines 104-105: `pythonpath = ["src", "."]` in pytest config. Development always runs with full dependency set.

**WHY 4 (Design)**: There is no "deployment validation" step that tests whether the installed DES module can actually import successfully under the target Python.

- **Evidence**: `des_plugin.py` `verify()` method (lines 805-897) runs an import check on line 817, but uses `sys.executable` (the installer's Python, inside pipx venv) rather than the `python3` that hooks will actually use. This means verification passes during install but fails at hook runtime.

**WHY 5 (Root Cause)**: **The verification tests importability in the wrong Python environment.** The install-time verification uses the installer's Python (which has all dependencies) rather than the target runtime Python (system `python3` which lacks dependencies).

---

## Backwards Chain Validation

| Root Cause | Forward Trace | Matches Symptoms? |
|---|---|---|
| A: Source-only deployment without dependencies | Source copied -> hooks use system python3 -> python3 has no yaml -> `import yaml` fails -> hook crashes | YES |
| B: No dependency deployment strategy for hooks | pipx isolates deps -> hooks use system python3 -> no bridge mechanism -> deps unavailable | YES |
| C: Verification uses wrong Python | Install verifies with pipx python -> passes -> hook runs with system python -> fails at runtime | YES (explains why install succeeds but runtime fails) |

All three root causes are consistent and non-contradictory. They represent different facets of the same architectural gap.

---

## Affected Dependencies

PyYAML is the first to fail because it is imported eagerly. However, the same problem affects ALL third-party dependencies used by DES at hook runtime:

| Dependency | Used By | Import Style |
|---|---|---|
| `pyyaml` | yaml_execution_log_reader, CLI tools, subagent_stop_service | Module-level |
| `pydantic` | DES config models (des_config.py) | Module-level (via settings) |
| `pydantic-settings` | DES configuration loading | Module-level |

---

## Solutions

### Immediate Mitigation (Restore Service)

**M1: Use pipx venv Python in hook commands**

Replace `python3` in the hook command template with the actual pipx venv Python path, resolved at install time:

```python
# In des_plugin.py _generate_hook_command():
import shutil
# Find the nwave-ai pipx venv python
pipx_python = shutil.which("nwave")  # resolves to pipx wrapper
# Or directly: ~/.local/pipx/venvs/nwave-ai/bin/python
python_path = sys.executable  # Capture installer's Python
```

**Tradeoff**: Breaks the portability goal (absolute path won't work on synced machines). Acceptable for single-machine installs.

### Permanent Fix Options

**P1: Vendor dependencies into `~/.claude/lib/python/`** (Recommended)

During install, copy PyYAML (and other runtime deps) into `~/.claude/lib/python/` alongside the DES module. Since PYTHONPATH already points there, vendored packages would be found automatically.

```python
# In des_plugin.py _install_des_module():
# After copying DES source, also install runtime deps
subprocess.run([
    sys.executable, "-m", "pip", "install",
    "--target", str(lib_python_dir),
    "pyyaml>=6.0",
], check=True)
```

**P2: Generate a wrapper script with embedded venv activation**

Create `~/.claude/scripts/des-hook.sh` that activates the correct Python before running:

```bash
#!/bin/sh
# Resolved at install time
VENV_PYTHON="$HOME/.local/pipx/venvs/nwave-ai/bin/python"
if [ -x "$VENV_PYTHON" ]; then
    exec "$VENV_PYTHON" -m des.adapters.drivers.hooks.claude_code_hook_adapter "$@"
else
    python3 -m des.adapters.drivers.hooks.claude_code_hook_adapter "$@"
fi
```

**P3: Make PyYAML a lazy/optional import with graceful degradation**

Wrap `import yaml` in try/except across all DES files. For the hook adapter specifically, allow non-YAML paths to succeed without PyYAML.

This is a partial fix only -- some operations genuinely need YAML.

### Early Detection

**D1: Fix verification to test with target Python**

In `des_plugin.py` `verify()`, replace `sys.executable` with `python3` resolution:

```python
# Instead of sys.executable, use the same python3 that hooks will use
result = subprocess.run(
    ["python3", "-c", f"import sys; sys.path.insert(0, {lib_python!r}); import yaml; from des.application import DESOrchestrator"],
    capture_output=True, text=True, timeout=5,
)
```

---

## Recommended Fix Priority

| Priority | Fix | Effort | Impact |
|---|---|---|---|
| 1 | **P1**: Vendor PyYAML into `~/.claude/lib/python/` | Low | Fixes all users immediately |
| 2 | **D1**: Fix verification to use target Python | Low | Catches regressions at install time |
| 3 | **P3**: Lazy imports for graceful degradation | Medium | Defense in depth |
| 4 | **P2**: Wrapper script with venv fallback | Medium | Handles edge cases |

---

## Files Requiring Changes

| File | Change |
|---|---|
| `/mnt/c/Repositories/Projects/nWave-dev/scripts/install/plugins/des_plugin.py` | Add dependency vendoring in `_install_des_module()`, fix `verify()` to use system python3 |
| `/mnt/c/Repositories/Projects/nWave-dev/scripts/build_dist.py` | Include vendored deps in dist/ layout |
| `/mnt/c/Repositories/Projects/nWave-dev/src/des/adapters/driven/hooks/yaml_execution_log_reader.py` | Consider lazy import guard (P3) |
| `/mnt/c/Repositories/Projects/nWave-dev/src/des/cli/verify_deliver_integrity.py` | Consider lazy import guard (P3) |
