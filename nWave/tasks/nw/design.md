---
description: "Designs system architecture with C4 diagrams and technology selection. Use when defining component boundaries, choosing tech stacks, or creating architecture documents."
argument-hint: "[component-name] - Optional: --residuality --paradigm=[auto|oop|fp]"
---


# NW-DESIGN: Architecture Design

**Wave**: DESIGN (wave 3 of 6) | **Agents**: Morgan (nw-solution-architect), nw-system-designer, nw-ddd-architect | **Command**: `*design-architecture`

## Overview

Execute DESIGN wave through discovery-driven architecture design. The command routes to the right architect based on design scope: system-level (distributed architecture, scalability), domain-level (DDD, bounded contexts), or application-level (component boundaries, tech stack). Users choose an interaction mode — guided (collaborative Q&A) or propose (architect analyzes requirements and presents options with trade-offs). Analyzes existing codebase, evaluates open-source alternatives, produces C4 diagrams (Mermaid) as mandatory output.

## Interactive Decision Points

> **Default: DESIGN RUNS. Skipping DESIGN for a feature requires explicit HUMAN authorization — ASK, never self-authorize.** (Ale 2026-07-19.) DESIGN being an "optional" wave does NOT make skip the default: for a feature, run DESIGN by default. Emitting a `## Wave: DESIGN / [REF] Design Skipped` witness is an authorization act — per asymmetric-authority (controls veto, only humans authorize), it must be granted by the human on ask, never written by the spine/agent on its own. If you believe DESIGN can be skipped for this feature, STOP and ask the human; do not author the skip witness unilaterally.

### Decision 0: Design Scope (MANDATORY — do NOT skip)

**Question**: What are you designing?

You MUST ask this question before invoking any architect. Do NOT default to application scope. The answer determines WHICH agent to invoke.

**Options**:
1. **System / infrastructure** — distributed architecture, scalability, caching, load balancing, message queues → invokes @nw-system-designer
2. **Domain / bounded contexts** — DDD, aggregates, Event Modeling, event sourcing, context mapping → invokes @nw-ddd-architect
3. **Application / components** — component boundaries, hexagonal architecture, tech stack, ADRs → invokes @nw-solution-architect
4. **Full stack** — all three in sequence: system -> domain -> application → invokes all three agents sequentially

### Decision 1: Interaction Mode

**Question**: How do you want to work?

**Options**:
1. **Guide me** — the architect asks questions, you make decisions together
2. **Propose** — the architect reads your requirements and proposes 2-3 options with trade-offs

## Prior Wave Consultation

Before beginning DESIGN work, read SSOT and prior wave artifacts:

1. **SSOT** (if `docs/product/` exists):
   - `docs/product/architecture/brief.md` — current architecture to extend (if exists)
   - `docs/product/architecture/adr-*.md` — existing architectural decisions
   - `docs/product/journeys/{name}.yaml` — journey schema for port identification
   - `docs/product/vision.md`, `docs/product/jobs.yaml`, `docs/product/kpi-contracts.yaml` — value context that bounds the design
2. **DISCUSS** (primary input, ephemeral workspace while the delivery is open): read the current `user-stories.md`, `story-map.md` and `outcome-kpis.md` under the feature's DISCUSS output — functional requirements, scope, priority rationale and quality attributes. There is no separate decision-summary ledger to read; the durable product SSOT above is the authority these artifacts must agree with.

DISCUSS already synthesizes evidence into structured user stories. DESIGN reads SSOT architecture first (to extend, not recreate), then the open delivery's ephemeral DISCUSS artifacts for the delta.

**READING ENFORCEMENT**: You MUST read every file listed in Prior Wave Consultation above using the Read tool before proceeding. After reading, output a confirmation checklist (`✓ {file}` for each read, `⊘ {file} (not found)` for missing). Do NOT skip files that exist — skipping causes architectural decisions disconnected from requirements.

After reading, check whether any DESIGN decisions would contradict DISCUSS requirements. Flag contradictions and resolve with user before proceeding. Example: DISCUSS requires "real-time updates" but DESIGN chooses batch processing — this must be resolved.

## Downstream Correction (No Delta Artifact)

When a DESIGN decision contradicts a fact from an earlier wave, name the
conflicting canonical owner and correct it there — never in a side file:
- A stale user-story or acceptance-criterion assumption is returned to the
  product owner and corrected at its source (DISCUSS's own artifact, or
  `docs/product/` if it was already promoted).
- A stale architecture assumption is corrected in `docs/product/architecture/brief.md`
  or the relevant ADR directly.

State the original assumption, the new one and the rationale inline in the
corrected owner document. There is no `upstream-changes.md` ledger; the
correction *is* the update to the owning artifact (ADR Section 7).

## Discovery Flow

Architecture decisions driven by quality attributes, not pattern shopping:

### Step 1: Understand the Problem
Review JTBD artifacts from DISCUSS to understand which jobs the architecture must serve. Morgan asks: What are we building? For whom? Which quality attributes matter most? (scalability|maintainability|testability|time-to-market|fault tolerance|auditability)

### Step 2: Understand Constraints
Morgan asks: Team size/experience? Timeline? Existing systems to integrate? Regulatory requirements? Operational maturity (CI/CD, monitoring)?

### Step 3: Team Structure (Conway's Law)
Morgan asks: How many teams? Communication patterns? Does proposed architecture match org chart?

### Step 3.5: Development Paradigm Selection

Morgan identifies primary language(s) from constraints, then applies:

- **FP-native** (Haskell|F#|Scala|Clojure|Elixir): recommend Functional
- **OOP-native** (Java|C#|Go): recommend OOP
- **Multi-paradigm** (TypeScript|Kotlin|Python|Rust|Swift): present both, let user choose based on team experience and domain fit

After confirmation, ask user permission to write paradigm to project CLAUDE.md:
- FP: `This project follows the **functional programming** paradigm. Use @nw-functional-software-crafter for implementation.`
- OOP: `This project follows the **object-oriented** paradigm. Use @nw-software-crafter for implementation.`

Default if user declines/unsure: OOP. User can override later.

### Step 4: Recommend Architecture Based on Drivers
Recommend based on quality attribute priorities|constraints|paradigm from Steps 1-3.5. Default: modular monolith with dependency inversion (ports-and-adapters). Overrides require evidence.

If functional paradigm selected, Morgan adapts architectural strategy:
- Types-first design: define algebraic data types and domain models before components
- Composition pipelines: data flows through transformation chains, not method dispatch
- Pure core / effect shell: domain logic is pure, IO lives at boundaries (adapters are functions)
- Effect boundaries replace port interfaces: function signatures serve as ports
- Immutable state: state changes produce new values, no mutation in the domain
These are strategic guidance items for the architecture document — no code snippets.

### Step 5: Advanced Architecture Stress Analysis (HIDDEN -- `--residuality` flag only)
When activated: apply complexity-science-based stress analysis — stressors|attractors|residues|incidence matrix|resilience modifications. See `stress-analysis` skill.
When not activated: skip entirely, do not mention.

### Step 6: Produce Deliverables
- Architecture document with component boundaries|tech stack|integration patterns
- C4 System Context diagram (Mermaid) -- MANDATORY
- C4 Container diagram (Mermaid) -- MANDATORY
- C4 Component diagrams (Mermaid) -- only for complex subsystems
- ADRs for significant decisions

Record component boundaries, unbounded input/state domains, typed failures and
port invariants once in the durable architecture brief. Project only the facts
needed by one delivery into its existing `DeliveryContract.targets` boundary,
contract shape and obligations; do not create a per-feature design manifest.

## Rigor Profile Integration

Before dispatching the architect agent, read rigor config from `.nwave/des-config.json` (key: `rigor`). If absent, use standard defaults.

- **`agent_model`**: Pass as `model` parameter to Task tool. If `"inherit"`, omit `model` (inherits from session).
- **`reviewer_model`**: If design review is performed, use this model for the reviewer agent. If `"skip"`, skip design review.
- **`review_enabled`**: If `false`, skip post-design review step.

## Agent Invocation

### Architect Routing (based on Decision 0)

| Decision 0 | Agent | Focus |
|-------------|-------|-------|
| System / infrastructure | @nw-system-designer | Distributed architecture, scalability, caching, load balancing, message queues |
| Domain / bounded contexts | @nw-ddd-architect | DDD, aggregates, Event Modeling, event sourcing, context mapping |
| Application / components | @nw-solution-architect | Component boundaries, hexagonal architecture, tech stack, ADRs |
| Full stack | @nw-system-designer then @nw-ddd-architect then @nw-solution-architect | All three in sequence |

Pass Decision 1 (guide/propose) to the invoked agent via `interaction_mode` parameter in the Task tool config. If the agent is invoked in a direct session (not via Task), it asks the user for the mode.

All agents write to `docs/product/architecture/` (SSOT). Each architect owns its section:
- @nw-system-designer writes `## System Architecture` in `brief.md`
- @nw-ddd-architect writes `## Domain Model` in `brief.md`
- @nw-solution-architect writes `## Application Architecture` in `brief.md`

**Full stack invocation**: The orchestrator (this task file) makes 3 sequential Task calls:
1. Invoke @nw-system-designer → waits for completion → `brief.md` now has `## System Architecture`
2. Invoke @nw-ddd-architect → reads `## System Architecture` from brief.md → completes → `brief.md` now has `## Domain Model`
3. Invoke @nw-solution-architect → reads both prior sections → completes → `brief.md` has all 3 sections

Each agent reads `docs/product/architecture/brief.md` at start. If prior architects' sections exist, build on them without contradicting. If absent, proceed normally.

### Agent Dispatch (after Decision 0)

<!-- DES-WAVE: design -->

**Wave-entry dispatch marker contract.** Include the `<!-- DES-WAVE: design -->` marker line above verbatim in EVERY architect Agent dispatch prompt. For a wave-ENTERING dispatch this single marker is the COMPLETE and SUFFICIENT contract — it both declares the wave (so the PreToolUse hook arms enforcement via the INFERRED fallback even on runtimes whose prompt-submission anchor never fired) and is recognized by the spine as a legitimate entry that is EXEMPT from the WAVE_MARKER_BYPASS veto. Do not add `DES-VALIDATION`/`DES-PROJECT-ID`/`DES-STEP-ID` to the architect entry dispatch; the DES-WAVE marker can only ADD gating, never remove it.

**In-wave child dispatch (non-entering).** If you dispatch a FURTHER sub-agent while the wave is already active (not the entry dispatch), that child is NOT exempt. A child carrying no DES markers is DENIED loud as a wave bypass. Such a child MUST carry the wave's DES marker set — copy `<!-- DES-WAVE: design -->` plus the wave's `DES-*` markers from the parent dispatch onto the child prompt.

Based on Decision 0 answer, invoke the corresponding agent:

**System scope** → @nw-system-designer
**Domain scope** → @nw-ddd-architect
**Application scope** → @nw-solution-architect
**Full stack** → @nw-system-designer then @nw-ddd-architect then @nw-solution-architect (sequential, see Full Stack Invocation above)

Execute \*design-architecture for {feature-id}.

Context files: see Prior Wave Consultation above.

**Configuration:**
- model: rigor.agent_model (omit if "inherit")
- interaction_mode: {Decision 1: "guide" or "propose"}
- interactive: moderate
- output_format: markdown
- diagram_format: mermaid (C4)
- stress_analysis: {true if --residuality flag, false otherwise}

**SKILL_LOADING**: Read your skill files at `~/.claude/skills/nw/solution-architect/`. At Phase 4, always load: `architecture-patterns.md`, `architectural-styles-tradeoffs.md`. Then follow your Skill Loading Strategy table for phase-specific skills.

## Progress Tracking

The invoked agent MUST create a task list from its workflow phases at the start of execution using TaskCreate. Each phase becomes a task with the gate condition as completion criterion. Mark tasks in_progress when starting each phase and completed when the gate passes. This gives the user real-time visibility into progress.

## Success Criteria

- [ ] Business drivers and constraints gathered before architecture selection
- [ ] Existing system analyzed before design (codebase search performed)
- [ ] Integration points with existing components documented
- [ ] Reuse vs. new component decisions justified
- [ ] Architecture supports all business requirements
- [ ] Technology stack selected with clear rationale
- [ ] Development paradigm selected and (optionally) written to project CLAUDE.md
- [ ] Component boundaries defined with dependency-inversion compliance
- [ ] C4 System Context + Container diagrams produced (Mermaid)
- [ ] ADRs written with alternatives considered
- [ ] Handoff accepted by nw-platform-architect (DEVOPS wave)

## Next Wave

**Handoff To**: nw-platform-architect (DEVOPS wave)
**Deliverables**: See Morgan's handoff package specification in agent file

## SSOT Update

The durable product-level SSOT is the only normative handoff DEVOPS and
DISTILL read — not a per-wave decision file. Update it directly:

1. **Architecture SSOT**: Update `docs/product/architecture/brief.md` with new component boundaries, driving ports, and key decisions. Add consumer-labeled sections: `## For Acceptance Designer` (driving ports, test entry points) and `## For Software Crafter` (component boundaries, key decisions). If `brief.md` does not exist, create it.
2. **ADRs**: Write new ADRs to `docs/product/architecture/adr-*.md`. ADRs are permanent — they accumulate, never replaced.
3. **C4 diagrams**: Update `docs/product/architecture/c4-diagrams.md` with current component topology.

If `docs/product/architecture/` does not exist, create it. This is SSOT bootstrap for architecture.

## Expected Outputs

### SSOT updates (in `docs/product/architecture/`)
```
  brief.md                       (created or updated — includes C4 diagrams, consumer-labeled sections)
  adr-*.md                       (new ADRs for this feature)
  c4-diagrams.md                 (current component topology, if separate from brief)
```

### Optional
```
CLAUDE.md (project root)         (optional: ## Development Paradigm section)
```
