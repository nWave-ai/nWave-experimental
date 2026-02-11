# Naming Cleanup Plan

**Status**: Ready for Review
**Created**: 2026-01-21
**Scope**: Remove legacy BMAD references and rename 5d-wave to nWave
**Execution Order**: This plan executes THIRD, after docs and scripts consolidations
**Impact**: Unified naming convention; removes predecessor framework references

---

## Executive Summary

After comprehensive codebase searches, two legacy naming conventions need cleanup:

1. **BMAD** (Business-driven Model-Agnostic Development) - The predecessor framework that inspired nWave
   - 4 references in 3 files
   - Decision: Delete entirely (no longer needed)

2. **5d-wave** - Old naming for the nWave framework
   - 42+ occurrences in 12 files
   - Decision: Rename to "nWave" throughout

**This plan** removes all legacy naming in a single, coordinated commit to maintain consistency.

---

## Naming Conventions Summary

### BMAD → DELETE

| Item | Current | Action |
|------|---------|--------|
| Knowledge base file | `nWave/data/methodologies/bmad-kb.md` | DELETE (561 lines) |
| Framework catalog | References in `framework-catalog.yaml` | REMOVE section |
| Release packager | Reference in documentation | UPDATE pointer |

**Rationale**: BMAD was the predecessor framework. Content is no longer relevant to nWave.

---

### 5d-wave → nWave

| Pattern | Replacement | Context |
|---------|-------------|---------|
| `5d-wave` | `nwave` | File names (kebab-case) |
| `5d_wave` | `nwave` | Python/YAML (snake_case) |
| `5D-Wave` | `nWave` | Documentation (title case) |
| `custom_5d_wave_*` | `custom_nwave_*` | YAML keys |
| `all_5d_wave_*` | `all_nwave_*` | YAML keys |

**Critical Files**:
- 2 files need renaming
- 10 files need content updates
- 2+ build artifacts auto-regenerate

---

## Detailed Execution Plan

### Phase 0: Pre-Migration Verification
**Time**: 10 minutes
**Risk**: NONE (read-only operations)

```bash
# Create backup branch
git checkout -b naming-cleanup-backup
git checkout -

# Verify backup exists
git branch | grep naming-cleanup-backup

# Find all affected files for verification
echo "=== BMAD References ==="
grep -r "bmad\|BMAD\|B-MAD" --include="*.md" --include="*.yaml" --include="*.py" . 2>/dev/null | grep -v build/ | grep -v ".git/"

echo "=== 5d-wave References ==="
grep -r "5d-wave\|5d_wave\|5D-Wave" --include="*.md" --include="*.yaml" --include="*.py" . 2>/dev/null | grep -v build/ | grep -v ".git/"

# Generate checksum for files we'll modify
find nWave/ tools/ docs/ -type f \( -name "*.md" -o -name "*.yaml" -o -name "*.py" \) -exec md5sum {} \; | sort > /tmp/naming-cleanup-checksums.txt
```

**Verification**: Backup created, all affected files identified

---

### Phase 1: Remove BMAD References
**Time**: 5 minutes
**Risk**: LOW (deleting predecessor framework references)

#### Step 1A: Delete BMAD Knowledge Base
```bash
# Delete the BMAD knowledge base file
git rm nWave/data/methodologies/bmad-kb.md

# Verify deletion
[ ! -f "nWave/data/methodologies/bmad-kb.md" ] && echo "✓ BMAD KB deleted"
```

#### Step 1B: Update Framework Catalog
```bash
# Edit framework-catalog.yaml to remove BMAD reference
# Lines ~259-264 need to be removed:
#   knowledge_base:
#     methodology_guide:
#       file: "data/bmad-kb.md"
#       description: "Comprehensive nWave methodology knowledge base"
#       content: "atdd_patterns_technology_integration_best_practices"

# This requires manual edit or sed command
```

#### Step 1C: Update Release Packager Documentation
```bash
# Edit release_packager.py line 352
# Change: - Framework guide: See `nWave/data/bmad-kb.md`
# To: - Framework guide: See `nWave/README.md`
```

**Verification**:
```bash
# Verify no BMAD references remain (should return empty)
grep -r "bmad\|BMAD\|B-MAD" --include="*.md" --include="*.yaml" --include="*.py" . 2>/dev/null | grep -v build/ | grep -v ".git/" || echo "✓ No BMAD references"
```

**Result**: BMAD completely removed from codebase

---

### Phase 2: Rename 5d-wave Files
**Time**: 5 minutes
**Risk**: LOW (using git mv preserves history)

```bash
# Rename checklist file
git mv nWave/checklists/5d-wave-methodology-checklist.md \
        nWave/checklists/nwave-methodology-checklist.md

# Rename template file
git mv nWave/templates/5d-wave-complete-methodology.yaml \
        nWave/templates/nwave-complete-methodology.yaml

# Verify renames
[ -f "nWave/checklists/nwave-methodology-checklist.md" ] && echo "✓ Checklist renamed"
[ -f "nWave/templates/nwave-complete-methodology.yaml" ] && echo "✓ Template renamed"
```

**Result**: Files renamed with git history preserved

---

### Phase 3: Update 5d-wave Content References
**Time**: 20 minutes
**Risk**: MEDIUM (content replacement requires verification)

#### Step 3A: Update nwave-methodology-checklist.md
```bash
# Update the renamed checklist file (24 occurrences)
# Replace "5D-Wave" → "nWave" throughout
# Replace "5d-wave" → "nwave" in technical references

# Example sed command (verify before running):
sed -i 's/5D-Wave/nWave/g' nWave/checklists/nwave-methodology-checklist.md
sed -i 's/5d-wave/nwave/g' nWave/checklists/nwave-methodology-checklist.md
```

#### Step 3B: Update Agent Definition Files
```bash
# Update visual-architect.md (lines 201, 486)
# Change: custom_5d_wave_diagrams → custom_nwave_diagrams
# Change: all_5d_wave_agents → all_nwave_agents
sed -i 's/custom_5d_wave_diagrams/custom_nwave_diagrams/g' nWave/agents/visual-architect.md
sed -i 's/all_5d_wave_agents/all_nwave_agents/g' nWave/agents/visual-architect.md

# Update visual-architect-reviewer.md (lines 202, 487)
sed -i 's/custom_5d_wave_diagrams/custom_nwave_diagrams/g' nWave/agents/visual-architect-reviewer.md
sed -i 's/all_5d_wave_agents/all_nwave_agents/g' nWave/agents/visual-architect-reviewer.md

# Update software-crafter.md
sed -i 's/5d_wave/nwave/g' nWave/agents/software-crafter.md

# Update software-crafter-reviewer.md
sed -i 's/5d_wave/nwave/g' nWave/agents/software-crafter-reviewer.md
```

#### Step 3C: Update Python Code
```bash
# Update team_processor.py (lines 80, 112)
# Change default values from "5d_wave" to "nwave"
sed -i 's/"5d_wave"/"nwave"/g' tools/processors/team_processor.py
```

#### Step 3D: Update YAML Templates
```bash
# Update AGENT_TEMPLATE.yaml (line 1288)
# Change comment example from "complete_5d_wave" to "complete_nwave"
sed -i 's/complete_5d_wave/complete_nwave/g' nWave/templates/AGENT_TEMPLATE.yaml
```

#### Step 3E: Update Other Checklists
```bash
# Update deliver-wave-checklist.md (3 occurrences)
sed -i 's/5D-Wave/nWave/g' nWave/checklists/deliver-wave-checklist.md
sed -i 's/5d-wave/nwave/g' nWave/checklists/deliver-wave-checklist.md

# Update atdd-compliance-checklist.md (1 occurrence)
sed -i 's/5D-Wave/nWave/g' nWave/checklists/atdd-compliance-checklist.md
```

#### Step 3F: Update Documentation
```bash
# Update SCRIPTS_CONSOLIDATION_PLAN.md references
sed -i 's/5d-wave/nwave/g' SCRIPTS_CONSOLIDATION_PLAN.md
sed -i 's/5D-Wave/nWave/g' SCRIPTS_CONSOLIDATION_PLAN.md

# Update test data
sed -i 's/5D-Wave/nWave/g' docs/features/framework-rationalization/03-distill/test-data-requirements.md
```

**Verification**:
```bash
# Verify no old 5d-wave references remain
grep -r "5d-wave\|5d_wave\|5D-Wave\|5d-Wave" --include="*.md" --include="*.yaml" --include="*.py" . 2>/dev/null | grep -v build/ | grep -v ".git/" | grep -v "validate-rename.sh" || echo "✓ No 5d-wave references"
```

**Note**: `validate-rename.sh` is excluded because it's a validation script that contains search patterns.

**Result**: All 5d-wave references updated to nWave

---

### Phase 4: Update Internal References
**Time**: 10 minutes
**Risk**: LOW (updating cross-references)

```bash
# Find any files that reference the OLD filenames
grep -r "5d-wave-methodology-checklist" --include="*.md" --include="*.yaml" . 2>/dev/null | grep -v ".git/"
grep -r "5d-wave-complete-methodology" --include="*.md" --include="*.yaml" . 2>/dev/null | grep -v ".git/"

# Update any found references to new filenames
# (Manual or scripted based on findings)
```

**Result**: All cross-references updated

---

### Phase 5: Commit Changes
**Time**: 5 minutes
**Risk**: NONE (just committing)

```bash
# Stage all changes
git add -A

# Verify staged changes
git status

# Create comprehensive commit
git commit -m "refactor: remove legacy BMAD references and rename 5d-wave to nWave

BMAD REMOVAL:
- Delete nWave/data/methodologies/bmad-kb.md (predecessor framework, no longer needed)
- Remove BMAD references from framework-catalog.yaml
- Update release_packager.py documentation pointer

5D-WAVE → NWAVE RENAMING:
- Rename: 5d-wave-methodology-checklist.md → nwave-methodology-checklist.md
- Rename: 5d-wave-complete-methodology.yaml → nwave-complete-methodology.yaml
- Update 10 files: agents, checklists, templates, code
- Replace patterns:
  - 5d-wave → nwave (kebab-case)
  - 5d_wave → nwave (snake_case)
  - 5D-Wave → nWave (title case)
  - custom_5d_wave_* → custom_nwave_* (YAML keys)
  - all_5d_wave_* → all_nwave_* (YAML keys)

IMPACT:
- Total files changed: 13 (3 BMAD + 10 5d-wave content + 2 renames)
- No functionality changes
- Unified naming convention across codebase
- Build artifacts will auto-regenerate

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

**Result**: All naming cleanup committed in single atomic commit

---

## Success Criteria

✅ After this cleanup (with verification commands):

- [ ] No BMAD references remain
  ```bash
  grep -r "bmad\|BMAD\|B-MAD" --include="*.md" --include="*.yaml" --include="*.py" . 2>/dev/null | grep -v build/ | grep -v ".git/" || echo "PASS: No BMAD"
  ```

- [ ] No 5d-wave references remain (except validate-rename.sh)
  ```bash
  grep -r "5d-wave\|5d_wave\|5D-Wave" --include="*.md" --include="*.yaml" --include="*.py" . 2>/dev/null | grep -v build/ | grep -v ".git/" | grep -v "validate-rename.sh" || echo "PASS: No 5d-wave"
  ```

- [ ] Files renamed correctly
  ```bash
  [ -f "nWave/checklists/nwave-methodology-checklist.md" ] && echo "PASS: Checklist renamed"
  [ -f "nWave/templates/nwave-complete-methodology.yaml" ] && echo "PASS: Template renamed"
  ```

- [ ] Git history preserved
  ```bash
  git log --follow --oneline nWave/checklists/nwave-methodology-checklist.md | head -5
  ```

- [ ] YAML keys updated correctly
  ```bash
  grep "custom_nwave_diagrams" nWave/agents/visual-architect.md && echo "PASS: YAML keys updated"
  ```

---

## Rollback Procedure

If something goes wrong:

```bash
# Option 1: Revert the commit
git log --oneline -5  # Find the naming cleanup commit
git revert <commit-hash>

# Option 2: Full rollback to backup branch
git checkout naming-cleanup-backup
git branch -D master
git checkout -b master

# Option 3: Hard reset
git reset --hard HEAD~1  # Remove last commit
```

---

## Timeline

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 0 | Pre-migration verification & backup | 10 min | Ready |
| 1 | Remove BMAD references (3 files) | 5 min | Ready |
| 2 | Rename 5d-wave files (2 files) | 5 min | Ready |
| 3 | Update 5d-wave content (10 files) | 20 min | Ready |
| 4 | Update internal references | 10 min | Ready |
| 5 | Commit changes | 5 min | Ready |
| **TOTAL** | **Complete naming cleanup** | **55 min** | **Ready to execute** |

---

## Files Affected

### BMAD Removal (3 files)
1. `nWave/data/methodologies/bmad-kb.md` - DELETE
2. `nWave/framework-catalog.yaml` - UPDATE (remove section)
3. `nWave/validators/release_packager.py` - UPDATE (change pointer)

### 5d-wave Renaming (12 files)
1. `nWave/checklists/5d-wave-methodology-checklist.md` → RENAME + UPDATE (24 occurrences)
2. `nWave/templates/5d-wave-complete-methodology.yaml` → RENAME
3. `nWave/agents/visual-architect.md` - UPDATE (2 YAML keys)
4. `nWave/agents/visual-architect-reviewer.md` - UPDATE (2 YAML keys)
5. `nWave/agents/software-crafter.md` - UPDATE (2 occurrences)
6. `nWave/agents/software-crafter-reviewer.md` - UPDATE (2 occurrences)
7. `tools/processors/team_processor.py` - UPDATE (2 default values)
8. `nWave/templates/AGENT_TEMPLATE.yaml` - UPDATE (1 comment)
9. `nWave/checklists/deliver-wave-checklist.md` - UPDATE (3 occurrences)
10. `nWave/checklists/atdd-compliance-checklist.md` - UPDATE (1 occurrence)
11. `SCRIPTS_CONSOLIDATION_PLAN.md` - UPDATE (2 occurrences)
12. `docs/features/framework-rationalization/03-distill/test-data-requirements.md` - UPDATE (1 occurrence)

### Build Artifacts (auto-regenerate)
- `build/lib/nWave/data/methodologies/bmad-kb.md` - Will be removed on rebuild
- `build/lib/nWave/checklists/*` - Will update on rebuild
- `build/lib/nWave/templates/*` - Will update on rebuild

---

## Risks & Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Broken references after renaming | MEDIUM | Phase 4 audits all cross-references |
| Missed occurrences | LOW | Comprehensive grep verification in Phase 0 and 5 |
| Build artifact conflicts | VERY LOW | Clean rebuild after naming changes |
| Git history loss | ELIMINATED | Using `git mv` and `git rm` |

---

## Ready for Execution?

This plan:
- ✅ Removes all BMAD predecessor framework references
- ✅ Renames all 5d-wave references to nWave
- ✅ Preserves git history with `git mv`
- ✅ Single atomic commit for consistency
- ✅ Comprehensive verification at each step
- ✅ Clear rollback procedures

**Execution order**: This runs THIRD, after both consolidations complete.

**Next steps after execution**:
1. Verify all success criteria pass
2. Run full test suite to ensure no breakage
3. Clean rebuild to update build artifacts
4. Update any CI/CD references if needed
