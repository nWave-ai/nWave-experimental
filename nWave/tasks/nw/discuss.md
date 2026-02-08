# NW-DISCUSS: Requirements Gathering and UX Journey Design

**Wave**: DISCUSS (wave 2 of 6)
**Agents**: Luna (nw-leanux-designer), Riley (nw-product-owner)
**Command**: `/nw:discuss`

## Overview

Execute DISCUSS wave through collaborative UX journey design, requirements gathering, user story creation, and acceptance criteria definition. Luna designs the user journey first, then Riley creates requirements and stories informed by those journey artifacts. Establishes ATDD foundation for subsequent waves.

For greenfield projects (no src/ code, no docs/feature/ history), Riley proposes a Walking Skeleton as Feature 0 to validate architecture end-to-end before functional features.

## Interactive Decision Points

Before proceeding, the orchestrator asks the user:

### Decision 1: Feature Type
**Question**: What type of feature is this?
**Options**:
1. User-facing -- UI/UX functionality visible to end users
2. Backend -- APIs, services, data processing
3. Infrastructure -- DevOps, CI/CD, tooling
4. Cross-cutting -- Spans multiple layers (auth, logging, etc.)
5. Other -- user provides custom input

### Decision 2: Walking Skeleton
**Question**: Should we start with a walking skeleton?
**Options**:
1. Yes -- recommended for greenfield projects
2. Depends -- brownfield; Riley evaluates existing structure first
3. No -- feature is isolated enough to skip

### Decision 3: UX Research Depth
**Question**: Priority for UX research depth?
**Options**:
1. Lightweight -- quick journey map, focus on happy path
2. Comprehensive -- full experience mapping with emotional arcs
3. Deep-dive -- extensive user research, multiple personas, edge cases

## Context Files Required

- docs/project-brief.md - Project context and objectives
- docs/stakeholders.yaml - Stakeholder identification and roles
- docs/architecture/constraints.md - Technical and business constraints

## Previous Artifacts (Wave Handoff)

- docs/discovery/problem-validation.md - From DISCOVER wave
- docs/discovery/opportunity-tree.md - From DISCOVER wave
- docs/discovery/lean-canvas.md - From DISCOVER wave

## Agent Invocation

### Phase 1: UX Journey Design

@nw-leanux-designer

Execute UX journey design for {feature-name}.

**Context Files:**

- docs/project-brief.md
- docs/discovery/problem-validation.md
- docs/discovery/opportunity-tree.md

**Configuration:**

- interactive: high
- output_format: markdown
- research_depth: {from Decision 3}

### Phase 2: Requirements and User Stories

@nw-product-owner

Execute `/nw:discuss` for {feature-name}, informed by Luna's journey artifacts.

**Context Files:**

- docs/project-brief.md
- docs/stakeholders.yaml
- docs/architecture/constraints.md
- docs/feature/{feature-name}/discuss/ux-journey.md (from Luna)
- docs/feature/{feature-name}/discuss/experience-map.md (from Luna)

**Configuration:**

- interactive: high
- output_format: markdown
- elicitation_depth: comprehensive
- feature_type: {from Decision 1}
- walking_skeleton: {from Decision 2}

## Success Criteria

- [ ] UX journey map complete with emotional arcs and shared artifacts
- [ ] Requirements completeness score > 0.95
- [ ] Stakeholder consensus achieved
- [ ] All acceptance criteria testable
- [ ] Handoff accepted by solution-architect (DESIGN wave)

## Next Wave

**Handoff To**: nw-solution-architect (DESIGN wave)
**Deliverables**: See Riley's handoff package specification in agent file, plus Luna's journey artifacts

## Expected Outputs

```
docs/feature/{feature-name}/discuss/
  ux-journey.md
  experience-map.md
  requirements.md
  user-stories.md
  acceptance-criteria.md
  dor-checklist.md
```
