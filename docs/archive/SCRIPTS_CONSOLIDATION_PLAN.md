# Scripts Consolidation Plan

**Status**: Reviewed and Revised ✅
**Created**: 2026-01-21
**Reviewed**: 2026-01-21 (Adversarial review completed)
**Scope**: Reorganize scripts/ (15 files + 7 hooks) for clarity, maintenance, and cross-platform compatibility
**Target State**: Python-based, modular, well-organized by function
**Impact**: No functionality loss; improved structure, maintainability, and portability
**Execution Order**: This plan executes SECOND, after docs consolidation

---

## Review Findings & Resolutions

### Adversarial Review Summary (18 issues identified)

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 4 | ✅ Resolved |
| HIGH | 6 | ✅ Resolved |
| MEDIUM | 6 | ✅ Resolved |
| LOW | 2 | ✅ Accepted |

### Key Issues Addressed

1. **Contradictory validator location** → Resolved: `scripts/validation/` (not nWave/validators/)
2. **Existing nWave/validators/ files ignored** → Resolved: Review and consolidate existing files
3. **No rollback plan** → Added backup branch + incremental commits
4. **Underestimated shell→Python time** → Updated to 2-4 hours
5. **Missing scripts not addressed** → Added audit step in Phase 0
6. **CI/CD integration gaps** → Added path update verification
7. **Import path dependencies** → Added grep for old paths before commit

### Decision Updates from Review

- **Validator location**: Changed from `nWave/validators/` to `scripts/validation/`
- **Existing validators**: Will be reviewed and consolidated (not ignored)
- **5d-wave→nWave renaming**: Handled as SEPARATE task after this consolidation
- **Git history**: All moves use `git mv` to preserve history

---

## Executive Summary

Your scripts directory has grown organically to 22 files (15 standalone + 7 hooks) with mixed purposes. While functional, the structure has inefficiencies:

- **Platform Issues**: Shell scripts work only on Unix/Mac; not portable to Windows
- **Organizational Issues**: Unclear separation between CLI tools, validation, and hooks
- **Maintenance Issues**: Duplicate validators (compliance v1 & v2), orphaned hooks, one-time migrations
- **Documentation Issues**: No README explaining script purposes or when to use them

**This plan** reorganizes scripts by function, converts to Python for cross-platform compatibility, eliminates duplicates, and creates clear structure.

---

## Decision Summary (Your Choices)

### ✅ Decision 1: Adversarial Testing Scripts
**Choice**: Archive both scripts (not useful for now)
**Rationale**:
- Require active LLM invocation (can't be automated in CI/CD)
- Claude Code has embedded safety/compliance
- 2,000+ lines of code for low-value functionality

**Action**:
- Archive `/scripts/run-adversarial-tests.py` → `/scripts/archive/`
- Archive `/scripts/execute-adversarial-tests.py` → `/scripts/archive/`
- Document: "Preserved for future security testing if needed"

**Result**: Cleaner scripts directory; can resurrect if security testing becomes priority

---

### ✅ Decision 2: Structure Validation Strategy (REVISED)
**Choice**: Create modular Python validators in `scripts/validation/`
**Rationale**:
- Fast, deterministic static analysis (no LLM needed)
- Should run on every commit as quality gate
- Python ensures cross-platform compatibility
- Modular design allows separate validators for agents, commands, steps, etc.
- **REVISED**: Validators in `scripts/validation/` (not nWave/validators/) to keep all scripts together

**Implementation**:
```
scripts/validation/
├── __init__.py
├── validate_agents.py       (validates agents vs AGENT_TEMPLATE.yaml)
├── validate_commands.py      (validates commands vs COMMAND_TEMPLATE.yaml)
├── validate_steps.py         (validates step files)
├── validate_formatter_env.py (checks ruff/mypy availability)
├── validate_readme_index.py  (ensures README.md index matches actual files)
└── coordinator.py            (runs all validators)
```

**Existing nWave/validators/ handling**:
- Review existing files: `command_template_validator.py`, `release_packager.py`, `release_validation.py`
- Consolidate overlapping functionality
- Move non-overlapping validators to `scripts/validation/`

**Integration**:
- Create `scripts/hooks/validate-structure.py` wrapper
- Add to `.pre-commit-config.yaml` as Phase 4 quality gate
- Blocks commit if validation fails

**Result**: Automatic quality gates on every commit; consistent file formatting

---

### ✅ Decision 3: Compliance Validators
**Choice**: Merge validate-agent-compliance.py + v2
**Rationale**:
- v2 may have improvements over v1
- Merging ensures best of both
- Single source of truth for agent validation

**Action**:
- Review both files for differences
- Merge best features into single `validate_agents.py`
- Archive `validate-agent-compliance-v2.py`
- Update any code referencing the old files

**Result**: Single, unified agent compliance validator

---

### ✅ Decision 4: Formatter Availability Hooks
**Choice**: Convert to Python, move to validation folder
**Rationale**:
- Python ensures cross-platform compatibility
- Belongs in validation folder with other validators
- Can be more intelligent about installation help

**Implementation**:
- Delete shell versions
- Create `scripts/validation/validate_formatter_env.py`
- Wraps as `scripts/hooks/validate-structure.py` (coordinates all validators)

**Result**: Cross-platform formatter validation; organized with other validators

---

### ✅ Decision 5: Orphaned Conflict Detection Hook
**Choice**: Archive (not applicable to current architecture)
**Rationale**:
- References `nWave/catalogs/` directory that doesn't exist
- Project evolved to embedded documentation (no separate catalogs)
- No references in codebase except in the hook itself

**Action**:
- Move to `/scripts/archive/agent-catalog-conflict-detection.sh`
- Document: "From earlier design phase; not used in current architecture"

**Alternative Action - NEW SCRIPT**:
- Create Python script: `validate_readme_index.py`
- Purpose: Ensure README.md documentation index matches actual files
- Runs as pre-commit hook (Phase 4)
- Automatically detects new agents, commands, features
- Warns if README index is stale

**Result**: Archive old hook; replace with more useful README validation

---

### ✅ Decision 6: One-Time Migration Scripts
**Choice**: Delete (no longer needed)
**Rationale**:
- `create-reviewer-agents.py` - Agent generation complete
- `migrate_step_files.py` - Data migration complete
- No ongoing use; clutter the codebase

**Action**:
- Delete `/scripts/create-reviewer-agents.py`
- Delete `/nWave/scripts/migrate_step_files.py`

**Result**: Cleaner codebase; remove technical debt

---

### ✅ Decision 7: Installation Scripts
**Choice**: Convert to Python + better folder structure
**Rationale**:
- Shell scripts not portable to Windows
- Python provides cross-platform compatibility
- Grouped organization makes purpose clear

**Implementation**:
```
scripts/install/
├── __init__.py
├── install.py               (installs nWave framework)
├── uninstall.py             (removes framework)
├── update.py                (orchestrates update pipeline)
└── backup.py                (manages backups during install)
```

**Conversion Notes**:
- Preserve all functionality from shell scripts
- Use Python's `shutil`, `subprocess`, `pathlib` for OS operations
- Maintain same CLI interface
- Test on Windows, Mac, Linux

**Result**: Cross-platform installation tools; organized in install/ subdirectory

---

### ✅ Decision 8: nWave Framework Scripts
**Choice**: Keep only active scripts, archive others, better folder structure
**Rationale**:
- `release_package.py` - Actively used for Phase 5 releases
- `validate_tdd_phases_ci.py` - Actively used in CI/CD (multi-platform)
- `install_nwave_target_hooks.py` - Unclear usage; move or archive

**Implementation**:
```
nWave/scripts/ → scripts/framework/
├── release_package.py       (release orchestration - KEEP, MOVE)
├── validate_tdd_phases_ci.py (CI/CD validation - KEEP, MOVE)
└── [archive/install_nwave_target_hooks.py if not actively used]
```

**Rationale for move**:
- Keeps all scripts in `/scripts/` instead of scattered in nWave/
- Easier to find and maintain
- Clearer that they're operational scripts, not framework code

**Result**: Consolidated script organization; clearer separation of framework code vs. operational tools

---

## Final Scripts Structure

```
scripts/
├── README.md                          ← NEW: Script documentation and index
│
├── install/                           ← Python-based installation tools
│   ├── __init__.py
│   ├── install.py                     (CONVERTED from install-nwave.sh)
│   ├── uninstall.py                   (CONVERTED from uninstall-nwave.sh)
│   ├── update.py                      (CONVERTED from update-nwave.sh)
│   └── backup.py                      (from enhanced-backup-system.sh)
│
├── validation/                        ← Python-based validators
│   ├── __init__.py
│   ├── validate_agents.py             (MERGED compliance v1 + v2)
│   ├── validate_commands.py           (validate commands vs template)
│   ├── validate_steps.py              (validate step files)
│   ├── validate_formatter_env.py      (check formatter availability)
│   ├── validate_readme_index.py       (NEW: validate README index)
│   └── coordinator.py                 (runs all validators)
│
├── hooks/                             ← Pre-commit hooks (Python-based)
│   ├── version-bump.sh                (KEEP: auto version increment)
│   ├── validate-structure.py          (NEW: coordinator for all Python validators)
│   ├── validate-tests.sh              (KEEP: pytest wrapper)
│   ├── validate-docs.sh               (KEEP: doc version validation)
│   └── detect-conflicts.sh            (KEEP: agent/command coupling detection)
│
├── framework/                         ← nWave framework operations
│   ├── release_package.py             (MOVED from nWave/scripts/)
│   └── validate_tdd_phases_ci.py      (MOVED from nWave/scripts/)
│
├── build-ide-bundle.sh                (KEEP: IDE bundle build)
│
└── archive/                           ← Historical and unused scripts
    ├── run-adversarial-tests.py       (archived: LLM-based testing)
    ├── execute-adversarial-tests.py   (archived: LLM-based testing)
    ├── agent-catalog-conflict-detection.sh (archived: outdated design)
    ├── validate-agent-compliance-v2.py (archived: merged into v1)
    └── README.md                      (explains what's archived and why)
```

---

## Execution Plan

### Phase 0: Pre-Migration Verification & Safety Setup
**Time**: 15 minutes
**Risk**: NONE (read-only operations + backup creation)

#### Phase 0A: Create Backup Branch
```bash
# Create backup branch for rollback capability
git checkout -b scripts-consolidation-backup
git checkout -  # Return to original branch

# Verify backup exists
git branch | grep scripts-consolidation-backup
```

#### Phase 0B: Audit Existing Scripts and Validators
```bash
# Document all existing scripts
find scripts/ -type f -name "*.py" -o -name "*.sh" | sort > /tmp/scripts-pre-migration.txt
find nWave/validators/ -type f -name "*.py" | sort >> /tmp/scripts-pre-migration.txt
find nWave/scripts/ -type f -name "*.py" | sort >> /tmp/scripts-pre-migration.txt

# Count files
echo "Pre-migration script count: $(wc -l < /tmp/scripts-pre-migration.txt)"

# Review existing nWave/validators/ contents
ls -la nWave/validators/
```

#### Phase 0C: Find Import Path References
```bash
# Find all references to paths that will change
grep -r "nWave/scripts" --include="*.py" --include="*.yaml" --include="*.md" . > /tmp/import-refs-to-update.txt
grep -r "nWave.scripts" --include="*.py" . >> /tmp/import-refs-to-update.txt

# Review references that need updating
cat /tmp/import-refs-to-update.txt
```

**Verification**: All safety measures in place before proceeding

---

### Phase 1: Create validation module structure (REVISED)
**Time**: 20 minutes
**Location**: `scripts/validation/` (NOT nWave/validators/)

**Actions**:
```bash
# Create validation directory
mkdir -p scripts/validation

# Create __init__.py
touch scripts/validation/__init__.py
```

**Files to create**:
- `scripts/validation/__init__.py` (Python package)
- `scripts/validation/validate_agents.py` (merged compliance v1 + v2)
- `scripts/validation/validate_commands.py`
- `scripts/validation/validate_steps.py`
- `scripts/validation/validate_formatter_env.py` (converted from shell)
- `scripts/validation/validate_readme_index.py` (NEW - deterministic README validation)
- `scripts/validation/coordinator.py` (orchestrates all validators)

**Consolidation of existing nWave/validators/**:
- Review `command_template_validator.py` → merge into `validate_commands.py`
- Review `release_packager.py` → move to `scripts/framework/`
- Review `release_validation.py` → merge into appropriate validator

```bash
# INCREMENTAL COMMIT (rollback point)
git add scripts/validation/
git commit -m "feat(scripts): create validation module structure"
```

**Risk**: LOW (creating new modules, no dependencies yet)

---

### Phase 2: Move framework scripts
**Time**: 15 minutes
**Actions**:
```bash
# Create framework directory
mkdir -p scripts/framework

# Move using git mv to preserve history
git mv nWave/scripts/release_package.py scripts/framework/
git mv nWave/scripts/validate_tdd_phases_ci.py scripts/framework/

# Move release_packager from validators (if not consolidated)
git mv nWave/validators/release_packager.py scripts/framework/
git mv nWave/validators/release_validation.py scripts/framework/

# Archive unclear scripts
mkdir -p scripts/archive
git mv nWave/scripts/install_nwave_target_hooks.py scripts/archive/

# Remove empty directories
rmdir nWave/scripts/ 2>/dev/null || true

# INCREMENTAL COMMIT (rollback point)
git commit -m "refactor(scripts): move framework scripts to scripts/framework/"
```

**Risk**: LOW (just moving files, updating import paths)

---

### Phase 2B: Update Import Paths
**Time**: 10 minutes
**Actions**:
```bash
# Update any imports referencing old paths
# Search for files that need updating
grep -r "from nWave.scripts" --include="*.py" .
grep -r "import nWave.scripts" --include="*.py" .

# Update imports (example - verify before running)
# find . -name "*.py" -exec sed -i 's/from nWave.scripts/from scripts.framework/g' {} \;

# INCREMENTAL COMMIT (rollback point)
git commit -m "refactor(scripts): update import paths for moved scripts"
```

**Risk**: MEDIUM (requires careful testing after path updates)

---

### Phase 3: Create installation Python scripts (REVISED TIME)
**Time**: 2-4 hours (revised from 30 minutes)
**Actions**:
```bash
# Create install directory
mkdir -p scripts/install
touch scripts/install/__init__.py
```

**Conversion tasks**:
- Convert `install-nwave.sh` (586 lines) → `scripts/install/install.py`
- Convert `uninstall-nwave.sh` → `scripts/install/uninstall.py`
- Convert `update-nwave.sh` → `scripts/install/update.py`
- Integrate backup functionality from `enhanced-backup-system.sh`

**Cross-platform considerations**:
- Use `pathlib` for all path operations
- Use `colorama` for Windows terminal colors
- Use `subprocess` with `shell=False` for security
- Test on Windows, Mac, Linux before committing

```bash
# INCREMENTAL COMMIT (rollback point)
git add scripts/install/
git commit -m "feat(scripts): convert installation scripts to Python"
```

**Risk**: MEDIUM-HIGH (involves file system operations across platforms; test thoroughly)

---

### Phase 4: Create pre-commit hook coordinator
**Time**: 15 minutes
**Actions**:
```bash
# Create the coordinator hook
touch scripts/hooks/validate-structure.py
```

- Create `scripts/hooks/validate-structure.py`
- Coordinates all Python validators in `scripts/validation/`
- Integrates with `.pre-commit-config.yaml`
- Outputs clear pass/fail results

```bash
# INCREMENTAL COMMIT (rollback point)
git add scripts/hooks/validate-structure.py
git commit -m "feat(scripts): add pre-commit validation coordinator"
```

**Risk**: LOW (orchestration of existing validators)

---

### Phase 5: Archive outdated scripts
**Time**: 10 minutes
**Actions**:
```bash
# Create archive directory (if not already created)
mkdir -p scripts/archive

# Archive adversarial testing scripts (git mv for history)
git mv scripts/run-adversarial-tests.py scripts/archive/
git mv scripts/execute-adversarial-tests.py scripts/archive/

# Archive orphaned hooks
git mv scripts/hooks/agent-catalog-conflict-detection.sh scripts/archive/

# Archive merged compliance validator
git mv scripts/validate-agent-compliance-v2.py scripts/archive/

# INCREMENTAL COMMIT (rollback point)
git commit -m "chore(scripts): archive outdated and merged scripts"
```

- Create `scripts/archive/README.md` explaining each archived script

**Risk**: NONE (just reorganizing)

---

### Phase 6: Create scripts documentation
**Time**: 15 minutes
**Actions**:
- Create `scripts/README.md` with:
  - Overview of each script/module
  - When to use each
  - Dependencies and setup
  - How to run validation locally
  - Integration with CI/CD
- Create `scripts/archive/README.md` explaining archived scripts

**Risk**: NONE (documentation only)

---

### Phase 7: Update .pre-commit-config.yaml
**Time**: 10 minutes
**Actions**:
- Update validator hook registration
- Change from individual shell hooks to Python coordinator
- Ensure Phase 4 runs all Python validators
- Test that pre-commit hooks work

**Risk**: LOW (testing required to ensure hooks still fire)

---

### Phase 8: Git cleanup and commit
**Time**: 10 minutes
**Actions**:
- Delete old shell installation scripts
- Delete old adversarial testing scripts
- Delete one-time migration scripts
- Commit all changes with clear message

**Risk**: LOW (deletion after successfully moving)

---

## Benefits Summary

| Aspect | Before | After | Benefit |
|--------|--------|-------|---------|
| **Platform Support** | Unix/Mac only (shell) | Windows/Mac/Linux (Python) | Works everywhere |
| **Organization** | Scattered across scripts/ and nWave/scripts/ | Organized by function (install/, validation/, hooks/, framework/) | Easy to find, maintain |
| **Validation** | Manual running of separate scripts | Automatic pre-commit hooks | Catches issues early |
| **Duplicates** | 3 duplicate sets (adversarial, compliance, formatter) | Single versions only | Reduced maintenance |
| **Documentation** | Unclear which script does what | README.md explains all scripts | Easier onboarding |
| **Reusability** | Monolithic scripts | Modular Python validators | Reusable in CI/CD, other projects |

---

## Rollback Procedure

If something goes wrong during execution:

```bash
# Option 1: Revert specific phase commit
git log --oneline -10  # Find the problematic commit
git revert <commit-hash>

# Option 2: Full rollback to backup branch
git checkout scripts-consolidation-backup
git branch -D master  # or your working branch
git checkout -b master  # Recreate from backup

# Option 3: Revert all consolidation commits
git reset --hard HEAD~N  # Where N = number of consolidation commits
```

---

## Timeline (REVISED)

| Phase | Task | Time | Total |
|-------|------|------|-------|
| 0 | Pre-migration verification (backup, audit, import refs) | 15 min | 15 min |
| 1 | Create validation modules in scripts/validation/ | 20 min | 35 min |
| 2 | Move framework scripts + commit | 15 min | 50 min |
| 2B | Update import paths + commit | 10 min | 60 min |
| 3 | Create installation Python scripts | **2-4 hours** | 3-5 hours |
| 4 | Create pre-commit coordinator | 15 min | 3.5-5.5 hours |
| 5 | Archive outdated scripts + commit | 10 min | 3.5-5.5 hours |
| 6 | Create documentation | 15 min | 3.5-5.5 hours |
| 7 | Update pre-commit config + commit | 10 min | 3.5-5.5 hours |
| 8 | Final verification + cleanup | 15 min | 3.5-5.5 hours |
| **TOTAL** | **Complete scripts reorganization** | **3.5-5.5 hours** | **Ready to execute** |

**Note**: Phase 3 (shell→Python conversion) is the largest effort. Consider splitting into sub-phases if needed.

---

## Success Criteria (with verification commands)

✅ After this consolidation:

- [ ] No duplicate validators (compliance, formatter checking)
  ```bash
  # Should find only one compliance validator
  find scripts/ -name "*compliance*" -o -name "*formatter*" | wc -l
  ```

- [ ] All validation scripts are Python (cross-platform compatible)
  ```bash
  # Should return only .py files in validation/
  ls scripts/validation/*.py && echo "PASS: All Python validators"
  ```

- [ ] Scripts organized by function
  ```bash
  [ -d "scripts/install" ] && [ -d "scripts/validation" ] && \
  [ -d "scripts/hooks" ] && [ -d "scripts/framework" ] && echo "PASS: Structure correct"
  ```

- [ ] Pre-commit hooks work
  ```bash
  pre-commit run --all-files && echo "PASS: Pre-commit hooks work"
  ```

- [ ] Installation scripts work (test on each platform)
  ```bash
  python scripts/install/install.py --dry-run && echo "PASS: Install script runs"
  ```

- [ ] Adversarial testing scripts archived
  ```bash
  [ -f "scripts/archive/run-adversarial-tests.py" ] && echo "PASS: Scripts archived"
  ```

- [ ] No old import paths remain
  ```bash
  grep -r "nWave.scripts" --include="*.py" . || echo "PASS: No old imports"
  grep -r "nWave/scripts" --include="*.py" . || echo "PASS: No old paths"
  ```

- [ ] Git history preserved for moved files
  ```bash
  git log --follow --oneline scripts/framework/release_package.py | head -5
  ```

---

## Risks & Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Platform-specific issues in Python conversion | MEDIUM | Test install scripts on Windows, Mac, Linux before committing |
| Pre-commit hook breakage | MEDIUM | Test hooks after each phase; incremental commits allow rollback |
| Missed dependencies in validators | LOW | Review imports and test validators in isolation |
| Broken paths after moving scripts | LOW | Phase 0C audits references; Phase 2B updates them |
| Partial failure mid-execution | LOW | Backup branch + incremental commits provide rollback points |
| Import path errors | MEDIUM | Grep for old paths before final commit |

---

## Ready for Execution?

This plan has been **reviewed and revised** based on adversarial review findings:
- ✅ Pre-migration verification phase added (backup, audit, import refs)
- ✅ Validator location resolved: `scripts/validation/` (not nWave/validators/)
- ✅ Existing validators will be reviewed and consolidated
- ✅ All moves use `git mv` for history preservation
- ✅ Incremental commits after each phase for rollback capability
- ✅ Time estimate revised: 3.5-5.5 hours (was 2 hours)
- ✅ Measurable success criteria with verification commands

**Execution order**: This scripts consolidation runs SECOND, after docs consolidation.

**5d-wave→nWave renaming**: Handled as SEPARATE task after both consolidations complete.

---

## Appendix: Key New Scripts

### validate_readme_index.py
Validates that docs/README.md index is up-to-date with actual documentation files.

**Purpose**: Deterministically ensure README.md stays in sync with reality

**What it does**:
- Scans actual files in docs/
- Parses README.md index section
- Compares expected vs. actual
- Warns if index is stale
- Can auto-update README with --fix flag

**Runs**: As pre-commit hook (Phase 4)

**Benefit**: README.md index never gets out of sync; users always see correct navigation

### validate_structure.py (Pre-commit coordinator)
Orchestrates all Python validators.

**Purpose**: Single entry point for all structure validation

**What it does**:
- Runs `validate_agents.py`
- Runs `validate_commands.py`
- Runs `validate_steps.py`
- Runs `validate_formatter_env.py`
- Runs `validate_readme_index.py`
- Aggregates results
- Provides clear pass/fail output

**Runs**: As pre-commit hook (Phase 4)

**Benefits**:
- All validation runs together
- Clear which validation failed
- Easy to add new validators
- Single pre-commit hook registration
