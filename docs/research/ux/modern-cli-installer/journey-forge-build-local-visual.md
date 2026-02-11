# Journey: Build nWave Local Candidate (forge:build-local-candidate)

**Designer**: Luna (leanux-designer)
**Date**: 2026-02-01
**Epic**: modern_CLI_installer
**Emotional Arc**: Focused → Confident → Accomplished

---

## Journey Overview

```
+---------------------------------------------------------------------------+
|                                                                           |
|   USER GOAL: Build a pipx-compatible candidate wheel from local source    |
|                                                                           |
|   Triggers:                                                               |
|   - After modifying core nWave code (verify package still builds)         |
|   - Before PR/release (pre-flight check everything is packaged properly)  |
|   - Testing custom agents (test them in installed context, not dev mode)  |
|                                                                           |
|   Version Strategy:                                                       |
|   - Bumps version using conventional commits OR --force-version           |
|   - Creates candidate: M.m.p-dev-YYYYMMDD-seq                             |
|   - Example: 1.2.0 → 1.3.0-dev-20260201-001 → ... → 1.3.0-dev-20260201-005|
|   - Final release (1.3.0) happens via CI/CD on main branch                |
|                                                                           |
|   Success: Candidate wheel in dist/, optionally installed for testing     |
|                                                                           |
+---------------------------------------------------------------------------+
```

---

## Step 1: Pre-flight Checks

```
+- Step 1: Environment Validation -----------------------+  Emotion: Focused
|                                                        |  "Let's make sure
|  $ forge:build-local-candidate                                   |   everything is ready"
|                                                        |
|  +--------------------------------------------------+  |
|  |  Forge: Build Local                              |  |
|  +--------------------------------------------------+  |
|                                                        |
|  Validating build environment...                       |
|                                                        |
|  +--------------------------------------------------+  |
|  |  Check              Status    Details            |  |
|  |  ------------------------------------------------|  |
|  |  Python version     [check]   3.12.1 (3.10+ OK)  |  |
|  |  build package      [check]   v1.2.1 installed   |  |
|  |  pyproject.toml     [check]   Valid, v${version} |  |
|  |  Source directory   [check]   nWave/ found       |  |
|  |  dist/ directory    [check]   Writable           |  |
|  +--------------------------------------------------+  |
|                                                        |
|  [check] All pre-flight checks passed!                 |
|                                                        |
+--------------------------------------------------------+
          |
          v
```

**Pre-flight Check Failure Example - Missing `build` package:**

```
+- Step 1: Environment Validation -----------------------+  Emotion: Blocked
|                                                        |  "Ah, I'm missing
|  $ forge:build-local-candidate                                   |   something"
|                                                        |
|  Validating build environment...                       |
|                                                        |
|  +--------------------------------------------------+  |
|  |  Check              Status    Details            |  |
|  |  ------------------------------------------------|  |
|  |  Python version     [check]   3.12.1 (3.10+ OK)  |  |
|  |  build package      [x]       Not installed      |  |
|  +--------------------------------------------------+  |
|                                                        |
|  [x] Pre-flight check failed: build package missing    |
|                                                        |
|  +--------------------------------------------------+  |
|  |  [warn] The 'build' package is required to       |  |
|  |       create Python wheels.                      |  |
|  |                                                  |  |
|  |  Install it now? [Y/n]                           |  |
|  +--------------------------------------------------+  |
|                                                        |
+--------------------------------------------------------+
          |
          | User types 'Y' or presses Enter
          v
+- Auto-repair -----------------------------------------+  Emotion: Relieved
|                                                        |  "Great, it's
|  Installing build package...                           |   fixing it for me"
|                                                        |
|  [spinner] pip install build                           |
|                                                        |
|  [check] build v1.2.1 installed successfully           |
|                                                        |
|  Resuming pre-flight checks...                         |
|                                                        |
+--------------------------------------------------------+
```

**Pre-flight Check Failure Example - Invalid pyproject.toml:**

```
+- Step 1: Environment Validation -----------------------+  Emotion: Blocked
|                                                        |  "Something's wrong
|  $ forge:build-local-candidate                                   |   with my config"
|                                                        |
|  Validating build environment...                       |
|                                                        |
|  +--------------------------------------------------+  |
|  |  Check              Status    Details            |  |
|  |  ------------------------------------------------|  |
|  |  Python version     [check]   3.12.1 (3.10+ OK)  |  |
|  |  build package      [check]   v1.2.1 installed   |  |
|  |  pyproject.toml     [x]       Parse error line 42|  |
|  +--------------------------------------------------+  |
|                                                        |
|  [x] Pre-flight check failed: pyproject.toml invalid   |
|                                                        |
|  +--------------------------------------------------+  |
|  |  [x] Error at line 42: unexpected character      |  |
|  |                                                  |  |
|  |  42 |   version = "2.1.0                         |  |
|  |                         ^ missing closing quote  |  |
|  |                                                  |  |
|  |  Fix pyproject.toml and re-run forge:build-local-candidate |  |
|  +--------------------------------------------------+  |
|                                                        |
+--------------------------------------------------------+
```

---

## Step 2: Version Bumping

```
+- Step 2: Version Resolution ----------------------------+  Emotion: Anticipation
|                                                        |  "What version will
|  [tag] Resolving candidate version...                  |   this be?"
|                                                        |
|  +--------------------------------------------------+  |
|  |  Current version   ${base_version} (pyproject.toml)|  |
|  |  Branch            ${branch_name}                 |  |
|  |  Last tag          v${last_tag_version}           |  |
|  +--------------------------------------------------+  |
|                                                        |
|  [magnifier] Analyzing conventional commits...         |
|                                                        |
|  +--------------------------------------------------+  |
|  |  Commits since v${last_tag_version}:              |  |
|  |  ------------------------------------------------|  |
|  |  feat(agents): add Luna leanux-designer      → MINOR|
|  |  feat(agents): add Eclipse reviewer          → MINOR|
|  |  fix(build): correct wheel metadata          → PATCH|
|  |  ------------------------------------------------|  |
|  |  Bump type: MINOR (highest precedence)            |  |
|  +--------------------------------------------------+  |
|                                                        |
|  +--------------------------------------------------+  |
|  |  [check] Version bump: ${base_version} → ${new_version}|
|  |  [check] Candidate:    ${candidate_version}        |  |
|  |          Format: M.m.p-dev-YYYYMMDD-seq           |  |
|  +--------------------------------------------------+  |
|                                                        |
+--------------------------------------------------------+
          |
          v
```

**Alternative: Force Version Override**

```
+- Step 2: Version Resolution (--force-version) ---------+  Emotion: Control
|                                                        |  "I know exactly
|  $ forge:build-local-candidate --force-version 2.0.0             |   what I want"
|                                                        |
|  +--------------------------------------------------+  |
|  |  [warn] Force version override active             |  |
|  |                                                  |  |
|  |  Current:    ${base_version}                     |  |
|  |  Forced to:  2.0.0                               |  |
|  |                                                  |  |
|  |  Candidate:  2.0.0-dev-20260201-001              |  |
|  +--------------------------------------------------+  |
|                                                        |
|  [check] Version must be higher than ${base_version}   |
|                                                        |
+--------------------------------------------------------+
```

**Error: Force Version Too Low**

```
+- Error: Version Constraint -----------------------------+  Emotion: Blocked
|                                                        |  "That version is
|  [x] Force version rejected                            |   too low"
|                                                        |
|  +--------------------------------------------------+  |
|  |  Current version: 1.3.0                          |  |
|  |  Forced version:  1.2.0                          |  |
|  |                                                  |  |
|  |  Force version must be higher than current.      |  |
|  |                                                  |  |
|  |  Try: --force-version 1.4.0 or higher           |  |
|  +--------------------------------------------------+  |
|                                                        |
+--------------------------------------------------------+
```

---

## Step 3: Build Process

```
+- Step 2: Building Distribution ------------------------+  Emotion: Anticipation
|                                                        |  "It's building!"
|  [hammer] Building nWave wheel...                      |
|                                                        |
|  +--------------------------------------------------+  |
|  |  Phase                    Status                 |  |
|  |  ------------------------------------------------|  |
|  |  Cleaning dist/           [check] Removed old    |  |
|  |  Processing source        [spinner] nWave/...    |  |
|  +--------------------------------------------------+  |
|                                                        |
+--------------------------------------------------------+
          |
          v
+- Step 2: Building Distribution ------------------------+  Emotion: Progress
|                                                        |  "Making progress"
|  [hammer] Building nWave wheel...                      |
|                                                        |
|  +--------------------------------------------------+  |
|  |  Phase                    Status                 |  |
|  |  ------------------------------------------------|  |
|  |  Cleaning dist/           [check] Removed old    |  |
|  |  Processing source        [check] ${file_count}  |  |
|  |  Running build backend    [progress====    ] 67% |  |
|  +--------------------------------------------------+  |
|                                                        |
|  [package] Processing: nWave/agents/...                |
|                                                        |
+--------------------------------------------------------+
          |
          v
+- Step 2: Build Complete -------------------------------+  Emotion: Satisfaction
|                                                        |  "It worked!"
|  [check] Build completed successfully                  |
|                                                        |
|  +--------------------------------------------------+  |
|  |  Phase                    Status                 |  |
|  |  ------------------------------------------------|  |
|  |  Cleaning dist/           [check] Removed old    |  |
|  |  Processing source        [check] ${file_count}  |  |
|  |  Running build backend    [check] Complete       |  |
|  +--------------------------------------------------+  |
|                                                        |
|  Duration: ${build_duration}                           |
|                                                        |
+--------------------------------------------------------+
          |
          v
```

---

## Step 4: Wheel Validation

```
+- Step 3: Validating Wheel -----------------------------+  Emotion: Trust
|                                                        |  "Good, it's
|  [magnifier] Validating wheel contents...              |   checking the build"
|                                                        |
|  +--------------------------------------------------+  |
|  |  Wheel: nwave-${candidate_version}-py3-none-any.whl        |  |
|  +--------------------------------------------------+  |
|                                                        |
|  +--------------------------------------------------+  |
|  |  Validation               Status                 |  |
|  |  ------------------------------------------------|  |
|  |  Wheel format             [check] Valid          |  |
|  |  Metadata present         [check] pyproject.toml |  |
|  |  Entry points             [check] nw CLI defined |  |
|  |  Agents bundled           [check] ${agent_count} |  |
|  |  Commands bundled         [check] ${command_count}|  |
|  |  Templates bundled        [check] ${template_count}|  |
|  |  pipx compatible          [check] Verified       |  |
|  +--------------------------------------------------+  |
|                                                        |
|  [check] Wheel validation passed!                      |
|                                                        |
+--------------------------------------------------------+
          |
          v
```

---

## Step 5: Success Summary

```
+- Step 4: Build Summary --------------------------------+  Emotion: Accomplished
|                                                        |  "Done! Ready
|                                                        |   to test"
|   +--------------------------------------------------+ |
|   |  [hammer] FORGE: BUILD COMPLETE                  | |
|   +--------------------------------------------------+ |
|                                                        |
|   [sparkles] nWave v${version} wheel built successfully!|
|                                                        |
|   +--------------------------------------------------+ |
|   |  Artifact          Location                      | |
|   |  ------------------------------------------------| |
|   |  [package] Wheel   dist/nwave-${candidate_version}-py3-none-any.whl |
|   |  [ruler] Size      ${wheel_size}                 | |
|   |  [clock] Built     ${build_timestamp}            | |
|   +--------------------------------------------------+ |
|                                                        |
|   +--------------------------------------------------+ |
|   |  Contents                     Count              | |
|   |  ------------------------------------------------| |
|   |  [robot] Agents               ${agent_count}     | |
|   |  [zap] Commands               ${command_count}   | |
|   |  [clipboard] Templates        ${template_count}  | |
|   +--------------------------------------------------+ |
|                                                        |
+--------------------------------------------------------+
          |
          v
```

---

## Step 6: Install Prompt (Connection to forge:install-local-candidate)

```
+- Step 5: Install Prompt -------------------------------+  Emotion: Guided
|                                                        |  "What should I
|   Your wheel is ready for testing!                     |   do next?"
|                                                        |
|   +--------------------------------------------------+ |
|   |  [info] Test this wheel locally?                 | |
|   |                                                  | |
|   |  This will install nwave-${version} to a local   | |
|   |  pipx environment for testing.                   | |
|   |                                                  | |
|   |  Install locally now? [Y/n]                      | |
|   +--------------------------------------------------+ |
|                                                        |
+--------------------------------------------------------+
          |
          | User types 'Y' or presses Enter
          v
+- Handoff to install-local -----------------------------+  Emotion: Seamless
|                                                        |  "One smooth flow"
|  Installing wheel locally...                           |
|                                                        |
|  [spinner] pipx install dist/nwave-${candidate_version}-py3-none-any.whl --force
|                                                        |
|  ... (forge:install-local-candidate journey continues) ...             |
|                                                        |
+--------------------------------------------------------+
```

**If user declines:**

```
+- Step 5: Manual Instructions --------------------------+  Emotion: Informed
|                                                        |  "I know what to
|   Your wheel is ready for testing!                     |   do next"
|                                                        |
|   Install locally now? [Y/n] n                         |
|                                                        |
|   +--------------------------------------------------+ |
|   |  To install manually, run:                       | |
|   |                                                  | |
|   |  pipx install dist/nwave-${candidate_version}-py3-none-any.whl --force
|   |                                                  | |
|   |  Or to test in development mode:                 | |
|   |                                                  | |
|   |  pip install -e .                                | |
|   +--------------------------------------------------+ |
|                                                        |
|   [book] Docs: https://nwave.dev/contributing/local-dev|
|                                                        |
+--------------------------------------------------------+
```

---

## Error Paths

### Error 1: pyproject.toml Not Found

```
+- Error: Missing pyproject.toml ------------------------+  Emotion: Blocked
|                                                        |  "Where's my
|  [x] pyproject.toml not found                          |   config?"
|                                                        |
|  +--------------------------------------------------+  |
|  |  forge:build-local-candidate must be run from the nWave    |  |
|  |  project root directory.                         |  |
|  |                                                  |  |
|  |  Expected: ./pyproject.toml                      |  |
|  |  Current dir: ${current_dir}                     |  |
|  |                                                  |  |
|  |  Try: cd /path/to/nwave && forge:build-local-candidate     |  |
|  +--------------------------------------------------+  |
|                                                        |
+--------------------------------------------------------+
```

### Error 2: Build Backend Failure

```
+- Error: Build Failed ----------------------------------+  Emotion: Frustrated
|                                                        |  "What went wrong?"
|  [x] Build failed                                      |
|                                                        |
|  +--------------------------------------------------+  |
|  |  Phase                    Status                 |  |
|  |  ------------------------------------------------|  |
|  |  Cleaning dist/           [check] Removed old    |  |
|  |  Processing source        [check] 47 files       |  |
|  |  Running build backend    [x] Failed             |  |
|  +--------------------------------------------------+  |
|                                                        |
|  +--------------------------------------------------+  |
|  |  [x] Error from build backend (setuptools):      |  |
|  |                                                  |  |
|  |  ModuleNotFoundError: No module named 'rich'     |  |
|  |                                                  |  |
|  |  [arrow] This usually means a dependency is      |  |
|  |         missing from pyproject.toml              |  |
|  |                                                  |  |
|  |  Suggested fix:                                  |  |
|  |  Add 'rich' to [project.dependencies] in         |  |
|  |  pyproject.toml                                  |  |
|  +--------------------------------------------------+  |
|                                                        |
+--------------------------------------------------------+
```

### Error 3: Existing Wheel Version Conflict

```
+- Warning: Version Conflict ----------------------------+  Emotion: Cautious
|                                                        |  "Wait, let me
|  [warn] Existing wheel found with same version         |   check this"
|                                                        |
|  +--------------------------------------------------+  |
|  |  Found: dist/nwave-${candidate_version}-py3-none-any.whl   |  |
|  |  Built: 2026-01-31 14:23:00                      |  |
|  |                                                  |  |
|  |  Overwrite existing wheel? [Y/n]                 |  |
|  +--------------------------------------------------+  |
|                                                        |
+--------------------------------------------------------+
          |
          | User types 'Y'
          v
+- Continuing ------------------------------------------+
|                                                        |
|  [check] Old wheel removed                             |
|  [spinner] Building new wheel...                       |
|                                                        |
+--------------------------------------------------------+
```

### Error 4: Permission Denied

```
+- Error: Permission Denied -----------------------------+  Emotion: Blocked
|                                                        |  "I can't write
|  [x] Cannot write to dist/ directory                   |   there"
|                                                        |
|  +--------------------------------------------------+  |
|  |  [x] Permission denied: dist/                    |  |
|  |                                                  |  |
|  |  The build process cannot create files in the    |  |
|  |  dist/ directory.                                |  |
|  |                                                  |  |
|  |  Suggested fixes:                                |  |
|  |  1. Check directory permissions: ls -la dist/   |  |
|  |  2. Remove read-only flag: chmod u+w dist/      |  |
|  |  3. Run with different user if needed           |  |
|  +--------------------------------------------------+  |
|                                                        |
+--------------------------------------------------------+
```

### Error 5: Python Version Mismatch

```
+- Error: Python Version --------------------------------+  Emotion: Informed
|                                                        |  "I need to
|  [x] Python version too old                            |   upgrade"
|                                                        |
|  +--------------------------------------------------+  |
|  |  Required: Python 3.10+                          |  |
|  |  Found:    Python 3.8.10                         |  |
|  |                                                  |  |
|  |  nWave requires Python 3.10 or newer to build.   |  |
|  |                                                  |  |
|  |  Upgrade options:                                |  |
|  |  - pyenv install 3.12 && pyenv local 3.12       |  |
|  |  - brew install python@3.12                     |  |
|  |  - Download from python.org                      |  |
|  +--------------------------------------------------+  |
|                                                        |
+--------------------------------------------------------+
```

---

## Shared Artifacts Registry

| Artifact | Source of Truth | Displayed In | Risk |
|----------|-----------------|--------------|------|
| `${base_version}` | pyproject.toml [project.version] | Step 2 | LOW - input to bump calculation |
| `${new_version}` | Calculated from conventional commits or --force-version | Step 2 | MEDIUM - determines candidate |
| `${candidate_version}` | Generated: M.m.p-dev-YYYYMMDD-seq | Steps 2, 4, 5, 6 | HIGH - must match wheel filename |
| `${branch_name}` | git rev-parse --abbrev-ref HEAD | Step 2 | LOW - informational |
| `${daily_sequence}` | Counter for builds on same day (001, 002, etc.) | Step 2 | LOW - uniqueness |
| `${wheel_path}` | Generated: dist/nwave-${candidate_version}-py3-none-any.whl | Steps 5, 6 | LOW - derived from candidate_version |
| `${wheel_size}` | Runtime file size calculation | Step 4 | LOW - cosmetic |
| `${build_timestamp}` | Runtime timestamp | Step 4 | LOW - informational |
| `${build_duration}` | Runtime duration calculation | Step 2 | LOW - informational |
| `${agent_count}` | Runtime count of bundled agents | Steps 3, 4 | LOW - validation |
| `${command_count}` | Runtime count of bundled commands | Steps 3, 4 | LOW - validation |
| `${template_count}` | Runtime count of bundled templates | Steps 3, 4 | LOW - validation |
| `${file_count}` | Runtime count of processed files | Step 2 | LOW - progress display |
| `${current_dir}` | Runtime pwd | Error 1 | LOW - debugging |

---

## Integration Checkpoints

### Checkpoint 1: Pre-flight to Build

```
+-------------------------------------------------+
| INTEGRATION CHECKPOINT                          |
| [check] pyproject.toml version = ${version}     |
| [check] Source directory nWave/ exists          |
| [check] build package available                 |
+-------------------------------------------------+
```

### Checkpoint 2: Build to Validation

```
+-------------------------------------------------+
| INTEGRATION CHECKPOINT                          |
| [check] Wheel created at dist/nwave-${version}  |
| [check] Wheel filename matches pyproject.toml   |
| [check] All source files bundled                |
+-------------------------------------------------+
```

### Checkpoint 3: Validation to Install Prompt

```
+-------------------------------------------------+
| INTEGRATION CHECKPOINT                          |
| [check] Wheel passed all validation checks      |
| [check] pipx compatibility verified             |
| [check] Wheel path available for install cmd    |
+-------------------------------------------------+
```

### Checkpoint 4: Handoff to install-local

```
+-------------------------------------------------+
| INTEGRATION CHECKPOINT                          |
| [check] ${wheel_path} passed to install-local   |
| [check] Version ${version} propagates           |
| [check] --force flag included (replaces old)    |
+-------------------------------------------------+
```

---

## Emotional Arc Summary

```
Focused --> Anticipation --> Progress --> Satisfaction --> Trust --> Accomplished --> Guided
   |            |               |              |             |            |              |
Step 1       Step 2          Step 3         Step 3        Step 4       Step 5         Step 6
Pre-flight   Versioning      Building       Complete      Validate     Summary        Prompt
```

**Design Principle**: Every step reinforces confidence. Pre-flight catches issues early. Progress shows work happening. Validation proves quality. Summary celebrates success. Prompt guides next action.

**Key Moments**:
- [hammer] Step 2 (Build): Visual progress with phases and percentages
- [magnifier] Step 3 (Validate): Trust-building verification of wheel contents
- [sparkles] Step 4 (Summary): Celebration with clear artifact details
- [arrow] Step 5 (Prompt): Seamless handoff to local installation

---

## Relationship to Other Journeys

```
LOCAL DEVELOPMENT FLOW:
+---------------------------+          +-------------------------------+
|                           |          |                               |
| forge:build-local-candidate|--------->| forge:install-local-candidate |
|                           |          |                               |
| • Bumps version (semver)  |  ${wheel_path}                           |
| • Creates candidate wheel |  ${candidate_version}                    |
| • 1.3.0-dev-20260201-001  |          | • Validates release readiness |
|                           |          | • Installs via pipx           |
+---------------------------+          | • Runs doctor verification    |
        ^                              +-------------------------------+
        |                                        |
        | (iterate until ready)                  | (ready for PR)
        |                                        v
        +----------------------------------------+
                                                 |
CI/CD RELEASE FLOW (on main):                    v
+---------------------------+          +---------------------------+
|                           |          |                           |
| Pipeline builds & tests   |--------->| Release 1.3.0 (final)     |
|                           |          |                           |
| • Drops -dev suffix       |          | • Git tag: v1.3.0         |
| • 1.3.0-dev-* → 1.3.0     |          | • GitHub Release artifact |
|                           |          | • PyPI/pipx: nwave==1.3.0 |
+---------------------------+          +---------------------------+
                                                 |
                                                 v
NEW USER FLOW:                         +---------------------------+
                                       |                           |
                                       | install-nwave (from PyPI) |
                                       |                           |
                                       | • pipx install nwave      |
                                       | • Same install experience |
                                       +---------------------------+
```

**Integration Points**:
- `forge:build-local-candidate` produces `${wheel_path}` with `${candidate_version}`
- `forge:install-local-candidate` consumes local wheel, validates release readiness
- `install-nwave` is the PyPI path for end users (same install experience)
- Candidate version `${candidate_version}` flows through local development
- Final version (without -dev suffix) is released by CI/CD on main

---

## Quality Checklist

- [x] Journey complete from trigger to goal
- [x] All steps have explicit CLI output mockups
- [x] Emotional annotations on every step
- [x] Shared artifacts tracked with sources
- [x] Integration checkpoints placed
- [x] Error paths documented with recovery (5 error scenarios)
- [x] Interactive repair for fixable issues (missing build package)
- [x] Celebratory Astro/Vite energy (emojis, progress bars, summaries)
- [x] Prompted flow for install handoff
- [x] Connection to install-nwave journey documented

---

*Journey designed by Luna following question-first methodology. Ready for Eclipse review.*
