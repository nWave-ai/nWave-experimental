---
description: "Conducts Jobs-to-be-Done analysis, UX journey design, and requirements gathering through interactive discovery. Use when starting feature analysis, defining user stories, or creating acceptance criteria."
argument-hint: "[feature-name] - Optional: --phase=[jtbd|journey|requirements] --interactive=[high|moderate] --output-format=[md|yaml]"
---

# NW-DISCUSS: Jobs-to-be-Done Analysis, UX Journey Design, and Requirements Gathering

**Wave**: DISCUSS (wave 2 of 6)
**Agent**: Luna (nw-product-owner)
**Command**: `/nw:discuss`

## Overview

Execute DISCUSS wave through Luna's integrated workflow: Jobs-to-be-Done analysis, UX journey discovery, emotional arc design, shared artifact tracking, requirements gathering, user story creation, and acceptance criteria definition. Luna starts by uncovering the jobs users are trying to accomplish, then maps those jobs to journeys and requirements. She handles the complete lifecycle from understanding user motivations through to DoR-validated stories ready for DESIGN wave. Establishes ATDD foundation for subsequent waves.

For greenfield projects (no src/ code, no docs/feature/ history), Luna proposes a Walking Skeleton as Feature 0 to validate architecture end-to-end before functional features.

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
2. Depends -- brownfield; Luna evaluates existing structure first
3. No -- feature is isolated enough to skip

### Decision 3: UX Research Depth
**Question**: Priority for UX research depth?
**Options**:
1. Lightweight -- quick journey map, focus on happy path
2. Comprehensive -- full experience mapping with emotional arcs
3. Deep-dive -- extensive user research, multiple personas, edge cases

### Decision 4: Number of User Jobs
**Question**: How many distinct jobs are your users trying to accomplish with this feature?
**Options**:
1. Single job -- one primary job to focus on
2. Multiple jobs (2-4) -- several related jobs, will need opportunity scoring
3. Unclear -- Luna will help discover and define the jobs through interview

## Context Files Required

- docs/project-brief.md - Project context and objectives
- docs/stakeholders.yaml - Stakeholder identification and roles
- docs/architecture/constraints.md - Technical and business constraints

## Previous Artifacts (Wave Handoff)

- docs/discovery/problem-validation.md - From DISCOVER wave
- docs/discovery/opportunity-tree.md - From DISCOVER wave
- docs/discovery/lean-canvas.md - From DISCOVER wave

## Agent Invocation

@nw-product-owner

Execute *jtbd-analysis for {feature-name}, then *journey informed by JTBD artifacts, then *gather-requirements informed by both.

Context files: see Context Files Required and Previous Artifacts above.

**Configuration:**

- format: visual | yaml | gherkin | all (default: all)
- research_depth: {from Decision 3}
- interactive: high
- output_format: markdown
- elicitation_depth: comprehensive
- feature_type: {from Decision 1}
- walking_skeleton: {from Decision 2}
- job_count: {from Decision 4}
- output_directory: docs/ux/{epic}/ (JTBD + journeys), docs/requirements/ (stories)

**Phase 1 -- Jobs-to-be-Done Analysis (REQUIRED):**

Luna uncovers the jobs users are trying to accomplish before designing journeys or writing stories. This grounds all subsequent artifacts in real user motivations.

1. **Job Discovery**: Luna asks the user to describe what their users are trying to accomplish. For each job, capture it in job story format: "When [situation], I want to [motivation], so I can [outcome]."
2. **Job Dimensions**: For each job, identify the functional dimension (the practical task), emotional dimension (how the user wants to feel), and social dimension (how the user wants to be perceived).
3. **Four Forces Analysis**: For each primary job, map the four forces by asking the user:
   - **Push** (current frustration): "What frustrated your users enough to request this change?"
   - **Pull** (desired future): "What would they be able to do that they cannot do now?"
   - **Anxiety** (adoption concerns): "What concerns do they have about adopting this?"
   - **Habit** (current behavior): "What current behavior would they have to change?"

   If interview transcripts, support tickets, or analytics data exist, Luna extracts forces from those artifacts instead of relying solely on the user's description.
4. **Opportunity Scoring** (when multiple jobs exist): Rank jobs by importance vs. satisfaction gap. Jobs with high importance and low current satisfaction represent the strongest opportunities. Produce a scored opportunity table.
5. **JTBD-to-Story Bridge**: Each job story feeds directly into user stories and acceptance criteria in Phase 3. Every user story must trace back to at least one job.

| Artifact | Path |
|----------|------|
| Job Stories | `docs/ux/{epic}/jtbd-job-stories.md` |
| Four Forces Analysis | `docs/ux/{epic}/jtbd-four-forces.md` |
| Opportunity Scores | `docs/ux/{epic}/jtbd-opportunity-scores.md` (when multiple jobs) |

**Phase 2 -- Journey Design:**

Luna runs deep discovery (questioning the user's mental model, emotional arc, shared artifacts, error paths) informed by the JTBD analysis, then produces visual journey + YAML schema + Gherkin scenarios. Each journey maps to one or more identified jobs.

| Artifact | Path |
|----------|------|
| Visual Journey | `docs/ux/{epic}/journey-{name}-visual.md` |
| Journey Schema | `docs/ux/{epic}/journey-{name}.yaml` |
| Gherkin Scenarios | `docs/ux/{epic}/journey-{name}.feature` |
| Artifact Registry | `docs/ux/{epic}/shared-artifacts-registry.md` |

**Phase 3 -- Requirements and User Stories:**

Luna crafts LeanUX user stories informed by her JTBD analysis and journey artifacts. Every user story traces back to at least one job story. Validates against DoR, invokes peer review, and prepares handoff package.

| Artifact | Path |
|----------|------|
| Requirements | `docs/requirements/requirements.md` |
| User Stories | `docs/requirements/user-stories.md` |
| Acceptance Criteria | `docs/requirements/acceptance-criteria.md` |
| DoR Checklist | `docs/requirements/dor-checklist.md` |

## Success Criteria

- [ ] JTBD analysis complete: all user jobs captured in job story format
- [ ] Job dimensions identified: functional, emotional, and social for each job
- [ ] Four Forces mapped for each job (push, pull, anxiety, habit)
- [ ] Opportunity scores produced (when multiple jobs exist)
- [ ] UX journey map complete with emotional arcs and shared artifacts
- [ ] Every journey maps to at least one identified job
- [ ] Discovery complete: user mental model understood, no vague steps
- [ ] Happy path defined: all steps from start to goal with expected outputs
- [ ] Emotional arc coherent: confidence builds progressively, no jarring transitions
- [ ] Shared artifacts tracked: every ${variable} has a single documented source
- [ ] Requirements completeness score > 0.95
- [ ] Every user story traces to at least one job story
- [ ] All acceptance criteria testable
- [ ] DoR passed: all 8 items validated with evidence
- [ ] Peer review approved
- [ ] Handoff accepted by solution-architect (DESIGN wave)

## Next Wave

**Handoff To**: nw-solution-architect (DESIGN wave)
**Deliverables**: Luna's complete package -- JTBD artifacts (job stories, four forces, opportunity scores) + journey artifacts (visual, YAML, Gherkin, artifact registry) + requirements (stories, acceptance criteria, DoR validation, peer review approval)

## Expected Outputs

```
docs/ux/{epic}/
  jtbd-job-stories.md
  jtbd-four-forces.md
  jtbd-opportunity-scores.md    (when multiple jobs)
  journey-{name}-visual.md
  journey-{name}.yaml
  journey-{name}.feature
  shared-artifacts-registry.md

docs/requirements/
  requirements.md
  user-stories.md               (each story traces to a job)
  acceptance-criteria.md
  dor-checklist.md
```

## Examples

### Example 1: User-facing feature with comprehensive UX research
```
/nw:discuss first-time-setup
```
Orchestrator asks Decision 1-4. User selects "User-facing", "No skeleton", "Comprehensive", "Multiple jobs". Luna starts with JTBD analysis: discovers jobs like "When I first open the app, I want to feel productive immediately, so I can justify the purchase." Maps four forces for each job. Scores opportunities. Then runs journey discovery informed by JTBD, produces visual journey + YAML + Gherkin. Finally crafts stories where each traces to a job, validates DoR, and prepares handoff.

### Example 2: JTBD-only invocation
```
/nw:discuss --phase=jtbd onboarding-flow
```
Runs only Luna's JTBD analysis phase (job discovery + dimensions + four forces + opportunity scoring). Produces JTBD artifacts without proceeding to journey design or requirements. Useful for early discovery when you need to understand user motivations before committing to UX design.

### Example 3: Journey-only invocation
```
/nw:discuss --phase=journey release-nwave
```
Runs only Luna's journey design phases (discovery + visualization + coherence validation). Produces journey artifacts without proceeding to requirements crafting. Useful when JTBD is already done and journey design needs standalone iteration.

### Example 4: Requirements-only invocation
```
/nw:discuss --phase=requirements new-plugin-system
```
Runs only Luna's requirements phases (gathering + crafting + DoR validation). Assumes JTBD and journey artifacts already exist or are not needed (e.g., backend feature).
