# Product Owner JTBD/ODI Knowledge Extraction

**Date**: 2026-02-09
**Sources Analyzed**: 6 files (3 historical, 1 current agent, 3 current skills)
**Purpose**: Extract all JTBD/ODI methodology knowledge NOT already present in current product-owner agent or skills, for potential skill creation.

---

## Coverage Baseline: What the Current Agent Already Has

Before documenting new knowledge, here is what `nw-product-owner.md` and its 3 skills already cover:

| Topic | Covered In |
|-------|-----------|
| LeanUX user story template | Agent + leanux-methodology skill |
| Story classification (User Story, Tech Task, Spike, Bug Fix) | Agent |
| Story sizing / right-sizing criteria | leanux-methodology skill |
| Story states (Draft -> Ready -> In Progress -> Done) | leanux-methodology skill |
| Definition of Ready (8-item checklist) | Agent + leanux-methodology skill |
| Definition of Done | leanux-methodology skill |
| Anti-pattern detection (6 anti-patterns) | Agent + leanux-methodology skill |
| UAT-first development flow | leanux-methodology skill |
| BDD Example Mapping | bdd-requirements skill |
| Three Amigos | bdd-requirements skill |
| Conversational patterns (Context, Outcome, Concrete) | bdd-requirements skill |
| Given-When-Then translation | bdd-requirements skill |
| Five Whys for business value | bdd-requirements skill |
| Confirmation bias defense | bdd-requirements skill |
| Red card management | bdd-requirements skill |
| Review dimensions (5 dimensions) | review-dimensions skill |
| Peer review output format | review-dimensions skill |
| Wave handoff package | leanux-methodology skill |

---

## EXTRACTION 1: ODI Two-Phase Framework (Discovery vs Execution)

**Source**: `/tmp/jtbd-guide.md`, lines 9-36
**Status**: NEW -- not present in current agent or skills
**Relevance**: HIGH -- gives the PO a framework for advising users on WHICH workflow to follow

### Content

The ODI framework operates in two fundamentally different phases that can be used independently:

**PHASE 1: DISCOVERY** -- When you DON'T KNOW what to build

```
[research] --> discuss --> design --> distill
    |            |           |          |
GATHER        WHAT are    HOW should  WHAT does
evidence      the needs?  it work?    "done" look like?
```

**PHASE 2: EXECUTION LOOP** -- When you KNOW what needs to change

```
[research] --> baseline --> roadmap --> split --> execute --> review
    |            |            |           |          |          |
GATHER        MEASURE      PLAN it     BREAK it   DO each    CHECK
evidence      first!       completely  into atoms  task       quality
                                          |
                              <-----------+ (loop per task)
```

Key insight: `research` is a CROSS-WAVE capability invocable at any point when evidence-based decision making is needed.

### Assessment

The current PO agent operates exclusively within the DISCUSS wave (Phase 1). It has no awareness of the broader ODI framework -- when to recommend the user skip discovery entirely and enter the execution loop directly. This knowledge would enable the PO to triage incoming requests and advise: "You already know what to build -- skip DISCUSS, go straight to baseline."

### Recommendation

**Create skill**: `jtbd-workflow-selection` -- A decision framework the PO can use to classify incoming work and recommend the appropriate workflow entry point.

---

## EXTRACTION 2: Five Job Types with Workflow Sequences

**Source**: `/tmp/jtbd-guide.md`, lines 72-270
**Status**: NEW -- not present in current agent or skills
**Relevance**: HIGH -- direct job classification framework

### Content

#### JOB 1: Build Something New (Greenfield)
> "I need to create something that doesn't exist yet"

Key Question: What should we build?

Sequence:
```
[research] -> discuss -> design -> [diagram] -> distill -> baseline -> roadmap -> split -> execute -> review
```

Why each step:

| Step | Purpose |
|------|---------|
| research | (Optional) Gather domain knowledge before requirements |
| discuss | Gather requirements -- you don't know what's needed yet |
| design | Make architecture decisions, select technology |
| diagram | (Optional) Visualize architecture for stakeholder communication |
| distill | Define acceptance tests -- what does "done" look like? |
| baseline | Measure starting point for tracking improvement |
| roadmap | Create comprehensive plan while context is fresh |
| split | Break into atomic, self-contained tasks |
| execute | Do each task with clean context |
| review | Quality gate before proceeding |

#### JOB 2: Improve Existing System (Brownfield)
> "I know what needs to change in our system"

Key Question: How do I change it safely and incrementally?

Sequence:
```
[research] -> baseline -> roadmap -> split -> execute -> review (repeat)
```

Why skip discovery:
- You already understand the system
- Problem is identified
- Go straight to measured, incremental execution

The baseline is CRITICAL: blocks roadmap creation until you MEASURE current state. Prevents "optimizing the wrong thing" anti-pattern. Forces evidence-based planning.

#### JOB 3: Complex Refactoring
> "Code works but structure needs improvement"

Key Question: How do I restructure without breaking things?

Simple refactoring:
```
[root-why] -> mikado -> refactor (incremental)
```

Complex refactoring with tracking:
```
[research] -> baseline -> roadmap (methodology: mikado) -> split -> execute -> review
```

Why Mikado Method: explores dependencies BEFORE committing to changes, reversible at every step, discovery tracking for audit trail.

#### JOB 4: Investigate and Fix Issue
> "Something is broken and I need to find why"

Key Question: What's the root cause?

Sequence:
```
[research] -> root-why -> develop -> deliver
```

Minimal sequence -- focused intervention only.

#### JOB 5: Research and Understand
> "I need to gather information before deciding"

Key Question: What are my options?

Sequence:
```
research -> [decision point: which job to pursue next]
```

No execution -- pure information gathering that feeds into other jobs.

### Quick Reference Matrix

| Job | You Know What? | Sequence |
|-----|---------------|----------|
| Greenfield | No | [research] -> discuss -> design -> [diagram] -> distill -> baseline -> roadmap -> split -> execute -> review |
| Brownfield | Yes | [research] -> baseline -> roadmap -> split -> execute -> review |
| Refactoring | Partially | [research] -> baseline -> mikado/roadmap -> split -> execute -> review |
| Bug Fix | Yes (symptom) | [research] -> root-why -> develop -> deliver |
| Research | No | research -> (output informs next job) |
| Documentation | Varies | [research] -> design -> diagram |

Items in `[brackets]` are optional.

Cross-wave commands (can be used anytime): research, diagram, root-why, git.

### Assessment

The current PO has a `Story Classification` section that maps work to 4 task types (User Story, Technical Task, Spike, Bug Fix). The JTBD framework is richer: it maps work to 5 job types with specific workflow sequences, entry points, and rationale for skipping/including phases. The PO's classification is about story format; the JTBD framework is about workflow selection.

These are complementary, not redundant. The PO currently classifies HOW to write the requirement. The JTBD framework classifies WHICH workflow the requirement enters.

### Recommendation

**Add to `jtbd-workflow-selection` skill**: Include the 5 job types, the quick reference matrix, and the "When to Skip Discovery" decision logic. The PO would use this during Phase 1 (GATHER) to advise users on workflow routing.

---

## EXTRACTION 3: Granular Jobs-by-Phase Tables

**Source**: `/tmp/jtbd-guide.md`, lines 283-393
**Status**: NEW -- not present in current agent or skills
**Relevance**: MEDIUM -- useful reference for the PO to understand what happens downstream

### Content

#### Discovery Phase Jobs

##### DISCUSS Wave

| Job | Outcome |
|-----|---------|
| Capture stakeholder needs | Requirements documented |
| Align business and tech | Shared understanding |
| Define acceptance criteria | Testable requirements |

##### DESIGN Wave

| Job | Outcome |
|-----|---------|
| Choose architecture pattern | Architecture decision |
| Select technology stack | Technology rationale |
| Define component boundaries | Clear module separation |
| Communicate architecture visually | Stakeholder-ready diagrams |

##### DISTILL Wave

| Job | Outcome |
|-----|---------|
| Define what "done" looks like | Acceptance tests (Given-When-Then) |

#### Execution Loop Jobs

##### BASELINE

| Job | Outcome |
|-----|---------|
| Measure current state | Quantified starting point |
| Identify biggest bottleneck | Prioritized problem |
| Find quick wins | Low-effort high-impact options |
| Prevent wrong-problem syndrome | Evidence-based focus |

##### ROADMAP

| Job | Outcome |
|-----|---------|
| Plan while context is fresh | Comprehensive plan |
| Capture dependencies | Sequenced steps |
| Enable parallel work | Independent task identification |

##### SPLIT

| Job | Outcome |
|-----|---------|
| Prevent context degradation | Atomic self-contained tasks |
| Enable clean execution | Each task has full context |
| Track progress granularly | Individual task state |

##### EXECUTE

| Job | Outcome |
|-----|---------|
| Do work with max LLM quality | Clean context per task |
| Track state transitions | TODO -> IN_PROGRESS -> DONE |
| Capture execution results | Evidence of completion |

##### REVIEW

| Job | Outcome |
|-----|---------|
| Catch issues before propagation | Quality gate |
| Get expert critique | Domain-specific feedback |
| Validate acceptance criteria | APPROVED / NEEDS_REVISION |

#### Job Categories Summary

| Category | Core Job |
|----------|----------|
| Understanding | Know what to build and why |
| Planning | Break work into safe, trackable chunks |
| Executing | Do work without context degradation |
| Validating | Catch issues early with quality gates |
| Communicating | Share understanding via diagrams and docs |
| Investigating | Find truth before acting |

### Assessment

The DISCUSS wave jobs are already covered by the PO agent's core workflow. The downstream jobs (DESIGN, DISTILL, BASELINE, ROADMAP, SPLIT, EXECUTE, REVIEW) are outside the PO's direct responsibility but useful as context for handoff quality -- the PO can validate that requirements will actually serve the needs of downstream phases.

### Recommendation

**Partial inclusion in `jtbd-workflow-selection` skill**: Include the Job Categories Summary as a reference table. Include BASELINE jobs specifically -- the PO should understand that baseline "prevents wrong-problem syndrome" and can use this to validate whether the user's requirement actually addresses the right problem.

---

## EXTRACTION 4: Baseline Types

**Source**: `/tmp/jtbd-guide.md`, lines 442-475
**Status**: NEW -- not present in current agent or skills
**Relevance**: MEDIUM -- useful for the PO when advising on brownfield work entry

### Content

The baseline command supports three types:

#### 1. Performance Optimization
Use when improving speed, reducing resource usage, or optimizing throughput.

Required:
- Timing measurements with breakdown
- Bottleneck ranking
- Target metrics with evidence
- Quick wins identified

#### 2. Process Improvement
Use when fixing workflow issues, preventing incidents, or improving reliability.

Required:
- Incident references OR failure modes
- Simplest alternatives considered (with why insufficient)

#### 3. Feature Development
Use when building new capabilities (greenfield or brownfield development).

Required:
- Current state analysis
- Requirements source and validation

### Assessment

The PO agent does not discuss baselines at all. When a user brings brownfield work, the PO should know to recommend baseline measurement before planning. The baseline types help the PO classify what kind of measurement is needed.

### Recommendation

**Include in `jtbd-workflow-selection` skill**: As a "Baseline Type Selection" subsection. The PO uses this to advise: "Before we plan this, let's measure the current state. This is a performance optimization, so we need timing measurements and bottleneck ranking."

---

## EXTRACTION 5: Execution Loop Principles and Anti-Patterns

**Source**: `/tmp/jtbd-guide.md`, lines 409-584
**Status**: PARTIALLY NEW -- some overlap with existing anti-pattern detection
**Relevance**: MEDIUM

### Content

#### Execution Loop Key Principles

1. **Evidence Before Decisions**: Research when you need data to decide
2. **Measure Before Plan**: Baseline is a BLOCKING gate for roadmap
3. **Atomic Tasks**: Each task is self-contained with all context embedded
4. **Clean Context**: Each execute starts fresh (no accumulated confusion)
5. **Quality Gates**: Review before moving to next task

#### Workflow-Level Anti-Patterns (NOT story-level)

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Skip research | Decisions without evidence | Research when unfamiliar with domain |
| Skip baseline | Optimize wrong thing | Always baseline before roadmap |
| Monolithic tasks | Context degradation | Use split for atomic tasks |
| Skip review | Quality issues propagate | Review before each execute |
| Architecture before measurement | Over-engineering | Baseline identifies quick wins first |
| Forward references in tasks | Tasks not self-contained | Each task must have all context embedded |

### Assessment

The current PO has 6 story-level anti-patterns (Implement-X, Generic Data, Technical AC, Oversized Stories, No Examples, Tests After Code). The workflow-level anti-patterns above are different in kind -- they operate at the project/feature level, not the story level. "Skip baseline" and "Architecture before measurement" are particularly relevant to the PO when scoping work.

### Recommendation

**Include in `jtbd-workflow-selection` skill**: As a "Workflow Anti-Patterns" section, distinct from the story-level anti-patterns already in `leanux-methodology`. The PO would detect these during initial requirements conversation.

---

## EXTRACTION 6: Common Workflow Recipes

**Source**: `/tmp/jtbd-guide.md`, lines 488-570
**Status**: NEW -- not present in current agent or skills
**Relevance**: LOW-MEDIUM -- more operational than methodological

### Content (abbreviated -- key patterns only)

| Workflow | Entry Point | Key Characteristic |
|----------|------------|-------------------|
| New Feature on Existing Codebase | baseline (skip discovery) | Existing system, new capability |
| Performance Optimization | baseline (type: performance_optimization) | Measurement-first |
| Legacy System Modernization | research + root-why + baseline | Deep understanding first |
| Quick Bug Fix | root-why + develop + deliver | Minimal sequence |
| Pure Research Task | research | Output informs next job selection |
| Data-Heavy Project | research + baseline | Specialist agent involvement |

### Assessment

These are workflow routing recipes -- the PO can use them to recommend the right entry point when a user describes their situation. Currently the PO treats everything as "gather requirements -> craft stories" regardless of context.

### Recommendation

**Include in `jtbd-workflow-selection` skill**: As a "Workflow Recipes" quick-reference table. The PO consults this to advise: "This sounds like a performance optimization -- you should start with baseline, not requirements."

---

## EXTRACTION 7: JTBD Personas with Job Step Tables

**Source**: `/tmp/cli-discovery-jtbd.md`, lines 9-147
**Status**: NEW -- not present in current agent or skills
**Relevance**: HIGH as METHODOLOGY (the persona/job-step table format), LOW as content (CLI-installer-specific)

### Content (methodology extracted, domain-specific content omitted)

The source demonstrates a rigorous persona + JTBD format:

#### Persona Structure
```
**Who**: [Role description]
**Demographics**: [4-5 specific characteristics]
**Jobs-to-be-Done**: [Job Step table]
**Pain Points**: [Mapped to jobs]
**Success Metrics**: [Quantified outcomes]
```

#### Job Step Table Format

| Job Step | Goal | Desired Outcome |
|----------|------|-----------------|
| {Verb} | {What the user wants} | Minimize {metric} of {undesirable state} |

Key methodological elements:
- Job Steps are VERBS (Discover, Validate, Install, Verify, Orient, Start)
- Goals describe what the user WANTS
- Desired Outcomes use ODI format: "Minimize [time/effort/risk] to [achieve X]"
- Pain Points are mapped back to specific Job Steps
- Success Metrics are quantified (e.g., "Install completed in < 2 minutes")

#### Multiple Personas for Same Product
The source defines 4 personas (Explorer, Returner, Deployer, Automator), each with different job steps reflecting their different relationship with the product. This demonstrates that JTBD analysis requires persona segmentation -- different users have fundamentally different jobs.

### Assessment

The current PO agent has no methodology for persona creation or JTBD analysis. The `bdd-requirements` skill has Example Mapping and conversational patterns, but no structured persona/JTBD methodology. The `leanux-methodology` skill references "Who (The User)" in the story template but provides no technique for discovering or validating personas.

This is a gap. When users bring vague requirements, the PO should be able to guide persona discovery with a structured approach before writing stories.

### Recommendation

**Create skill**: `persona-jtbd-analysis` -- A structured methodology for persona creation and JTBD analysis that the PO uses during Phase 1 (GATHER) when the user does not yet have clear personas. Include:
- Persona template structure
- Job Step table format with ODI outcome statements
- Pain Point to Job mapping
- Success Metric quantification
- Multi-persona segmentation guidance

---

## EXTRACTION 8: Opportunity Scoring and Prioritization

**Source**: `/tmp/cli-discovery-jtbd.md`, lines 180-268
**Status**: EXISTS in product-discoverer skills, NOT in product-owner skills
**Relevance**: MEDIUM -- the PO needs a lighter version for story prioritization

### Content

Prioritized Opportunity Areas using ODI scoring:

```
Score = Importance + Max(0, Importance - Satisfaction)
```

Opportunity format:
```
### Opportunity N: {Title}
**Score: X/10** (Importance: Y, Satisfaction: Z)
**Current State**: {What exists today}
**Desired Outcome**: {What users want}
**Elements**: {Specific features/capabilities}
**Evidence**: {What validates this opportunity}
```

### Assessment

The `product-discoverer/opportunity-mapping.md` skill already has the Opportunity Scoring Algorithm and OST methodology. The PO does not need to duplicate this. However, the PO should know when to DEFER to the product-discoverer agent for deep opportunity analysis, and when to apply a simpler value/effort prioritization (which the PO already has via MoSCoW in the legacy agent).

### Recommendation

**No new skill needed**. Add a cross-reference note to `jtbd-workflow-selection`: "For deep opportunity analysis with ODI scoring, defer to the product-discoverer agent. The PO applies simpler MoSCoW prioritization for story-level ordering."

---

## EXTRACTION 9: Assumption Validation Framework

**Source**: `/tmp/cli-discovery-jtbd.md`, lines 150-177
**Status**: EXISTS in product-discoverer skills, PARTIALLY in PO
**Relevance**: LOW for duplication, but the specific 3-tier structure is useful

### Content

Three tiers of assumption confidence:

**Validated Assumptions** (HIGH confidence):
- Evidence + confidence rating
- Decision: proceed

**Partially Validated Assumptions** (MEDIUM confidence):
- Evidence + gaps + confidence rating
- Decision: proceed with caveats

**Invalidated/Risky Assumptions** (identified risk):
- Evidence against + risk + mitigation
- Decision: mitigate or pivot

### Assessment

The `product-discoverer/interviewing-techniques.md` skill has an Assumption Testing Framework with risk scoring. The PO's `bdd-requirements` skill has "Confirmation Bias Defense" which partially overlaps. The 3-tier classification (Validated / Partially Validated / Invalidated) is a useful output format not present elsewhere.

### Recommendation

**No new skill needed**. This is product-discoverer territory. The PO can reference the product-discoverer for assumption validation when needed.

---

## EXTRACTION 10: Decision Gates for Discovery Phases

**Source**: `/tmp/cli-discovery-jtbd.md`, lines 428-454
**Status**: EXISTS in product-discoverer/discovery-workflow.md
**Relevance**: LOW for PO (this is product-discoverer territory)

### Content

Decision gates G1-G4 with proceed/pivot/kill criteria. Already fully covered in `product-discoverer/discovery-workflow.md`.

### Recommendation

**No extraction needed**. This is product-discoverer scope.

---

## EXTRACTION 11: Legacy PO -- Requirements Gathering Framework

**Source**: `/tmp/legacy-product-owner.md`, lines 475-574
**Status**: PARTIALLY COVERED -- some in agent, some deeper detail lost

### Content

#### Elicitation Techniques (4 methods with process + outputs)

**Stakeholder Interviews**:
- Process: Prepare stakeholder-specific question sets, conduct structured interviews with active listening, document requirements with context and rationale, validate understanding through confirmation and examples
- Outputs: Stakeholder requirement sets, business context documentation, domain terminology

**Collaborative Workshops**:
- Process: Design workshop agenda with clear objectives, facilitate discussion with structured techniques, manage conflicts and drive toward consensus, document decisions and action items
- Outputs: Prioritized requirement lists, consensus decisions, workshop artifacts

**User Story Mapping**:
- Process: Map complete user workflow end-to-end, identify touchpoints and system interactions, break down workflow into manageable user stories, prioritize stories based on business value and user impact
- Outputs: User story maps, prioritized backlogs, release planning foundation

**Domain Modeling**:
- Process: Identify key domain concepts and relationships, define ubiquitous language with stakeholders, create domain model with business rules, validate model with domain experts
- Outputs: Domain models, ubiquitous language glossary, business rule documentation

### Assessment

The current PO agent's Phase 1 (GATHER) says: "Elicit requirements through structured conversation. Use Example Mapping with context questioning and outcome questioning patterns." This is narrower than the legacy's 4 techniques. The `bdd-requirements` skill has Example Mapping and Three Amigos in detail, but User Story Mapping and Domain Modeling are not covered.

User Story Mapping is particularly valuable -- it provides a technique for breaking down epics into stories that the current PO lacks. The current agent detects oversized stories but has no methodology for the initial decomposition from epic to story.

### Recommendation

**Partial inclusion**: User Story Mapping methodology should be added to either `bdd-requirements` or a new `story-mapping` skill. Domain Modeling overlaps with DDD and may be too specialized for the PO agent. Stakeholder Interviews and Collaborative Workshops are high-level process guidance already implicit in the agent's conversational approach.

---

## EXTRACTION 12: Legacy PO -- Requirement Types Classification

**Source**: `/tmp/legacy-product-owner.md`, lines 535-573
**Status**: NEW -- not explicitly present in current agent or skills
**Relevance**: MEDIUM -- adds structure to requirements beyond user stories

### Content

#### Functional Requirements
- Specific business capabilities and features
- User interactions and system responses
- Data processing and transformation rules
- Integration and interface requirements
- Validation: testable through acceptance tests, traceable to business objectives, complete and unambiguous, measurable outcomes

#### Non-Functional Requirements (NFRs)
- Performance: Response time, throughput, scalability requirements
- Security: Authentication, authorization, data protection requirements
- Usability: User experience, accessibility, interface requirements
- Reliability: Availability, fault tolerance, recovery requirements
- Validation: quantifiable metrics and thresholds, testable through automated validation, architecturally significant decisions

#### Business Rules
- Business policy enforcement requirements
- Data validation and integrity rules
- Workflow and process constraints
- Compliance and regulatory requirements
- Validation: clear rule specification with examples, exception handling and edge cases, rule precedence and conflict resolution

### Assessment

The current PO's `review-dimensions` skill checks for "Missing Non-Functional Requirements" but the PO agent itself does not guide the user to elicit NFRs or business rules during requirements gathering. The 3-type classification (Functional, NFR, Business Rules) with validation criteria is a structured approach the PO could use during Phase 1 to ensure completeness.

### Recommendation

**Partial inclusion in `bdd-requirements` skill**: Add a "Requirements Completeness Check" section that prompts the PO to elicit all three requirement types, not just user stories. Alternatively, include as part of the `jtbd-workflow-selection` skill's guidance for greenfield projects.

---

## EXTRACTION 13: Legacy PO -- Ubiquitous Language Development Process

**Source**: `/tmp/legacy-product-owner.md`, lines 820-853
**Status**: NEW -- not present as a process in current agent or skills
**Relevance**: MEDIUM -- extends the "Domain Language Primacy" principle

### Content

#### Language Establishment Process

**Discovery Phase**:
- Identify domain-specific terminology through stakeholder interviews
- Document existing business language and definitions
- Capture synonyms and variations in terminology usage
- Identify ambiguous terms requiring clarification

**Definition Phase**:
- Collaborate with domain experts to establish precise definitions
- Resolve terminology conflicts and inconsistencies
- Create comprehensive glossary with examples
- Validate definitions with all stakeholder groups

**Adoption Phase**:
- Integrate ubiquitous language into all project artifacts
- Train team members on domain terminology
- Establish language governance and evolution process
- Monitor and maintain language consistency

#### Communication Standards
- Use ubiquitous language in all requirements documentation
- Maintain terminology consistency across user stories
- Align acceptance criteria language with domain vocabulary
- Ensure stakeholder communication uses agreed terminology

### Assessment

The current PO agent has "Domain language primacy" as principle #4 and the `bdd-requirements` skill uses real names in examples. But there is no structured process for DISCOVERING and ESTABLISHING the ubiquitous language itself. The legacy PO had a 3-phase process (Discovery -> Definition -> Adoption) which is more systematic.

### Recommendation

**Partial inclusion**: The 3-phase language establishment process could be added to the `bdd-requirements` skill as a "Domain Language Discovery" section. This would formalize what the agent currently does implicitly.

---

## EXTRACTION 14: Legacy PO -- Value Assessment and Prioritization Framework

**Source**: `/tmp/legacy-product-owner.md`, lines 662-696
**Status**: PARTIALLY NEW -- MoSCoW exists conceptually but Value/Effort matrix is new
**Relevance**: MEDIUM

### Content

#### Business Impact Dimensions
- Revenue impact: Direct contribution to revenue generation or cost reduction
- User satisfaction: Improvement in user experience and satisfaction metrics
- Operational efficiency: Streamlining of business processes and workflows
- Strategic alignment: Support for long-term business objectives and vision

#### MoSCoW Technique
- Must Have: Critical requirements for minimum viable product
- Should Have: Important requirements for full product value
- Could Have: Nice-to-have requirements for enhanced experience
- Won't Have: Requirements deferred to future releases

#### Value/Effort Matrix
- High value, low effort: Quick wins with immediate business impact
- High value, high effort: Strategic investments requiring careful planning
- Low value, low effort: Easy implementations with minimal impact
- Low value, high effort: Candidates for elimination or deferral

### Assessment

The current PO has no explicit prioritization methodology. It validates story sizing and DoR but does not help the user prioritize BETWEEN stories. MoSCoW and Value/Effort are standard PO tools that should be available.

### Recommendation

**Include in `leanux-methodology` skill**: Add a "Story Prioritization" section with MoSCoW and Value/Effort Matrix. This is a natural fit alongside the existing story sizing and story states content.

---

## EXTRACTION 15: Legacy PO -- Risk Management Framework

**Source**: `/tmp/legacy-product-owner.md`, lines 698-730
**Status**: PARTIALLY NEW -- review-dimensions has priority validation but not full risk framework
**Relevance**: LOW-MEDIUM

### Content

Three risk categories:
- **Business Risks**: Market changes, regulatory changes, stakeholder availability, budget/timeline constraints
- **Technical Risks**: Integration complexity, technology selection, data migration, performance/security
- **Project Risks**: Resource availability, scope creep, communication challenges, quality/testing

Assessment criteria: Probability (Low/Medium/High), Impact (Low/Medium/High), Risk Score, Mitigation Urgency

Mitigation strategies: Avoidance, Mitigation, Transfer, Acceptance

### Assessment

The `review-dimensions` skill's Priority Validation dimension partially covers risk (Q1: "Is this the largest bottleneck?"). But a structured risk identification and classification framework is not present. The PO should be able to identify risks during requirements gathering and document them in the handoff package.

### Recommendation

**No new skill needed**. The risk framework is standard project management content. If needed, add a brief risk identification checklist to `leanux-methodology` skill's Wave Handoff Package section.

---

## Summary: Extraction Disposition

| # | Topic | Status | Recommendation |
|---|-------|--------|---------------|
| 1 | ODI Two-Phase Framework | NEW | New skill: `jtbd-workflow-selection` |
| 2 | Five Job Types with Sequences | NEW | New skill: `jtbd-workflow-selection` |
| 3 | Granular Jobs-by-Phase Tables | NEW | Partial include in `jtbd-workflow-selection` |
| 4 | Baseline Types | NEW | Include in `jtbd-workflow-selection` |
| 5 | Execution Loop Anti-Patterns | PARTIALLY NEW | Include in `jtbd-workflow-selection` |
| 6 | Common Workflow Recipes | NEW | Include in `jtbd-workflow-selection` |
| 7 | JTBD Personas + Job Step Tables | NEW | New skill: `persona-jtbd-analysis` |
| 8 | Opportunity Scoring | EXISTS in product-discoverer | No action (cross-reference only) |
| 9 | Assumption Validation 3-Tier | EXISTS in product-discoverer | No action |
| 10 | Decision Gates | EXISTS in product-discoverer | No action |
| 11 | Elicitation Techniques (User Story Mapping) | PARTIALLY COVERED | Add User Story Mapping to `bdd-requirements` |
| 12 | Requirement Types (Functional/NFR/Business Rules) | NEW | Add completeness check to `bdd-requirements` |
| 13 | Ubiquitous Language Process | NEW | Add to `bdd-requirements` |
| 14 | Value/Effort Prioritization | NEW | Add to `leanux-methodology` |
| 15 | Risk Management Framework | PARTIALLY COVERED | Minor addition to `leanux-methodology` handoff |

---

## Recommended New Skills

### Skill 1: `jtbd-workflow-selection`
**Purpose**: Enable the PO to classify incoming work by JTBD type and recommend the appropriate nWave workflow entry point.

**Content** (from extractions 1, 2, 3, 4, 5, 6):
- ODI Two-Phase Framework (Discovery vs Execution Loop)
- Five Job Types with workflow sequences and quick reference matrix
- "When to Skip Discovery" decision logic
- Baseline Type selection guidance
- Workflow-level anti-patterns (distinct from story-level)
- Common workflow recipes for routing
- Job Categories Summary reference

**Estimated size**: ~150-200 lines
**Impact**: Transforms the PO from a single-wave operator into a workflow advisor who can triage work before entering the DISCUSS wave.

### Skill 2: `persona-jtbd-analysis`
**Purpose**: Structured methodology for persona creation and JTBD analysis during early requirements gathering.

**Content** (from extraction 7):
- Persona template (Who, Demographics, JTBD table, Pain Points, Success Metrics)
- Job Step table format with ODI outcome statements ("Minimize [metric] of [state]")
- Pain Point to Job Step mapping
- Success Metric quantification
- Multi-persona segmentation guidance
- Example: Explorer/Returner/Deployer pattern showing different job steps for different user relationships

**Estimated size**: ~80-120 lines
**Impact**: Gives the PO a structured technique for the "Who" section of user stories, moving from ad-hoc persona descriptions to rigorous JTBD analysis.

---

## Recommended Additions to Existing Skills

### `bdd-requirements` additions
- User Story Mapping technique (from extraction 11) -- ~30 lines
- Requirements Completeness Check covering Functional/NFR/Business Rules (from extraction 12) -- ~25 lines
- Ubiquitous Language Discovery process (from extraction 13) -- ~20 lines

### `leanux-methodology` additions
- Story Prioritization section with MoSCoW and Value/Effort Matrix (from extraction 14) -- ~25 lines
- Risk identification checklist for handoff package (from extraction 15) -- ~10 lines
