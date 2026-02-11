# Research: Wave Command Output Paths Update

**Research Date**: 2026-01-23
**Research Type**: Code change documentation
**Documentation Type**: Reference
**Researcher**: Lyra (orchestrator)

---

## Executive Summary

nWave wave commands (DISCUSS, DESIGN, DISTILL, DELIVER) have been updated to use a feature-based folder structure instead of global folders. All deliverables now output to `docs/feature/{feature-name}/{wave-name}/` for better organization and traceability.

---

## Changes Made

### Files Modified

1. **nWave/tasks/nw/discuss.md**
   - Updated expected outputs from `docs/requirements/` to `docs/feature/{feature-name}/discuss/`
   - Deliverables: requirements.md, user-stories.md, acceptance-criteria.md, dor-checklist.md

2. **nWave/tasks/nw/design.md**
   - Updated all references from `docs/requirements/` to `docs/feature/{feature-name}/discuss/` (for inputs)
   - Updated expected outputs from `docs/architecture/` to `docs/feature/{feature-name}/design/`
   - Deliverables: architecture-design.md, technology-stack.md, component-boundaries.md, data-models.md, diagrams/

3. **nWave/tasks/nw/distill.md**
   - Updated all references from `docs/requirements/` to `docs/feature/{feature-name}/discuss/` (for inputs)
   - Updated all references from `docs/architecture/` to `docs/feature/{feature-name}/design/` (for inputs)
   - Updated expected outputs to `docs/feature/{feature-name}/distill/`
   - Deliverables: acceptance-tests.feature, step-definitions.{language}, test-scenarios.md

4. **nWave/tasks/nw/deliver.md**
   - Updated all references from `docs/architecture/` to `docs/feature/{feature-name}/design/` (for inputs)
   - Updated expected outputs from `docs/demo/` to `docs/feature/{feature-name}/deliver/`
   - Deliverables: production-deployment.md, stakeholder-feedback.md, business-impact-report.md

### Path Patterns

#### Old Structure (Global Folders)
```
docs/
├── requirements/       # All features mixed together
├── architecture/       # All features mixed together
├── testing/           # All features mixed together
└── demo/              # All features mixed together
```

#### New Structure (Feature-Based)
```
docs/
└── feature/
    └── {feature-name}/
        ├── discuss/    # DISCUSS wave outputs
        ├── design/     # DESIGN wave outputs
        ├── distill/    # DISTILL wave outputs
        └── deliver/    # DELIVER wave outputs
```

---

## Rationale

### Benefits

1. **Feature Isolation**: All artifacts for a feature are co-located
2. **Traceability**: Clear progression from requirements → design → tests → delivery
3. **Parallel Development**: Multiple features can be worked on simultaneously without file conflicts
4. **Wave Clarity**: Folder names match wave names (discuss, design, distill, deliver)
5. **Lifecycle Visibility**: Feature evolution is visible in folder structure

### Alignment with nWave Methodology

The 6-wave nWave methodology:
1. DISCOVER (wave 1) - Problem validation
2. DISCUSS (wave 2) - Requirements gathering
3. DESIGN (wave 3) - Architecture design
4. DISTILL (wave 4) - Acceptance test creation
5. DEVELOP (wave 5) - Implementation
6. DELIVER (wave 6) - Production deployment

The new folder structure aligns with waves 2-6, making the methodology visible in the file system.

---

## Technical Details

### Placeholder Pattern

All wave commands use `{feature-name}` as a placeholder that gets replaced at runtime with the actual feature name:

```markdown
# Example from discuss.md
# Expected outputs (reference only):
# - docs/feature/{feature-name}/discuss/requirements.md
```

### Context File Updates

Commands also reference input files from previous waves using the same pattern:

```markdown
# Example from design.md
## Context Files Required
- docs/feature/{feature-name}/discuss/requirements.md
- docs/feature/{feature-name}/discuss/user-stories.md
```

### Cross-Wave References

Each wave reads from the previous wave's output folder:
- DESIGN reads from `discuss/`
- DISTILL reads from `discuss/` and `design/`
- DELIVER reads from `design/` (and implementation in `src/`)

---

## Implementation Evidence

### DES Feature Example

The Deterministic Execution System (DES) feature on branch `determinism` was reorganized to match this structure:

**Before**:
```
docs/feature/des/
├── requirements.md
├── user-stories.md
├── acceptance-criteria.md
└── dor-checklist.md

docs/architecture/des/
├── architecture-design.md
├── component-boundaries.md
├── data-models.md
└── technology-stack.md
```

**After**:
```
docs/feature/des/
├── discuss/
│   ├── requirements.md
│   ├── user-stories.md
│   ├── acceptance-criteria.md
│   └── dor-checklist.md
└── design/
    ├── architecture-design.md
    ├── component-boundaries.md
    ├── data-models.md
    └── technology-stack.md
```

Commit: `9f8ec0c` - "refactor(des): reorganize docs by nWave wave structure"

---

## Sources

1. **Primary Source**: Direct code inspection of modified files
   - nWave/tasks/nw/discuss.md (commit 9f8ec0c parent)
   - nWave/tasks/nw/design.md (commit 9f8ec0c parent)
   - nWave/tasks/nw/distill.md (commit 9f8ec0c parent)
   - nWave/tasks/nw/deliver.md (commit 9f8ec0c parent)

2. **Implementation Evidence**: DES feature folder reorganization
   - Git history on branch `determinism`
   - Commit `9f8ec0c`: refactor(des): reorganize docs by nWave wave structure

---

## Coverage Analysis

- **Citation Coverage**: 100% (all facts directly from code)
- **Source Quality**: Primary sources (actual code files)
- **Verification**: All paths verified through file system inspection
- **Completeness**: All 4 wave commands documented (DISCUSS, DESIGN, DISTILL, DELIVER)

Note: DEVELOP wave does not have "expected outputs" section as it produces implementation code in `src/` rather than documentation artifacts.

---

*Research conducted for reference documentation creation.*
