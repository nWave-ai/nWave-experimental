# NW-ROADMAP: Goal Planning

**Wave**: CROSS_WAVE
**Agent**: Architect (nw-solution-architect) or domain-appropriate agent

## Overview

Dispatches an expert agent to create a structured YAML roadmap for achieving a goal. The roadmap is the single source of truth for step execution -- the orchestrator extracts context directly from it (no intermediate step files).

Output: `docs/feature/{project-id}/roadmap.yaml`

## Usage

```bash
/nw:roadmap @nw-solution-architect "Migrate monolith to microservices"
/nw:roadmap @nw-software-crafter "Replace legacy authentication system"
/nw:roadmap @nw-product-owner "Implement multi-tenant support"
```

## Agent Invocation

Parse parameters:
1. Agent name (after @, validated against agent registry)
2. Goal description (quoted string)

@{agent-name}

Create a comprehensive roadmap for: {goal-description}

**Context files to pass** (if available):
- Measurement baseline (inline from orchestrator, not separate file)
- docs/refactoring/mikado-graph.md (if Mikado methodology)
- Relevant existing documentation

**Configuration:**
- output: docs/feature/{project-id}/roadmap.yaml
- schema_version: "2.0"
- methodology: standard | mikado

## Invocation Principles

Keep the prompt minimal. The agent knows roadmap structure, YAML format, and planning methodology.

Pass: project ID + goal description + measurement context (if available).
Do not pass: YAML templates, phase guidance, step decomposition rules.

For performance roadmaps, include measurement context inline so the agent can validate targets against baselines and prioritize by impact.

## Success Criteria

### Dispatcher (you)
- [ ] Agent name parsed and validated
- [ ] Goal description extracted
- [ ] Task tool invoked with agent and goal

### Agent output (reference)
- [ ] Valid YAML at docs/feature/{project-id}/roadmap.yaml
- [ ] Steps are self-contained and atomic (executable without prior context)
- [ ] Acceptance criteria are behavioral and measurable
- [ ] Step decomposition ratio <= 2.5 (steps / production files)
- [ ] Dependencies mapped, time estimates provided
- [ ] Mikado integration included if methodology: mikado

## Error Handling

- Invalid agent: report valid agents and stop
- Missing goal: show usage syntax and stop

## Workflow Context

```bash
/nw:roadmap @agent "goal"           # 1. Plan
/nw:execute @agent "project" "01-01" # 2. Execute steps
/nw:finalize @agent "project"        # 3. Finalize
```

## Examples

### Example 1: Standard architecture roadmap
```
/nw:roadmap @nw-solution-architect "Migrate authentication to OAuth2"
```
Dispatcher parses agent=nw-solution-architect, goal="Migrate authentication to OAuth2", invokes Task tool. Agent produces docs/feature/auth-oauth2-migration/roadmap.yaml.

### Example 2: Performance roadmap with measurement context
```
/nw:roadmap @nw-solution-architect "Optimize test suite execution"
```
Orchestrator (develop.md) passes measurement data inline. Agent validates targets against baseline, prioritizes largest bottleneck first, identifies quick wins for Phase 1.

### Example 3: Mikado refactoring
```
/nw:roadmap @nw-software-crafter "Extract payment module from monolith"
```
Agent sets methodology: mikado, references docs/refactoring/mikado-graph.md, maps leaf nodes to implementation steps with discovery tracking.
