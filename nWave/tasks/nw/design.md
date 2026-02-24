---
description: "Designs system architecture with C4 diagrams and technology selection. Use when defining component boundaries, choosing tech stacks, or creating architecture documents."
argument-hint: "[component-name] - Optional: --residuality --paradigm=[auto|oop|fp]"
---

# NW-DESIGN: Architecture Design

**Wave**: DESIGN (wave 3 of 6)
**Agents**: Morgan (nw-solution-architect)
**Command**: `*design-architecture`

## Overview

Execute DESIGN wave through discovery-driven architecture design. Morgan asks about business drivers and constraints first, then recommends architecture that fits -- no pattern menus, no upfront style selection.

Morgan analyzes the existing codebase, evaluates open-source alternatives, and produces C4 diagrams (Mermaid) as mandatory output.

## Context Files Required

- docs/feature/{feature-name}/discuss/requirements.md - From DISCUSS wave
- docs/feature/{feature-name}/discuss/user-stories.md - From DISCUSS wave
- docs/feature/{feature-name}/discuss/domain-model.md - From DISCUSS wave
- docs/feature/{feature-name}/discuss/ux-journey.md - From DISCUSS wave
- docs/feature/{feature-name}/discuss/jtbd-job-stories.md - Job stories from DISCUSS wave (JTBD Phase 1)
- docs/feature/{feature-name}/discuss/jtbd-four-forces.md - Four Forces analysis from DISCUSS wave
- docs/feature/{feature-name}/discuss/jtbd-opportunity-scores.md - Opportunity scores (if multiple jobs)
- docs/feature/{feature-name}/design/constraints.md - Technical and business constraints

## Discovery Flow

Architecture decisions are driven by quality attributes, not pattern shopping:

### Step 1: Understand the Problem
Review JTBD artifacts from the DISCUSS wave to understand which jobs the architecture must serve.
Morgan asks: What are we building? For whom? What quality attributes matter most? (scalability, maintainability, testability, time-to-market, fault tolerance, auditability)

### Step 2: Understand Constraints
Morgan asks: Team size and experience? Timeline? Existing systems to integrate with? Regulatory requirements? Operational maturity (CI/CD, monitoring)?

### Step 3: Team Structure (Conway's Law)
Morgan asks: How many teams? How do they communicate? Does the proposed architecture match the org chart?

### Step 3.5: Development Paradigm Selection

Morgan identifies the primary language(s) from constraints, then applies this decision logic:

- **FP-native languages** (Haskell, F#, Scala, Clojure, Elixir): recommend Functional paradigm
- **OOP-native languages** (Java, C#, Go): recommend OOP paradigm
- **Multi-paradigm languages** (TypeScript, Kotlin, Python, Rust, Swift): present both options, let user choose based on team experience and domain fit

Morgan explains the choice and asks for user confirmation. After confirmation:
- Ask user permission to write the paradigm choice to the project's CLAUDE.md (at project root)
- If approved, write/append a `## Development Paradigm` section:
  - FP: `This project follows the **functional programming** paradigm. Use @nw-functional-software-crafter for implementation.`
  - OOP: `This project follows the **object-oriented** paradigm. Use @nw-software-crafter for implementation.`
- This enables all downstream commands to auto-detect the paradigm without re-asking

Default (if user declines to write or is unsure): OOP. The user can always override later.

### Step 4: Recommend Architecture Based on Drivers
Morgan recommends architecture based on the quality attribute priorities, constraints, and paradigm choice gathered in Steps 1-3.5. Default is modular monolith with dependency inversion (ports-and-adapters). Overrides require evidence. User can request a different approach.

If functional paradigm was selected, Morgan adapts architectural strategy:
- Types-first design: define algebraic data types and domain models before components
- Composition pipelines: data flows through transformation chains, not method dispatch
- Pure core / effect shell: domain logic is pure, IO lives at boundaries (adapters are functions)
- Effect boundaries replace port interfaces: function signatures serve as ports
- Immutable state: state changes produce new values, no mutation in the domain
These are strategic guidance items for the architecture document — no code snippets.

### Step 5: Advanced Architecture Stress Analysis (HIDDEN -- activated by `--residuality` flag only)
When activated: Morgan applies complexity-science-based stress analysis to identify how the architecture behaves under extreme and unexpected conditions. Generates stressors, identifies system attractors and residues, builds incidence matrix, and modifies architecture for resilience. See the `stress-analysis` skill for full methodology.

When not activated: Skip this step entirely. Do not mention or propose it.

### Step 6: Produce Deliverables
- Architecture document with component boundaries, tech stack, integration patterns
- C4 System Context diagram (Mermaid) -- MANDATORY
- C4 Container diagram (Mermaid) -- MANDATORY
- C4 Component diagrams (Mermaid) -- only for complex subsystems
- ADRs for significant decisions

## Agent Invocation

@nw-solution-architect

Execute \*design-architecture for {feature-name}.

Context files: see Context Files Required above.

**Configuration:**

- interactive: moderate
- output_format: markdown
- diagram_format: mermaid (C4)
- stress_analysis: {true if --residuality flag, false otherwise}

## Success Criteria

- [ ] Business drivers and constraints gathered before architecture selection
- [ ] Existing system analyzed before design (codebase search performed)
- [ ] Integration points with existing components documented
- [ ] Reuse vs. new component decisions justified
- [ ] Architecture supports all business requirements
- [ ] Technology stack selected with clear rationale
- [ ] Development paradigm selected and (optionally) written to project CLAUDE.md
- [ ] Component boundaries defined with dependency-inversion compliance
- [ ] C4 System Context diagram produced (Mermaid)
- [ ] C4 Container diagram produced (Mermaid)
- [ ] ADRs written with alternatives considered
- [ ] Handoff accepted by nw-platform-architect (DEVOP wave)

## Next Wave

**Handoff To**: nw-platform-architect (DEVOP wave)
**Deliverables**: See Morgan's handoff package specification in agent file

## Expected Outputs

```
docs/feature/{feature-name}/design/
  architecture-design.md       (includes C4 diagrams in Mermaid)
  technology-stack.md
  component-boundaries.md
  data-models.md
docs/adrs/
  ADR-NNN-*.md
CLAUDE.md (project root)   (optional: ## Development Paradigm section)
```
