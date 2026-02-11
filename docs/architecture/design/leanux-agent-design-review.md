> **Note**: The build pipeline (dist/ide) referenced in this document was eliminated in the build-pipeline-elimination feature. This document is preserved for historical reference only.

# LeanUX Agent Design Review

**Reviewer**: Sage (agent-builder)
**Date**: 2026-01-30
**Status**: REVISED - New Agent Recommended (after Mike's challenge)

---

## Executive Summary

**Initial Position (WRONG)**: I initially recommended enhancing product-discoverer rather than creating a new agent.

**Revised Position (CORRECT)**: After Mike's challenge, I acknowledge I was conflating **discovery skills** with **design skills**. These are fundamentally different competencies:

| Skill Domain | product-discoverer (Scout) | LeanUX Designer (NEW) |
|--------------|---------------------------|----------------------|
| **Core Question** | "Is this worth building?" | "How should this feel to use?" |
| **Primary Method** | Mom Test interviews, JTBD | Journey mapping, prototyping |
| **Output Type** | Validated hypotheses | Experience blueprints |
| **Philosophy** | Evidence-based validation | Apple HIG, "form follows feeling" |
| **Artifact** | Lean Canvas, OST | User journey map, TUI mockups |

**My recommendation**: Create a dedicated **LeanUX Product Designer** agent that **pairs with** product-discoverer in the DISCUSS wave, bringing Apple design philosophy and horizontal coherence skills that Scout lacks.

---

## Part 1: Why I Was Wrong

### The Single Responsibility Argument (Corrected)

I argued that adding journey mapping to product-discoverer would be simpler. Mike correctly pointed out this violates single responsibility:

**product-discoverer's identity** (from actual spec):
```yaml
persona:
  role: Product Discovery Facilitator & Evidence-Based Learning Guide
  identity: Expert who guides teams through evidence-based product discovery
            using Mom Test interviewing, Jobs-to-be-Done analysis,
            Opportunity Solution Trees, and Lean Canvas validation.
```

Scout's DNA is **validation**: "Is the problem real? Is the opportunity valuable? Will the market pay?" These are **discovery** questions requiring **research** skills.

**The Apple LeanUX++ skillset** is different:
- User journey mapping with **emotional coherence** - not just "what steps" but "how does each step feel?"
- Progressive fidelity prototyping - paper sketches, ASCII mockups, interactive TUI
- Apple HIG principles - "form follows feeling", material honesty, concentrated focus
- CLI/TUI design patterns - clig.dev principles, command vocabulary, progressive disclosure
- Horizontal integration validation - cross-feature coherence, shared artifact tracking

These are **design** questions requiring **creative** skills.

### The Analogy

Asking Scout to do Apple-style design is like asking a market researcher to design the iPhone interface. Both valuable roles. Both need different skills. Both should exist.

### Capability Gap Analysis (Revised)

| Capability | Scout Can Do | LeanUX Designer Needed |
|------------|--------------|----------------------|
| Validate problem exists | YES | - |
| Map jobs-to-be-done | YES (functional) | YES (emotional layer) |
| Create opportunity tree | YES | - |
| User journey with emotions | NO | YES |
| Progressive prototyping | NO | YES |
| Apple HIG principles | NO | YES |
| CLI/TUI design patterns | NO | YES |
| Horizontal coherence check | NO | YES |
| Shared artifact tracking | NO | YES |

---

## Part 2: Wave Integration (Revised)

### Proposed nWave Flow with LeanUX Designer

```
DISCUSS:
  product-discoverer (Scout)     +     leanux-designer (NEW - Luna?)
       |                                      |
       | Problem/Opportunity/                 | User Journey Map
       | Solution/Viability                   | Emotional coherence
       |                                      | TUI prototypes
       v                                      v
       +------ PAIRING -------+
                 |
                 v
            product-owner (Riley)
                 |
                 | User Stories with
                 | BDD + Journey References
                 v
DESIGN:
  solution-architect (Dakota) ---> architecture-diagram-manager (Aria)
       |
       | Architecture + ADRs
       | (informed by journey map)
       v
DISTILL:
  acceptance-designer (Quinn)
       |
       | Acceptance Tests (.feature)
       | Including E2E journey scenarios
       v
DEVELOP:
  software-crafter (Crafty)
```

### Relationship Options

**Option 1: Sequential (NOT RECOMMENDED)**
```
Scout (discovery) -> Luna (design) -> Riley (stories)
```
Problem: Adds handoff, creates waterfall micro-stage.

**Option 2: Pairing (RECOMMENDED)**
```
Scout + Luna work together -> Riley
```
Scout validates "should we build this?", Luna designs "how should it feel?", both feed Riley simultaneously.

**Option 3: Sub-agent (POSSIBLE)**
```
Scout invokes Luna for journey mapping
```
Scout owns the flow, Luna provides design consultation. Respects Scout's leadership while adding design skills.

**Recommendation**: Option 2 (Pairing) or Option 3 (Sub-agent). Both preserve the benefits of integrated discovery+design while respecting single responsibility.

---

## Part 3: Handover Contract Design (Revised)

### LeanUX Designer Outputs

```yaml
# docs/ux/
  user-journey-map.md          # Complete journey with emotional annotations
  journey-e2e-scenarios.md     # Gherkin scenarios for horizontal integration
  tui-prototype-specs.md       # CLI/TUI interaction specifications
  shared-artifacts-registry.md # Cross-feature dependencies and resources
```

### User Journey Map Schema (Enhanced with Emotional Layer)

```markdown
# User Journey Map: {Goal Name}

## Goal
{What the user is ultimately trying to accomplish}

## Primary Persona
{Reference to validated persona from Scout's Phase 1}

## Emotional Arc
{How the user should FEEL at each stage - Apple "form follows feeling"}

## Journey Stages

### Stage 1: {Stage Name}
- **User Goal**: {What user wants to accomplish}
- **Entry Conditions**: {How user enters this stage}
- **Emotional State**: {How user feels entering - anxious? curious? frustrated?}
- **Actions**: {What user does}
- **CLI Commands**: {Specific commands/interactions}
- **System Touchpoints**: {Features involved}
- **Emotional Outcome**: {How user should feel after - confident? relieved? empowered?}
- **Exit Conditions**: {How user completes stage}
- **Connected Stories**: [US-xxx, US-yyy]
- **Shared Artifacts**: [{artifact}: {purpose}]
- **Design Principles Applied**: {Which Apple HIG / clig.dev principles}

### Stage 2: {Stage Name}
...

## Cross-Stage Dependencies
| From Stage | To Stage | Dependency Type | Shared Resource | Integration Risk |
|------------|----------|-----------------|-----------------|------------------|
| 1 | 2 | Data | version.txt | HIGH - single source of truth |
| 2 | 3 | State | Config loaded | MEDIUM - state persistence |

## Integration Checkpoints
- [ ] All stages have at least one connected story
- [ ] Shared artifacts identified and tracked
- [ ] E2E scenario written for complete journey
- [ ] No orphan stories (all connect to journey)
- [ ] Emotional arc is coherent (no jarring transitions)
- [ ] CLI vocabulary is consistent across stages
- [ ] Progressive disclosure respected

## E2E Goal-Completion Scenario

```gherkin
Feature: {Goal Name} Complete Journey

  @horizontal @e2e
  Scenario: User completes {goal} end-to-end
    Given {persona} is in {initial context}
    And {persona} feels {initial emotional state}

    # Stage 1: {Stage Name}
    When {persona} runs "{command}"
    Then {persona} sees "{expected output}"
    And {persona} feels {emotional outcome}

    # Stage 2: {Stage Name}
    When {persona} {action from stage 2}
    Then {observable outcome from stage 2}
    And shared artifact "{artifact}" is consistent with Stage 1

    # ... through all stages

    # Final
    Then {persona} has achieved {goal}
    And {persona} feels {final emotional state - empowered, confident, satisfied}
```
```

### TUI Prototype Spec Schema

```markdown
# TUI Prototype: {Feature/Command Name}

## Command Vocabulary
- Primary command: `crafter {verb} {noun}`
- Flags: `--{flag}` with descriptions
- Shortcuts: `-{short}` mappings

## Interaction Flow

### Initial State
```
$ crafter {command}
{ASCII mockup of initial output}
```

### User Action 1
```
$ {user input}
{ASCII mockup of response}
```

### Progressive Disclosure
- Level 1 (default): {basic output}
- Level 2 (--verbose): {detailed output}
- Level 3 (--debug): {diagnostic output}

## Error States
### Error: {Error Type}
```
$ crafter {command} {bad input}
Error: {clear, actionable error message}
Suggestion: {recovery hint}
```

## Design Principles Applied
- [ ] Consistent command structure (clig.dev)
- [ ] Transparent operations (show what's happening)
- [ ] Graceful degradation (clear errors, recovery paths)
- [ ] Progressive disclosure (simple default, detail on demand)
- [ ] Material honesty (CLI should feel like CLI)
```

---

## Part 4: Agent Specification Outline (Revised)

### Recommended Agent: leanux-designer

```yaml
name: leanux-designer
description: Use for DISCUSS wave - designing user journeys with emotional coherence, creating TUI prototypes, and validating horizontal feature integration using Apple LeanUX++ methodology

design_pattern: "ReAct (iterative design with tool calling)"
primary_wave: "DISCUSS"
secondary_involvement:
  - "DISTILL (E2E scenario handoff to acceptance-designer)"
  - "DEVELOP (design consultation for UX questions)"

persona:
  name: Luna
  role: Experience Designer & Horizontal Coherence Architect
  style: Creative, empathetic, detail-obsessed, systems-thinking
  identity: Expert who transforms validated opportunities into coherent user
            experiences using Apple design philosophy, progressive prototyping,
            and CLI/TUI design patterns. Ensures features connect to form
            complete, emotionally satisfying user journeys.

  core_principles:
    - Form Follows Feeling - Every interaction should evoke the right emotion
    - Horizontal Before Vertical - Map the complete journey before individual features
    - Material Honesty - CLI should feel like CLI, not a poor GUI imitation
    - Progressive Fidelity - Paper sketch -> ASCII mockup -> Interactive prototype
    - Concentrated Focus - One journey perfected before expanding scope
    - Hidden Quality Excellence - Even unseen details matter
    - Coherence Over Completeness - Better a coherent subset than a fragmented whole
    - Single Source of Truth - Shared artifacts must have one owner
    - Journey as Contract - The journey map IS the horizontal integration spec

key_responsibilities:
  - Create user journey maps with emotional annotations from validated opportunities
  - Design CLI/TUI interactions following clig.dev and Apple HIG principles
  - Prototype at progressive fidelity levels (paper -> ASCII -> interactive)
  - Track shared artifacts and cross-feature dependencies
  - Validate horizontal coherence before features proceed to DESIGN
  - Create E2E scenarios for acceptance testing
  - Consult on UX questions during DEVELOP

integration_points:
  pairs_with:
    product_discoverer:
      relationship: "Luna pairs with Scout during DISCUSS"
      receives: ["opportunity-tree.md", "problem-validation.md", "job-map.md"]
      provides: ["design perspective during validation sessions"]

  hands_off_to:
    product_owner:
      artifacts: ["user-journey-map.md", "tui-prototype-specs.md"]
      purpose: "Journey context and interaction specs for story creation"

    acceptance_designer:
      artifacts: ["journey-e2e-scenarios.md"]
      purpose: "Horizontal integration acceptance tests"

    solution_architect:
      artifacts: ["shared-artifacts-registry.md"]
      purpose: "Integration architecture decisions"

quality_gates:
  - "Journey map covers complete goal-completion flow"
  - "Emotional arc is coherent (no jarring transitions)"
  - "All shared artifacts tracked with single owner"
  - "E2E scenario is executable (valid Gherkin)"
  - "CLI vocabulary is consistent across journey"
  - "Progressive disclosure respected"
  - "No orphan features (all connect to journey)"
  - "TUI prototypes validated with at least 3 users"

handoff_validation:
  blocks_until:
    - "Journey map complete with emotional annotations"
    - "E2E scenario passes syntax validation"
    - "Shared artifact registry reviewed by solution-architect"
    - "TUI prototype user feedback incorporated"
    - "Peer review by leanux-designer-reviewer APPROVED"
```

---

## Part 5: Addressing the Original Problem

### The Evidence (Restated)
1. 3 different version files (no single source of truth)
2. Hardcoded URLs copied from templates without context
3. dist/ide/ path that doesn't match install expectations
4. CLI commands exist but slash commands don't

### How Luna Fixes This

**1. Shared Artifact Registry**
Luna creates `shared-artifacts-registry.md` that tracks:
```yaml
shared_artifacts:
  version:
    source_of_truth: "pyproject.toml"
    consumers: ["CLI --version", "about command", "README"]
    owner: "build-system"
    integration_risk: "HIGH - must stay synchronized"

  install_path:
    source_of_truth: "config/paths.yaml"
    consumers: ["install script", "uninstall script", "docs"]
    owner: "installer feature"
    integration_risk: "HIGH - path mismatch breaks install"
```

**2. Journey-Level Integration Check**
Before any feature proceeds, Luna validates:
- "Does this feature touch a shared artifact?"
- "Is the shared artifact in the registry?"
- "Is there one owner?"
- "Are all consumers documented?"

**3. E2E Scenarios Catch Integration Failures**
Luna's E2E scenarios test the complete flow:
```gherkin
Scenario: User installs and verifies version
  Given a fresh system without crafter-ai
  When user runs "pip install crafter-ai"
  Then the package installs successfully
  When user runs "crafter --version"
  Then the version matches pyproject.toml
  And the version matches "crafter about"
```

This scenario would have caught the version file mismatch immediately.

---

## Part 6: Conclusion (Revised)

### My Updated Assessment

| Aspect | Initial Position | Revised Position |
|--------|------------------|------------------|
| New agent needed? | No (enhance Scout) | **Yes** (different skill set) |
| User journey mapping? | Yes (in Scout) | **Yes (in Luna)** |
| Emotional coherence? | Not considered | **Critical** (Apple philosophy) |
| Progressive prototyping? | Not needed (CLI) | **Yes** (ASCII mockups, TUI specs) |
| Horizontal integration? | Add to Scout | **Luna's core responsibility** |
| Relationship to Scout? | Replacement | **Pairing partner** |

### Why I Changed My Mind

Mike's challenge exposed a category error in my thinking. I was treating "understanding users" as a single skill. In reality:

- **Understanding if users have a problem** (Scout's job) is **research**
- **Designing how users should experience a solution** (Luna's job) is **design**

Research skills: interviewing, evidence gathering, hypothesis testing
Design skills: journey mapping, emotional design, prototyping, coherence architecture

These are complementary but distinct. A great researcher isn't automatically a great designer.

### Final Recommendation

**Create the LeanUX Designer agent (Luna)** with:
1. Apple LeanUX++ methodology embedded in core principles
2. Journey mapping with emotional coherence as primary artifact
3. Progressive fidelity prototyping for CLI/TUI
4. Shared artifact registry for horizontal integration
5. E2E scenario creation for acceptance testing
6. Pairing relationship with product-discoverer (Scout)
7. Full 5-framework compliance per AGENT_TEMPLATE.yaml
8. Reviewer variant (leanux-designer-reviewer) for quality validation

---

## Appendix A: Single Responsibility Compliance

**Concern**: Does adding Luna violate single responsibility by fragmenting discovery?

**Answer**: No. Luna's responsibility is **design**, not discovery. The responsibilities split cleanly:

| Agent | Single Responsibility | Verification |
|-------|----------------------|--------------|
| Scout | Validate that a problem/opportunity is worth pursuing | "Should we build this?" |
| Luna | Design how the solution should feel and integrate | "How should this feel?" |
| Riley | Define what specifically to build (stories/criteria) | "What exactly are we building?" |

Three agents, three questions, three skill sets. Clean separation.

---

## Appendix B: Risk Analysis

| Risk | Mitigation |
|------|------------|
| Adds handoff latency | Pairing model (Scout+Luna work together, not sequentially) |
| Ownership confusion | Clear artifact ownership in contracts |
| Over-design before validation | Luna only activates after Scout's Phase 2 (opportunity validated) |
| Journey maps become shelfware | Journey map is a required handoff artifact, not optional documentation |
| TUI prototypes slow development | Progressive fidelity - start with paper, only go interactive if needed |

---

## Part 7: The /nw:sketch Command Analysis

### The Concept

Mike proposes a command that generates **visual E2E user journeys with TUI mockups** - allowing stakeholders to "experience" the flow before any code exists. This is a powerful shift-left mechanism.

### Question 1: Does this belong to Luna or is it standalone?

**Answer: Luna's PRIMARY command**

This command IS Luna's core capability materialized. The sketch is not just a command Luna happens to have - it's the physical manifestation of her design philosophy:

| Luna's Principle | How /nw:sketch Embodies It |
|------------------|---------------------------|
| Form Follows Feeling | Visual mockups show the emotional experience |
| Horizontal Before Vertical | E2E journey shown before individual features |
| Progressive Fidelity | ASCII mockups = mid-fidelity prototypes |
| Journey as Contract | The sketch IS the horizontal integration spec |
| Material Honesty | CLI mockups look like actual CLI |

**Ownership**: `/nw:sketch` is Luna's primary command, not a standalone utility.

### Question 2: How does this integrate with nWave workflow?

```
DISCUSS Phase:
  Scout validates opportunity
       │
       ▼
  Luna creates /nw:sketch ◄─── PRIMARY OUTPUT
       │
       ├──► Stakeholder review ("Can you see the flow?")
       │
       ├──► Integration validation (shared artifacts visible)
       │
       ▼
  Riley creates stories WITH sketch references
       │
       ▼
DESIGN Phase:
  Dakota uses sketch for architecture decisions
  (shared artifacts → components, data flow visible)
       │
       ▼
DISTILL Phase:
  Quinn transforms sketch → acceptance tests
  (Each TUI box → Gherkin scenario)
       │
       ▼
DEVELOP Phase:
  Crafty implements to match sketch
  (TUI mockups = expected output specs)
```

**The sketch becomes a living artifact that flows through ALL waves:**
- DISCUSS: Created by Luna, reviewed by stakeholders
- DESIGN: Informs architecture (what components, what data flows)
- DISTILL: Transforms directly into acceptance tests
- DEVELOP: Serves as expected output specification

### Question 3: Artifact Format

**Recommendation: Dual-format schema that generates both visual and Gherkin**

```yaml
# docs/ux/journey-sketch.yaml

journey:
  name: "Release nWave"
  goal: "Developer releases a new version of nWave framework"
  persona: "Mike (framework maintainer)"

  emotional_arc:
    start: "Anxious (will it work?)"
    middle: "Focused (following the steps)"
    end: "Confident (verified and released)"

steps:
  - id: 1
    name: "Build"
    command: "/nw:forge"

    tui_mockup: |
      ┌─ Step 1: Build ──────────────────────────────────────────┐
      │ $ /nw:forge                                              │
      │                                                          │
      │ nWave Forge v${version}                                  │
      │ [1/3] Running tests............... ✓ ${test_count} passed│
      │ [2/3] Building distribution....... ✓ dist/              │
      │ [3/3] Validating bundle........... ✓ ${agent_count} agents│
      │                                                          │
      │ Install locally? [Y/n] _                                 │
      └──────────────────────────────────────────────────────────┘

    shared_artifacts:
      - name: "version"
        source: "pyproject.toml"
        displayed_as: "${version}"
        consumers: ["header", "install confirmation"]
      - name: "agent_count"
        source: "dist/ide/agents/"
        displayed_as: "${agent_count} agents"

    emotional_state:
      entry: "Anxious - will tests pass?"
      exit: "Relieved - build succeeded"

    user_decision:
      prompt: "Install locally? [Y/n]"
      options:
        - input: "Y"
          next_step: 2
        - input: "n"
          next_step: "exit"

    gherkin: |
      Scenario: Build phase completes successfully
        Given Mike has uncommitted changes ready for release
        When Mike runs "/nw:forge"
        Then Mike sees "nWave Forge v{version}"
        And all tests pass with count displayed
        And distribution builds to dist/
        And agent count matches actual agents in dist/ide/agents/
        And Mike is prompted "Install locally? [Y/n]"

  - id: 2
    name: "Install"
    command: "Y (confirm)"

    tui_mockup: |
      ┌─ Step 2: Install ────────────────────────────────────────┐
      │ Installing to ~/.claude/...                              │
      │ ✓ Agents: ${agent_count} files                           │
      │ ✓ Commands: ${command_count} files                       │
      │ ✓ Version: ${version}                                    │
      │                                                          │
      │ Test locally or create release? [test/release] _         │
      └──────────────────────────────────────────────────────────┘

    shared_artifacts:
      - name: "version"
        source: "pyproject.toml"
        displayed_as: "${version}"
        validation: "MUST match Step 1 version"
      - name: "install_path"
        source: "config/paths.yaml"
        displayed_as: "~/.claude/"

    integration_checkpoint: |
      CRITICAL: Version shown here MUST match:
      - Step 1 header version
      - pyproject.toml
      - Installed agent metadata

      If mismatch detected → BLOCK with error

# ... additional steps ...

integration_validation:
  shared_artifact_consistency:
    - artifact: "version"
      must_match_across: [1, 2, 3, 4]
      failure_message: "Version mismatch detected between steps"

    - artifact: "agent_count"
      must_match_across: [1, 2]
      failure_message: "Agent count changed between build and install"

  cross_step_dependencies:
    - from_step: 1
      to_step: 2
      dependency: "Build must complete before install"
      data_flow: ["version", "agent_count", "dist/"]
```

**This schema enables:**
1. **Visual rendering**: Generate ASCII art journey from `tui_mockup` fields
2. **Gherkin generation**: Extract `gherkin` fields into .feature files
3. **Integration validation**: Parse `shared_artifacts` to build registry
4. **Consistency checking**: Validate `integration_validation` rules

### Question 4: Would this have caught the bugs?

**Bug 1: 3 different version files**

```
┌─ Step 1: Build ──────────────────────────────────────────┐
│ nWave Forge v1.2.86    ◄── From pyproject.toml          │
└──────────────────────────────────────────────────────────┘
          │
          ▼
┌─ Step 2: Install ────────────────────────────────────────┐
│ ✓ Version: 1.2.85      ◄── WAIT! Different version!     │
│                            From version.txt              │
└──────────────────────────────────────────────────────────┘
          │
          ▼
┌─ Step 3: Verify ─────────────────────────────────────────┐
│ $ crafter --version                                      │
│ crafter-ai 1.2.84      ◄── THIRD version! From __init__ │
└──────────────────────────────────────────────────────────┘
```

**How the sketch catches it:**

When Luna creates the sketch, she must specify the `source` for each `${version}` placeholder:

```yaml
shared_artifacts:
  - name: "version"
    source: "pyproject.toml"  # ← Forces single source of truth
    displayed_as: "${version}"
    consumers: ["build header", "install confirmation", "--version output"]
```

If the schema requires ONE source but the implementation has THREE, the sketch review surfaces this immediately:

**Luna's validation question**: "You show version in 3 places. What's the single source of truth?"

**Bug 2: Hardcoded URLs from templates**

```
┌─ Step 4: Documentation ──────────────────────────────────┐
│ README.md updated with:                                  │
│ Install: pip install git+https://github.com/org/repo    │
│                       ▲                                  │
│                       └── Where does this URL come from? │
└──────────────────────────────────────────────────────────┘
```

**How the sketch catches it:**

```yaml
shared_artifacts:
  - name: "repo_url"
    source: "???"  # ← Luna must answer: where is the canonical URL?
    displayed_as: "https://github.com/..."
    consumers: ["README", "install docs", "error messages"]
```

Luna is forced to ask: "What's the source of truth for the repository URL?" If nobody can answer, that's a design gap.

**Bug 3: dist/ide/ path mismatch**

```
┌─ Step 2: Install ────────────────────────────────────────┐
│ Installing to ~/.claude/...                              │
│ Source: dist/ide/agents/                                 │
│ Target: ~/.claude/agents/nw/                             │
│         ▲                                                │
│         └── Does this path actually exist?               │
└──────────────────────────────────────────────────────────┘
```

**How the sketch catches it:**

```yaml
shared_artifacts:
  - name: "install_path"
    source: "config/paths.yaml"
    validation: |
      MUST satisfy:
      - Source path exists after build
      - Target path is writable
      - Path conventions match documentation
```

The visual sketch makes path assumptions VISIBLE. Stakeholders can ask: "Wait, isn't the install path supposed to be ~/.claude/commands/nw/?"

**Bug 4: CLI commands without slash commands**

```
┌─ Journey: Update Framework ──────────────────────────────┐
│                                                          │
│ Step 1: User wants to update                             │
│ $ crafter update        ◄── CLI command exists          │
│                                                          │
│ Step 2: User in Claude Code                              │
│ /nw:update              ◄── Does this exist?            │
│ ERROR: Unknown command                                   │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**How the sketch catches it:**

When mapping the journey, Luna asks: "How does the user trigger this in each context?"

```yaml
steps:
  - name: "Update Framework"
    contexts:
      terminal:
        command: "crafter update"
        exists: true
      claude_code:
        command: "/nw:update"
        exists: false  # ← GAP IDENTIFIED
```

The sketch forces enumeration of ALL contexts where a user might trigger a feature.

### Question 5: Command Naming

**Analysis of options:**

| Name | Pros | Cons |
|------|------|------|
| `/nw:sketchUI` | Clear it's visual/UI focused | "UI" might imply GUI |
| `/nw:journey-sketch` | Emphasizes journey aspect | Long, hyphenated |
| `/nw:tui-prototype` | Technically accurate | "prototype" implies more fidelity than ASCII |
| `/nw:storyboard` | Film/animation term for visual sequences | Might confuse with user stories |
| `/nw:flowsketch` | Combines flow + sketch | Novel term, might not be intuitive |
| `/nw:sketch` | Simple, memorable | Might be too generic |

**My Recommendation: `/nw:sketch`**

Rationale:
1. **Simple and memorable** - Easy to type, easy to remember
2. **Implies appropriate fidelity** - "Sketch" = rough, quick, iterative (not polished)
3. **Consistent with Luna's progressive fidelity philosophy** - Sketch is the starting point
4. **Verb-like feel** - "Let me sketch this journey" feels natural
5. **Namespace clarity** - `/nw:` prefix makes it clear it's an nWave command

**Alternative if more specificity needed**: `/nw:journey-sketch` for the E2E journey, with `/nw:sketch` as alias.

### Command Specification

```yaml
command:
  name: sketch
  full_name: /nw:sketch
  owner: leanux-designer (Luna)

  description: |
    Generate visual E2E user journey with TUI mockups.
    Shows the complete goal-completion flow as ASCII screens,
    revealing integration points and shared artifacts.

  usage: |
    /nw:sketch <journey-name> [--format=visual|yaml|gherkin|all]

    Examples:
      /nw:sketch "release nWave"           # Visual ASCII output
      /nw:sketch "install framework" --format=yaml    # Schema output
      /nw:sketch "first-time setup" --format=gherkin  # Generate .feature
      /nw:sketch "update agents" --format=all         # All formats

  inputs:
    required:
      - journey_name: "Name of the goal-completion journey to sketch"
    optional:
      - format: "Output format (visual, yaml, gherkin, all)"
      - persona: "Override default persona for this journey"
      - include_errors: "Include error state mockups (default: true)"

  outputs:
    visual: |
      ASCII art journey with TUI boxes connected by arrows
      Emotional annotations at each step
      Shared artifact callouts
      Integration checkpoints highlighted

    yaml: |
      Structured schema (journey-sketch.yaml)
      Machine-readable for tooling
      Source of truth for other formats

    gherkin: |
      .feature file with scenarios extracted from steps
      @horizontal @e2e tags for journey tests
      Ready for acceptance-designer handoff

  workflow_integration:
    discuss:
      - Luna creates sketch after Scout validates opportunity
      - Stakeholders review visual journey
      - Shared artifacts identified and registered

    design:
      - Dakota references sketch for component boundaries
      - Aria uses sketch for sequence diagrams

    distill:
      - Quinn transforms sketch → acceptance tests
      - Gherkin output becomes starting point for .feature files

    develop:
      - Crafty implements to match TUI mockups
      - Sketch serves as expected output specification

  quality_gates:
    - "All shared artifacts have single source of truth"
    - "All steps have emotional state annotations"
    - "No orphan steps (all connect to goal)"
    - "Cross-step dependencies documented"
    - "Gherkin generation produces valid syntax"
```

---

## Appendix C: Full Example - "Release nWave" Journey Sketch

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  JOURNEY: Release nWave Framework                                            ║
║  PERSONA: Mike (framework maintainer)                                        ║
║  GOAL: Ship a new version with confidence                                    ║
║  EMOTIONAL ARC: Anxious → Focused → Confident → Satisfied                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

┌─ Step 1: Build ──────────────────────────────────────────┐  Emotion: Anxious
│ $ /nw:forge                                              │  "Will tests pass?"
│                                                          │
│ nWave Forge v1.2.86          ◄─┐                         │
│ [1/3] Running tests............│.. ✓ 847 passed         │
│ [2/3] Building distribution...│... ✓ dist/              │
│ [3/3] Validating bundle.......│... ✓ 28 agents          │
│                               │                          │
│ Install locally? [Y/n] _      │                          │
└───────────────────────────────│──────────────────────────┘
                                │
     SHARED ARTIFACT: version ──┘ Source: pyproject.toml
                                  Consumers: [header, install, --version, README]
          │
          │ User types: Y
          ▼
┌─ Step 2: Install ────────────────────────────────────────┐  Emotion: Focused
│ Installing to ~/.claude/...   ◄── install_path          │  "Following steps"
│ ✓ Agents: 28 files            ◄── agent_count           │
│ ✓ Commands: 22 files          ◄── command_count         │
│ ✓ Version: 1.2.86             ◄── version (MUST MATCH!) │
│                                                          │
│ Test locally or create release? [test/release] _         │
└──────────────────────────────────────────────────────────┘
          │
          │ ┌─────────────────────────────────────────────┐
          │ │ INTEGRATION CHECKPOINT                      │
          │ │ ✓ version matches Step 1                    │
          │ │ ✓ agent_count matches build output          │
          │ │ ✓ install_path exists and is writable       │
          │ └─────────────────────────────────────────────┘
          │
          │ User types: test
          ▼
┌─ Step 3: Local Verification ─────────────────────────────┐  Emotion: Careful
│ $ /nw:smoke-test                                         │  "Does it work?"
│                                                          │
│ Smoke Test Results:                                      │
│ ✓ Agents load correctly (28/28)                          │
│ ✓ Commands respond (22/22)                               │
│ ✓ Version consistent: 1.2.86  ◄── version CHECK         │
│                                                          │
│ Ready to release? [Y/n] _                                │
└──────────────────────────────────────────────────────────┘
          │
          │ ┌─────────────────────────────────────────────┐
          │ │ INTEGRATION CHECKPOINT                      │
          │ │ ✓ Installed version matches build version   │
          │ │ ✓ All agents functional                     │
          │ │ ✓ All commands respond                      │
          │ └─────────────────────────────────────────────┘
          │
          │ User types: Y
          ▼
┌─ Step 4: Create Release ─────────────────────────────────┐  Emotion: Confident
│ $ /nw:release                                            │  "This is solid"
│                                                          │
│ Creating release v1.2.86...   ◄── version                │
│ ✓ Git tag created: v1.2.86                               │
│ ✓ GitHub release drafted                                 │
│ ✓ Changelog updated                                      │
│                                                          │
│ Release URL: https://github.com/.../v1.2.86              │
│                          ◄── repo_url                    │
│ Publish release? [Y/n] _                                 │
└──────────────────────────────────────────────────────────┘
          │
          │ User types: Y
          ▼
┌─ Step 5: Publish & Verify ───────────────────────────────┐  Emotion: Satisfied
│ Publishing release...                                    │  "Done right"
│ ✓ GitHub release published                               │
│ ✓ Assets uploaded                                        │
│                                                          │
│ Verify installation from release:                        │
│ $ pip install git+https://github.com/.../v1.2.86        │
│                          ◄── repo_url + version          │
│                                                          │
│ ✓ Installation successful                                │
│ ✓ Version matches: 1.2.86                                │
│                                                          │
│ 🎉 Release v1.2.86 complete!                             │
└──────────────────────────────────────────────────────────┘

╔══════════════════════════════════════════════════════════════════════════════╗
║  SHARED ARTIFACT REGISTRY                                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Artifact      │ Source           │ Steps Used │ Risk Level                  ║
║  ─────────────────────────────────────────────────────────────────────────── ║
║  version       │ pyproject.toml   │ 1,2,3,4,5  │ HIGH - must be consistent   ║
║  agent_count   │ dist/ide/agents/ │ 1,2,3      │ MEDIUM - count validation   ║
║  install_path  │ config/paths.yaml│ 2          │ HIGH - path must exist      ║
║  repo_url      │ pyproject.toml   │ 4,5        │ MEDIUM - URL consistency    ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  INTEGRATION CHECKPOINTS SUMMARY                                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  After Step │ Validates                                                      ║
║  ─────────────────────────────────────────────────────────────────────────── ║
║  1 → 2      │ Build artifacts exist, version captured                        ║
║  2 → 3      │ Install matches build, paths valid                             ║
║  3 → 4      │ Local verification passes, version consistent                  ║
║  4 → 5      │ Release created, tags match version                            ║
║  5 (final)  │ Published release installable, version matches                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

This sketch would have IMMEDIATELY surfaced:
- **3 version files**: Registry shows ONE source, forces single source of truth
- **Hardcoded URLs**: repo_url must have documented source
- **Path mismatch**: install_path validation at Step 2 checkpoint
- **Missing commands**: Journey shows both CLI and slash command contexts

---

**Reviewer**: Sage (agent-builder)
**Verdict**: REVISED - CREATE NEW AGENT (leanux-designer)
**Confidence**: HIGH (after reconsidering discovery vs. design skill distinction)
**Acknowledgment**: Mike's challenge was correct. I was conflating research and design.

---

## Appendix D: Implementation Roadmap for /nw:sketch

### Phase 1: Core Command (MVP)
1. Create `leanux-designer` agent (Luna) with basic spec
2. Implement `/nw:sketch` command with visual output only
3. Manual shared artifact tracking

### Phase 2: Schema & Generation
1. Define journey-sketch.yaml schema
2. Implement YAML output format
3. Implement Gherkin generation from schema

### Phase 3: Integration Validation
1. Automated shared artifact consistency checking
2. Integration checkpoint validation
3. Cross-step dependency tracking

### Phase 4: Workflow Integration
1. Connect to acceptance-designer (Quinn) for DISTILL handoff
2. Connect to solution-architect (Dakota) for DESIGN input
3. Add to nWave orchestration flow
