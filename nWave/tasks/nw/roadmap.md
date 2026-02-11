---
description: "Create comprehensive planning document"
argument-hint: '[agent] [goal-description] - Example: @solution-architect "Migrate to microservices"'
---

# NW-ROADMAP: Goal Planning

**Wave**: CROSS_WAVE
**Agent**: Architect (nw-solution-architect) or domain-appropriate agent

## Overview

Dispatches an expert agent to fill in a pre-scaffolded YAML roadmap skeleton. The CLI tools handle structure; the agent handles content.

Output: `docs/feature/{project-id}/roadmap.yaml`

## Usage

```bash
/nw:roadmap @nw-solution-architect "Migrate monolith to microservices"
/nw:roadmap @nw-software-crafter "Replace legacy authentication system"
/nw:roadmap @nw-product-owner "Implement multi-tenant support"
```

## Workflow: 3-Step Pipeline

### Step 1: Parse and Scaffold

Parse parameters:
1. Agent name (after @, validated against agent registry)
2. Goal description (quoted string)
3. Derive project-id from goal (kebab-case, e.g., "Migrate to OAuth2" -> "migrate-to-oauth2")

Run the CLI to create a skeleton with TODO placeholders:

```bash
python -m des.cli.roadmap init \
  --project-id {project-id} \
  --goal "{goal-description}" \
  --output docs/feature/{project-id}/roadmap.yaml
```

If the init command exits non-zero, report the error and stop.

For complex projects, estimate phase/step counts and pass them:

```bash
python -m des.cli.roadmap init \
  --project-id {project-id} \
  --goal "{goal-description}" \
  --phases 3 --steps "01:3,02:2,03:1" \
  --output docs/feature/{project-id}/roadmap.yaml
```

### Step 2: Agent Fills Content

Invoke the agent via Task tool with:

```
@{agent-name}

Fill in the roadmap skeleton at docs/feature/{project-id}/roadmap.yaml.

The file has TODO placeholders — replace every TODO with real content.
Goal: {goal-description}

Do not change the YAML structure. Fill in: descriptions, acceptance criteria,
time estimates, dependencies, and step details.
```

**Context files to pass** (if available):
- Measurement baseline (inline from orchestrator)
- docs/refactoring/mikado-graph.md (if Mikado methodology)
- Relevant existing documentation

### Step 3: Validate (Hard Gate)

After the agent completes, run validation:

```bash
python -m des.cli.roadmap validate docs/feature/{project-id}/roadmap.yaml
```

Exit code handling:
- **0**: Validation passed. Report success.
- **1**: Validation errors found. Print the error output and stop. Do not proceed.
- **2**: Usage error. Report and stop.

This is a hard gate. If validation fails, the roadmap is not ready for execution.

## Invocation Principles

Keep the agent prompt minimal. The agent knows roadmap structure and planning methodology.

Pass: skeleton file path + goal description + measurement context (if available).
Do not pass: YAML templates, phase guidance, step decomposition rules.

For performance roadmaps, include measurement context inline so the agent can validate targets against baselines.

## Success Criteria

### Dispatcher (you)
- [ ] Parameters parsed (agent name, goal, project-id)
- [ ] Skeleton scaffolded via `des.cli.roadmap init`
- [ ] Agent invoked to fill TODO placeholders
- [ ] Validation passed via `des.cli.roadmap validate`

### Agent output (reference)
- [ ] All TODO placeholders replaced with real content
- [ ] Steps are self-contained and atomic
- [ ] Acceptance criteria are behavioral and measurable
- [ ] Step decomposition ratio <= 2.5 (steps / production files)
- [ ] Dependencies mapped, time estimates provided

## Error Handling

- Invalid agent: report valid agents and stop
- Missing goal: show usage syntax and stop
- Scaffold failure (exit 2): report CLI error and stop
- Validation failure (exit 1): print errors, do not proceed to execution

## Examples

### Example 1: Standard architecture roadmap
```
/nw:roadmap @nw-solution-architect "Migrate authentication to OAuth2"
```
Dispatcher derives project-id="migrate-auth-to-oauth2", scaffolds skeleton, invokes agent to fill TODOs, validates output. Agent produces docs/feature/migrate-auth-to-oauth2/roadmap.yaml.

### Example 2: Performance roadmap with measurement context
```
/nw:roadmap @nw-solution-architect "Optimize test suite execution"
```
Orchestrator passes measurement data inline. Agent fills skeleton, validates targets against baseline, prioritizes largest bottleneck first.

### Example 3: Mikado refactoring
```
/nw:roadmap @nw-software-crafter "Extract payment module from monolith"
```
Agent fills skeleton with methodology: mikado, references mikado-graph.md, maps leaf nodes to steps.

## Workflow Context

```bash
/nw:roadmap @agent "goal"           # 1. Plan (scaffold + fill + validate)
/nw:execute @agent "project" "01-01" # 2. Execute steps
/nw:finalize @agent "project"        # 3. Finalize
```
