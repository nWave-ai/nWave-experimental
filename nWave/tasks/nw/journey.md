# NW-JOURNEY: Design User Experience Journey

**Wave**: DISCUSS
**Agent**: Luna (nw-leanux-designer)

## Overview

Design the optimal user experience for completing a goal. Luna conducts deep discovery questioning to understand the user's mental model and emotional journey, then produces visual artifacts (ASCII mockups, YAML schema, Gherkin scenarios) as proof of understanding.

The journey process catches horizontal integration failures before code by tracking shared artifacts across steps.

## Agent Invocation

@nw-leanux-designer

Execute \*journey for {goal-name}.

**Configuration:**

- format: visual | yaml | gherkin | all (default: all)
- output_directory: docs/ux/{epic}/

## Output Artifacts

| Artifact | Path |
|----------|------|
| Visual Journey | `docs/ux/{epic}/journey-{name}-visual.md` |
| Journey Schema | `docs/ux/{epic}/journey-{name}.yaml` |
| Gherkin Scenarios | `docs/ux/{epic}/journey-{name}.feature` |
| Artifact Registry | `docs/ux/{epic}/shared-artifacts-registry.md` |

## Success Criteria

- [ ] Discovery complete: user mental model understood, no vague steps
- [ ] Happy path defined: all steps from start to goal with expected outputs
- [ ] Emotional arc coherent: confidence builds progressively, no jarring transitions
- [ ] Shared artifacts tracked: every ${variable} has a single documented source
- [ ] Integration checkpoints validate cross-step consistency
- [ ] Example data is realistic, not generic placeholders

## Examples

### Example 1: User onboarding journey
```
/nw:journey first-time-setup
```
Luna asks discovery questions about the user's mental model, designs an emotional arc from confusion to confidence, produces ASCII mockups and Gherkin scenarios as proof of understanding.

## Next Wave

**Handoff To**: Riley (nw-product-owner) for story creation, or Quinn (nw-acceptance-designer) for E2E tests
**Deliverables**: Visual journey + YAML schema + Gherkin scenarios + artifact registry
