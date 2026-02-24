---
name: jtbd-core
description: Core JTBD theory and job story format - job dimensions, job story template, job stories vs user stories, 8-step universal job map, outcome statements, and forces of progress
---

# JTBD Core Theory

Jobs-to-be-Done reframes product development around the progress customers seek rather than the products they buy. Customers "hire" products to accomplish specific jobs. The job exists independently of any solution.

## The Three Job Dimensions

Every job has three dimensions. Capture all three during discovery -- functional jobs surface first, but emotional and social jobs drive switching decisions.

**Functional**: The practical task to accomplish. Measurable, concrete, what the customer articulates first.
- "Deploy a new feature to production without downtime"
- "Identify the root cause of a performance regression"

**Emotional**: How the customer wants to feel (or avoid feeling). Internal, personal, often unarticulated.
- "Feel confident that my changes will not break production"
- "Feel in control of the project timeline despite changing requirements"

**Social**: How the customer wants to be perceived by others. Identity, status, professional reputation.
- "Be seen as a technically competent lead who makes sound decisions"
- "Demonstrate to stakeholders that the team delivers measurable value"

### Discovery Questions by Dimension

| Dimension | Questions |
|-----------|-----------|
| Functional | "What were you trying to accomplish?" / "Walk me through what you did." |
| Emotional | "How did that make you feel?" / "What were you worried about?" |
| Social | "Who else was involved or affected?" / "What would others think?" |

## Job Story Format

Job stories emphasize situation and motivation rather than persona and action.

```
When [situation/context],
I want to [motivation/capability],
so I can [expected outcome/benefit].
```

### Writing Tips

1. **Refine the situation with context**: "When I am nearly done with a document" beats "When I want to save a document"
2. **Focus on the job, not the task**: The job is the higher-level goal; the task is one possible way to achieve it
3. **Specify motivation, not implementation**: "I want to be confident my work is saved" not "I want a save button"
4. **Leave the design space open**: Job stories do not prescribe solutions
5. **Reveal the forces**: The story should hint at push (frustration), pull (desire), anxiety (risk), and habit (comfort)

### Worked Example

```markdown
## Job Story: Confident Production Deployment

**When** I am about to deploy a feature that touches payment processing,
**I want to** validate that all critical paths are covered by tests,
**so I can** deploy with confidence that revenue-generating flows will not break.

### Functional Job
Verify test coverage for critical business paths before deployment.

### Emotional Job
Feel confident and in control during high-stakes deployments.

### Social Job
Be trusted by the team as someone who ships reliably without causing incidents.

### Forces Analysis
- **Push**: Recent deployment broke checkout flow, causing revenue loss
- **Pull**: Automated coverage report would eliminate manual checking
- **Anxiety**: Will the coverage tool flag false negatives?
- **Habit**: Currently eyeballing test files manually before each deploy
```

## Job Stories vs User Stories

| Aspect | User Story | Job Story |
|--------|-----------|-----------|
| Format | As a [persona], I want to [action], so that [benefit] | When [situation], I want to [motivation], so I can [outcome] |
| Focus | Who the user is | What situation triggers the need |
| Anchoring | Identity/role | Context/circumstance |
| Grouping | Users grouped by role | Users grouped by situation |
| Design driver | Persona characteristics | Causality and context |

### When to Use Each

**Use job stories when**:
- Defining product strategy and discovering new opportunities
- Understanding why customers switch solutions
- Early-stage requirements where personas are not yet established
- The same job applies across multiple user roles

**Use user stories when**:
- Detailed implementation planning with known personas
- The development team needs clear scope boundaries
- Tracking work in a sprint backlog
- Communication with stakeholders who think in user profiles

**Use both together**: Job stories for strategic discovery, then translate into user stories for implementation. The job story reveals the *why*; the user story captures the *what to build*.

## The Translation Pipeline

```
Job Statement (strategic, solution-agnostic)
    |
    v
Job Story (contextual, situation-driven)
    |
    v
User Story (implementable, persona-driven)
    |
    v
Acceptance Criteria (testable conditions)
    |
    v
BDD Scenario (automatable Given-When-Then)
```

### Example Translation

**Job Statement**: "Help me manage deployment risk when releasing new features"

**Job Story**: "When I am about to deploy a feature that touches payment processing, I want to validate that all critical paths are covered by tests, so I can deploy with confidence."

**User Story**: "As a developer deploying to production, I want to see a test coverage report for critical paths before deployment, so that I can verify all revenue-critical flows are tested."

**Acceptance Criteria**:
- Test coverage for payment processing module is at least 90%
- Coverage report highlights any critical paths with less than 80% coverage
- Deployment is blocked if any critical path has zero test coverage

## The 8-Step Universal Job Map

All jobs follow this universal structure (Ulwick). Walk through all 8 steps to surface requirements that feature-driven thinking misses.

| Step | Description | Discovery Question |
|------|-------------|-------------------|
| 1. **Define** | Determine goals, plan approach, assess resources | "What information do users need before starting?" |
| 2. **Locate** | Gather necessary inputs, materials, information | "Where do users find the data/resources they need?" |
| 3. **Prepare** | Set up environment, organize inputs | "What setup or configuration is required?" |
| 4. **Confirm** | Verify readiness, validate inputs | "How do users confirm they have everything?" |
| 5. **Execute** | Perform the core task | "What is the primary action sequence?" |
| 6. **Monitor** | Check progress, verify results | "How do users know if things are working?" |
| 7. **Modify** | Adjust, handle exceptions, course-correct | "What do users do when something goes wrong?" |
| 8. **Conclude** | Finalize, clean up, assess outcome | "How do users wrap up and assess success?" |

### Worked Example: "Deploy Application to Production"

1. **Define**: Determine version to deploy, review change log, assess risk level
2. **Locate**: Find correct build artifact, gather deployment config, locate rollback scripts
3. **Prepare**: Set up deployment pipeline, configure environment variables, notify stakeholders
4. **Confirm**: Run pre-deployment checks, verify build integrity, confirm deployment window
5. **Execute**: Trigger deployment, apply database migrations, update routing
6. **Monitor**: Watch health checks, verify service responses, check error rates
7. **Modify**: Roll back if errors exceed threshold, scale resources, apply hotfix
8. **Conclude**: Update deployment log, notify team, archive deployment artifact

Steps 1-4 (Define through Confirm) are where most missing requirements hide. Teams jump straight to Execute without considering the full journey.

## Outcome Statements

Outcome statements express customer needs as measurable, solution-free metrics. Used in opportunity scoring (see `jtbd-opportunity-scoring` skill).

```
[Direction] + the [metric] + [object of control] + [contextual clarifier]
```

Direction: "Minimize" or "Maximize". Metric: time, likelihood, number, or frequency.

### Examples

- "Minimize the time it takes to determine which features are most important"
- "Minimize the likelihood of overlooking a critical edge case"
- "Maximize the likelihood that acceptance criteria cover all relevant scenarios"
- "Minimize the number of iterations needed to reach shared understanding"

### Quality Checks for Outcome Statements

- Solution-free: no reference to specific technology
- Measurable: can be rated on importance and satisfaction scales
- Controllable: the customer can assess whether the outcome improved
- Unambiguous: interpreted the same way by all stakeholders

## The Four Forces of Progress

For a switch to happen, Push + Pull must exceed Anxiety + Habit. Product teams often focus only on Pull (making their product attractive) while ignoring Anxiety and Habit reduction.

```
        PROGRESS (switching happens)
             ^
             |
Push of  ----+---- Pull of New
Current       |     Solution
Situation     |
             |
        NO PROGRESS (staying put)
             ^
             |
Anxiety  ----+---- Habit of
of New        |     Present
Solution      |
```

1. **Push** (demand-generating): Frustration with the current solution
2. **Pull** (demand-generating): Attractiveness of the alternative
3. **Anxiety** (demand-reducing): Fear, risk, learning curve of the new solution
4. **Habit** (demand-reducing): Familiarity, comfort, sunk costs with the current solution

### Forces Template

```markdown
## Forces Analysis: [Feature/Decision]

### Demand-Generating
- **Push**: [Current frustrations driving change]
- **Pull**: [Attractions of the new solution]

### Demand-Reducing
- **Anxiety**: [Fears about the new approach]
- **Habit**: [Inertia of the current approach]

### Assessment
- Switch likelihood: [High/Medium/Low]
- Key blocker: [Strongest demand-reducing force]
- Key enabler: [Strongest demand-generating force]
- Design implication: [What the product must do to tip the balance]
```

## Cross-References

- For interview techniques to discover jobs: load `jtbd-interviews` skill
- For prioritization using opportunity scoring: load `jtbd-opportunity-scoring` skill
- For translating jobs to BDD scenarios: load `jtbd-bdd-integration` skill
- For persona-level JTBD analysis: load `persona-jtbd-analysis` skill
- For workflow selection by job type: load `jtbd-workflow-selection` skill
