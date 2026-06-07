---
description: "Generates C4 architecture diagrams (context, container, component) in Mermaid or PlantUML. Use when creating or updating architecture visualizations."
argument-hint: "[diagram-type] - Optional: --format=[mermaid|plantuml|c4] --level=[context|container|component]"
---

# NW-DIAGRAM: Architecture Diagram Generation

**Wave**: CROSS_WAVE | **Agent**: Morgan (nw-solution-architect) | **Command**: `*create-diagrams`

## Overview

Generate architecture diagrams from design documents. Supports C4 model levels (context|container|component) in Mermaid|PlantUML|C4 format. Audience-appropriate: high-level context for stakeholders|component details for developers|deployment topology for operations.

## Context Files Required

- docs/product/architecture/brief.md (SSOT — component boundaries, technology stack, design decisions)

## Agent Invocation

@nw-solution-architect

Execute \*create-diagrams for {architecture-component}.

**Context Files:** docs/product/architecture/brief.md

**Configuration:**
- diagram_type: component (component|deployment|sequence|data|context)
- format: mermaid (mermaid|plantuml|c4)
- level: container (context|container|component)
- output_directory: docs/product/architecture/

## Progress Tracking

The invoked agent MUST create a task list from its workflow phases at the start of execution using TaskCreate. Each phase becomes a task with the gate condition as completion criterion. Mark tasks in_progress when starting each phase and completed when the gate passes. This gives the user real-time visibility into progress.

## Success Criteria

- [ ] Diagrams accurately represent current architecture
- [ ] Audience-appropriate detail level applied
- [ ] Diagrams render without syntax errors
- [ ] Output files created in configured directory

## Next Wave

**Handoff To**: {invoking-agent-returns-to-workflow}
**Deliverables**: Architecture diagrams in configured format

## Examples

### Example 1: Generate C4 container diagram
```
/nw-diagram payment-service --diagram_type=component --format=mermaid --level=container
```
Morgan reads architecture docs and produces a Mermaid container diagram showing service boundaries, data stores, and external integrations.

## Expected Outputs

```
docs/product/architecture/
  system-context.{ext}
  component-architecture.{ext}
  deployment-architecture.{ext}
```
