# Journey: Install Local Candidate (forge:install-local-candidate)

**Designer**: Luna (leanux-designer)
**Date**: 2026-02-01
**Epic**: modern_CLI_installer
**Emotional Arc**: Focused --> Celebratory

---

## Journey Overview

```
+---------------------------------------------------------------------------+
|                                                                           |
|   USER GOAL: Install and validate a locally-built nWave candidate        |
|                                                                           |
|   Triggers:                                                               |
|   - Missed install prompt during forge:build-local                        |
|   - Full release rehearsal before CI/CD                                   |
|   - Manual testing to fix installation process                            |
|   - Iterate on release scripts without rebuilding                         |
|   - Second-chance install after declining in build stage                  |
|                                                                           |
|   Success: Candidate installed, verified, release report generated        |
|                                                                           |
+---------------------------------------------------------------------------+
```

---

## Step 1: Pre-flight Checks

```
+- Step 1: Environment & Wheel Validation ------------------+  Emotion: Focused
|                                                           |  "Let's make sure
|  $ forge:install-local-candidate                          |   everything is ready"
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Forge: Install Local Candidate                     |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  Validating installation environment...                   |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Check                 Status    Details             |  |
|  |  ---------------------------------------------------|  |
|  |  Python version        [check]   3.12.1 (3.10+ OK)   |  |
|  |  pipx available        [check]   v1.4.3 installed    |  |
|  |  ~/.claude writable    [check]   Permissions OK      |  |
|  |  Wheel exists          [check]   ${wheel_path}       |  |
|  |  Wheel format          [check]   Valid .whl          |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  [check] All pre-flight checks passed!                    |
|                                                           |
+-----------------------------------------------------------+
          |
          v
```

**Pre-flight Check Failure Example - Wheel Not Found:**

```
+- Step 1: Environment & Wheel Validation ------------------+  Emotion: Blocked
|                                                           |  "I need to build
|  $ forge:install-local-candidate                          |   first"
|                                                           |
|  Validating installation environment...                   |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Check                 Status    Details             |  |
|  |  ---------------------------------------------------|  |
|  |  Python version        [check]   3.12.1 (3.10+ OK)   |  |
|  |  pipx available        [check]   v1.4.3 installed    |  |
|  |  ~/.claude writable    [check]   Permissions OK      |  |
|  |  Wheel exists          [x]       No wheel in dist/   |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  [x] Pre-flight check failed: No wheel found in dist/     |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  [warn] No wheel file found in dist/ directory.      |  |
|  |                                                      |  |
|  |  Build a wheel first:                                |  |
|  |                                                      |  |
|  |    forge:build-local                                 |  |
|  |                                                      |  |
|  |  Or run automatically?                               |  |
|  |                                                      |  |
|  |  Run forge:build-local now? [Y/n]                    |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
          |
          | User types 'Y' or presses Enter
          v
+- Auto-chain to build-local -------------------------------+  Emotion: Seamless
|                                                           |  "Good, it's
|  [spinner] Running forge:build-local...                   |   building for me"
|                                                           |
|  ... (forge:build-local journey runs) ...                 |
|                                                           |
|  [check] Wheel built successfully                         |
|                                                           |
|  Resuming install-local-candidate...                      |
|                                                           |
+-----------------------------------------------------------+
```

**Pre-flight Check Failure Example - Missing pipx:**

```
+- Step 1: Environment & Wheel Validation ------------------+  Emotion: Blocked
|                                                           |  "I'm missing
|  $ forge:install-local-candidate                          |   something"
|                                                           |
|  Validating installation environment...                   |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Check                 Status    Details             |  |
|  |  ---------------------------------------------------|  |
|  |  Python version        [check]   3.12.1 (3.10+ OK)   |  |
|  |  pipx available        [x]       Not installed       |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  [x] Pre-flight check failed: pipx not installed          |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  [warn] pipx is required for isolated installation.  |  |
|  |                                                      |  |
|  |  Install pipx:                                       |  |
|  |                                                      |  |
|  |    pip install pipx                                  |  |
|  |    pipx ensurepath                                   |  |
|  |                                                      |  |
|  |  Then re-run: forge:install-local-candidate          |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
```

---

## Step 2: Release Readiness Validation

```
+- Step 2: Release Readiness Check -------------------------+  Emotion: Trust
|                                                           |  "Checking all the
|  [magnifier] Validating release readiness...              |   release pieces"
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Wheel: nwave-${candidate_version}-py3-none-any.whl  |  |
|  |  Example: nwave-1.3.0-dev-20260201-001-py3-none-any.whl
|  +-----------------------------------------------------+  |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Release Check             Status                    |  |
|  |  ---------------------------------------------------|  |
|  |  twine check               [check] Wheel valid       |  |
|  |  Metadata complete         [check] All fields set    |  |
|  |  Entry points              [check] nw CLI defined    |  |
|  |  CHANGELOG exists          [check] Recent entry OK   |  |
|  |  Version format            [check] PEP 440 valid     |  |
|  |  License bundled           [check] LICENSE in wheel  |  |
|  |  README bundled            [check] README.md OK      |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  [check] Release readiness: READY FOR PYPI               |
|                                                           |
+-----------------------------------------------------------+
          |
          v
```

**Release Readiness Warning Example - Missing CHANGELOG:**

```
+- Step 2: Release Readiness Check -------------------------+  Emotion: Cautious
|                                                           |  "Hmm, missing
|  [magnifier] Validating release readiness...              |   something"
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Wheel: nwave-${candidate_version}-py3-none-any.whl  |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Release Check             Status                    |  |
|  |  ---------------------------------------------------|  |
|  |  twine check               [check] Wheel valid       |  |
|  |  Metadata complete         [check] All fields set    |  |
|  |  Entry points              [check] nw CLI defined    |  |
|  |  CHANGELOG exists          [warn]  No recent entry   |  |
|  |  Version format            [check] PEP 440 valid     |  |
|  |  License bundled           [check] LICENSE in wheel  |  |
|  |  README bundled            [check] README.md OK      |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  [warn] Release readiness: WARNINGS (non-blocking)        |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  [info] CHANGELOG.md has no entry for ${version}    |  |
|  |                                                      |  |
|  |  This is OK for local testing but should be fixed   |  |
|  |  before CI/CD release.                               |  |
|  |                                                      |  |
|  |  Continue anyway? [Y/n]                              |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
```

**Release Readiness Failure Example - twine check fails:**

```
+- Step 2: Release Readiness Check -------------------------+  Emotion: Blocked
|                                                           |  "Something's wrong
|  [magnifier] Validating release readiness...              |   with the package"
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Wheel: nwave-${candidate_version}-py3-none-any.whl  |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Release Check             Status                    |  |
|  |  ---------------------------------------------------|  |
|  |  twine check               [x]    Invalid metadata   |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  [x] Release readiness: FAILED                            |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  [x] twine check failed:                             |  |
|  |                                                      |  |
|  |  ERROR: Missing required metadata: description       |  |
|  |                                                      |  |
|  |  Fix pyproject.toml and rebuild:                     |  |
|  |    1. Add [project.description] in pyproject.toml    |  |
|  |    2. Re-run forge:build-local                       |  |
|  |    3. Re-run forge:install-local-candidate           |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
```

---

## Step 3: Install Candidate

```
+- Step 3: Installing Candidate ----------------------------+  Emotion: Anticipation
|                                                           |  "Installing now!"
|  [rocket] Installing candidate...                         |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Phase                      Status                   |  |
|  |  ---------------------------------------------------|  |
|  |  Uninstalling previous      [spinner] pipx uninstall |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
          |
          v
+- Step 3: Installing Candidate ----------------------------+  Emotion: Progress
|                                                           |  "Making progress"
|  [rocket] Installing candidate...                         |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Phase                      Status                   |  |
|  |  ---------------------------------------------------|  |
|  |  Uninstalling previous      [check] Removed          |  |
|  |  Installing from wheel      [progress====    ] 60%   |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  [package] Installing: ${wheel_path}                      |
|                                                           |
+-----------------------------------------------------------+
          |
          v
+- Step 3: Install Complete --------------------------------+  Emotion: Satisfaction
|                                                           |  "It worked!"
|  [check] Installation completed successfully              |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Phase                      Status                   |  |
|  |  ---------------------------------------------------|  |
|  |  Uninstalling previous      [check] Removed          |  |
|  |  Installing from wheel      [check] Complete         |  |
|  |  Symlinking nw              [check] Available        |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  Duration: ${install_duration}                            |
|                                                           |
+-----------------------------------------------------------+
          |
          v
```

---

## Step 4: Post-Install Verification (Doctor Check)

```
+- Step 4: Doctor Verification -----------------------------+  Emotion: Trust
|                                                           |  "Verifying
|  [stethoscope] Running nw doctor...                       |   everything works"
|                                                           |
|  +-----------------------------------------------------+  |
|  |  nWave Candidate Health Check                        |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Component             Status    Details             |  |
|  |  ---------------------------------------------------|  |
|  |  Core installation     [check]   ${install_path}     |  |
|  |  Agent files           [check]   ${agent_count} OK   |  |
|  |  Command files         [check]   ${command_count} OK |  |
|  |  Template files        [check]   ${template_count} OK|  |
|  |  Config valid          [check]   nwave.yaml OK       |  |
|  |  Permissions           [check]   All accessible      |  |
|  |  Version match         [check]   ${candidate_version}|  |
|  +-----------------------------------------------------+  |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  nw --version Output:                                |  |
|  |  ---------------------------------------------------|  |
|  |  nWave Framework v${candidate_version}               |  |
|  |  Installed: ${install_path}                          |  |
|  |  Build: ${date}-${sequence}                          |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  [check] Status: HEALTHY                                  |
|                                                           |
+-----------------------------------------------------------+
          |
          v
```

**Doctor Check Failure Example - Missing Agents:**

```
+- Step 4: Doctor Verification -----------------------------+  Emotion: Concerned
|                                                           |  "Something's
|  [stethoscope] Running nw doctor...                       |   not right"
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Component             Status    Details             |  |
|  |  ---------------------------------------------------|  |
|  |  Core installation     [check]   ${install_path}     |  |
|  |  Agent files           [x]       0 found (expected 47)|  |
|  +-----------------------------------------------------+  |
|                                                           |
|  [x] Status: UNHEALTHY                                    |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  [x] Agent files not installed to ~/.claude          |  |
|  |                                                      |  |
|  |  Expected: ~/.claude/agents/nw/                      |  |
|  |  Found: Directory empty or missing                   |  |
|  |                                                      |  |
|  |  This may indicate:                                  |  |
|  |  - Wheel was built without post-install hooks        |  |
|  |  - ~/.claude permissions issue                       |  |
|  |  - Installation interrupted                          |  |
|  |                                                      |  |
|  |  Try: nw install --repair                            |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
```

---

## Step 5: Release Report

```
+- Step 5: Release Report ----------------------------------+  Emotion: Celebratory
|                                                           |  "Done! Full
|                                                           |   release ready!"
|  +-----------------------------------------------------+  |
|  |  [sparkles] FORGE: CANDIDATE INSTALLED               |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  [party] nWave Candidate v${candidate_version} ready!     |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  RELEASE SUMMARY                                     |  |
|  +-----------------------------------------------------+  |
|  |                                                      |  |
|  |  [package] Version    ${candidate_version}           |  |
|  |  [branch]  Branch     ${branch}                      |  |
|  |  [calendar] Built     ${build_timestamp}             |  |
|  |  [clock]   Installed  ${install_timestamp}           |  |
|  |  [ruler]   Size       ${wheel_size}                  |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  INSTALL MANIFEST                                    |  |
|  +-----------------------------------------------------+  |
|  |                                                      |  |
|  |  [robot]     Agents     ${agent_count}               |  |
|  |  [zap]       Commands   ${command_count}             |  |
|  |  [clipboard] Templates  ${template_count}            |  |
|  |  [folder]    Location   ${install_path}              |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  RELEASE READINESS                                   |  |
|  +-----------------------------------------------------+  |
|  |                                                      |  |
|  |  [check] twine check         Passed                  |  |
|  |  [check] Metadata            Complete                |  |
|  |  [check] Entry points        nw CLI defined          |  |
|  |  [check] CHANGELOG           Has entry for ${version}|  |
|  |  [check] License             Bundled                 |  |
|  |  [check] Doctor              HEALTHY                 |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  TEST CHECKLIST                                      |  |
|  +-----------------------------------------------------+  |
|  |                                                      |  |
|  |  [ ] Restart Claude Code (Cmd+Q then reopen)         |  |
|  |  [ ] Run: /nw:version                                |  |
|  |  [ ] Run: /nw:help                                   |  |
|  |  [ ] Test an agent: /nw:product-owner                |  |
|  |  [ ] Run: nw doctor                                  |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
          |
          v
+- Step 5: Next Steps --------------------------------------+  Emotion: Guided
|                                                           |  "I know what
|                                                           |   to do next"
|  +-----------------------------------------------------+  |
|  |  [info] What's Next?                                 |  |
|  +-----------------------------------------------------+  |
|  |                                                      |  |
|  |  LOCAL TESTING:                                      |  |
|  |    1. Restart Claude Code                            |  |
|  |    2. Try: /nw:version                               |  |
|  |    3. Run the test checklist above                   |  |
|  |                                                      |  |
|  |  READY FOR CI/CD:                                    |  |
|  |    All checks passed! This candidate is ready for    |  |
|  |    CI/CD release pipeline to publish to PyPI.        |  |
|  |                                                      |  |
|  |  RELEASE COMMAND (CI/CD only):                       |  |
|  |    twine upload dist/nwave-${version}-py3-none-any.whl
|  |                                                      |  |
|  |  [book] Docs: https://nwave.dev/contributing/release |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
```

---

## Error Paths

### Error 1: No Wheel Found

```
+- Error: No Wheel Found -----------------------------------+  Emotion: Blocked
|                                                           |  "I need to build
|  [x] No wheel found in dist/                              |   first"
|                                                           |
|  +-----------------------------------------------------+  |
|  |  forge:install-local-candidate requires a wheel.     |  |
|  |                                                      |  |
|  |  Expected: dist/nwave-*.whl                          |  |
|  |  Found: No .whl files in dist/                       |  |
|  |                                                      |  |
|  |  Build first with: forge:build-local                 |  |
|  |                                                      |  |
|  |  Or chain automatically?                             |  |
|  |  Run forge:build-local now? [Y/n]                    |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
```

### Error 2: Multiple Wheels Found

```
+- Error: Multiple Wheels Found ----------------------------+  Emotion: Confused
|                                                           |  "Which one
|  [warn] Multiple wheels found in dist/                    |   should I use?"
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Found:                                              |  |
|  |    1. nwave-2.1.0-py3-none-any.whl  (2.3 MB, 14:23) |  |
|  |    2. nwave-2.0.0-py3-none-any.whl  (2.1 MB, 10:15) |  |
|  |                                                      |  |
|  |  Select wheel to install [1-2, or 'c' to cancel]:    |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
          |
          | User types '1'
          v
+- Continuing ----------------------------------------------+
|                                                           |
|  [check] Selected: nwave-2.1.0-py3-none-any.whl           |
|  Continuing with installation...                          |
|                                                           |
+-----------------------------------------------------------+
```

### Error 3: pipx Install Failure

```
+- Error: Install Failed -----------------------------------+  Emotion: Frustrated
|                                                           |  "What went wrong?"
|  [x] pipx install failed                                  |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Phase                      Status                   |  |
|  |  ---------------------------------------------------|  |
|  |  Uninstalling previous      [check] Removed          |  |
|  |  Installing from wheel      [x]    Failed            |  |
|  +-----------------------------------------------------+  |
|                                                           |
|  +-----------------------------------------------------+  |
|  |  [x] Error from pipx:                                |  |
|  |                                                      |  |
|  |  pip subprocess failed with error:                   |  |
|  |  ERROR: No matching distribution found for rich>=13.0|  |
|  |                                                      |  |
|  |  [arrow] This usually means a dependency version     |  |
|  |         conflict exists.                             |  |
|  |                                                      |  |
|  |  Suggested fixes:                                    |  |
|  |  1. Check pyproject.toml dependency versions         |  |
|  |  2. Try: pipx install --pip-args="--upgrade" ${wheel}|  |
|  |  3. Report issue at github.com/nwave/nwave/issues    |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
```

### Error 4: Permission Denied on ~/.claude

```
+- Error: Permission Denied --------------------------------+  Emotion: Blocked
|                                                           |  "I can't write
|  [x] Cannot write to ~/.claude/                           |   there"
|                                                           |
|  +-----------------------------------------------------+  |
|  |  [x] Permission denied: ~/.claude/agents/nw/         |  |
|  |                                                      |  |
|  |  The installer cannot write nWave files to the       |  |
|  |  Claude Code configuration directory.                |  |
|  |                                                      |  |
|  |  Suggested fixes:                                    |  |
|  |  1. Check permissions: ls -la ~/.claude/             |  |
|  |  2. Fix ownership: chown -R $USER ~/.claude/         |  |
|  |  3. Set alternate path:                              |  |
|  |     NWAVE_INSTALL_PATH=~/my-claude/agents/nw         |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
```

### Error 5: Version Mismatch After Install

```
+- Error: Version Mismatch ---------------------------------+  Emotion: Concerned
|                                                           |  "Something's
|  [x] Installed version doesn't match wheel                |   not right"
|                                                           |
|  +-----------------------------------------------------+  |
|  |  Wheel version:     ${wheel_version}                 |  |
|  |  Installed version: ${installed_version}             |  |
|  |                                                      |  |
|  |  This may indicate:                                  |  |
|  |  - Cache issue with pipx                             |  |
|  |  - Multiple nwave installations                      |  |
|  |                                                      |  |
|  |  Suggested fixes:                                    |  |
|  |  1. Clear pipx cache: pipx reinstall nwave           |  |
|  |  2. Check PATH: which nw                             |  |
|  |  3. Force reinstall:                                 |  |
|  |     pipx uninstall nwave && pipx install ${wheel}    |  |
|  +-----------------------------------------------------+  |
|                                                           |
+-----------------------------------------------------------+
```

---

## Shared Artifacts Registry

| Artifact | Source of Truth | Example Value | Displayed In | Risk |
|----------|-----------------|---------------|--------------|------|
| `${candidate_version}` | M.m.p-dev-YYYYMMDD-seq | `1.3.0-dev-20260201-001` | Steps 2, 4, 5 | HIGH - must match wheel |
| `${version}` | pyproject.toml [project.version] base only | `1.3.0` | Steps 2, 5 | HIGH - semantic version |
| `${date}` | Build date YYYYMMDD | `20260201` | Steps 2, 5 | LOW - informational |
| `${sequence}` | Daily build sequence number | `001` | Steps 2, 5 | LOW - informational |
| `${branch}` | git branch name | `installer` | Step 5 only | LOW - informational only |
| `${wheel_path}` | dist/nwave-*.whl (from forge:build-local) | Steps 1, 2, 3, 5 | HIGH - must exist |
| `${wheel_size}` | Runtime file size calculation | Step 5 | LOW - cosmetic |
| `${install_path}` | ~/.claude/agents/nw/ or NWAVE_INSTALL_PATH | Steps 4, 5 | MEDIUM - must be valid |
| `${install_timestamp}` | Runtime timestamp | Step 5 | LOW - informational |
| `${build_timestamp}` | From wheel metadata | Step 5 | LOW - informational |
| `${install_duration}` | Runtime duration calculation | Step 3 | LOW - informational |
| `${agent_count}` | Runtime count after install | Steps 4, 5 | LOW - validation |
| `${command_count}` | Runtime count after install | Steps 4, 5 | LOW - validation |
| `${template_count}` | Runtime count after install | Steps 4, 5 | LOW - validation |

---

## Integration Checkpoints

### Checkpoint 1: Pre-flight to Release Readiness

```
+-------------------------------------------------+
| INTEGRATION CHECKPOINT                          |
| [check] Wheel exists at ${wheel_path}           |
| [check] pipx available                          |
| [check] ~/.claude writable                      |
+-------------------------------------------------+
```

### Checkpoint 2: Release Readiness to Install

```
+-------------------------------------------------+
| INTEGRATION CHECKPOINT                          |
| [check] twine check passed                      |
| [check] Metadata complete                       |
| [check] Version format valid                    |
| [check] Entry points defined                    |
+-------------------------------------------------+
```

### Checkpoint 3: Install to Doctor

```
+-------------------------------------------------+
| INTEGRATION CHECKPOINT                          |
| [check] pipx install succeeded                  |
| [check] nw command available in PATH            |
| [check] Agents deployed to ${install_path}      |
+-------------------------------------------------+
```

### Checkpoint 4: Doctor to Report

```
+-------------------------------------------------+
| INTEGRATION CHECKPOINT                          |
| [check] All doctor checks passed                |
| [check] Version matches wheel                   |
| [check] All components healthy                  |
+-------------------------------------------------+
```

---

## Emotional Arc Summary

```
Focused --> Trust --> Anticipation --> Satisfaction --> Trust --> Celebratory --> Guided
   |          |            |                |             |            |             |
Step 1     Step 2       Step 3           Step 3        Step 4       Step 5        Step 5
Pre-flight  Release     Install         Complete       Doctor       Report       Next Steps
```

**Design Principle**: Every step builds confidence toward release. Pre-flight catches missing pieces. Release readiness validates PyPI compatibility. Doctor proves installation works. Report celebrates and guides.

**Key Moments**:
- [magnifier] Step 2 (Release Readiness): Trust-building PyPI simulation with twine check
- [rocket] Step 3 (Install): Visual progress with phase completion
- [stethoscope] Step 4 (Doctor): Comprehensive verification matching install-nwave
- [party] Step 5 (Report): Celebration with full release summary and test checklist

---

## Relationship to Other Journeys

```
+-------------------+          +-----------------------------+
|                   |          |                             |
| forge:build-local | -------> | forge:install-local-candidate |
|                   |   ${wheel_path}                        |
| Creates wheel     |          | Installs & validates        |
| in dist/          |          | Produces release report     |
+-------------------+          +-----------------------------+
        |                                   |
        | (missed install                   | (uses same doctor)
        |  prompt path)                     |
        v                                   v
+-------------------+          +-------------------+
|                   |          |                   |
| User declined     |          | install-nwave     |
| install prompt    |          | (PyPI version)    |
|                   |          |                   |
| Second chance!    |          | Same verification |
+-------------------+          +-------------------+
```

**Integration Points**:
- `forge:install-local-candidate` consumes `${wheel_path}` from `forge:build-local`
- Uses same pre-flight checks as `install-nwave` (Python, pipx, permissions)
- Doctor verification matches `install-nwave` Step 5 exactly
- Release report format suitable for CI/CD consumption

---

## Candidate Version Format

```
+---------------------------------------------------------------------------+
|  CANDIDATE VERSION FORMAT                                                  |
+---------------------------------------------------------------------------+
|                                                                            |
|  Format: M.m.p-dev-YYYYMMDD-seq                                           |
|                                                                            |
|  Examples:                                                                 |
|    1.3.0-dev-20260201-001                                                 |
|    1.3.0-dev-20260201-002                                                 |
|    1.3.0-dev-20260201-003                                                 |
|                                                                            |
|  Components:                                                               |
|    M.m.p          Base semantic version from pyproject.toml               |
|    dev            Fixed literal indicating development candidate          |
|    YYYYMMDD       Build date                                               |
|    seq            Daily build number (001, 002, etc.)                      |
|                                                                            |
|  Notes:                                                                    |
|    - NO branch name in version (not PEP 440 compliant)                    |
|    - Final release versions (no suffix) only come from CI/CD on main      |
|    - Version bumping happens in forge:build-local, not here               |
|    - This format is PEP 440 compatible (dev release identifier)           |
|                                                                            |
+---------------------------------------------------------------------------+
```

---

## Quality Checklist

- [x] Journey complete from trigger to goal
- [x] All steps have explicit CLI output mockups
- [x] Emotional annotations on every step
- [x] Shared artifacts tracked with sources
- [x] Integration checkpoints placed
- [x] Error paths documented with recovery (5 error scenarios)
- [x] Interactive repair for fixable issues (missing wheel, multiple wheels)
- [x] Celebratory Astro/Vite energy (emojis, progress bars, summaries)
- [x] Connection to forge:build-local journey documented
- [x] Doctor verification matches install-nwave Step 5
- [x] Release report suitable for CI/CD consumption
- [x] Test checklist included for user verification
- [x] Candidate version format documented

---

*Journey designed by Luna following question-first methodology. Ready for Eclipse review.*
