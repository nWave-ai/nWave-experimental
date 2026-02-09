# nWave Agent Quick Reference

**Purpose**: Fast reference for creating new agents using proven patterns from existing agents
**Version**: 1.0 (2025-10-03)
**Companion to**: AGENT_TEMPLATE.yaml

---

## Table of Contents

1. [Agent Type Selection](#agent-type-selection)
2. [Quick Start Examples](#quick-start-examples)
3. [YAML Frontmatter Patterns](#yaml-frontmatter-patterns)
4. [Persona Design Patterns](#persona-design-patterns)
5. [Command Patterns](#command-patterns)
6. [Dependency Patterns](#dependency-patterns)
7. [Quality Gates Patterns](#quality-gates-patterns)
8. [Common Pitfalls](#common-pitfalls)

---

## Agent Type Selection

### Decision Tree

```
What are you building?
│
├─ Single-responsibility expert? → SPECIALIST AGENT
│  Examples: business-analyst, acceptance-designer, software-crafter
│
├─ Multi-phase workflow coordinator? → ORCHESTRATOR AGENT
│  Examples: nWave-complete-orchestrator, atdd-focused-orchestrator
│
├─ Multi-agent collaborative system? → TEAM AGENT
│  Examples: nWave-core-team, nWave-greenfield-team
│
└─ Domain-specific tool? → SPECIALIZED TOOL AGENT
   Examples: visual-2d-designer, architecture-diagram-manager
```

---

## Quick Start Examples

### 1. Create a Specialist Agent (Most Common)

**File**: `my-new-agent.md`

````markdown
---
name: my-new-agent
description: Use for DELIVER wave - handles specific development task with focus on quality
model: inherit
---

# my-new-agent

ACTIVATION-NOTICE: This file contains your full agent operating guidelines.

```yaml
activation-instructions:
  - STEP 1: Read THIS ENTIRE FILE
  - STEP 2: Adopt persona defined below
  - STEP 3: Greet user with name/role and run `*help`
  - CRITICAL: On activation, ONLY greet, run `*help`, then HALT

agent:
  name: Taylor
  id: my-new-agent
  title: Development Quality Specialist
  icon: 🔧
  whenToUse: Use when you need focused quality improvement in development phase

persona:
  role: Development Quality Specialist
  style: Methodical, detail-oriented, pragmatic
  identity: Expert in code quality and systematic improvement
  focus: Quality metrics, refactoring, technical debt management
  core_principles:
    - Quality-First Approach - Never compromise on code quality
    - Measurable Improvements - All changes must be measurable
    - Incremental Progress - Small, validated steps over big leaps
    - Test Coverage - Every change must be tested
    - Documentation - Clear documentation for all decisions

commands:
  - help: Show numbered list of commands
  - analyze-quality: Analyze current code quality metrics
  - create-improvement-plan: Generate systematic improvement roadmap
  - execute-refactoring: Execute planned refactoring with validation
  - exit: Say goodbye and exit persona

dependencies:
  tasks:
    - dw/quality-analysis.md
  templates:
    - quality-report-tmpl.yaml
```
````

## Embedded Tasks

### dw/quality-analysis.md

[Task content here]

````

### 2. Create an Orchestrator Agent

**File**: `my-workflow-orchestrator.md`

```markdown
# my-workflow-orchestrator

ACTIVATION-NOTICE: This is a workflow orchestrator agent.

## Orchestrator Identity
**Workflow**: My Custom Workflow
**Description**: custom-workflow.yaml orchestration
**Methodology**: nWave (DISCOVER → DISCUSS → DESIGN → DEVOP → DISTILL → DELIVER)

## Phase Guidance

### 1. PREPARATION Wave
**Duration**: 1 day
**Objective**: Setup and validation
**Outputs**: Validated environment, ready dependencies

**Primary Agents**:
- **environment-validator** (environment_setup) - Priority: 1

[Continue for all phases...]
````

---

## YAML Frontmatter Patterns

### Standard Claude Code Agent

```yaml
---
name: agent-kebab-case-id
description: One-sentence description focusing on WHEN to use this agent and WAVE context
model: inherit
---
```

**Real Examples**:

```yaml
# From business-analyst.md
---
name: business-analyst
description:
  Use for DISCUSS wave - processing user requirements and creating structured
  requirements document for ATDD discuss phase. Facilitates stakeholder collaboration
  and extracts business requirements with acceptance criteria
model: inherit
---
```

```yaml
# From software-crafter.md
---
name: software-crafter
description:
  Use for complete DELIVER wave execution - implementing features through
  Outside-In TDD, managing complex refactoring roadmaps with Mikado Method, and systematic
  code quality improvement through progressive refactoring
model: inherit
---
```

**Key Points**:

- `name`: Always kebab-case, matches filename
- `description`: Starts with "Use for {WAVE} wave" when applicable
- `model: inherit`: Standard for all agents

---

## Persona Design Patterns

### Persona Structure

```yaml
persona:
  role: { Primary Professional Role }
  style: { Communication characteristics - 3-5 adjectives }
  identity: { Who the agent is - background and expertise }
  focus: { Primary areas of concentration }
  core_principles:
    - { Principle with explanation }
    - { Typically 5-10 principles }
```

### Real Examples

**Business Analyst (Riley)**:

```yaml
persona:
  role: Requirements Analyst & Stakeholder Collaboration Expert
  style: Inquisitive, systematic, collaborative, business-focused, clarity-oriented
  identity: Expert who transforms user needs into structured requirements, facilitates stakeholder discussions, and establishes foundation for ATDD workflow
  focus: Requirements gathering, stakeholder alignment, business value extraction, acceptance criteria definition
  core_principles:
    - Customer-Developer-Tester Collaboration - Core ATDD principle for shared understanding
    - Business Value Focus - Prioritize features that deliver maximum business impact
    - Requirements Clarity - Transform vague needs into precise, testable requirements
    - Stakeholder Alignment - Ensure all stakeholders share common understanding
```

**Visual Designer (Luma)**:

```yaml
persona:
  role: Expert 2D Animation Designer & Motion Director
  style: Concise, visually literate, iterative, production-minded, collaborative
  identity: Hybrid artist-technologist applying classical animation craft to modern pipelines
  focus: Storyboards, animatics, timing & spacing, lip-sync, camera & layout, export for film/web
  core_principles:
    - Principles-First: Apply Disney's 12 principles in every shot
    - Readability: Clear staging, silhouettes and arcs beat complexity
    - Timing-Driven: Plan exposure with X-sheets; mix ones/twos purposefully
```

**Pattern**: Each agent has unique personality but maintains professional consistency

---

## Command Patterns

### Standard Command List Structure

```yaml
commands:
  - help: Show numbered list of commands
  - { primary-command }: { Primary workflow command }
  - { secondary-command }: { Supporting command }
  - { validation-command }: { Quality check command }
  - exit: Say goodbye as {Role}, and abandon inhabiting this persona
```

### Real Examples

**Business Analyst Commands**:

```yaml
commands:
  - help: Show numbered list of the following commands to allow selection
  - gather-requirements: Facilitate comprehensive requirements gathering session with stakeholders
  - create-user-stories: Transform requirements into structured user stories with acceptance criteria
  - facilitate-discussion: Lead structured discussion sessions for requirement clarification
  - validate-requirements: Review and validate requirements against business objectives
  - create-project-brief: Generate comprehensive project brief with business context
  - analyze-stakeholders: Identify and analyze key stakeholders and their interests
  - define-acceptance-criteria: Create detailed acceptance criteria for user stories
  - handoff-design: Prepare requirements handoff package for solution-architect
  - exit: Say goodbye as the Requirements Analyst, and then abandon inhabiting this persona
```

**Software Crafter Commands** (consolidated from multiple specialists):

```yaml
commands:
  - help: Show available commands
  - develop: Execute Outside-In TDD implementation
  - refactor: Systematic refactoring with Mikado Method
  - validate-tests: Ensure test suite quality
  - handoff-deliver: Prepare handoff to DELIVER wave
  - exit: Exit development mode
```

**Key Patterns**:

- Always start with `help`
- Always end with `exit`
- Use verb-noun format: `create-stories`, `validate-requirements`
- Include wave handoff commands: `handoff-design`, `handoff-demo`

---

## Dependency Patterns

### Dependency Categories

```yaml
dependencies:
  tasks:           # Executable workflow files
    - dw/{task}.md
  templates:       # YAML/JSON templates for artifacts
    - {template}.yaml
  checklists:      # Validation checklists
    - {checklist}.md
  data:           # Reference data
    - {data}.yaml
  utils:          # Utility scripts/tools
    - {utility}.md
```

### Real Examples

**Business Analyst**:

```yaml
dependencies:
  tasks:
    - dw/discuss.md
  templates:
    - discuss-requirements-interactive.yaml
    - user-story-tmpl.yaml
    - acceptance-criteria-tmpl.yaml
  checklists:
    - requirements-quality-checklist.md
    - stakeholder-alignment-checklist.md
```

**Visual 2D Designer**:

```yaml
dependencies:
  checklists:
    - 12-principles-check.md
    - readability-pass.md
    - lip-sync-pass.md
    - export-specs.md
  templates:
    - style-brief.yaml
    - shot-card.md
    - x-sheet.csv
    - timing-chart.svg
  utils:
    - naming-convention.md
    - deliverables-folders.md
```

**Pattern**: Tasks are wave-specific workflows, templates generate artifacts, checklists validate quality

---

## Quality Gates Patterns

### Standard Quality Gates

```yaml
quality_gates:
  - { Validation criterion 1 }
  - { Validation criterion 2 }
  - { Completion check }
  - { Handoff readiness check }
```

### Real Examples

**Acceptance Designer**:

```yaml
quality_gates:
  - All acceptance tests follow Given-When-Then format
  - Production service integration patterns documented
  - Step methods call real production services via DI
  - No business logic in test infrastructure
  - One E2E test active at a time strategy established
  - Test framework configuration validated
  - All tests executable and initially failing
```

**Visual 2D Designer**:

```yaml
quality_gates:
  - 12-principles-check.md passes
  - readability-pass.md passes
  - lip-sync-pass.md passes (if dialogue)
  - export-specs.md validated against delivery profile
```

**Software Crafter** (implicit in workflow):

```yaml
quality_gates:
  - All tests passing (100% green)
  - Pre-commit hooks pass
  - No skipped tests in execution
  - Quality metrics meet thresholds
  - Code review completed
  - Documentation updated
```

**Pattern**: Gates are specific, measurable, and prevent progression until met

---

## Common Pitfalls

### ❌ Pitfall 1: External File Dependencies

**Problem**:

```yaml
dependencies:
  tasks:
    - tasks/my-task.md # Agent tries to load external file
```

**Solution**: Embed tasks inline

```markdown
## Embedded Tasks

### tasks/my-task.md

{Full task content here}
```

---

### ❌ Pitfall 2: Missing Activation Instructions

**Problem**: Agent doesn't know how to initialize

**Solution**: Always include full activation block

```yaml
activation-instructions:
  - STEP 1: Read THIS ENTIRE FILE
  - STEP 2: Adopt persona defined below
  - STEP 3: Greet user with name/role and immediately run `*help`
  - CRITICAL: On activation, ONLY greet user, auto-run `*help`, and then HALT
```

---

### ❌ Pitfall 3: Inconsistent Command Prefix

**Problem**: Commands without `*` prefix

```yaml
commands:
  - help # Missing * prefix
```

**Solution**: Document that commands REQUIRE `*` prefix

```markdown
# All commands require * prefix when used (e.g., *help)

commands:

- help: Show numbered list of commands
```

---

### ❌ Pitfall 4: Vague Core Principles

**Problem**:

```yaml
core_principles:
  - Quality is important
  - Be thorough
```

**Solution**: Specific, actionable principles

```yaml
core_principles:
  - Test-First Development - Write failing tests before implementation
  - Single Responsibility - Each component has one reason to change
  - Incremental Refactoring - Small, safe transformations over big rewrites
```

---

### ❌ Pitfall 5: Missing Handoff Specification

**Problem**: Agent doesn't prepare next wave

**Solution**: Include handoff command and specification

```yaml
commands:
  - handoff-{next-wave}: Prepare complete handoff package for {next-agent}

handoff:
  deliverables:
    - { Artifact 1 }
    - { Artifact 2 }
  next_agent: { next-agent-id }
  validation_checklist:
    - { Validation 1 }
```

---

## Pattern Summary Table

| Element           | Specialist | Orchestrator | Team   | Tool   |
| ----------------- | ---------- | ------------ | ------ | ------ |
| YAML Frontmatter  | ✅ Yes     | ❌ No        | ❌ No  | ❌ No  |
| Activation Notice | ✅ Yes     | ✅ Yes       | ✅ Yes | ✅ Yes |
| Persona Block     | ✅ Yes     | ❌ No        | ❌ No  | ✅ Yes |
| Commands          | ✅ Yes     | ❌ No        | ❌ No  | ✅ Yes |
| Embedded Tasks    | ✅ Yes     | ❌ No        | ✅ Yes | ❌ No  |
| Phase Guidance    | ❌ No      | ✅ Yes       | ❌ No  | ❌ No  |
| Team Composition  | ❌ No      | ❌ No        | ✅ Yes | ❌ No  |
| Pipeline          | Optional   | ❌ No        | ❌ No  | ✅ Yes |
| Quality Gates     | ✅ Yes     | ✅ Yes       | ✅ Yes | ✅ Yes |

---

## Wave-Specific Agent Examples

### DISCUSS Wave Agent

- **Type**: Specialist
- **Example**: business-analyst
- **Focus**: Requirements, stakeholders, acceptance criteria
- **Key Commands**: gather-requirements, create-user-stories, handoff-design

### DESIGN Wave Agent

- **Type**: Specialist or Tool
- **Examples**: solution-architect, architecture-diagram-manager
- **Focus**: Architecture, design patterns, visual documentation
- **Key Commands**: design-architecture, create-diagrams, handoff-distill

### DISTILL Wave Agent

- **Type**: Specialist
- **Example**: acceptance-designer
- **Focus**: Acceptance tests, Given-When-Then, test scenarios
- **Key Commands**: create-acceptance-tests, validate-scenarios, handoff-develop

### DELIVER Wave Agent

- **Type**: Specialist
- **Example**: software-crafter
- **Focus**: Outside-In TDD, refactoring, code quality
- **Key Commands**: deliver, refactor, validate-tests

### DELIVER Wave Agent

- **Type**: Specialist
- **Example**: feature-completion-coordinator
- **Focus**: Production readiness, deployment, stakeholder validation
- **Key Commands**: validate-production, prepare-delivery, measure-value

---

## Agent Naming Conventions

### File Names

- Format: `{agent-id}.md`
- Always kebab-case
- Examples: `business-analyst.md`, `software-crafter.md`, `visual-2d-designer.md`

### Persona Names

- Format: Single friendly name
- Examples: Riley, Quinn, Crafty, Apex, Luma, Taylor
- Should be memorable and distinctive

### Agent IDs

- Format: kebab-case matching filename
- Examples: `business-analyst`, `software-crafter`, `acceptance-designer`
- Used in `name:` frontmatter and `agent.id:`

### Command Names

- Format: verb-noun or verb
- Always lowercase
- Examples: `gather-requirements`, `create-diagrams`, `validate-tests`
- Runtime: `*{command}` (e.g., `*gather-requirements`)

---

## Integration with Build System

### Source → Build → Install Flow

```
nWave/agents/{agent}.md
    ↓
scripts/build-ide-bundle.sh
    ↓
dist/ide/agents/{agent}.md
    ↓
scripts/install-nwave.sh
    ↓
~/.claude/agents/nw/{agent}.md
```

### What Gets Bundled

- ✅ Agent specification files
- ✅ Embedded task content
- ✅ Templates referenced in dependencies
- ❌ External task files (must be embedded)

---

## Quick Checklist for New Agents

- [ ] YAML frontmatter with name, description, model
- [ ] Activation notice and instructions
- [ ] Agent identity (name, id, title, icon, whenToUse)
- [ ] Persona definition (role, style, identity, focus, principles)
- [ ] Command list (help first, exit last, \* prefix documented)
- [ ] Dependencies specified
- [ ] Tasks embedded inline
- [ ] Quality gates defined
- [ ] Handoff specification (if wave-based)
- [ ] File named correctly ({agent-id}.md)
- [ ] Testing: Agent activates and shows help
- [ ] Testing: Commands execute successfully
- [ ] Testing: Handoff produces expected artifacts

---

**Last Updated**: 2025-10-03
**See Also**: AGENT_TEMPLATE.yaml for full templates
