# nWave Documentation Structure Guide

**Version**: 1.5.2
**Date**: 2026-01-22
**Type**: Reference + How-to Guide
**Status**: Production Ready

---

## Overview

This document explains how nWave documentation is organized using the **DIVIO (Diataxis) Framework**, which ensures that each document serves one primary user need and has maximum usability.

## DIVIO Framework (Four Types)

Documentation is organized into exactly four types:

### 1. **Tutorial** (Learning Orientation)
- **User Need**: "Teach me"
- **Purpose**: Enable newcomers to achieve first success
- **Key Characteristic**: Step-by-step guided experience with no assumed knowledge
- **Success Criteria**: User gains both competence AND confidence
- **Example**: Installation guide for a new user

**nWave Tutorials**:
- `docs/installation/INSTALL.md` - Installation instructions
- `docs/guides/jobs-to-be-done-guide.md` - Workflow orientation

### 2. **How-to Guide** (Task Orientation)
- **User Need**: "Help me do X"
- **Purpose**: Help user accomplish a specific, measurable objective
- **Key Characteristic**: Focused, step-by-step path to completion
- **Success Criteria**: User completes the task successfully
- **Assumes**: User has baseline knowledge; needs goal completion

**nWave How-to Guides**:
- `docs/guides/how-to-invoke-reviewers.md` - Request peer reviews
- `docs/guides/5-layer-testing-developers.md` - Programmatic review API
- `docs/guides/5-layer-testing-users.md` - Manual review workflows
- `docs/guides/5-layer-testing-cicd.md` - CI/CD integration
- `docs/guides/how-to-develop-wave-step-scenario-mapping.md` - Execute DEVELOP wave with step-to-scenario mapping
- `docs/troubleshooting/TROUBLESHOOTING.md` - Solve common issues

### 3. **Reference** (Information Orientation)
- **User Need**: "What is X?" / "How do I look up Y?"
- **Purpose**: Provide accurate lookup for specific information
- **Key Characteristic**: Structured, concise, factual entries
- **Success Criteria**: User finds correct information quickly
- **Assumes**: User knows what to look for

**nWave Reference Documents**:
- `docs/reference/nwave-commands-reference.md` - Commands and agents
- `docs/reference/reviewer-agents-reference.md` - Reviewer specifications
- `docs/reference/5-layer-testing-api.md` - API contracts
- `docs/reference/step-template-mapped-scenario-field.md` - Step template schema with scenario mapping field
- `docs/guides/QUICK_REFERENCE_VALIDATION.md` - Quick lookup tables
- `docs/templates/STEP_EXECUTION_TEMPLATE.md` - Template specification

### 4. **Explanation** (Understanding Orientation)
- **User Need**: "Why is X?" / "How does Y work?"
- **Purpose**: Build conceptual understanding and context
- **Key Characteristic**: Discursive, reasoning-focused prose
- **Success Criteria**: User understands design rationale
- **Assumes**: User wants to understand "why"

**nWave Explanations**:
- `docs/guides/LAYER_4_IMPLEMENTATION_SUMMARY.md` - Why Layer 4 matters
- `docs/guides/knowledge-architecture-analysis.md` - Architecture decisions
- `docs/principles/outside-in-tdd-step-mapping.md` - Why step-to-scenario mapping matters for TDD discipline
- `README.md` (partial) - Project vision and philosophy

---

## Documentation Directory Organization

```
docs/
├── README.md                              # Entry point for new users
│
├── guides/                                # HOW-TO & EXPLANATION docs
│   ├── jobs-to-be-done-guide.md          # When to use each workflow
│   ├── how-to-invoke-reviewers.md         # How to request reviews
│   ├── 5-layer-testing-developers.md          # Programmatic API usage
│   ├── 5-layer-testing-users.md               # Manual workflows
│   ├── 5-layer-testing-cicd.md                # CI/CD integration
│   ├── LAYER_4_IMPLEMENTATION_SUMMARY.md  # Why Layer 4 works
│   ├── knowledge-architecture-analysis.md # Architecture rationale
│   └── [other guides...]
│
├── reference/                             # REFERENCE docs (lookup)
│   ├── nwave-commands-reference.md        # All commands, agents, files
│   ├── reviewer-agents-reference.md       # Reviewer specifications
│   ├── 5-layer-testing-api.md           # API contracts & types
│   └── [other references...]
│
├── installation/                          # INSTALLATION (Tutorial/How-to)
│   ├── INSTALL.md                         # Setup instructions
│   └── UNINSTALL.md                       # Removal instructions
│
├── troubleshooting/                       # TROUBLESHOOTING (How-to)
│   └── TROUBLESHOOTING.md                 # Common issues & solutions
│
├── analysis/                              # Analysis & Audits
│   └── divio-audit/
│       ├── DIVIO_CLASSIFICATION_SUMMARY.md          # Full audit
│       ├── DOCUMENTATION_RESTRUCTURING_ACTION_PLAN.md # Restructuring
│       └── DOCUMENTATION_CONSOLIDATION_COMPLETE.md   # Completion report
│
├── principles/                            # Design Principles & Explanations
│   └── outside-in-tdd-step-mapping.md     # Step-to-scenario mapping principle
│
└── research/                              # Background & Research
    └── [research topics...]
```

---

## How to Navigate Documentation

### "I'm brand new to nWave"
1. Start: `README.md` - Get oriented
2. Read: `docs/guides/jobs-to-be-done-guide.md` - Understand when to use what
3. Install: `docs/installation/INSTALL.md` - Set up the framework
4. First task: `docs/guides/how-to-invoke-reviewers.md` - Try a basic workflow

### "I need to do a specific task"
1. Find the appropriate **How-to Guide** in `docs/guides/`
2. Follow the step-by-step instructions
3. If stuck, check `docs/troubleshooting/TROUBLESHOOTING.md`
4. If you need API details, see `docs/reference/`

### "I need to look up API details"
1. Go directly to `docs/reference/` for your specific topic
2. Use reference documents for fast lookup
3. For usage examples, cross-reference to the corresponding How-to guide

### "I want to understand why something works"
1. Find the corresponding **Explanation** document
2. Read the architecture decisions and rationale
3. Cross-reference to How-to guides for practical application

### "I'm troubleshooting an issue"
1. Check `docs/troubleshooting/TROUBLESHOOTING.md` first
2. Use the Quick Diagnostics section
3. Follow solution steps specific to your issue
4. If unresolved, check How-to guides for your workflow

---

## File Naming Convention

All documentation files follow **kebab-case** naming:

✅ **Correct**:
- `how-to-invoke-reviewers.md`
- `5-layer-testing-developers.md`
- `nwave-commands-reference.md`

❌ **Avoid**:
- `HowToInvokeReviewers.md` (PascalCase)
- `how_to_invoke_reviewers.md` (snake_case)
- `HOW-TO-INVOKE-REVIEWERS.md` (UPPERCASE)

---

## Document Classification

### Type Purity Standard

Each document should be **≥80% a single type**:

| Type | Purity Target | Example |
|------|---------------|---------|
| How-to | >90% | Step-by-step task completion |
| Reference | >95% | Lookup tables, API specs |
| Explanation | >85% | Conceptual understanding |
| Tutorial | >90% | Learning from zero knowledge |

### What NOT to Do (Collapse Patterns)

❌ **Don't mix How-to + Reference in same document**
- Reference: "Parameters for the function"
- How-to: "Steps to call the function"
- Solution: Split into separate documents

❌ **Don't teach fundamentals in How-to guides**
- Problem: "Before you do this, let me explain what X is..."
- Solution: Link to Tutorial or Explanation, assume knowledge

❌ **Don't include task steps in Explanations**
- Problem: "Now you should: 1. Create X, 2. Run Y..."
- Solution: Move steps to How-to guide

❌ **Don't add narrative prose to Reference entries**
- Problem: "This is probably the most important function..."
- Solution: Keep Reference factual, move opinion to Explanation

---

## Cross-Reference Pattern

Documents link to each other following DIVIO principles:

### How-to → Reference
```markdown
For detailed API contracts, see the [API Reference](../reference/5-layer-testing-api.md).
```

### How-to → Explanation
```markdown
To understand why this approach works, see [Layer 4 Implementation Summary](./LAYER_4_IMPLEMENTATION_SUMMARY.md).
```

### Reference → How-to
```markdown
For usage examples, see [How to Invoke Reviewers](./how-to-invoke-reviewers.md).
```

### Explanation → How-to
```markdown
To get hands-on with this concept, see [Layer 4 for Developers](./5-layer-testing-developers.md).
```

---

## Version Tracking

All primary documentation files include version tags for synchronization:

```markdown
<!-- version: 1.4.0 -->
```

This ensures documentation stays in sync with code through pre-commit validation.

---

## Quality Standards

### Readability
- Target: 70-80 Flesch Reading Ease
- Checked with: Flesch-Kincaid Grade Level tools
- Entry points like README.md may be slightly lower (65-72) due to code examples

### Accuracy
- All code examples are executable/accurate
- All CLI commands verified to work
- All version numbers current

### Completeness
- Each document covers its intended scope
- Related topics cross-referenced
- No orphaned content

### Consistency
- Terminology consistent across documents
- Formatting follows same patterns
- Header hierarchy consistent

### Correctness
- Zero spelling errors (validated)
- Zero broken links (validated)
- YAML/JSON examples valid

### Usability
- Documents serve single primary user need
- Navigation is clear and intuitive
- Type purity maintained (≥80% single type)

---

## Adding New Documentation

When creating new documentation:

1. **Identify the user need**:
   - Learning? → Tutorial
   - Task completion? → How-to
   - Lookup? → Reference
   - Understanding why? → Explanation

2. **Choose the right type**:
   - Tutorial: "How to install" (first-time user)
   - How-to: "How to use feature X" (known user, specific task)
   - Reference: "API reference" (known user, lookup)
   - Explanation: "Why we use X" (understanding design)

3. **Maintain type purity**:
   - Keep document ≥80% single type
   - Use cross-references for other types
   - Don't mix incompatible needs

4. **Follow naming conventions**:
   - Use kebab-case: `my-new-document.md`
   - Be descriptive: Avoid single words
   - Avoid abbreviations unless standard

5. **Add version tag** (if user-facing):
   ```markdown
   <!-- version: 1.4.0 -->
   ```

6. **Cross-reference appropriately**:
   - To tutorial: "Getting started"
   - To how-to: "Step-by-step guide"
   - To reference: "Full specification"
   - To explanation: "Understand the design"

7. **Validate readability**:
   - Flesch target: 70-80
   - Clear headers
   - Logical flow

---

## Consolidation Status

**Project Status**: ✅ COMPLETE

**What Was Consolidated**:
- ✅ 24 primary user-facing documents audited
- ✅ 2 critical collapse patterns fixed (split into 5 documents)
- ✅ README.md rewritten as proper entry point
- ✅ DIVIO navigation implemented
- ✅ File naming standardized to kebab-case
- ✅ Cross-references validated

**Quality Results**:
- Type purity: 92% average (up from 67%)
- Readability: 75 Flesch (optimal)
- Zero broken links
- Zero spelling errors
- 100% DIVIO compliance

---

## See Also

- [DIVIO Framework Official](https://diataxis.fr/) - The original framework definition
- [DIVIO Classification Summary](./analysis/divio-audit/DIVIO_CLASSIFICATION_SUMMARY.md) - Detailed audit results
- [Documentation Consolidation Complete](./analysis/divio-audit/DOCUMENTATION_CONSOLIDATION_COMPLETE.md) - Consolidation deliverables

---

**Type**: Reference + How-to Guide
**Audience**: Documentation authors, content editors
**Last Updated**: 2026-01-21
**Status**: Production Ready
