# Branch Reuse Plan: feat/claude-code-plugin

**Date**: 2026-02-27
**Author**: Morgan (Solution Architect)
**Source branch**: `feat/claude-code-plugin` (11 commits, 67 changed files)
**Target branch**: `open-code-support`
**Status**: Analysis complete -- requires git commands for execution

---

## Important: Tool Limitations

This analysis was performed using file inspection (Read/Glob/Grep) without access to `git log`, `git diff`, or `git show` commands. The commit-level analysis below is based on what the architecture design document and codebase references tell us about the branch. **Before executing any import strategy, run the git commands in the Execution Checklist (Section 7) to get exact commit hashes and confirm file contents.**

---

## 1. Branch Content Summary

### What feat/claude-code-plugin contains (from architecture-design.md Prior Art section)

| Component | File/Location | Lines | Purpose |
|-----------|--------------|-------|---------|
| sync_to_plugin.py | `scripts/sync_to_plugin.py` | 409 | Main build script -- copies agents/skills/commands, embeds DES, generates hooks.json |
| YAML-to-JSON migration | Multiple `src/des/` and `tests/des/` files | ~500+ | Eliminates pyyaml dependency for plugin |
| E2E validate.py | `tests/e2e/plugin-install/validate.py` | ~100 | Validates plugin directory structure |
| E2E Dockerfile | `tests/e2e/plugin-install/Dockerfile` | ~30 | Containerized install test |
| E2E runner | `tests/e2e/plugin-install/run.py` | ~50 | Orchestrates E2E test |
| Hook JSON generation | Inside sync_to_plugin.py | - | hooks.json template with `${CLAUDE_PLUGIN_ROOT}` |
| Skills-to-SKILL.md | Inside sync_to_plugin.py | - | Wraps each skill file into SKILL.md directory |
| Plugin manifest | Generated | - | plugin.json with name="nw" |

### What open-code-support contains (current branch)

| Component | File/Location | Purpose |
|-----------|--------------|---------|
| Architecture design | `docs/feature/nwave-plugin/design/architecture-design.md` | Full architecture doc with roadmap |
| Component boundaries | `docs/feature/nwave-plugin/design/component-boundaries.md` | Source-to-plugin mapping |
| Technology stack | `docs/feature/nwave-plugin/design/technology-stack.md` | Zero-dependency rationale |
| Architecture review | `docs/feature/nwave-plugin/design/architecture-review.md` | Atlas review (conditionally approved) |
| ADR-001 | `docs/adrs/ADR-001-plugin-marketplace-distribution.md` | Plugin as primary distribution |
| ADR-002 | `docs/adrs/ADR-002-des-hooks-in-plugin.md` | DES bundled self-contained |
| ADR-003 | `docs/adrs/ADR-003-skill-structure-mapping.md` | Skills copy strategy |
| JTBD docs | Various `docs/` | Jobs-to-be-done research |

---

## 2. YAML-to-JSON Migration Scope

This is the highest-value, most self-contained work from the branch. The current `master` branch has **6 files** using `import yaml`:

### Files requiring migration

| File | YAML Usage | Migration Complexity |
|------|-----------|---------------------|
| `src/des/adapters/driven/hooks/yaml_execution_log_reader.py` | `yaml.safe_load` for execution-log.yaml | **HIGH** -- core DES runtime path, needs new JSON reader adapter |
| `src/des/application/subagent_stop_service.py` | `yaml.safe_load` + `yaml.dump` for execution-log.yaml | **HIGH** -- reads and writes YAML execution log |
| `src/des/domain/roadmap_schema.py` | `yaml.safe_load` for roadmap-schema.yaml | **MEDIUM** -- loads schema definition file |
| `src/des/cli/roadmap.py` | `yaml.dump` + `yaml.safe_load` for roadmap CLI | **MEDIUM** -- CLI tool, generates/reads YAML roadmaps |
| `src/des/cli/log_phase.py` | `yaml.safe_load` + `yaml.dump` for execution-log.yaml | **MEDIUM** -- CLI tool appends phases |
| `src/des/cli/verify_deliver_integrity.py` | `yaml.safe_load` for both roadmap.yaml and execution-log.yaml | **LOW** -- verification CLI |

### Template files requiring conversion

| Current (YAML) | Target (JSON) |
|----------------|---------------|
| `nWave/templates/roadmap-schema.yaml` | `nWave/templates/roadmap-schema.json` |
| `nWave/templates/execution-log-template.yaml` | `nWave/templates/execution-log-template.json` |

### Files NOT needing migration (CLI-only, not in DES runtime hot path)

The CLI files (`roadmap.py`, `log_phase.py`, `verify_deliver_integrity.py`) are development tools, not plugin runtime. They can retain YAML support since they run in the dev environment where pyyaml is available. **Only the hook execution path must be YAML-free.**

### Critical runtime path (MUST migrate)

1. `yaml_execution_log_reader.py` -- replace with JSON reader
2. `subagent_stop_service.py` -- use JSON for execution log writes
3. `roadmap_schema.py` -- load from JSON instead of YAML

---

## 3. Commit Categorization (Projected)

Based on the branch's known content, the 11 commits likely decompose as follows. **Run `git log --oneline feat/claude-code-plugin --not master` for exact hashes.**

### Category: CHERRY-PICK (self-contained, no expected conflicts)

| # | Likely Commit Description | Rationale |
|---|--------------------------|-----------|
| 1 | YAML-to-JSON migration for execution log reader | Self-contained adapter swap. New `json_execution_log_reader.py` alongside existing YAML reader. Port interface unchanged. |
| 2 | YAML-to-JSON migration for roadmap schema | Self-contained. Replace YAML loader with JSON loader in `roadmap_schema.py`. |
| 3 | Execution log template YAML-to-JSON | Template file conversion. No code conflicts. |
| 4 | Roadmap schema YAML-to-JSON | Template file conversion. No code conflicts. |

**Estimated**: 3-5 commits in YAML-to-JSON migration, all cherry-pickable.

### Category: ADAPT (useful code, needs modification)

| # | Likely Commit Description | Adaptation Needed |
|---|--------------------------|-------------------|
| 5 | sync_to_plugin.py build script | **Rename** to `build_plugin.py`. **Refactor** from procedural to FP pipeline (our design requires functional paradigm). Core logic (directory mapping, import rewriting, hooks.json generation) is reusable. |
| 6 | E2E plugin validation | Adapt paths: `lib/des/` confirmed matching. Verify plugin structure expectations match our architecture. |
| 7 | E2E Dockerfile + runner | Minor path adjustments if any. Mostly reusable as-is. |

### Category: SKIP (not needed or conflicts with design)

| # | Likely Commit Description | Skip Rationale |
|---|--------------------------|----------------|
| 8 | Skills-to-SKILL.md conversion | ADR-003 on current branch decided **NO SKILL.md rename**. Branch wraps skills in SKILL.md directories; our design copies skills as-is. |
| 9 | Any settings.json / systemMessage changes | Prior art fix for `systemMessage` not supported -- already documented in our architecture design. May be obsolete. |

### Category: MERGE (interdependent, take as group)

| # | Likely Commit Description | Rationale |
|---|--------------------------|-----------|
| 10-11 | Test updates for JSON migration | Must come with corresponding YAML-to-JSON commits. Cannot cherry-pick independently. |

---

## 4. Recommended Import Strategy

### Phase A: Cherry-pick YAML-to-JSON migration (Priority 1)

**Why first**: This is a prerequisite for zero-dependency plugin (eliminates pyyaml). It is also the largest body of work on the branch and the most self-contained.

```bash
# Step 1: Identify the YAML-to-JSON commits
git log --oneline feat/claude-code-plugin --not master | grep -i "yaml\|json\|migration"

# Step 2: Cherry-pick in chronological order
git cherry-pick <hash1> <hash2> ...

# Step 3: Run tests to verify
pipenv run pytest tests/des/ -x
```

**Conflicts to watch**:
- `subagent_stop_service.py` -- this file is large (361+ lines) and may have diverged since the branch was created
- `claude_code_hook_adapter.py` -- imports `YamlExecutionLogReader`; migration commit should swap to JSON reader
- `conftest.py` or test fixtures that create YAML execution logs

### Phase B: Selective file copy for build script (Priority 2)

**Do NOT cherry-pick** the `sync_to_plugin.py` commit. Instead:

1. `git show feat/claude-code-plugin:scripts/sync_to_plugin.py > /tmp/sync_to_plugin_reference.py`
2. Use as **reference implementation** for `build_plugin.py`
3. Extract reusable logic:
   - Directory mapping configuration (source paths to plugin paths)
   - hooks.json template generation
   - DES import rewriting (already in `build_dist.py`)
   - plugin.json metadata generation
4. Rewrite in FP style per architecture design

**Reusable from sync_to_plugin.py** (estimated):
- ~60% of logic is reusable (directory copies, import rewriting, hooks generation)
- ~20% needs adaptation (SKILL.md wrapping -- skip per ADR-003)
- ~20% is scaffold/CLI that will be rewritten

### Phase C: Copy E2E tests (Priority 3)

```bash
# Copy E2E test files directly
git show feat/claude-code-plugin:tests/e2e/plugin-install/validate.py > tests/e2e/plugin-install/validate.py
git show feat/claude-code-plugin:tests/e2e/plugin-install/Dockerfile > tests/e2e/plugin-install/Dockerfile
git show feat/claude-code-plugin:tests/e2e/plugin-install/run.py > tests/e2e/plugin-install/run.py
```

**Review before committing**:
- validate.py references to `lib/des/` (should match our architecture)
- Dockerfile base image and Python version
- Any hardcoded paths or assumptions about plugin structure

---

## 5. Files: As-Is vs Needs Adaptation

### Can use as-is (after cherry-pick/copy)

| File | Confidence | Notes |
|------|-----------|-------|
| JSON execution log reader (new file) | HIGH | New adapter, no conflicts |
| JSON roadmap schema loader changes | HIGH | Swaps YAML for JSON in existing loader |
| `roadmap-schema.json` (new template) | HIGH | JSON version of existing YAML |
| `execution-log-template.json` (new template) | HIGH | JSON version of existing YAML |
| Test fixtures for JSON formats | HIGH | New test files |
| `tests/e2e/plugin-install/Dockerfile` | MEDIUM | May need Python version update |

### Needs adaptation

| File | Change Required | Effort |
|------|----------------|--------|
| `sync_to_plugin.py` -> `build_plugin.py` | Rename + FP refactor + remove SKILL.md wrapping + align with architecture design | MEDIUM (2-3 hours reference, but rewritten by crafter) |
| `tests/e2e/plugin-install/validate.py` | Verify path expectations match architecture | LOW |
| `tests/e2e/plugin-install/run.py` | Verify runner assumptions | LOW |
| `subagent_stop_service.py` | May have merge conflicts if both branches modified | MEDIUM |

### Skip entirely

| File | Reason |
|------|--------|
| Any SKILL.md wrapping logic | ADR-003 decided against this approach |
| `systemMessage` removal fixes | Already documented as prior art, no code needed |

---

## 6. Conflict Risk Assessment

### High risk (likely conflicts)

| File | Why | Mitigation |
|------|-----|-----------|
| `src/des/application/subagent_stop_service.py` | Both branches likely modified. 361+ lines, YAML read/write in lines 277-351. | Cherry-pick JSON migration, resolve conflicts manually in the YAML->JSON section. |
| `src/des/adapters/drivers/hooks/claude_code_hook_adapter.py` | Import of `YamlExecutionLogReader` on line 44 must change to JSON reader. Both branches may have modified hook adapter. | Apply import change manually if cherry-pick conflicts. |

### Medium risk (possible conflicts)

| File | Why | Mitigation |
|------|-----|-----------|
| `tests/des/` test files | Test fixtures may have YAML-format execution logs that need JSON conversion. | Run full test suite after cherry-pick. |
| `pyproject.toml` | If branch modified dependencies (removed pyyaml). | Do NOT remove pyyaml from pyproject.toml yet -- CLI tools and dev environment still need it. Only the plugin runtime must be YAML-free. |

### Low risk (no expected conflicts)

| File | Why |
|------|-----|
| `docs/` files on current branch | Branch has no `docs/feature/nwave-plugin/` files (that is our branch only) |
| `nWave/templates/` new JSON files | New files, no overlap |
| `tests/e2e/plugin-install/` | New directory, no overlap |

---

## 7. Execution Checklist

Run these commands before executing the import strategy:

```bash
# 1. List all branch commits (get exact hashes)
git log --oneline feat/claude-code-plugin --not master

# 2. Check file change scope
git diff --stat master...feat/claude-code-plugin

# 3. Identify YAML-to-JSON specific changes
git diff --stat master...feat/claude-code-plugin -- src/des/ tests/des/

# 4. Check merge base (how far branches diverged)
git merge-base open-code-support feat/claude-code-plugin

# 5. Check our branch commits (identify potential conflicts)
git log --oneline open-code-support --not master

# 6. Read the build script from the branch
git show feat/claude-code-plugin:scripts/sync_to_plugin.py | head -50

# 7. Read E2E validation
git show feat/claude-code-plugin:tests/e2e/plugin-install/validate.py

# 8. Dry-run cherry-pick to detect conflicts
git cherry-pick --no-commit <yaml-to-json-hash>
git diff --cached --stat
git cherry-pick --abort
```

---

## 8. Delta: What Remains After Import

After importing from `feat/claude-code-plugin`, the following work remains for the roadmap:

### Already done (from branch import)

- [x] YAML-to-JSON migration for DES runtime (execution log reader, roadmap schema)
- [x] E2E validation test structure
- [x] E2E containerized test infrastructure
- [x] hooks.json template with `${CLAUDE_PLUGIN_ROOT}`
- [x] DES import rewriting proven pattern
- [x] Plugin name = "nw" confirmed working
- [x] `systemMessage` not supported -- known and documented

### Still needed (roadmap steps)

| Roadmap Step | Status After Import | Work Remaining |
|-------------|-------------------|----------------|
| **01-01**: Plugin assembler with metadata generation | ~40% done (sync_to_plugin.py as reference) | Rewrite as `build_plugin.py` in FP style. Remove SKILL.md wrapping. Add plugin.json generation from pyproject.toml. |
| **01-02**: DES bundle with hooks generation | ~60% done (import rewriting + hooks template exist) | Integrate into `build_plugin.py`. Adapt for `${CLAUDE_PLUGIN_ROOT}` paths. Bundle DES templates. |
| **01-03**: Plugin validation and build verification | ~50% done (validate.py exists) | Integrate validation into build pipeline. Add schema validation for hooks.json. |
| **02-01**: Release pipeline extension | 0% done | New CI/CD job in release.yml |
| **02-02**: Coexistence verification | 0% done | E2E test for plugin + custom installer coexistence |

### Net effort reduction

- **Without branch import**: ~5 full roadmap steps, estimated 3-4 days
- **With branch import**: ~3 effective steps (01-01 reduced to adaptation, 01-02 and 01-03 partially done)
- **Estimated savings**: ~40% effort reduction, consistent with architecture-design.md projection

---

## 9. Recommendation

**Import strategy**: Hybrid (cherry-pick + selective copy)

1. **Cherry-pick** all YAML-to-JSON migration commits first (self-contained, high value, prerequisite)
2. **Selective copy** the E2E test files (Dockerfile, validate.py, run.py)
3. **Reference only** for sync_to_plugin.py (use as input to write new `build_plugin.py` in FP style)
4. **Skip** SKILL.md wrapping logic entirely (conflicts with ADR-003)

**Do NOT merge the entire branch** -- it contains the SKILL.md wrapping decision that contradicts our ADR-003, and the procedural build script that contradicts our FP paradigm decision. Cherry-pick + selective copy gives us the value without the conflicts.
