# Documentation Consolidation Plan

**Status**: Reviewed and Revised ✅
**Created**: 2026-01-21
**Reviewed**: 2026-01-21 (Adversarial review completed)
**Scope**: Reorganize docs/ (129 files, 1.5MB) for clarity and navigation
**Impact**: No content loss; improved structure and discoverability
**Execution Order**: This plan executes FIRST, before scripts consolidation

---

## Review Findings & Resolutions

### Adversarial Review Summary (22 issues identified)

| Severity | Count | Status |
|----------|-------|--------|
| HIGH | 4 | ✅ Resolved |
| MEDIUM | 10 | ✅ Resolved |
| LOW | 8 | ✅ Accepted/Resolved |

### Key Issues Addressed

1. **No link audit** → Added Phase 0A: Pre-migration link audit
2. **No content verification** → Added Phase 0B: Checksum generation
3. **feature/ cleanup undefined** → Added Phase 0C: Diff feature/ vs features/
4. **Git history loss** → Changed all `mv` to `git mv`
5. **No rollback plan** → Added backup branch + incremental commits
6. **Unmeasurable success criteria** → Added verification commands

---

## Executive Summary

Your documentation has grown organically to 129 files across 27 directories. While content is comprehensive, structure has become confusing:

- **Critical Issue**: Duplicate `docs/feature/` and `docs/features/` directories
- **Navigation Problem**: 5 conceptual guide files scattered at docs/ root
- **Organization Issue**: Research, Reports, and Evolution lack clear hierarchy
- **Orphaned Items**: Empty directories and out-of-scope files

**This plan** reorganizes without losing content, improves navigation, and establishes clear hierarchy.

---

## Decision Summary (Your Choices)

### ✅ Decision 1: Resolve Duplicate Feature Directories
**Choice**: Delete `docs/feature/` entirely
**Rationale**: `docs/feature/` is incomplete/orphaned. `docs/features/` is the complete, well-organized directory containing framework-rationalization phases.

**Action**:
- Delete `/docs/feature/` directory
- Consolidate any unique content from `feature/` into `features/`
- Result: Single source of truth

---

### ✅ Decision 2: Root-Level Guide Files
**Choice**: Keep some at root, move others to subdirectories
**Reasoning**: Some files are foundational and belong at root level; others should move to `guides/` or `research/`

**Specifically**:
- **Keep at docs/ root**:
  - `jobs-to-be-done-guide.md` (framework methodology - foundational)
- **Move to docs/guides/**:
  - `CI-CD-README.md` → `ci-cd-setup.md`
  - `ide-bundling-algorithm.md` → `ide-integration.md`
- **Move to docs/research/**:
  - `knowledge-architecture-analysis.md` → `research/domains/knowledge-architecture/`
  - `knowledge-architecture-integration-summary.md` → `research/domains/knowledge-architecture/`

**Result**: Root level has 4 files instead of 9 (cleaner)

---

### ✅ Decision 3: Documentation Navigation
**Choice**: Create README.md + QUICKSTART.md + CHANGELOG.md at docs/ root
**Rationale**: Help users understand documentation structure and find things

**What this means**:
- `docs/README.md` - Explains documentation structure, how to navigate
- `docs/QUICKSTART.md` - Common tasks and where to find them
- `docs/CHANGELOG.md` - Track documentation updates and changes

**Result**: Users landing in docs/ have clear guidance on how to navigate

---

### ✅ Decision 4: Research Directory Organization
**Choice**: Organize by research domain
**Current state**: 8 files flat with mixed domains (databases, data-engineering, Claude Code, CV optimization)

**Proposed structure**:
```
docs/research/
├── domains/
│   ├── data-engineering/
│   │   ├── data-engineering-comprehensive-research-*.md
│   │   └── databases-data-engineering-*.md
│   ├── database-querying/
│   │   ├── database-querying-design-security-*.md
│   │   ├── sql-querying-practical-examples-*.md
│   │   └── nosql-querying-*.md
│   └── knowledge-architecture/
│       ├── knowledge-architecture-analysis.md (moved from root)
│       └── knowledge-architecture-integration.md (moved from root)
└── frameworks/
    └── claude-code-subagent-activation-best-practices.md
```

**Result**: Researchers can quickly find all related studies on a topic

---

### ✅ Decision 5: Reports Organization
**Choice**: Move feature-specific reports into features/; keep cross-cutting in central reports/

**Current confusing state**: 6 overlapping subcategories (adversarial, validation, framework, production, testing, archive)

**New state**:
- **Central docs/reports/** keeps only cross-cutting reports:
  - `adversarial/` (adversarial testing - cross-project concern)
  - `validation/` (compliance validation - cross-project concern)
  - `production-readiness/` (deployment readiness - cross-project concern)
  - `archive/` (historical/deprecated)

- **Feature-specific reports** move into `docs/features/framework-rationalization/`:
  - Framework cleanup, propagation, implementation reports now live with the feature they validate

**Result**: Clear distinction between cross-cutting concerns and feature-specific validation

---

### ✅ Decision 6: Cross-Phase Documentation
**Choice**: Archive cross-phase/ (these are temporary/historical)
**Current**: 7 files in `docs/cross-phase/` (workflow integration, release, consistency, etc.)

**Action**: Move to `docs/archive/cross-phase/` (historical validation/workflow integration documentation)

**Result**: Active docs are cleaner; historical items preserved in archive

---

### ✅ Decision 7: Evolution Directory
**Choice**: Keep docs/evolution/ as-is (important historical context)
**Rationale**: Evolution documents how the framework improved over time - valuable context

**Action**: No changes to `docs/evolution/`

**Result**: Preserve project history and development timeline

---

### ✅ Decision 8: Cleanup Orphaned Items
**Choice**: Delete orphaned/out-of-scope items

**Deletions**:
1. `docs/demo/` - Empty directory (abandoned)
2. `docs/research/cv-optimization/cv-best-practices-it-istituzioni-italiane.md` - Out-of-scope (personal/regional CV advice)
3. `docs/reports/archive/NEXT_STEPS_WEEK2-3.md` - Archive (old planning from unclear phase)
4. `docs/reports/testing/test-p206-results.md` - Archive (single test result file)

**Result**: Remove clutter and out-of-scope content

---

## Detailed Execution Plan

### Phase 0: Pre-Migration Verification & Safety Setup
**Time**: 15 minutes
**Risk**: NONE (read-only operations + backup creation)

#### Phase 0A: Create Backup Branch
```bash
# Create backup branch for rollback capability
git checkout -b docs-consolidation-backup
git checkout -  # Return to original branch

# Verify backup exists
git branch | grep docs-consolidation-backup
```

#### Phase 0B: Generate Content Checksums
```bash
# Generate checksums for all docs files BEFORE any changes
find docs/ -type f -exec md5sum {} \; | sort > /tmp/docs-pre-migration-checksums.txt

# Count files
echo "Pre-migration file count: $(find docs/ -type f | wc -l)"
```

#### Phase 0C: Audit Internal Links
```bash
# Find all markdown links that reference docs/ paths
grep -roh '\[.*\](.*\.md)' docs/ | sort | uniq > /tmp/docs-internal-links.txt

# Find links that will break (referencing files being moved)
grep -E '(CI-CD-README|ide-bundling-algorithm|cross-phase|knowledge-architecture)' /tmp/docs-internal-links.txt > /tmp/docs-links-to-update.txt

# Review and plan updates
cat /tmp/docs-links-to-update.txt
```

#### Phase 0D: Verify feature/ vs features/ Content
```bash
# List contents of both directories
echo "=== docs/feature/ contents ==="
find docs/feature/ -type f 2>/dev/null || echo "(directory may not exist)"

echo "=== docs/features/ contents ==="
find docs/features/ -type f | head -20

# If feature/ exists, diff against features/
# Only proceed with deletion if feature/ has no unique content
```

**Verification**: All safety measures in place before proceeding

---

### Phase 1: Delete Directories & Files
**Time**: 5 minutes
**Risk**: LOW (only orphaned/duplicate items, backup exists)

```bash
# Delete duplicate feature directory
rm -rf docs/feature/

# Delete empty directory
rm -rf docs/demo/

# Delete out-of-scope research
rm -rf docs/research/cv-optimization/

# Create archive structure
mkdir -p docs/archive/cross-phase
mkdir -p docs/archive/orphaned
```

**Verification**: Confirm deletions, verify no content loss

---

### Phase 2: Move Cross-Phase Files to Archive
**Time**: 5 minutes
**Risk**: LOW (just moving, no deletion)

```bash
# Move all 7 cross-phase files to archive (using git mv to preserve history)
for f in docs/cross-phase/*; do git mv "$f" docs/archive/cross-phase/; done
rmdir docs/cross-phase/

# Move orphaned reports to archive
git mv docs/reports/archive/NEXT_STEPS_WEEK2-3.md docs/archive/orphaned/
git mv docs/reports/testing/test-p206-results.md docs/archive/orphaned/

# Clean up empty report subdirectories
rmdir docs/reports/archive/ 2>/dev/null
rmdir docs/reports/testing/ 2>/dev/null

# INCREMENTAL COMMIT (rollback point)
git commit -m "chore(docs): archive cross-phase and orphaned files"
```

**Result**: All temporary/historical content organized in archive/

---

### Phase 3: Reorganize Research Directory
**Time**: 10 minutes
**Risk**: LOW (moving files, keeping all content)

```bash
# Create domain structure
mkdir -p docs/research/domains/data-engineering
mkdir -p docs/research/domains/database-querying
mkdir -p docs/research/domains/knowledge-architecture
mkdir -p docs/research/frameworks

# Move files to appropriate domains (using git mv to preserve history)
# Note: Use explicit filenames instead of wildcards for reliability
git mv docs/research/data-engineering-comprehensive-research-20251003.md \
   docs/research/domains/data-engineering/
git mv docs/research/databases-data-engineering-20251003-143424.md \
   docs/research/domains/data-engineering/
git mv docs/research/database-querying-design-security-governance-20251003-150123.md \
   docs/research/domains/database-querying/
git mv docs/research/sql-querying-practical-examples-20251003-165818.md \
   docs/research/domains/database-querying/
git mv docs/research/nosql-querying-20251003-174827.md \
   docs/research/domains/database-querying/

# Move knowledge architecture files from docs root
git mv docs/knowledge-architecture-analysis.md \
   docs/research/domains/knowledge-architecture/
git mv docs/knowledge-architecture-integration-summary.md \
   docs/research/domains/knowledge-architecture/

# Move framework research (verify filename before running)
# git mv docs/research/claude-code-subagent-activation-*.md docs/research/frameworks/

# INCREMENTAL COMMIT (rollback point)
git commit -m "chore(docs): reorganize research by domain"
```

**Result**: Research organized by domain; easy to find related studies

---

### Phase 4: Reorganize Root-Level Documentation
**Time**: 10 minutes
**Risk**: LOW (moving guide files, creating new index files)

```bash
# Move guide files to guides/ (using git mv to preserve history)
git mv docs/CI-CD-README.md docs/guides/ci-cd-setup.md
git mv docs/ide-bundling-algorithm.md docs/guides/ide-integration.md

# Root-level files that will remain
# - jobs-to-be-done-guide.md (stays at root - foundational)
# - README.md (will create - navigation guide)
# - QUICKSTART.md (will create - common tasks)
# - CHANGELOG.md (will create - doc history)

# INCREMENTAL COMMIT (rollback point)
git commit -m "chore(docs): move guides to guides/ directory"
```

**Result**: Root level cleaner; guides organized in guides/

---

### Phase 4B: Update Internal Links
**Time**: 10 minutes
**Risk**: LOW (updating references)

```bash
# Update any files that reference the moved files
# Search for old paths and update to new paths

# Example sed commands (verify paths exist before running):
# find docs/ -name "*.md" -exec sed -i 's|CI-CD-README.md|guides/ci-cd-setup.md|g' {} \;
# find docs/ -name "*.md" -exec sed -i 's|ide-bundling-algorithm.md|guides/ide-integration.md|g' {} \;

# Verify no broken links remain
grep -r "CI-CD-README.md" docs/ || echo "✓ No old CI-CD references"
grep -r "ide-bundling-algorithm.md" docs/ || echo "✓ No old IDE references"

# INCREMENTAL COMMIT (rollback point)
git commit -m "chore(docs): update internal links for moved files"
```

**Result**: All internal links updated to new paths

---

### Phase 5: Create Documentation Navigation Files
**Time**: 15 minutes
**Risk**: NONE (creating new helpful content)

**Create `docs/README.md`** (documentation navigation guide):
```markdown
# nWave Documentation

Welcome! This directory contains comprehensive documentation for the nWave
multi-agent workflow framework.

## Quick Navigation

### 🚀 Getting Started
- [QUICKSTART.md](./QUICKSTART.md) - Common tasks and where to find them
- [jobs-to-be-done-guide.md](./jobs-to-be-done-guide.md) - Framework methodology

### 📚 Documentation Structure

#### Implementation & Features
- **guides/** - Conceptual guides and how-to documentation
- **features/** - Active feature implementation organized by wave (discuss → design → distill → develop → deliver)
- **features/framework-rationalization/** - Primary feature with 75+ implementation steps

#### Research & Knowledge
- **research/domains/** - Research organized by topic:
  - data-engineering/ - Data engineering fundamentals and patterns
  - database-querying/ - Database design, querying, optimization
  - knowledge-architecture/ - Knowledge architecture analysis
- **research/frameworks/** - Framework-specific research

#### Quality & Deployment
- **reports/** - Cross-cutting validation and quality reports:
  - adversarial/ - Adversarial verification testing
  - validation/ - Compliance and template validation
  - production-readiness/ - Production deployment readiness
  - feature-specific reports live in features/framework-rationalization/

#### Reference Materials
- **installation/** - Installation and setup procedures
- **templates/** - Reusable workflow and execution templates
- **diagrams/** - Visual documentation and architecture diagrams
- **evolution/** - Historical record of framework improvements (important context!)

#### Historical & Deprecated
- **archive/** - Archived and deprecated documentation
  - cross-phase/ - Historical workflow integration documentation
  - orphaned/ - Old planning documents and deprecated items

## Documentation Updates

See [CHANGELOG.md](./CHANGELOG.md) for recent documentation changes.

## Finding Something Specific

1. **Looking for setup/installation?** → See `installation/`
2. **Need to understand the framework?** → Start with `jobs-to-be-done-guide.md`
3. **Researching databases/data?** → See `research/domains/`
4. **Want implementation details?** → See `features/framework-rationalization/`
5. **Checking quality/validation?** → See `reports/`
6. **Need troubleshooting?** → See `guides/troubleshooting.md` or `reports/`
7. **Curious about how we got here?** → See `evolution/`

## Directory Statistics

- Total files: ~120 (organized, non-archive)
- Primary feature: framework-rationalization (75+ implementation steps)
- Research domains: 3 (data-engineering, database-querying, knowledge-architecture)
- Active guides: 8+ guides covering setup, validation, integration
- Quality reports: 10+ validation and compliance reports

```

**Create `docs/QUICKSTART.md`** (common tasks):
```markdown
# Documentation Quick Start

## Common Questions & Where to Find Answers

### "How do I install/set up?"
→ `installation/INSTALL.md`

### "What is nWave and how does it work?"
→ `jobs-to-be-done-guide.md`

### "How do I set up CI/CD?"
→ `guides/ci-cd-setup.md`

### "How do I integrate with IDE?"
→ `guides/ide-integration.md`

### "Where are the implementation steps?"
→ `features/framework-rationalization/04-develop/steps/`

### "What research has been done on databases?"
→ `research/domains/database-querying/`

### "What research has been done on data engineering?"
→ `research/domains/data-engineering/`

### "What's the framework architecture?"
→ `guides/` or `features/framework-rationalization/02-design/`

### "Is the framework production-ready?"
→ `reports/production-readiness/`

### "How is the project organized?"
→ `README.md` (this file!)

### "What changed in documentation recently?"
→ `CHANGELOG.md`

### "How did the framework evolve?"
→ `evolution/`

### "What are the validation results?"
→ `reports/validation/` or `reports/adversarial/`
```

**Create `docs/CHANGELOG.md`** (documentation updates):
```markdown
# Documentation Changelog

## [2026-01-21] Documentation Consolidation & Reorganization

### Added
- `docs/README.md` - Documentation navigation guide
- `docs/QUICKSTART.md` - Common questions and where to find answers
- `docs/CHANGELOG.md` - Documentation history (this file)
- `docs/research/domains/` - Reorganized research by topic
- `docs/archive/` - Centralized archive for historical and deprecated documentation

### Moved
- `CI-CD-README.md` → `guides/ci-cd-setup.md`
- `ide-bundling-algorithm.md` → `guides/ide-integration.md`
- `knowledge-architecture-*.md` → `research/domains/knowledge-architecture/`
- `cross-phase/` (7 files) → `archive/cross-phase/`
- Research files → `research/domains/` (organized by topic)

### Deleted
- `docs/feature/` - Consolidated duplicate directory
- `docs/demo/` - Empty directory
- `docs/research/cv-optimization/` - Out-of-scope personal content

### Improved
- Documentation structure clarity and navigation
- Research organization by domain (easier discovery)
- Root-level documentation cleaner (4 foundational files instead of 9)
- Reports organization reflects feature vs cross-cutting concerns

### Migration Path
If you have old links to moved files:
- `CI-CD-README.md` → `guides/ci-cd-setup.md`
- `ide-bundling-algorithm.md` → `guides/ide-integration.md`
- Cross-phase docs → `archive/cross-phase/`
- See `README.md` for new navigation structure

---

## [Previous entries would go here]

```

**Result**: Users have clear guidance on documentation structure

---

### Phase 6: Move Feature-Specific Reports
**Time**: 10 minutes
**Risk**: LOW (moving reports into feature directory)

```bash
# Create reports subdirectory in framework-rationalization feature
mkdir -p docs/features/framework-rationalization/04-develop/reports

# Move feature-specific reports from central reports/ to feature location (git mv)
git mv docs/reports/framework/FRAMEWORK_CLEANUP_SUMMARY.md \
   docs/features/framework-rationalization/04-develop/reports/
git mv docs/reports/framework/FRAMEWORK_PROPAGATION_FINAL_REPORT.md \
   docs/features/framework-rationalization/04-develop/reports/
git mv docs/reports/framework/PRODUCTION_FRAMEWORKS_IMPLEMENTATION_REPORT.md \
   docs/features/framework-rationalization/04-develop/reports/

# Remove now-empty framework subdirectory
rmdir docs/reports/framework/ 2>/dev/null

# INCREMENTAL COMMIT (rollback point)
git commit -m "chore(docs): move feature-specific reports to feature directory"
```

**Result**: Feature-specific reports live with feature; central reports only have cross-cutting concerns

---

### Phase 7: Git Commit - Complete Reorganization
**Time**: 5 minutes
**Risk**: NONE (just committing organized changes)

```bash
git add -A
git commit -m "chore(docs): Consolidate and reorganize documentation structure

MAJOR CHANGES:
- Delete duplicate docs/feature/ directory (consolidate to docs/features/)
- Delete empty docs/demo/ directory
- Delete out-of-scope cv-optimization research
- Archive cross-phase/ (7 files) to docs/archive/cross-phase/
- Archive orphaned reports and planning documents

REORGANIZATION:
- Research: Reorganize by domain (data-engineering, database-querying, knowledge-architecture)
- Reports: Move feature-specific reports into docs/features/framework-rationalization/
- Root guides: Move CI-CD and IDE integration to docs/guides/
- Navigation: Add README.md, QUICKSTART.md, CHANGELOG.md at docs/ root

IMPROVEMENTS:
- Root level: 9 files → 4 files (cleaner)
- Research: Flat structure → domain-organized (better discoverability)
- Reports: Unclear 6 categories → clear separation (cross-cutting vs feature-specific)
- Navigation: Users can now understand structure via README and QUICKSTART

No content loss; all items preserved or archived appropriately."
```

**Result**: All changes committed with clear history

---

## Final Documentation Structure

```
docs/
├── README.md                     ← Navigation guide (NEW)
├── QUICKSTART.md                 ← Common questions (NEW)
├── CHANGELOG.md                  ← Documentation history (NEW)
├── jobs-to-be-done-guide.md      ← Framework methodology (KEPT)
│
├── guides/                       ← How-to & conceptual documentation
│   ├── HOW_TO_INVOKE_REVIEWERS.md
│   ├── LAYER_4_IMPLEMENTATION_SUMMARY.md
│   ├── LAYER_4_INTEGRATION_GUIDE.md
│   ├── QUICK_REFERENCE_VALIDATION.md
│   ├── troubleshooting.md
│   ├── ci-cd-setup.md            ← (MOVED from root)
│   └── ide-integration.md        ← (MOVED from root)
│
├── features/                     ← Active feature implementations
│   └── framework-rationalization/
│       ├── 01-discuss/
│       ├── 02-design/
│       ├── 03-distill/
│       └── 04-develop/
│           ├── steps/ (75+ step files)
│           ├── reports/          ← (MOVED feature-specific reports here)
│           ├── baseline.yaml
│           └── roadmap.yaml
│
├── research/                     ← Domain-organized research
│   ├── domains/                  ← (REORGANIZED - was flat)
│   │   ├── data-engineering/
│   │   │   ├── data-engineering-comprehensive-research-*.md
│   │   │   └── databases-data-engineering-*.md
│   │   ├── database-querying/
│   │   │   ├── database-querying-design-security-*.md
│   │   │   ├── sql-querying-practical-examples-*.md
│   │   │   └── nosql-querying-*.md
│   │   └── knowledge-architecture/
│   │       ├── knowledge-architecture-analysis.md       ← (MOVED from root)
│   │       └── knowledge-architecture-integration.md    ← (MOVED from root)
│   └── frameworks/
│       └── claude-code-subagent-activation-*.md
│
├── reports/                      ← Cross-cutting quality reports
│   ├── adversarial/
│   │   ├── ADVERSARIAL_TEST_REPORT.md
│   │   └── ADVERSARIAL_VERIFICATION_WORKFLOW.md
│   ├── validation/
│   │   ├── AGENT_TEMPLATE_COMPLIANCE_ANALYSIS.md
│   │   ├── COMPLIANCE_VALIDATION_REPORT.md
│   │   ├── MANUAL_COMPLIANCE_CHECK.md
│   │   └── VALIDATION_IMPLEMENTATION_SUMMARY.md
│   ├── production-readiness/
│   │   └── PRODUCTION_READINESS_REPORT.md
│   └── archive/                  ← (NEW - reports cleanup)
│
├── installation/                 ← Setup procedures (unchanged)
│   ├── INSTALL.md
│   └── UNINSTALL.md
│
├── templates/                    ← Reusable templates (unchanged)
│   └── STEP_EXECUTION_TEMPLATE.md
│
├── diagrams/                     ← Visual documentation (unchanged)
│   └── develop-workflow-sequence.md
│
├── evolution/                    ← Historical improvements (unchanged)
│   ├── 2025-12-04_agent-prioritization-improvements.md
│   └── 2026-01-12_11-phase-tdd-integration.md
│
└── archive/                      ← Historical/deprecated (NEW)
    ├── cross-phase/              ← (MOVED from docs/cross-phase/)
    │   ├── cross-01-workflow-integration.md
    │   ├── cross-02-release-workflow.md
    │   ├── ... (7 files total)
    └── orphaned/                 ← (NEW)
        ├── NEXT_STEPS_WEEK2-3.md
        └── test-p206-results.md
```

**Summary**:
- **Directories**: 27 → 18 (cleaner hierarchy)
- **Root files**: 9 → 4 (much cleaner)
- **Content loss**: ZERO (all preserved or archived)
- **New navigation**: README, QUICKSTART, CHANGELOG help users navigate

---

## Risks & Mitigation

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Links break after reorganization | MEDIUM | Phase 0C link audit + Phase 4B link updates |
| Confusion during transition | LOW | Clear commit message; README explains structure |
| Accidental deletion | VERY LOW | Backup branch created in Phase 0A; `git mv` preserves history |
| Content loss | VERY LOW | Checksum verification (Phase 0B vs Phase 7B) |
| Partial failure mid-execution | LOW | Incremental commits after each phase; can revert individual commits |
| Git history loss | ELIMINATED | All moves use `git mv` instead of `mv` |

### Rollback Procedure

If something goes wrong:

```bash
# Option 1: Revert specific phase commit
git log --oneline -10  # Find the problematic commit
git revert <commit-hash>

# Option 2: Full rollback to backup branch
git checkout docs-consolidation-backup
git branch -D master  # or your working branch
git checkout -b master  # Recreate from backup

# Option 3: Revert all consolidation commits
git reset --hard HEAD~N  # Where N = number of consolidation commits
```

---

## Success Criteria

✅ After this consolidation (with verification commands):

- [ ] No duplicate directories (feature/ & features/ → features/ only)
  ```bash
  [ ! -d "docs/feature" ] && echo "PASS: No duplicate feature dir"
  ```

- [ ] Root level has only 4 foundational files
  ```bash
  [ $(ls -1 docs/*.md 2>/dev/null | wc -l) -eq 4 ] && echo "PASS: 4 root md files"
  ```

- [ ] Research organized by domain
  ```bash
  [ -d "docs/research/domains/data-engineering" ] && echo "PASS: Research domains exist"
  ```

- [ ] Reports clearly separated (cross-cutting vs feature-specific)
  ```bash
  [ -d "docs/features/framework-rationalization/04-develop/reports" ] && echo "PASS: Feature reports relocated"
  ```

- [ ] All content preserved (checksum verification)
  ```bash
  # Compare file counts (should match minus deleted items)
  PRE=$(wc -l < /tmp/docs-pre-migration-checksums.txt)
  POST=$(find docs/ -type f | wc -l)
  echo "Pre: $PRE files, Post: $POST files"
  ```

- [ ] All internal links work (no broken references)
  ```bash
  # Should return empty (no broken links)
  grep -rE '\[.*\]\((CI-CD-README|ide-bundling-algorithm|cross-phase/)' docs/ || echo "PASS: No broken links"
  ```

- [ ] Git history preserved for moved files
  ```bash
  git log --follow --oneline docs/guides/ci-cd-setup.md | head -5
  ```

---

## Timeline

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 0 | Pre-migration verification (backup, checksums, link audit, feature/ diff) | 15 min | Ready |
| 1 | Delete orphans/duplicates | 5 min | Ready |
| 2 | Move cross-phase to archive + commit | 5 min | Ready |
| 3 | Reorganize research by domain + commit | 10 min | Ready |
| 4 | Move root guides to guides/ + commit | 10 min | Ready |
| 4B | Update internal links + commit | 10 min | Ready |
| 5 | Create navigation files | 15 min | Ready |
| 6 | Move feature reports + commit | 10 min | Ready |
| 7 | Final verification + squash/cleanup commit | 10 min | Ready |
| **TOTAL** | **Complete docs reorganization** | **90 min** | **Ready to execute** |

---

## Ready for Execution?

This plan has been **reviewed and revised** based on adversarial review findings:
- ✅ Pre-migration verification phase added (backup, checksums, link audit)
- ✅ All `mv` commands changed to `git mv` for history preservation
- ✅ Incremental commits after each phase for rollback capability
- ✅ Explicit rollback procedures documented
- ✅ Measurable success criteria with verification commands
- ✅ Link audit and update phases added

**Execution order**: This docs consolidation runs FIRST, before scripts consolidation.

**Next step**: Proceed to update SCRIPTS_CONSOLIDATION_PLAN.md with similar improvements.
