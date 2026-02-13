# Current Command Analysis

**Date**: 2026-02-08
**Scope**: All 23 command files in `nWave/tasks/nw/`
**Total lines across all commands**: 10,067

---

## 1. Command Inventory

| # | Filename | Lines | Purpose | Category |
|---|----------|-------|---------|----------|
| 1 | develop.md | 2,394 | DELIVER wave orchestrator - delegates roadmap/execute/review/finalize/mutation-test | orchestrator |
| 2 | document.md | 1,191 | DIVIO documentation creation via researcher + documentarist agents | orchestrator |
| 3 | execute.md | 1,051 | Atomic task execution engine with TDD 7-phase cycle | dispatcher |
| 4 | finalize.md | 964 | Feature completion, archive evolution doc, cleanup | dispatcher |
| 5 | roadmap.md | 758 | Comprehensive goal planning via solution-architect | dispatcher |
| 6 | review.md | 692 | Expert critique and quality assurance for artifacts | dispatcher |
| 7 | mutation-test.md | 497 | Feature-scoped mutation testing quality gate | dispatcher |
| 8 | distill.md | 465 | Acceptance test creation (BDD/Gherkin) | dispatcher |
| 9 | journey.md | 428 | UX journey design with Luna (leanux-designer) | simple |
| 10 | discuss.md | 213 | Requirements gathering and walking skeleton check | dispatcher |
| 11 | design.md | 195 | Architecture design via solution-architect | dispatcher |
| 12 | research.md | 192 | Evidence-driven knowledge research | dispatcher |
| 13 | deliver.md | 138 | Production readiness validation | dispatcher |
| 14 | update.md | 137 | Update nWave to latest release (CLI docs) | simple |
| 15 | mikado.md | 133 | Complex refactoring via Mikado Method | dispatcher |
| 16 | refactor.md | 121 | Systematic code refactoring (L1-L6) | dispatcher |
| 17 | diagram.md | 121 | Visual architecture diagram generation | dispatcher |
| 18 | discover.md | 99 | Evidence-based product discovery | dispatcher |
| 19 | root-why.md | 71 | Toyota 5 Whys root cause analysis | dispatcher |
| 20 | start.md | 60 | Initialize nWave workflow | simple |
| 21 | git.md | 55 | Git workflow operations | simple |
| 22 | version.md | 52 | Display framework version | simple |
| 23 | forge.md | 40 | Create agent via agent-builder | simple |

---

## 2. Size Distribution

| Bucket | Count | Files |
|--------|-------|-------|
| 0-100 | 5 | forge, version, start, root-why, discover |
| 100-300 | 8 | git, diagram, refactor, mikado, update, deliver, research, design |
| 300-500 | 3 | journey, distill, mutation-test |
| 500-1000 | 3 | review, roadmap, finalize |
| 1000+ | 4 | execute, document, develop (2394!) |

**Average**: 437 lines
**Median**: 192 lines (research.md)
**Total**: 10,067 lines

The top 4 files (develop, document, execute, finalize) account for 5,600 lines -- 56% of all command content.

---

## 3. Structural Analysis

### 5 Largest Commands

#### develop.md (2,394 lines)
- **Parameter parsing/validation**: ~5% (minimal, inline orchestrator)
- **Workflow/orchestration logic**: ~30% (9-phase workflow with resume logic)
- **Agent prompt templates**: ~25% (embedded prompts for each sub-command)
- **Examples/documentation**: ~10%
- **Error handling**: ~5%
- **Removable content**: ~25%
  - Duplicates entire orchestrator briefing (repeated in every command)
  - Embeds full mutation-test workflow inline (600+ lines duplicating mutation-test.md)
  - Italian/English mixed comments
  - Schema migration notes for deprecated formats

#### document.md (1,191 lines)
- **Parameter parsing/validation**: ~5%
- **Workflow/orchestration logic**: ~15% (4-phase with review iterations)
- **Agent prompt templates**: ~30% (complete prompts for 4 agents)
- **Examples/documentation**: ~20% (DIVIO templates, cross-reference patterns)
- **Error handling**: ~20% (extensive error scenarios for each phase)
- **Removable content**: ~30%
  - Complete DIVIO templates (belong in documentarist agent/skill)
  - Review iteration handling duplicated for research and documentation phases
  - Observability/metrics section (aspirational, not implemented)

#### execute.md (1,051 lines)
- **Parameter parsing/validation**: ~15% (Steps 1-4 of invocation protocol)
- **Workflow/orchestration logic**: ~10%
- **Agent prompt templates**: ~25% (complete TDD 7-phase prompt template)
- **Examples/documentation**: ~15% (deprecated patterns, JSON examples)
- **Error handling**: ~15% (state machine, JSON error templates)
- **Removable content**: ~35%
  - 300+ lines of JSON state examples (verbose, never used by append-only format)
  - Deprecated step file references still present
  - Phase history tracking in JSON format (contradicts v2.0 pipe-delimited format)
  - Execution metrics JSON (aspirational)
  - Complete agent registry duplicated from other commands

#### finalize.md (964 lines)
- **Parameter parsing/validation**: ~15%
- **Workflow/orchestration logic**: ~10%
- **Agent prompt templates**: ~20% (evolution document template)
- **Examples/documentation**: ~25% (150-line markdown template, archive philosophy)
- **Error handling**: ~10%
- **Removable content**: ~30%
  - 150-line evolution document markdown template (agent knows how to write summaries)
  - Duplicate agent registry
  - Duplicate parameter parsing rules
  - Archive philosophy prose
  - Functional integration gate duplicated from distill.md (CM-A/CM-E overlap)

#### roadmap.md (758 lines)
- **Parameter parsing/validation**: ~15%
- **Workflow/orchestration logic**: ~10%
- **Agent prompt templates**: ~25% (measurement gate + YAML template)
- **Examples/documentation**: ~25% (example roadmap, step types)
- **Error handling**: ~5%
- **Removable content**: ~30%
  - 120+ line YAML roadmap template (agent knows YAML structure)
  - Measurement gate duplicated from develop.md
  - Complete agent registry (6th copy)
  - Step decomposition principles (belong in architect agent)
  - Context extraction Python examples (orchestrator implementation detail)

### 3 Smallest Commands

#### forge.md (40 lines)
- Clean, minimal dispatcher. References agent for all domain knowledge. Exemplary.

#### version.md (52 lines)
- Pure documentation. Hardcoded version number (stale). No agent delegation needed.

#### start.md (60 lines)
- Clean dispatcher. Minimal overhead. Good model.

---

## 4. Pattern Identification

### 4.1 Common Boilerplate (Repeated Across Files)

**Orchestrator Briefing Block** -- Appears in 12 commands (verbatim or near-verbatim):
```
**CRITICAL ARCHITECTURAL CONSTRAINT**: Sub-agents launched via Task tool
have NO ACCESS to the Skill tool. They can ONLY use: Read, Write, Edit,
Bash, Glob, Grep.
```
~20-30 lines each occurrence. **Total waste: ~300 lines across all files.**

**Agent Registry Block** -- Appears in 6 commands (execute, finalize, roadmap, review, develop, document):
```
Valid agents are: nw-researcher, nw-software-crafter, nw-solution-architect...
Each agent has specific capabilities:
- nw-researcher: Information gathering...
```
~15-20 lines each. **Total waste: ~100 lines.**

**Parameter Parsing Rules** -- Appears in 5 commands (execute, finalize, roadmap, review, develop):
```
Apply these rules to ALL extracted parameters:
1. Strip leading and trailing whitespace
2. Remove surrounding quotes...
```
~10-15 lines each. **Total waste: ~60 lines.**

**"What NOT to Include" block** -- Appears in 11 commands:
```
- "Agent should invoke /nw:X" (agent cannot invoke them)
- Any reference to skills or other commands
```
~8-12 lines each. **Total waste: ~100 lines.**

**Pre-Invocation Validation Checklist** -- Appears in 5 commands:
```
Before invoking Task tool, verify ALL items:
- [ ] Agent name extracted and validated
- [ ] Agent name in valid agent list...
```
~10-15 lines each. **Total waste: ~60 lines.**

### 4.2 Sections Duplicating Agent Knowledge

| Command | Duplicated Knowledge | Lines | Should Live In |
|---------|---------------------|-------|---------------|
| document.md | DIVIO templates (tutorial/howto/reference/explanation) | ~150 | nw-documentarist agent |
| document.md | Research procedures & quality gates | ~80 | nw-researcher agent |
| distill.md | BDD/Gherkin syntax, hexagonal boundary enforcement (CM-A) | ~120 | nw-acceptance-designer agent |
| design.md | Hexagonal architecture principles, reuse checklist | ~60 | nw-solution-architect agent |
| mutation-test.md | Cosmic-ray configuration, multi-language tool matrix | ~200 | nw-software-crafter agent/skill |
| finalize.md | Evolution document template, archive procedures | ~150 | nw-devop agent |
| execute.md | TDD 7-phase cycle details, checkpoint strategy | ~200 | nw-software-crafter agent |
| roadmap.md | Roadmap YAML schema, step decomposition rules | ~150 | nw-solution-architect agent |
| journey.md | UX discovery questions, emotional arc design | ~200 | nw-leanux-designer agent |

**Estimated total agent-knowledge duplication: ~1,300 lines (13% of all command content).**

### 4.3 Sections Duplicating Platform Capabilities

| Pattern | Occurrences | Lines Each | Platform Feature |
|---------|-------------|------------|-----------------|
| "Sub-agents have NO ACCESS to Skill tool" | 12 | 3-5 | Architecture fact, state once |
| Agent registry validation | 6 | 15-20 | Could be a shared lookup |
| Parameter parsing rules | 5 | 10-15 | Could be standardized utility |
| Pre-invocation checklist | 5 | 10-15 | Could be shared pattern |

### 4.4 Parameter Parsing Patterns

**Inconsistent across commands:**
- execute.md: 3 params (agent, project-id, step-id) -- unique
- finalize.md: 2 params (agent, project-id) -- shared with roadmap
- roadmap.md: 2 params (agent, goal-description) -- similar to finalize
- review.md: 3 params (agent, artifact-type, artifact-path) -- unique
- All others: 0-1 params (topic name only)

Each command re-implements the same parsing logic. No shared pattern.

### 4.5 Delegation Patterns

**Three distinct patterns:**

1. **Dispatcher pattern** (15 commands): Command describes agent invocation, orchestrator delegates via Task tool. Includes orchestrator briefing, "What to do/not do" blocks.

2. **Orchestrator pattern** (1 command: develop.md): Command IS the orchestrator. Reads other commands, extracts workflows, builds prompts. Most complex.

3. **Documentation pattern** (5 commands: version, update, start, git, forge): Minimal delegation, mostly reference docs.

---

## 5. Anti-Pattern Inventory

### 5.1 Commands Containing Domain Knowledge Belonging in Agents

| Command | Domain Knowledge | Lines | Impact |
|---------|-----------------|-------|--------|
| mutation-test.md | Complete cosmic-ray config format, multi-language tool matrix, venv setup, feature-scoped config generation | ~300 | Agent should know mutation tools |
| document.md | Complete DIVIO framework with 4 templates + review criteria | ~400 | Documentarist/researcher agents own this |
| distill.md | BDD syntax, hexagonal boundary rules, test directory conventions | ~250 | Acceptance-designer agent owns this |
| journey.md | UX discovery methodology, emotional arc patterns, artifact tracking | ~250 | Luna agent owns this |
| execute.md | TDD 7-phase details, checkpoint commit strategy, state machine | ~250 | Software-crafter agent owns this |

### 5.2 Commands Re-implementing Agent Workflows

- **develop.md** re-implements the entire workflow of 6+ other commands inline (roadmap, execute, review, mutation-test, refactor, finalize). It embeds ~600 lines of mutation-test workflow and ~400 lines of refactoring workflow.
- **document.md** re-implements the full 4-phase research-review-document-review workflow that could be a simple "invoke these agents in sequence."

### 5.3 Overly Prescriptive Step-by-Step Instructions

- **execute.md** STEP 1-5: 250 lines of parameter extraction that amounts to "parse arguments and invoke Task tool"
- **finalize.md** STEP 1-5: 200 lines of identical parameter parsing
- **roadmap.md** STEP 1-5: 200 lines of identical parameter parsing
- **review.md** STEP 1-5: 200 lines of identical parameter parsing

**These 4 commands share ~90% identical parameter parsing logic across ~800 lines.**

### 5.4 Redundant Validation

- **finalize.md** Step 4.5 (all-steps-complete gate): 40 lines of validation that the devop agent should perform
- **distill.md** CM-A hexagonal boundary check: 50 lines duplicated in finalize.md as CM-E
- **review.md** format validation for execution-log.yaml: 40 lines the reviewer agent already enforces
- **execute.md** pre-invocation checklist: 15 items, most of which are trivial (non-empty strings)

### 5.5 Dead Code / Unused Sections

| Command | Dead Content | Lines |
|---------|-------------|-------|
| execute.md | JSON state examples (contradicts v2.0 pipe format) | ~200 |
| execute.md | Execution queue management JSON (never implemented) | ~15 |
| execute.md | Deprecated step file references ("OLD SIGNATURE") | ~20 |
| roadmap.md | `<!-- BUILD:INJECT -->` placeholder (never built) | ~5 |
| roadmap.md | Baseline file validation gate (commented out in v2.0) | ~10 |
| finalize.md | Step JSON file references ("Legacy step files") | ~10 |
| review.md | Old split command references | ~10 |
| develop.md | Schema v1.0 references mixed with v2.0 | ~50 |
| version.md | Hardcoded version "1.6.46" (will be stale) | all |

---

## 6. Comparison with Agent Migration

### Same "Production Frameworks" Bloat?

**Yes, worse.** Commands have the same monolithic tendency as agents, but amplified by:
- Commands duplicate agent knowledge AND add orchestration boilerplate on top
- The "Orchestrator Briefing" pattern adds 20-30 lines to every file
- Commands contain complete agent prompt templates (sometimes 100+ lines of prompt text that the orchestrator must copy verbatim)

### Same Aggressive Language?

**Pervasive.** Examples from commands:

| Aggressive Pattern | Count | Files |
|-------------------|-------|-------|
| "CRITICAL" | 45+ | Nearly all |
| "MANDATORY" | 20+ | execute, finalize, roadmap, review, mutation-test, develop |
| "BLOCKING" / "HARD BLOCKER" | 8 | execute, finalize, roadmap, develop |
| "NON-NEGOTIABLE" | 2 | finalize, execute |
| Emoji emphasis (warning signs, checkmarks) | 50+ | develop, mutation-test, distill |

The develop.md file alone contains the word "CRITICAL" 15+ times.

### Same Monolithic vs Modular Tension?

**Identical pattern.** The top 4 commands (develop, document, execute, finalize) exhibit the same monolithic bloat as the worst agents:

| Metric | Agents (pre-migration) | Commands |
|--------|----------------------|----------|
| Largest file | ~2,000 lines | 2,394 lines (develop.md) |
| Top 4 files % of total | ~55% | 56% |
| Boilerplate repetition | Safety frameworks | Orchestrator briefings |
| Domain knowledge location | Embedded in agents | Duplicated in commands AND agents |
| Aggressive language | Moderate | Heavy |

---

## 7. Key Findings

### The 80/20 Problem

- **80% of command content** lives in 6 files (develop, document, execute, finalize, roadmap, review)
- **~30% of that content** is removable (duplicated knowledge, deprecated formats, verbose examples)
- **~15% of all content** is boilerplate repeated across files

### The Duplication Triangle

Commands duplicate content in three directions:
1. **Command-to-Command**: Orchestrator briefings, agent registries, parameter parsing (5-6x each)
2. **Command-to-Agent**: Domain knowledge that belongs in agents (~1,300 lines)
3. **Command-to-Self**: develop.md embeds other commands inline (~1,000 lines)

### Estimated Reducible Content

| Category | Lines | % of Total |
|----------|-------|-----------|
| Cross-command boilerplate | ~620 | 6% |
| Agent knowledge duplication | ~1,300 | 13% |
| Dead code / deprecated refs | ~320 | 3% |
| Verbose examples (JSON state) | ~400 | 4% |
| develop.md inline command duplication | ~1,000 | 10% |
| **Total reducible** | **~3,640** | **36%** |

A well-structured command system could deliver the same functionality in ~6,400 lines (vs current 10,067).

### The Forge Model

`forge.md` at 40 lines is the ideal. It:
- Names the agent
- States what to do
- Lists success criteria
- References agent for all domain knowledge

Every dispatcher command could follow this pattern at 40-100 lines if domain knowledge lives in agents and boilerplate is extracted to a shared preamble.

---

## 8. Recommendations (Summary)

1. **Extract shared boilerplate** into a single preamble file (orchestrator briefing, agent registry, parameter parsing rules, pre-invocation checklist). Commands reference it, not copy it.

2. **Move domain knowledge back to agents**. Commands should be thin dispatchers (forge.md model). Agent prompt templates belong in agents, not commands.

3. **Decompose develop.md** from 2,394-line monolith into a lean orchestrator that references sub-commands rather than embedding them.

4. **Purge dead code**: Remove all JSON state examples, deprecated step file references, v1.0 schema notes, BUILD:INJECT placeholders.

5. **Standardize command structure** around the forge.md pattern: header, overview, agent invocation, success criteria, next wave. Target 40-150 lines per command.

6. **Remove aggressive language**: Replace "CRITICAL", "MANDATORY", "NON-NEGOTIABLE", "HARD BLOCKER" with direct statements.
