# Documentation Restructuring Action Plan

**Version**: 1.5.2
**Date**: 2026-01-22
**Priority**: CRITICAL
**Scope**: Eliminate DIVIO collapse patterns in 3 files
**Timeline**: 2 weeks
**Owner**: Documentation Team
**Status**: COMPLETED

---

## Executive Brief

Two documentation files violate DIVIO type purity (40-45% vs minimum 80% threshold). Restructuring these files into properly-classified separate documents will:

1. **Improve usability** by serving each user need appropriately
2. **Eliminate collapse patterns** that confuse readers
3. **Increase readability** from 58-62 Flesch to 75+ Flesch
4. **Achieve 100% compliance** with DIVIO classification standards

**Total Effort**: 10-12 hours spread across 2 weeks
**Risk**: Low (content not lost, just reorganized)
**Benefit**: High (significant usability improvement)

---

## Action 1: Split HOW_TO_INVOKE_REVIEWERS.md

**Estimated Effort**: 3-4 hours
**Priority**: CRITICAL (Week 1)
**Current State**: 610 lines, 3 mixed content types (40% how-to + 35% reference + 25% explanation)
**Target State**: 3 separate documents, each >80% single type

### Problem Analysis

Current document serves three incompatible user needs:

| User Need | Current Lines | Content Type |
|-----------|---------------|--------------|
| "How do I invoke reviewers?" | 122-159 (manual methods) | How-to |
| "What is a reviewer agent?" | 30-65 (system overview) | Reference + Explanation |
| "Why do reviewers matter?" | 9-28 (executive summary) | Explanation |
| "How do I configure reviewers?" | 436-477 (configuration) | Reference |
| "What's the review process?" | 57-67 (5-phase workflow) | Explanation |

**Result**: Reader opens document confused about purpose. Installation status mixed with capability definition mixed with task guidance.

### Solution: Create 3 Documents

#### Document 1: HOW_TO_INVOKE_REVIEWERS.md (How-to Guide)

**Purpose**: Teach user HOW to request and iterate on peer reviews

**Content** (Source from current lines 122-159, 316-404):
- Manual invocation methods (all 3 methods)
- Task tool invocation workflow
- Direct activation approach
- Interpretation of YAML feedback
- Revision and re-submission process
- Understanding iteration limits
- Troubleshooting review failures

**Structure**:
```
1. Quick Start (copy-paste command)
2. Method 1: Task Tool Invocation
3. Method 2: Direct Agent Activation
4. Method 3: Workflow Integration
5. Interpreting Feedback
6. Revising and Re-Submitting
7. When Review Fails (Escalation)
8. Troubleshooting
```

**Length**: 200-250 lines
**Readability Target**: 75-80 Flesch
**Type Purity Target**: >95%

**Write**: 1 hour

---

#### Document 2: REVIEWER_AGENTS_REFERENCE.md (Reference)

**Purpose**: Look up reviewer agent specifications and configuration

**Content** (Source from current lines 30-65, 436-477):
- Reviewer agents table (12 agents with persona, focus)
- Agent role descriptions
- Configuration reference (.nwave/layer4.yaml)
- Environment variables
- API/command contracts (move from LAYER_4_INTEGRATION_GUIDE.md)
- Quick reference for each reviewer type

**Structure**:
```
1. Reviewer Agents Quick Matrix
   ├─ Agent name, persona, primary focus
   ├─ Business analyst reviewer (Scout)
   ├─ Solution architect reviewer (Atlas)
   ├─ ... (all 12 agents)
   └─ Keywords: bias detection, completeness, clarity, etc.

2. Configuration Reference
   ├─ Environment variables
   ├─ .nwave/layer4.yaml schema
   ├─ Example configuration
   └─ Defaults and overrides

3. When to Use Which Reviewer
   ├─ By phase (DISCUSS, DESIGN, DISTILL, DEVELOP)
   ├─ By artifact type (requirements, architecture, tests, code)
   └─ By issue type (bias, completeness, clarity, testability)
```

**Length**: 150-200 lines
**Readability Target**: 70-75 Flesch (reference docs acceptable at higher range)
**Type Purity Target**: >95%

**Write**: 1-1.5 hours

---

#### Document 3: LAYER_4_ADVERSARIAL_VERIFICATION_OVERVIEW.md (Explanation)

**Purpose**: Understand WHY reviewers matter and what problems they solve

**Content** (Source from current lines 9-28, 57-67, and existing LAYER_4_IMPLEMENTATION_SUMMARY.md):
- What is Layer 4? (definition)
- How Layer 4 differs from Layer 3
- Core problem: confirmation bias
- Benefits: bias reduction, quality improvement, knowledge transfer
- 5-Phase review workflow explained
- When to use (decision framework)
- Success metrics and expected outcomes

**Structure**:
```
1. Executive Summary (Why reviewers exist)
2. Core Problem: Confirmation Bias
3. What is Layer 4? (vs Layer 3)
4. 5-Phase Review Workflow Explained
   ├─ Phase 1: Production
   ├─ Phase 2: Review
   ├─ Phase 3: Revision
   ├─ Phase 4: Approval
   └─ Phase 5: Handoff
5. Benefits Realized
6. When to Use Reviewers
7. Success Metrics
```

**Length**: 200-250 lines
**Readability Target**: 75-80 Flesch
**Type Purity Target**: >95%

**Note**: This partially overlaps with existing LAYER_4_IMPLEMENTATION_SUMMARY.md. Can consolidate/reference rather than duplicate.

**Write**: 0.5-1 hour (mostly consolidation)

---

### Migration Checklist

- [ ] **Backup original**: Copy `docs/guides/HOW_TO_INVOKE_REVIEWERS.md` to `docs/guides/HOW_TO_INVOKE_REVIEWERS.md.bak`
- [ ] **Write Document 1**: HOW_TO_INVOKE_REVIEWERS.md (how-to) from lines 122-159, 316-404
- [ ] **Write Document 2**: REVIEWER_AGENTS_REFERENCE.md (reference) from lines 30-65, 436-477
- [ ] **Write Document 3**: LAYER_4_ADVERSARIAL_VERIFICATION_OVERVIEW.md (explanation) or consolidate with existing summary
- [ ] **Add Cross-References**:
  - How-to doc: "For background on why reviewers matter, see LAYER_4_ADVERSARIAL_VERIFICATION_OVERVIEW.md"
  - How-to doc: "For agent specifications, see REVIEWER_AGENTS_REFERENCE.md"
  - Reference doc: "For how to invoke reviewers, see HOW_TO_INVOKE_REVIEWERS.md"
- [ ] **Validate Type Purity**: Each doc should be >95% single type
- [ ] **Check Readability**: Target Flesch 75-80
- [ ] **Review Links**: Ensure all internal references work
- [ ] **Delete Original**: Remove mixed HOW_TO_INVOKE_REVIEWERS.md
- [ ] **Update Index**: Add new docs to any documentation index/TOC

---

## Action 2: Reorganize LAYER_4_INTEGRATION_GUIDE.md

**Estimated Effort**: 4-5 hours
**Priority**: CRITICAL (Week 1-2)
**Current State**: 903 lines, 4 mixed content types (45% how-to + 40% reference + 15% explanation)
**Target State**: 4 separate documents, each >90% single type

### Problem Analysis

Current document serves four incompatible audiences:

| Audience | Needs | Current Mix |
|----------|-------|------------|
| Developers | Code examples (how-to) + API contracts (reference) | Mixed with user/DevOps |
| Users | CLI workflows (how-to) + command examples | Mixed with code examples |
| DevOps | Pipeline YAML (how-to) + configuration (reference) | Mixed with developer code |
| All | Error handling, contracts, configuration (reference) | Scattered throughout |

**Problem**: Developer looking for `ReviewRequest` interface finds CLI commands. User looking for `nwave review` command finds Python code.

### Solution: Create 4 Documents

#### Document 1: LAYER_4_API_REFERENCE.md (Reference)

**Purpose**: API contracts, interfaces, and configuration for all integration types

**Content** (Source from current lines 130-200, 698-767):
- ReviewRequest interface
- ReviewResult interface
- ReviewApproval interface
- ReviewFeedback structure
- Issue interface
- ReviewCriteria interface
- Error types and exceptions
- Environment variables (complete list)
- Configuration file (.nwave/layer4.yaml) schema
- Default values and overrides

**Structure**:
```
1. Input Contracts
   ├─ ReviewRequest
   ├─ Artifact
   └─ ReviewCriteria

2. Output Contracts
   ├─ ReviewResult
   ├─ ReviewApproval
   ├─ ReviewFeedback
   ├─ Issue
   └─ ReviewMetrics

3. Error Handling
   ├─ ReviewerNotFoundError
   ├─ MaxIterationsExceededError
   ├─ ReviewerDisagreementError
   └─ ArtifactValidationError

4. Configuration
   ├─ Environment Variables
   ├─ .nwave/layer4.yaml Schema
   ├─ Configuration Examples
   └─ Default Values

5. Quick Reference Tables
```

**Length**: 300-350 lines
**Readability Target**: 70-75 Flesch (reference acceptable at higher readability)
**Type Purity Target**: >98%

**Write**: 1.5-2 hours

---

#### Document 2: LAYER_4_FOR_DEVELOPERS.md (How-to)

**Purpose**: Programmatic integration for developers

**Content** (Source from current lines 24-128, 202-235):
- Basic Python and TypeScript invocation examples
- Advanced: Custom review criteria
- Error handling patterns
- Review orchestration API
- Workflow patterns
- Testing reviewer invocation

**Structure**:
```
1. Quick Start (Python and TypeScript examples)
2. Basic Invocation Pattern
3. Advanced: Custom Review Workflow
4. Error Handling
   ├─ ReviewerNotFoundError
   ├─ MaxIterationsExceededError
   └─ Other exceptions
5. Review Orchestration API
6. Integration Patterns
7. Testing Reviewer Invocation
8. Troubleshooting
```

**Length**: 200-250 lines
**Readability Target**: 75-80 Flesch
**Type Purity Target**: >95%

**Note**: Cross-reference to LAYER_4_API_REFERENCE.md for contract details

**Write**: 1.5 hours

---

#### Document 3: LAYER_4_FOR_USERS.md (How-to)

**Purpose**: Manual review workflows via CLI and interactive mode

**Content** (Source from current lines 245-405):
- Manual review request (CLI)
- Review specific dimensions
- Interactive review mode
- Interpreting YAML feedback
- Revision and re-submission
- Understanding iteration limits
- When review fails (escalation)

**Structure**:
```
1. Quick Start
   └─ Copy-paste command for first review

2. Manual Review Request
   ├─ Basic command
   ├─ Review specific dimensions
   └─ Output interpretation

3. Interactive Review Mode
   ├─ Artifact selection
   ├─ Reviewer selection
   ├─ Dimension selection

4. Understanding Feedback
   ├─ Strengths section
   ├─ Critical issues
   ├─ Recommendations
   └─ Approval status

5. Revision Workflow
   ├─ Addressing feedback
   ├─ Re-submission process
   └─ Iteration 2 approval

6. When Review Fails (Escalation)

7. Troubleshooting
```

**Length**: 200-250 lines
**Readability Target**: 75-80 Flesch
**Type Purity Target**: >95%

**Note**: Cross-reference to LAYER_4_API_REFERENCE.md for configuration details

**Write**: 1.5 hours

---

#### Document 4: LAYER_4_FOR_CICD.md (How-to)

**Purpose**: CI/CD pipeline integration examples

**Content** (Source from current lines 414-695):
- GitHub Actions integration (complete workflow)
- GitLab CI integration
- Jenkins pipeline integration
- Pass/fail criteria configuration
- Metrics collection and export
- Troubleshooting pipeline issues

**Structure**:
```
1. Quick Start (GitHub Actions)
2. GitHub Actions Integration
   ├─ Workflow file (.github/workflows/layer4-review.yml)
   ├─ Configuration
   ├─ PR comments
   └─ Artifact upload

3. GitLab CI Integration
   ├─ .gitlab-ci.yml configuration
   ├─ Stages and jobs
   └─ Artifact collection

4. Jenkins Pipeline Integration
   ├─ Jenkinsfile structure
   ├─ Pipeline stages
   └─ Reporting

5. Pass/Fail Criteria
   ├─ Blocking criteria
   ├─ Warning criteria
   └─ Custom thresholds

6. Metrics Collection
   ├─ Prometheus export
   ├─ Datadog export
   ├─ CloudWatch export
   └─ Custom metrics

7. Troubleshooting
   ├─ Workflow failures
   ├─ Configuration issues
   └─ Debugging commands

8. Best Practices
```

**Length**: 250-300 lines
**Readability Target**: 75-80 Flesch
**Type Purity Target**: >95%

**Note**: Cross-reference to LAYER_4_API_REFERENCE.md for configuration details

**Write**: 1.5-2 hours

---

### Migration Checklist

- [ ] **Backup original**: Copy current `docs/guides/LAYER_4_INTEGRATION_GUIDE.md` to `.bak`
- [ ] **Write Document 1**: LAYER_4_API_REFERENCE.md (1.5-2 hours)
- [ ] **Write Document 2**: LAYER_4_FOR_DEVELOPERS.md (1.5 hours)
- [ ] **Write Document 3**: LAYER_4_FOR_USERS.md (1.5 hours)
- [ ] **Write Document 4**: LAYER_4_FOR_CICD.md (1.5-2 hours)
- [ ] **Add Cross-References** (all 4 documents should cross-reference):
  - "For API contracts, see LAYER_4_API_REFERENCE.md"
  - "For code examples, see LAYER_4_FOR_DEVELOPERS.md"
  - "For CLI workflows, see LAYER_4_FOR_USERS.md"
  - "For CI/CD setup, see LAYER_4_FOR_CICD.md"
  - All reference back to: LAYER_4_IMPLEMENTATION_SUMMARY.md (explanation)
- [ ] **Validate Type Purity**: Each doc should be >90% single type
- [ ] **Check Readability**: Target Flesch 75-80
- [ ] **Review Code Examples**: Ensure all Python/TypeScript compile correctly
- [ ] **Test CLI Commands**: Verify command examples work as documented
- [ ] **Review Cross-Links**: Ensure all references resolve
- [ ] **Delete Original**: Remove mixed LAYER_4_INTEGRATION_GUIDE.md
- [ ] **Update Documentation Index**: Add 4 new docs to any TOC

---

## Action 3: Extract Reference from jobs-to-be-done-guide.md

**Estimated Effort**: 2-3 hours
**Priority**: MEDIUM (Week 2-3)
**Current State**: Framework explanation (70%) + reference tables (25%) + examples (5%)
**Target State**: Pure explanation (90%+) + separate reference document

### Problem Analysis

Current document is primarily explanation (70% purity) with embedded reference tables:
- Command Reference Matrix (lines 624-666)
- Agent Selection Guide (lines 481-510)
- File Locations (lines 668-682)

While this doesn't violate the 80% minimum, tables interrupt explanation flow.

### Solution: Create 1 Reference Document

#### Extract: NW_COMMANDS_REFERENCE.md (Reference)

**Content** (Source from current lines 624-666, 481-510):
- Complete wave command reference
- Cross-wave command reference
- Utility command reference
- Agent selection guide (who to use for what)
- File location reference
- Parameter descriptions for each command

**Structure**:
```
1. Discovery Wave Commands
   ├─ /nw:start
   ├─ /nw:discuss
   ├─ /nw:design
   ├─ /nw:distill
   └─ /nw:skeleton

2. Execution Loop Commands
   ├─ /nw:baseline
   ├─ /nw:roadmap
   ├─ /nw:split
   ├─ /nw:execute
   ├─ /nw:review
   ├─ /nw:finalize
   └─ /nw:deliver

3. Cross-Wave Commands
   ├─ /nw:research
   ├─ /nw:root-why
   ├─ /nw:mikado
   ├─ /nw:refactor
   ├─ /nw:develop
   └─ /nw:diagram

4. Utility Commands
   ├─ /nw:git
   └─ /nw:forge

5. Agent Selection Guide
   ├─ Core wave agents
   ├─ Cross-wave specialist agents
   ├─ Utility agents
   └─ Reviewer agents

6. File Location Reference
   ├─ Research files
   ├─ Embedded knowledge
   ├─ Workflow artifacts
   └─ Documentation
```

**Length**: 150-200 lines
**Type Purity Target**: >98%

**Update Original**: jobs-to-be-done-guide.md
- Remove command reference matrix
- Remove agent selection guide
- Keep agent explanations (why to use each agent)
- Add cross-reference: "For complete command reference, see NW_COMMANDS_REFERENCE.md"
- Add cross-reference to file locations section

**Result**:
- Original doc: 90%+ explanation (up from 70%)
- New doc: 98%+ reference
- Both docs cleaner and more focused

**Write**: 1.5-2 hours

---

### Migration Checklist

- [ ] **Create NW_COMMANDS_REFERENCE.md** (1.5-2 hours)
- [ ] **Update jobs-to-be-done-guide.md** (30 minutes):
  - Remove command reference matrix
  - Remove agent selection guide (move to reference)
  - Add cross-references to new reference doc
- [ ] **Validate Type Purity**: Original should be 90%+, new should be 98%+
- [ ] **Test Cross-References**: Ensure all links work
- [ ] **Update Documentation Index**: Add new reference doc

---

## Process Improvements (Week 3+)

### Establish DIVIO Classification Review

**Add to documentation style guide**:

1. **Classification Checklist for New Docs**:
   - [ ] Have I identified the primary user need? (task, lookup, understanding, learning)
   - [ ] Is my document primarily serving one need (80%+ in one quadrant)?
   - [ ] Could this serve multiple needs better as separate documents?
   - [ ] Does my document title match its type? (How-to, Reference, Explanation, Tutorial)

2. **Type Identification Quick Check**:
   - How-to: Can user accomplish a specific task? → Yes = How-to
   - Reference: Is this factual lookup content? → Yes = Reference
   - Explanation: Does this explain reasoning and context? → Yes = Explanation
   - Tutorial: Is this for complete newcomers? → Yes = Tutorial

3. **PR Review Checklist** (add to CONTRIBUTING.md):
   - [ ] Document classified by author (confirm in PR description)
   - [ ] Type purity ≥80%? (verify by reading)
   - [ ] Readability 70-80 Flesch? (can use automated tools)
   - [ ] Single user need served? (no task + lookup + explanation mixes)
   - [ ] Title reflects type? (How-to, Reference, Explanation, Tutorial)

### Template for DIVIO-Compliant Documentation

Provide template structure for each type:

**How-to Template**:
```
# How to [Accomplish Specific Task]

## Prerequisites
[What user must already know]

## Steps
1. [Clear step]
2. [Clear step]
...

## Verification
[How to confirm success]

## Troubleshooting
[Common failures and fixes]
```

**Reference Template**:
```
# [Thing Reference]

## Quick Lookup
[Table or alphabetical listing]

## Details
[Factual entries for each item]

## Configuration
[Settings and options]
```

**Explanation Template**:
```
# [Concept] Explained

## Overview
[What this is and why it matters]

## Core Concepts
[Definitions and relationships]

## How It Works
[The reasoning and mechanics]

## Why This Matters
[Benefits and rationale]

## When to Use
[Decision framework]
```

---

## Timeline and Assignments

### Week 1 (CRITICAL)

| Day | Task | Effort | Owner |
|-----|------|--------|-------|
| Mon-Tue | Action 1: Split HOW_TO_INVOKE_REVIEWERS.md | 3-4h | Documentation Lead |
| Tue-Wed | Action 2: Reorganize LAYER_4 (Documents 1-2) | 3h | Documentation Lead |
| Wed-Thu | Action 2: Reorganize LAYER_4 (Documents 3-4) | 2-2.5h | Documentation Lead |
| Thu-Fri | Review, cross-references, validation | 2h | Tech Lead + Peer Review |

**Week 1 Total**: 10-11.5 hours

### Week 2-3 (MEDIUM)

| Task | Effort | Owner |
|------|--------|-------|
| Action 3: Extract NW_COMMANDS_REFERENCE.md | 2-3h | Documentation Lead |
| Establish DIVIO review process | 1-2h | Tech Lead |
| Update style guide and templates | 1h | Documentation Lead |

**Week 2-3 Total**: 4-6 hours

**Grand Total**: 14-17.5 hours across 2-3 weeks

---

## Success Criteria

### Type Purity

- [ ] All 12 files achieve ≥80% type purity
- [ ] Critical files (currently 40-45%) reach >95%
- [ ] Jobs guide reaches 90%+

### Readability

- [ ] No files below 70 Flesch
- [ ] Target range 75-80 achieved by most files
- [ ] Collapsed documents improve from 58-62 to 75+

### User Experience

- [ ] How-to readers can find task steps without explanation noise
- [ ] Reference readers can find information quickly
- [ ] Explanation readers understand concepts without task distraction

### Compliance

- [ ] Classification verified by peer review
- [ ] Cross-references validated
- [ ] Documentation index updated
- [ ] All 16 resulting documents (currently 12) properly organized

### Process

- [ ] DIVIO classification checklist added to contribution guidelines
- [ ] PR review process includes type purity verification
- [ ] Documentation team trained on DIVIO classification

---

## Risks and Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Loss of content during split | Low | High | Backup originals; keep .bak files for 2 weeks |
| Broken cross-references | Medium | Medium | Comprehensive link validation before deletion |
| Inconsistent tone across new docs | Low | Low | Have single author review all 4 documents |
| User confusion from new structure | Low | Medium | Add index document explaining doc organization |

---

## Rollback Plan

If problems arise during implementation:

1. **Before executing any changes**: Backup all original files
2. **After each document creation**: Peer review before deleting original
3. **If issues found during peer review**: Restore from backup and revise
4. **If rollback needed**: Restore all backed-up originals; no loss of original content

---

## Questions to Answer Before Starting

1. **Who will execute these changes?** (Assign owner)
2. **When will peer review happen?** (Monday/Friday?)
3. **Do we need stakeholder approval on new structure?** (Check with documentation governance)
4. **Should we update documentation index/TOC simultaneously?** (Yes, recommend)
5. **What tools will we use for readability scoring?** (Flesch tool, hemingwayapp.com, or similar)

---

## How to Track Progress

Create a checklist issue in your project management tool with these sections:

- [ ] **Action 1: HOW_TO_INVOKE_REVIEWERS.md Split** (4h)
  - [ ] Backup original
  - [ ] Write how-to document
  - [ ] Write reference document
  - [ ] Write explanation document
  - [ ] Add cross-references
  - [ ] Peer review
  - [ ] Delete original

- [ ] **Action 2: LAYER_4_INTEGRATION_GUIDE.md Reorganize** (4-5h)
  - [ ] Backup original
  - [ ] Write API reference document
  - [ ] Write for-developers guide
  - [ ] Write for-users guide
  - [ ] Write for-CI-CD guide
  - [ ] Add cross-references
  - [ ] Peer review
  - [ ] Delete original

- [ ] **Action 3: Extract NW_COMMANDS_REFERENCE.md** (2-3h)
  - [ ] Create reference document
  - [ ] Update jobs-to-be-done-guide.md
  - [ ] Add cross-references
  - [ ] Peer review

- [ ] **Process Improvement** (2h)
  - [ ] Update CONTRIBUTING.md
  - [ ] Add style guide section
  - [ ] Create templates

---

**Status**: Ready to execute
**Next Step**: Assign owner and schedule Week 1 work
