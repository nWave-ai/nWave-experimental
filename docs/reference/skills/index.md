# Skills

## nw-ab-agent-template

- [nw-ab-agent-template](nw-ab-agent-template.md) — KNOWLEDGE — the canonical agent-spec template (frontmatter + body skeleton). Reference loaded by the create/migrate procedures; no sequence.

## nw-ab-anti-patterns

- [nw-ab-anti-patterns](nw-ab-anti-patterns.md) — KNOWLEDGE — agent/skill/command anti-pattern catalog with fixes. Reference scanned by validate-spec; no sequence.

## nw-ab-create-agent

- [nw-ab-create-agent](nw-ab-create-agent.md) — PROCEDURE — create a NEW agent via the 5-phase workflow (ANALYZE→DESIGN→CREATE→VALIDATE→REFINE). Trigger: build a new AI agent. Composes nw-ab-validate-spec.

## nw-ab-critique-dimensions

- [nw-ab-critique-dimensions](nw-ab-critique-dimensions.md) — Review dimensions for validating agent quality - template compliance, safety, testing, and priority validation

## nw-ab-examples

- [nw-ab-examples](nw-ab-examples.md) — KNOWLEDGE — canonical worked examples for agent creation, migration, and command optimization. Reference for the relevant procedures; no sequence.

## nw-ab-house-style

- [nw-ab-house-style](nw-ab-house-style.md) — KNOWLEDGE — caveman-native authoring house style + by-construction guarantees (Reasoning Mandate injection, A05/A06 anchors, measured-gain compression). Reference for create/migrate; no sequence.

## nw-ab-merge-agents

- [nw-ab-merge-agents](nw-ab-merge-agents.md) — PROCEDURE — merge agent B into agent A, relocating skills and cleaning up all references. Trigger: two agents must become one. Composes nw-ab-validate-spec.

## nw-ab-migrate-monolith

- [nw-ab-migrate-monolith](nw-ab-migrate-monolith.md) — PROCEDURE — migrate a legacy monolithic agent (>400L / embedded config / aggressive language) to lean core + skills, RECURSING into oversized referenced skills. Trigger: a bloated legacy agent spec, or a monolithic skill (>250L bundling >1 job). Composes nw-ab-validate-spec.

## nw-ab-optimize-command

- [nw-ab-optimize-command](nw-ab-optimize-command.md) — PROCEDURE — optimize a bloated command file to a lean declarative definition (forge.md pattern). Trigger: a command file over its size target with reducible content.

## nw-ab-todoify-file

- [nw-ab-todoify-file](nw-ab-todoify-file.md) — PROCEDURE — convert an agent/skill/command file's prose workflow + prose success-criteria to numbered task lists. Trigger: a file with prose workflow or prose success-criteria sections.

## nw-ab-validate-spec

- [nw-ab-validate-spec](nw-ab-validate-spec.md) — PROCEDURE — validate an EXISTING agent spec against the 19-item checklist. Trigger: checking a spec for compliance (also the shared composition target create/migrate/merge invoke). One job: run the checklist, report pass/fail.

## nw-ab-validation-checklist

- [nw-ab-validation-checklist](nw-ab-validation-checklist.md) — KNOWLEDGE (data) — the 19-item agent-spec validation checklist. The item definitions the validate-spec / todoify procedures RUN against. No sequence of its own.

## nw-abr-critique-dimensions

- [nw-abr-critique-dimensions](nw-abr-critique-dimensions.md) — Review dimensions for validating agent quality - template compliance, safety, testing, and priority validation

## nw-ad-critique-dimensions

- [nw-ad-critique-dimensions](nw-ad-critique-dimensions.md) — Review dimensions for acceptance test quality - happy path bias, GWT compliance, business language purity, coverage completeness, walking skeleton user-centricity, priority validation, observable behavior assertions, traceability coverage, and walking skeleton boundary proof

## nw-ad-distill-dod

- [nw-ad-distill-dod](nw-ad-distill-dod.md) — DISTILL Definition of Done — the hard gate checklist at the DISTILL-to-DELIVER transition for nw-acceptance-designer. Consult at Phase 4 handoff (*validate-dod before *handoff-develop). Block handoff on any failure. Reference checklist only — mandate/gate definitions live in nw-test-design-mandates, nw-at-completeness-check, nw-distill.

## nw-ad-mandate-summaries

- [nw-ad-mandate-summaries](nw-ad-mandate-summaries.md) — Acceptance-designer operational summaries of the test-design mandates the agent applies during AT authoring (Contract Shape, Driving-Port-Only, Dormant-Seam, SSOT-via-Types, plus the Mandate-9-v2 tag-vs-composition rule and the adapter-integration slice authoring trigger). Operational summaries only — canonical definitions live in nw-test-design-mandates + nw-distill. Consult during Phase 2 scenario authoring and Phase 4 mandate-compliance evidence.

## nw-adversarial-refutation

- [nw-adversarial-refutation](nw-adversarial-refutation.md) — The adversarial-refutation review stance — assume the artifact is WRONG and try to PROVE it, default-to-refuted, diverse lenses, and an exhibited executable counterexample. The shared SSOT every DELIVER review (per-slice C_REVIEWER_AUDIT + per-feature F_FINAL_REVIEW) applies so the expensive final swarm is needed less.

## nw-agent-creation-workflow

- [nw-agent-creation-workflow](nw-agent-creation-workflow.md) — Detailed 5-phase workflow for creating agents - from requirements analysis through validation and iterative refinement

## nw-agent-evals

- [nw-agent-evals](nw-agent-evals.md) — Lightweight eval method for testing nWave AGENTS and SKILLS (LLM behavior) as a lean alternative to heavy BDD/ATD. An eval = one prompt -> one captured run (trace + artifacts) -> a small set of checks -> a comparable score over time. Load when validating agent behavior, building a regression net for an agent/skill, or reducing agent-test bloat.

## nw-agent-testing

- [nw-agent-testing](nw-agent-testing.md) — 5-layer testing approach for agent validation including adversarial testing, security validation, and prompt injection resistance

## nw-architectural-styles-tradeoffs

- [nw-architectural-styles-tradeoffs](nw-architectural-styles-tradeoffs.md) — Architectural style selection decision matrices, trade-off analysis, structural enforcement rules, and combination patterns. Load when choosing or evaluating architecture styles.

## nw-architecture-patterns

- [nw-architecture-patterns](nw-architecture-patterns.md) — Comprehensive architecture patterns, methodologies, quality frameworks, and evaluation methods for solution architects. Load when designing system architecture or selecting patterns.

## nw-at-completeness-check

- [nw-at-completeness-check](nw-at-completeness-check.md) — Canonical AT completeness gate (lean core) — composes a Tier-1 coverage taxonomy (C1-C7 + 15-item checklist), a Tier-2 structural-invariants gate (S-family), gap routing, and taxonomy lifecycle. Paradigm-neutral. Drives the acceptance-designer reviewer verdict deterministically.

## nw-authoritative-sources

- [nw-authoritative-sources](nw-authoritative-sources.md) — Domain-specific authoritative source databases, search strategies by topic category, and source freshness rules

## nw-bdd-methodology

- [nw-bdd-methodology](nw-bdd-methodology.md) — BDD patterns for acceptance test design - Given-When-Then structure, scenario writing rules, pytest-bdd implementation, anti-patterns, and living documentation

## nw-bdd-requirements

- [nw-bdd-requirements](nw-bdd-requirements.md) — BDD requirements discovery methodology - Example Mapping, Three Amigos, conversational patterns, Given-When-Then translation, and collaborative specification

## nw-brainstorming

- [nw-brainstorming](nw-brainstorming.md) — Structured divergent thinking techniques — HMW framing, SCAMPER, Crazy 8s mechanics, and option diversity guarantees. Enforces strict separation of generation and evaluation phases.

## nw-buddy

- [nw-buddy](nw-buddy.md) — nWave concierge — ask any question about methodology, project state, commands, migration, or troubleshooting. Read-only, contextual answers.

## nw-buddy-command-catalog

- [nw-buddy-command-catalog](nw-buddy-command-catalog.md) — All /nw-* commands — what they do, when to use them, which agent they invoke. For the buddy agent to help users pick the right command.

## nw-buddy-project-reading

- [nw-buddy-project-reading](nw-buddy-project-reading.md) — How the nWave buddy agent reads a project to answer questions — detection, order of inspection, and citation discipline.

## nw-buddy-ssot-knowledge

- [nw-buddy-ssot-knowledge](nw-buddy-ssot-knowledge.md) — Single Source of Truth detection — where truth lives in an nWave repo and how to avoid contradicting it.

## nw-buddy-wave-knowledge

- [nw-buddy-wave-knowledge](nw-buddy-wave-knowledge.md) — Wave methodology knowledge for the buddy agent — what each wave does, its inputs and outputs, and how to route questions.

## nw-bugfix

- [nw-bugfix](nw-bugfix.md) — Bug fix workflow: root cause analysis → user review → regression test + fix via TDD

## nw-canary

- [nw-canary](nw-canary.md) — Canary skill for auto-injection detection

## nw-cicd-and-deployment

- [nw-cicd-and-deployment](nw-cicd-and-deployment.md) — CI/CD pipeline design methodology, deployment strategies, GitHub Actions patterns, and branch/release strategies. Load when designing pipelines or deployment workflows.

## nw-code-analysis-port

- [nw-code-analysis-port](nw-code-analysis-port.md) — KNOWLEDGE — resolve code facts (who-calls-X / where-defined-or-read / call-graph / change-scope / file-atoms) THROUGH the nWave vendor-neutral CodeFactPort, preferring Tsunami, then AST, with grep as last resort and degrading LOUD. Trigger: any time an agent designs, writes, analyzes, or reviews code or tests and needs a structural code fact.

## nw-code-design-fp

- [nw-code-design-fp](nw-code-design-fp.md) — FP code-design SSOT — the WHAT-to-design catalog (algebra-driven design, domain modelling with types, railway/error-track isolation) shared by the solution architect (design-time) and the functional crafter (execution-time).

## nw-code-design-oo

- [nw-code-design-oo](nw-code-design-oo.md) — OO code-design SSOT — the WHAT-to-design anti-smell catalog (Object Calisthenics, RPP smell taxonomy, effect isolation) shared by the solution architect (design-time) and the crafter (execution-time).

## nw-collaboration-and-handoffs

- [nw-collaboration-and-handoffs](nw-collaboration-and-handoffs.md) — Cross-agent collaboration protocols, workflow handoff patterns, and commit message formats for TDD/Mikado/refactoring workflows

## nw-collapse-detection

- [nw-collapse-detection](nw-collapse-detection.md) — Documentation collapse anti-patterns - detection rules, bad examples, and remediation strategies for type-mixing violations

## nw-command-design-patterns

- [nw-command-design-patterns](nw-command-design-patterns.md) — Best practices for command definition files - size targets, declarative template, anti-patterns, and canonical examples based on research evidence

## nw-command-design-patterns-authoring

- [nw-command-design-patterns-authoring](nw-command-design-patterns-authoring.md) — The v2.8+ new-command installation contract - which three files to produce and their frontmatter when creating a brand-new command

## nw-command-design-patterns-classification

- [nw-command-design-patterns-classification](nw-command-design-patterns-classification.md) — How to size and categorize a command, the declarative command template, and the WHAT-vs-HOW logic-placement rule

## nw-command-design-patterns-reduction

- [nw-command-design-patterns-reduction](nw-command-design-patterns-reduction.md) — What is reducible in a bloated command - the duplication triangle, the anti-pattern catalog, and the compress/never-compress rules

## nw-command-optimization-workflow

- [nw-command-optimization-workflow](nw-command-optimization-workflow.md) — Step-by-step workflow for converting bloated command files to lean declarative definitions

## nw-continue

- [nw-continue](nw-continue.md) — Detects current wave progress for a feature and resumes at the next step. Scans docs/feature/ for artifacts.

## nw-crafter-discipline-atdd-pure

- [nw-crafter-discipline-atdd-pure](nw-crafter-discipline-atdd-pure.md) — Crafter discipline contract for the ATDD-pure workflow — what the slim crafter does in Phase A (GREEN-the-ATs with AT-driven minimalism), Phase B (coverage-driven dead-code elimination — DEPRECATED velocity-v2, absorbed into A_GREEN), and Phase E (batch L1-L6 refactor), plus hard prohibitions

## nw-data-architecture-patterns

- [nw-data-architecture-patterns](nw-data-architecture-patterns.md) — Data architecture patterns (warehouse, lake, lakehouse, mesh), ETL/ELT pipelines, streaming architectures, scaling strategies, and schema design patterns

## nw-database-technology-selection

- [nw-database-technology-selection](nw-database-technology-selection.md) — Database comparison catalogs, RDBMS vs NoSQL selection criteria, CAP/ACID/BASE theory, OLTP vs OLAP, and technology-specific characteristics

## nw-ddd-architect

- [nw-ddd-architect](nw-ddd-architect.md) — DDD architect design-time mandates — the Fixture-Fanout Enumeration Mandate for shared-substrate per-caller migration (enumerate production callers plus fixture sites plus atomic bundle scope, mechanically enforced) that both the ddd-architect and its reviewer load by name

## nw-ddd-event-modeling

- [nw-ddd-event-modeling](nw-ddd-event-modeling.md) — Event Modeling facilitation technique — brainstorm events, identify commands and views, define aggregate boundaries, write Given-When-Then specifications

## nw-ddd-eventsourcing

- [nw-ddd-eventsourcing](nw-ddd-eventsourcing.md) — Event Sourcing and CQRS as DDD implementation patterns — when to use, aggregate event streams, projections, snapshots, sagas, upcasting, conflict resolution

## nw-ddd-strategic

- [nw-ddd-strategic](nw-ddd-strategic.md) — Strategic DDD — bounded context discovery, context mapping patterns, subdomain classification, ubiquitous language, and organizational alignment

## nw-ddd-tactical

- [nw-ddd-tactical](nw-ddd-tactical.md) — Tactical DDD — aggregate design rules, entities, value objects, domain events, repositories, domain services, and anti-pattern detection

## nw-deliver

- [nw-deliver](nw-deliver.md) — Orchestrates the full DELIVER wave end-to-end (roadmap > execute-all > finalize). Use when all prior waves are complete and the feature is ready for implementation.

## nw-deliver-atdd-pure-slice-gates

- [nw-deliver-atdd-pure-slice-gates](nw-deliver-atdd-pure-slice-gates.md) — DELIVER ATDD-pure per-slice phase-boundary contracts — the D_REFACTOR_COMMIT exit gate (E1 slice-commit completeness + E2 contract-gate scope), Phase D routing decision rules, A_GREEN/D_REFACTOR_COMMIT separation enforcement, the verdict-hash trailer, per-phase-boundary telemetry, and the post-commit falsifier-gate hook. Load when a per-slice phase boundary beyond the A_GREEN entry dispatch must be governed.

## nw-deliver-classic-orchestration

- [nw-deliver-classic-orchestration](nw-deliver-classic-orchestration.md) — DELIVER classic roadmap-driven spine (deprecated fallback, ADR-028 D6) — the §Orchestration Flow phase list (setup, paradigm/mutation/deliverable-type detection, roadmap creation + review, execute-all-steps, post-merge integration + Elevator Pitch demo gate, refactoring, adversarial review, mutation, integrity, finalize, retrospective, report), orchestrator responsibilities, the Task invocation pattern (DES template), the roadmap quality gate, skip/resume, and the per-step design compliance check. Load when the mode dispatch routes to the classic spine, or when the per-slice spine re-enters the shared refactor/review/mutation/integrity/finalize phases as written.

## nw-deliver-orchestration

- [nw-deliver-orchestration](nw-deliver-orchestration.md) — DELIVER wave orchestration workflow -- 9 phases from baseline to finalization. Load when user invokes *deliver command. Covers state tracking, smart skip logic, retry, resume, and quality gate enforcement.

## nw-density-resolution-contract

- [nw-density-resolution-contract](nw-density-resolution-contract.md) — Shared density-resolution contract for wave skills. Canonical detail on the D12 cascade, density resolver call, ad-hoc override workflow, and DocumentationDensityEvent telemetry emission. Referenced from nw-discover / nw-discuss / nw-design / nw-devops / nw-distill / nw-deliver.

## nw-deployment-strategies

- [nw-deployment-strategies](nw-deployment-strategies.md) — Rollback procedures, risk assessment, pre/post-deployment validation, and contingency planning. Load when orchestrating deployment or preparing rollback plans. For deployment strategy details (canary, blue-green, rolling), see `cicd-and-deployment` skill.

## nw-der-review-criteria

- [nw-der-review-criteria](nw-der-review-criteria.md) — Evaluation criteria and scoring for data engineering artifact reviews

## nw-design

- [nw-design](nw-design.md) — Designs system architecture with C4 diagrams and technology selection (recomposing core). DESIGN identity + density-aware output contract + gate-parsed Reuse Analysis contract + interactive decision points + architect routing/dispatch. Lean core that COMPOSES the narrow nw-design-* modules; the prior-wave-reading and discovery-flow procedures live in those modules, not re-inlined here. Routes to the right architect based on design scope (system, domain, application, or full stack). Two interaction modes: guide (collaborative Q&A) or propose (architect presents options with trade-offs).

## nw-design-discovery-flow

- [nw-design-discovery-flow](nw-design-discovery-flow.md) — DESIGN discovery-driven architecture flow — problem understanding, constraints, Conway's Law mapping, paradigm selection, Reuse Analysis (contract pinned in the nw-design core), architecture recommendation, optional stress analysis, deliverables, and the Outcome Collision Check. Run when architecture work begins, after the wave-entry decisions are resolved.

## nw-design-methodology

- [nw-design-methodology](nw-design-methodology.md) — Apple LeanUX++ design workflow, journey schema, emotional arc patterns, and CLI UX patterns. Load when transitioning from discovery to visualization or when designing journey artifacts.

## nw-design-patterns

- [nw-design-patterns](nw-design-patterns.md) — 7 agentic design patterns with decision tree for choosing the right pattern for each agent type

## nw-design-prior-wave-reading

- [nw-design-prior-wave-reading](nw-design-prior-wave-reading.md) — DESIGN prior-wave consultation + back-propagation procedure — read SSOT architecture + DISCUSS/SPIKE artifacts with a confirmation checklist, run the migration gate, check contradictions, and back-propagate changed assumptions (including upstream-changes.md for the product owner). Run BEFORE beginning DESIGN work.

## nw-devops

- [nw-devops](nw-devops.md) — Designs CI/CD pipelines, infrastructure, observability, and deployment strategy (recomposing core). DEVOPS identity + density-aware output contract + agent dispatch + peer-review gate + output/handoff contract. Lean core that COMPOSES the narrow nw-devops-* modules; the prior-wave-reading, decision-point, and environment-inventory procedures live in those modules, not re-inlined here. Use when preparing platform readiness for a feature.

## nw-devops-decision-points

- [nw-devops-decision-points](nw-devops-decision-points.md) — DEVOPS interactive decision catalog — Decisions 1-9 (deployment target, container orchestration, CI/CD platform, existing infrastructure, observability and logging, deployment strategy, continuous learning, Git branching strategy, mutation testing strategy) with options, defaults, and the CLAUDE.md persistence wording. Consult when presenting or resolving the wave-entry decisions.

## nw-devops-environment-inventory

- [nw-devops-environment-inventory](nw-devops-environment-inventory.md) — DEVOPS mandatory environment-inventory deliverable — produce environments.yaml (target environments, coexistence matrix, platform coverage, deployment assumptions) that DISTILL parses to parametrize acceptance scenarios over target environments (Mandate 4 / Environmental Realism). Run BEFORE completing the DEVOPS wave.

## nw-devops-prior-wave-reading

- [nw-devops-prior-wave-reading](nw-devops-prior-wave-reading.md) — DEVOPS prior-wave consultation + back-propagation procedure — read the DISCUSS outcome KPIs and the DESIGN artifacts with a confirmation checklist, check contradictions against the architecture, and back-propagate changed assumptions (including upstream-changes.md for the architect). Run BEFORE beginning DEVOPS work.

## nw-diagram

- [nw-diagram](nw-diagram.md) — Generates C4 architecture diagrams (context, container, component) in Mermaid or PlantUML. Use when creating or updating architecture visualizations.

## nw-discover

- [nw-discover](nw-discover.md) — Conducts evidence-based product discovery through customer interviews and assumption testing. Use at project start to validate problem-solution fit.

## nw-discovery-methodology

- [nw-discovery-methodology](nw-discovery-methodology.md) — Question-first approach to understanding user journeys. Load when starting a new journey design or when the discovery phase needs deepening.

## nw-discovery-workflow

- [nw-discovery-workflow](nw-discovery-workflow.md) — 4-phase discovery workflow with decision gates, phase transitions, success metrics, and state tracking

## nw-discuss

- [nw-discuss](nw-discuss.md) — Conducts Jobs-to-be-Done analysis, UX journey design, and requirements gathering through interactive discovery (recomposing core). DISCUSS identity + output-tier contract + scope escalation/Epic Mode + agent dispatch. Lean core that COMPOSES the narrow nw-discuss-* modules; phase procedures live in those modules, not re-inlined here. Use when starting feature analysis, defining user stories, or creating acceptance criteria.

## nw-discuss-decision-points

- [nw-discuss-decision-points](nw-discuss-decision-points.md) — DISCUSS interactive decision catalog — Decisions 1-4 (feature type, walking skeleton, UX research depth, JTBD inclusion) with options, defaults, and rationale. Consult when presenting or resolving the wave-entry decisions.

## nw-discuss-journey-design

- [nw-discuss-journey-design](nw-discuss-journey-design.md) — DISCUSS Phase 2 journey design procedure — mental model discovery, happy path, emotional arc, shared artifact tracking, error paths, and Gherkin scenario generation, with artifact paths. Run when designing the UX journey informed by JTBD.

## nw-discuss-jtbd-analysis

- [nw-discuss-jtbd-analysis](nw-discuss-jtbd-analysis.md) — DISCUSS Phase 1 JTBD analysis procedure — job discovery, job dimensions, four forces, opportunity scoring, and the JTBD-to-story bridge, with artifact paths. Run when Decision 4 = Yes and JTBD analysis is about to start.

## nw-discuss-prior-wave-reading

- [nw-discuss-prior-wave-reading](nw-discuss-prior-wave-reading.md) — DISCUSS prior-wave consultation + back-propagation procedure — read SSOT + DISCOVER/DIVERGE artifacts with reading enforcement, run the migration gate, check DISCOVER contradictions, and back-propagate changed assumptions. Run BEFORE beginning DISCUSS work.

## nw-discuss-requirements-stories

- [nw-discuss-requirements-stories](nw-discuss-requirements-stories.md) — DISCUSS Phase 3 requirements + user stories procedure — LeanUX stories with job traceability, the Elevator Pitch gate, the slice-composition hard gate, ACs, KPIs, DoR validation, optional peer review, handoff, and the Wave Decisions Summary. Run when crafting stories/ACs/DoR and closing the wave.

## nw-discuss-story-mapping

- [nw-discuss-story-mapping](nw-discuss-story-mapping.md) — DISCUSS Phase 2.5 user story mapping procedure — backbone, walking-skeleton slice, elephant-carpaccio slicing with taste tests, slice briefs, and prioritization, with artifact paths. Run when decomposing the feature into a story map + thin vertical slices.

## nw-distill

- [nw-distill](nw-distill.md) — Acceptance test creation methodology for the DISTILL wave (recomposing core). DISTILL identity + induction map + gate-G design↔AT coherence rubric + the mandatory final wave review gate. Lean core that COMPOSES the narrow nw-distill-* modules and the nw-test-design-mandates-* family; deep domain knowledge lives in those modules, not re-inlined here.

## nw-distill-coverage-obligations

- [nw-distill-coverage-obligations](nw-distill-coverage-obligations.md) — DISTILL coverage-verification procedure at gate-OUT — driving-adapter verification, per-adapter real-IO scenario coverage (Mandate 6), the adapter-integration slice (10-property matrix), outcomes registration, dormant-seam reconciliation cross-check, and the self-review checklist. Run after scenarios are authored, before reviewer dispatch.

## nw-distill-feature-delta-schema

- [nw-distill-feature-delta-schema](nw-distill-feature-delta-schema.md) — Feature-delta.md authoring schema for DISTILL — the canonical four-column inherited-commitments table format, the scaffold command, the E1+E2 validator rules, and incremental authoring. Consult while authoring or validating a feature-delta wave section's table structure.

## nw-distill-port-treatment-policy

- [nw-distill-port-treatment-policy](nw-distill-port-treatment-policy.md) — Port-to-port acceptance criteria + the Architecture of Reference (port-class → test treatment) + the Project Infrastructure Policy (concrete mechanism per port) + the walking-skeleton canonical definition and not-applicable exemptions. Consult while classifying a port's test treatment and the concrete mechanism for this codebase.

## nw-distill-prior-wave-reading

- [nw-distill-prior-wave-reading](nw-distill-prior-wave-reading.md) — DISTILL prior-wave reading + reconciliation procedure — read all prior-wave SSOT + feature-delta, run the Wave-Decision Reconciliation HARD GATE, fire the DESIGN-absent + Total-AT Tier-A advisories, and back-propagate gaps. Run BEFORE writing any scenario.

## nw-distill-red-scaffolding

- [nw-distill-red-scaffolding](nw-distill-red-scaffolding.md) — DISTILL RED-ready scaffolding procedure (Mandate 7) — create minimal stub files so ATs are RED (assertion failure, impl missing) not BROKEN (import/infra error), with per-language scaffold recipes, then run the pre-DELIVER fail-for-the-right-reason gate that classifies each failing scenario before handoff.

## nw-diverge

- [nw-diverge](nw-diverge.md) — Generates 3-5 divergent design directions through JTBD analysis, competitive research, structured brainstorming, and taste evaluation before convergence. Use when the team has a validated problem but hasn't chosen a solution approach.

## nw-diverger-review-criteria

- [nw-diverger-review-criteria](nw-diverger-review-criteria.md) — Review criteria for the nw-diverger-reviewer — validates JTBD rigor, research quality, option diversity, taste application correctness, and recommendation coherence in DIVERGE wave artifacts

## nw-divio-framework

- [nw-divio-framework](nw-divio-framework.md) — DIVIO/Diataxis four-quadrant documentation framework - type definitions, classification decision tree, and signal catalog

## nw-document

- [nw-document](nw-document.md) — Creates evidence-based documentation following DIVIO/Diataxis principles. Use when writing tutorials, how-to guides, reference docs, or explanations.

## nw-domain-driven-design

- [nw-domain-driven-design](nw-domain-driven-design.md) — Strategic and tactical DDD patterns, bounded context discovery, context mapping, aggregate design rules, and decision frameworks for when to apply DDD

## nw-dor-validation

- [nw-dor-validation](nw-dor-validation.md) — Definition of Ready checklist criteria, antipattern detection patterns, UAT quality rules, and domain language enforcement for product owner review

## nw-dr-review-criteria

- [nw-dr-review-criteria](nw-dr-review-criteria.md) — Critique dimensions, severity framework, verdict decision matrix, and review output format for documentation assessment reviews

## nw-execute

- [nw-execute](nw-execute.md) — Dispatches one unit of DELIVER work to a specialized agent for TDD execution. Use to run a step (classic workflow mode, a roadmap.json plan) or one carpaccio slice (ATDD-pure workflow mode).

## nw-expectation-charter

- [nw-expectation-charter](nw-expectation-charter.md) — Charter-authoring competence for ANY flow (DISCUSS wave, /nw-bugfix, technical fixes that skip DISCUSS) — how to write a user-side, discovery-preserving expectation charter that arms the DELIVER EXAMINE gate. Consult whenever an agent must author or judge a docs/product/expectations/ charter.

## nw-fast-forward

- [nw-fast-forward](nw-fast-forward.md) — Fast-forwards through remaining waves end-to-end without stopping for review between waves.

## nw-finalize

- [nw-finalize](nw-finalize.md) — Archives a completed feature to docs/evolution/, migrates lasting artifacts to permanent directories, and cleans up the temporary workspace. Use after all implementation steps pass.

## nw-five-whys-methodology

- [nw-five-whys-methodology](nw-five-whys-methodology.md) — Toyota 5 Whys methodology with multi-causal branching, evidence requirements, and validation techniques

## nw-forge

- [nw-forge](nw-forge.md) — Creates new specialized agents using the 5-phase workflow (ANALYZE > DESIGN > CREATE > VALIDATE > REFINE). Use when building a new AI agent or validating an existing agent specification.

## nw-formal-verification-tlaplus

- [nw-formal-verification-tlaplus](nw-formal-verification-tlaplus.md) — TLA+ and PlusCal for specifying distributed system invariants. Decision heuristics for when formal verification adds value, key patterns, state explosion management, and alternatives comparison.

## nw-fp-algebra-driven-design

- [nw-fp-algebra-driven-design](nw-fp-algebra-driven-design.md) — Algebra-driven API design with monoids, semigroups, and interpreters via algebraic equations

## nw-fp-clojure

- [nw-fp-clojure](nw-fp-clojure.md) — Clojure language-specific patterns, data-first modeling, REPL-driven development, and spec

## nw-fp-domain-modeling

- [nw-fp-domain-modeling](nw-fp-domain-modeling.md) — Domain modeling with algebraic data types, smart constructors, and type-level error handling

## nw-fp-fsharp

- [nw-fp-fsharp](nw-fp-fsharp.md) — F# language-specific patterns, Railway-Oriented Programming, and Computation Expressions

## nw-fp-haskell

- [nw-fp-haskell](nw-fp-haskell.md) — Haskell language-specific patterns, GADTs, type classes, and effect systems

## nw-fp-hexagonal-architecture

- [nw-fp-hexagonal-architecture](nw-fp-hexagonal-architecture.md) — Hexagonal architecture patterns with pure core and side-effect shell for functional codebases

## nw-fp-kotlin

- [nw-fp-kotlin](nw-fp-kotlin.md) — Kotlin language-specific patterns with Arrow, Raise DSL, and coroutine-based effects

## nw-fp-principles

- [nw-fp-principles](nw-fp-principles.md) — Core functional programming thinking patterns and type system foundations, language-agnostic

## nw-fp-scala

- [nw-fp-scala](nw-fp-scala.md) — Scala 3 language-specific patterns with ZIO, Cats Effect, and opaque types

## nw-fp-usable-design

- [nw-fp-usable-design](nw-fp-usable-design.md) — Naming conventions, API ergonomics, and usability patterns for functional code

## nw-hexagonal-testing

- [nw-hexagonal-testing](nw-hexagonal-testing.md) — 5-layer agent output validation, I/O contract specification, vertical slice development, and test doubles policy with per-layer examples

## nw-hotspot

- [nw-hotspot](nw-hotspot.md) — Git change frequency hotspot analysis — find the most-changed files in your codebase

## nw-infrastructure-and-observability

- [nw-infrastructure-and-observability](nw-infrastructure-and-observability.md) — Infrastructure as Code patterns (Terraform, Kubernetes), observability design (SLOs, metrics, alerting, dashboards), and pipeline security stages. Load when designing infrastructure, observability, or security scanning.

## nw-interviewing-techniques

- [nw-interviewing-techniques](nw-interviewing-techniques.md) — Mom Test questioning toolkit, JTBD analysis, interview conduct, assumption testing framework, and hypothesis design

## nw-investigation-techniques

- [nw-investigation-techniques](nw-investigation-techniques.md) — Evidence collection methods, problem categorization, analysis techniques, and solution design patterns

## nw-jtbd-analysis

- [nw-jtbd-analysis](nw-jtbd-analysis.md) — JTBD methodology for extracting real jobs behind feature requests — job statements, abstraction layers, first-principles extraction, ODI outcome statements, and opportunity scoring

## nw-jtbd-bdd-integration

- [nw-jtbd-bdd-integration](nw-jtbd-bdd-integration.md) — Translating JTBD analysis to BDD scenarios - job story to Given-When-Then patterns, forces-based test discovery, job-map-based test discovery, and property-shaped criteria

## nw-jtbd-core

- [nw-jtbd-core](nw-jtbd-core.md) — Core JTBD theory and job story format - job dimensions, job story template, job stories vs user stories, 8-step universal job map, outcome statements, and forces of progress

## nw-jtbd-interviews

- [nw-jtbd-interviews](nw-jtbd-interviews.md) — JTBD discovery techniques adapted for AI product owner context. Four Forces extraction, job dimension probing, question banks, and anti-patterns for interactive feature discovery conversations.

## nw-jtbd-opportunity-scoring

- [nw-jtbd-opportunity-scoring](nw-jtbd-opportunity-scoring.md) — JTBD opportunity scoring and prioritization - outcome statement format, opportunity algorithm, scoring interpretation, feature prioritization, and opportunity matrix template

## nw-jtbd-workflow-selection

- [nw-jtbd-workflow-selection](nw-jtbd-workflow-selection.md) — JTBD workflow classification and routing - ODI two-phase framework, five job types with workflow sequences, baseline type selection, workflow anti-patterns, and common recipes

## nw-leanux-methodology

- [nw-leanux-methodology](nw-leanux-methodology.md) — LeanUX backlog management methodology - user story template, story sizing, story states, task types, Definition of Ready/Done, anti-pattern detection and remediation

## nw-legacy-refactoring-ddd

- [nw-legacy-refactoring-ddd](nw-legacy-refactoring-ddd.md) — DDD-guided legacy refactoring patterns -- strangler fig, bubble context, ACL migration, 14 tactical/strategic/infrastructure patterns, and incremental monolith-to-microservices methodology

## nw-mikado

- [nw-mikado](nw-mikado.md) — [EXPERIMENTAL] Complex refactoring roadmaps with visual tracking

## nw-mikado-method

- [nw-mikado-method](nw-mikado-method.md) — Enhanced Mikado Method for complex architectural refactoring - systematic dependency discovery, tree-based planning, and bottom-up execution

## nw-mutation-test

- [nw-mutation-test](nw-mutation-test.md) — Runs feature-scoped mutation testing to validate test suite quality. Use after implementation to verify tests catch real bugs (kill rate >= 80%).

## nw-new

- [nw-new](nw-new.md) — Guided wizard to start a new feature. Asks what you want to build, recommends the right starting wave, and launches it.

## nw-operational-safety

- [nw-operational-safety](nw-operational-safety.md) — Tool safety protocols, adversarial output validation, error recovery patterns, and I/O contracts for research operations

## nw-opportunity-mapping

- [nw-opportunity-mapping](nw-opportunity-mapping.md) — Opportunity Solution Trees, opportunity scoring, Lean Canvas, JTBD job mapping, and technique selection guide

## nw-optimize-tests

- [nw-optimize-tests](nw-optimize-tests.md) — Minimizes test count while preserving coverage. Detects byte-identical pairs, parametrize-inflation, language-guarantee tests, AST-shape tests, stale migration nets. Approval gate before any change.

## nw-outcome-kpi-framework

- [nw-outcome-kpi-framework](nw-outcome-kpi-framework.md) — Outcome KPI definition methodology - synthesizes Who Does What By How Much (Gothelf/Seiden), Running Lean (Maurya), and Measure What Matters (Doerr) into a practical framework for measurable outcome KPIs

## nw-par-critique-dimensions

- [nw-par-critique-dimensions](nw-par-critique-dimensions.md) — Platform design review critique dimensions and severity levels. Load when reviewing CI/CD pipelines, infrastructure, deployment strategies, observability, or security designs.

## nw-par-review-criteria

- [nw-par-review-criteria](nw-par-review-criteria.md) — Quality dimensions and review checklist for devop reviews

## nw-pdr-review-criteria

- [nw-pdr-review-criteria](nw-pdr-review-criteria.md) — Evidence quality validation and decision gate criteria for product discovery reviews

## nw-persona-jtbd-analysis

- [nw-persona-jtbd-analysis](nw-persona-jtbd-analysis.md) — Structured persona creation and JTBD analysis methodology - persona templates, ODI job step tables, pain point mapping, success metric quantification, and multi-persona segmentation

## nw-platform-engineering-foundations

- [nw-platform-engineering-foundations](nw-platform-engineering-foundations.md) — Foundational platform engineering knowledge from key references -- Continuous Delivery, SRE, Accelerate, Team Topologies, Chaos Engineering, and Secure Delivery. Load when contextual grounding in platform engineering theory is needed.

## nw-po-review-dimensions

- [nw-po-review-dimensions](nw-po-review-dimensions.md) — Requirements quality critique dimensions for peer review - confirmation bias detection, completeness validation, clarity checks, testability assessment, and priority validation

## nw-por-review-criteria

- [nw-por-review-criteria](nw-por-review-criteria.md) — Review dimensions and bug patterns for journey artifact reviews

## nw-post-mortem-framework

- [nw-post-mortem-framework](nw-post-mortem-framework.md) — Blameless post-mortem structure, incident timeline reconstruction, response evaluation, and organizational learning

## nw-production-readiness

- [nw-production-readiness](nw-production-readiness.md) — Monitoring, observability, operational procedures, CI/CD lessons learned, and quality gate definitions. Load when assessing production readiness or validating operational excellence.

## nw-production-safety

- [nw-production-safety](nw-production-safety.md) — Agent safety boundaries - input validation, output filtering, scope constraints, and document creation policy

## nw-progressive-refactoring

- [nw-progressive-refactoring](nw-progressive-refactoring.md) — Progressive L1-L6 refactoring hierarchy, 22 code smell taxonomy, atomic transformations, test code smells, and Fowler refactoring catalog

## nw-property-based-testing

- [nw-property-based-testing](nw-property-based-testing.md) — Property-based testing strategies (PBT — ACTIVE, authored by the acceptance-designer during DISTILL), shrinking, PBT+TDD integration. (Mutation testing is documented but DEPRECATED per FR-1 — PBT is not.)

## nw-quality-framework

- [nw-quality-framework](nw-quality-framework.md) — Quality gates - 11 commit readiness gates, build/test protocol, validation checkpoints, and quality metrics

## nw-quality-validation

- [nw-quality-validation](nw-quality-validation.md) — Type-specific validation checklists, six quality characteristics, and quality gate thresholds for documentation assessment

## nw-query-optimization

- [nw-query-optimization](nw-query-optimization.md) — SQL and NoSQL query optimization techniques, indexing strategies, execution plan analysis, JOIN algorithms, cardinality estimation, and database-specific query patterns

## nw-refactor

- [nw-refactor](nw-refactor.md) — Applies the Refactoring Priority Premise (RPP) levels L1-L6 for systematic code refactoring. Use when improving code quality through structured refactoring passes.

## nw-research

- [nw-research](nw-research.md) — Gathers knowledge from web and files, cross-references across multiple sources, and produces cited research documents. Use when investigating technologies, patterns, or decisions that need evidence backing.

## nw-research-methodology

- [nw-research-methodology](nw-research-methodology.md) — Research output templates, distillation workflow, and quality standards for evidence-driven research

## nw-review

- [nw-review](nw-review.md) — Dispatches an expert reviewer agent to critique workflow artifacts. Use when a roadmap, implementation, or step needs quality review before proceeding.

## nw-review-output-format

- [nw-review-output-format](nw-review-output-format.md) — YAML output format and approval criteria for platform design reviews. Load when generating review feedback.

## nw-review-workflow

- [nw-review-workflow](nw-review-workflow.md) — Detailed review process, v2 validation checklist, and scoring methodology for agent definition reviews

## nw-rigor

- [nw-rigor](nw-rigor.md) — Selects a quality-vs-token-consumption profile (lean, standard, thorough, exhaustive, custom, inherit) and persists it globally (~/.nwave/global-config.json) or per-project (.nwave/des-config.json). Use when tuning how much rigor wave commands apply.

## nw-roadmap

- [nw-roadmap](nw-roadmap.md) — Creates a phased roadmap.json for a feature goal with acceptance criteria and TDD steps. Use when planning implementation steps before execution.

## nw-roadmap-design

- [nw-roadmap-design](nw-roadmap-design.md) — Roadmap concision rules, step decomposition efficiency, AC abstraction guidelines, and step-to-scenario mapping. Load when creating implementation roadmaps.

## nw-roadmap-review-checks

- [nw-roadmap-review-checks](nw-roadmap-review-checks.md) — Roadmap-specific validation checks for architecture reviews. Load when reviewing roadmaps for implementation readiness.

## nw-root-why

- [nw-root-why](nw-root-why.md) — Root cause analysis and debugging

## nw-rr-critique-dimensions

- [nw-rr-critique-dimensions](nw-rr-critique-dimensions.md) — Critique dimensions and scoring for research document reviews

## nw-sa-critique-dimensions

- [nw-sa-critique-dimensions](nw-sa-critique-dimensions.md) — Architecture quality critique dimensions for peer review. Load when invoking solution-architect-reviewer or performing self-review of architecture documents.

## nw-sar-critique-dimensions

- [nw-sar-critique-dimensions](nw-sar-critique-dimensions.md) — Architecture quality critique dimensions for peer review. Load when performing architecture document reviews.

## nw-sc-review-dimensions

- [nw-sc-review-dimensions](nw-sc-review-dimensions.md) — Reviewer critique dimensions for peer review - implementation bias detection, test quality validation, completeness checks, and priority validation

## nw-sd-case-studies

- [nw-sd-case-studies](nw-sd-case-studies.md) — 25 real-world system design case studies condensed from Alex Xu's System Design Interview Vol 1 and 2 - requirements, architecture, deep dive insights, key takeaways

## nw-sd-framework

- [nw-sd-framework](nw-sd-framework.md) — 4-step system design framework with back-of-envelope estimation, scaling ladder, and common pitfalls

## nw-sd-patterns

- [nw-sd-patterns](nw-sd-patterns.md) — Core distributed systems patterns - load balancing, caching, sharding, consistent hashing, message queues, rate limiting, CDN, Bloom filters, ID generation, replication, conflict resolution, CAP theorem

## nw-sd-patterns-advanced

- [nw-sd-patterns-advanced](nw-sd-patterns-advanced.md) — Advanced distributed patterns - event sourcing, CQRS, saga, stream processing, append-only log, exactly-once delivery, sequencer, double-entry ledger, erasure coding, order book, watermarks

## nw-security-and-governance

- [nw-security-and-governance](nw-security-and-governance.md) — Database security (encryption, access control, injection prevention), data governance (lineage, quality, MDM), and compliance frameworks (GDPR, CCPA, HIPAA)

## nw-security-by-design

- [nw-security-by-design](nw-security-by-design.md) — Security design principles, STRIDE threat modeling, OWASP Top 10 architectural mitigations, and secure patterns. Load when designing systems or reviewing architecture for security.

## nw-shared-artifact-tracking

- [nw-shared-artifact-tracking](nw-shared-artifact-tracking.md) — Shared artifact registry, common artifact patterns, and integration validation. Load when tracking data that flows across journey steps or validating horizontal coherence.

## nw-source-verification

- [nw-source-verification](nw-source-verification.md) — Source reputation tiers, cross-referencing methodology, bias detection, and citation format requirements

## nw-speculative-dispatch

- [nw-speculative-dispatch](nw-speculative-dispatch.md) — Speculative parallel implementation methodology — dispatch N candidate implementations, audit all, score, pick best. Auditability mandate: ALL candidates logged (not just winner).

## nw-spike

- [nw-spike](nw-spike.md) — Runs a timeboxed PROBE to validate one core assumption, then optionally PROMOTES the probe into a walking skeleton — the first e2e thin slice of the feature, committed and demo-able. Use after DISCUSS when the feature involves a new mechanism, performance requirement, or external integration.

## nw-spike-methodology

- [nw-spike-methodology](nw-spike-methodology.md) — Teaches agents how to run a timeboxed spike - throwaway code that validates one assumption before DESIGN

## nw-stakeholder-engagement

- [nw-stakeholder-engagement](nw-stakeholder-engagement.md) — Demonstration preparation, audience-tailored presentations, feedback collection, and business outcome measurement. Load when preparing demos or measuring business value delivery.

## nw-stress-analysis

- [nw-stress-analysis](nw-stress-analysis.md) — Advanced architecture stress analysis methodology for designing systems that survive unknown stresses. Load when --residuality flag is used or when designing high-uncertainty, mission-critical systems.

## nw-taste-evaluation

- [nw-taste-evaluation](nw-taste-evaluation.md) — Design taste evaluation framework — DVF primary filter, Apple/Google/Jobs design principles as explicit scoring criteria, weighted decision matrix, and option ranking for the DIVERGE wave

## nw-tdd-cross-language

- [nw-tdd-cross-language](nw-tdd-cross-language.md) — Port the state-delta + property-based testing paradigm to languages other than Python. DIY recipes per language; canonical Python ref shipped in nwave_ai.state_delta.

## nw-tdd-methodology

- [nw-tdd-methodology](nw-tdd-methodology.md) — Deep knowledge for Outside-In TDD - double-loop architecture, ATDD integration, port-to-port testing, walking skeletons, and test doubles policy

## nw-tdd-methodology-paradigm

- [nw-tdd-methodology-paradigm](nw-tdd-methodology-paradigm.md) — The default test-writing paradigm for unit + acceptance tests - property-based + state-delta mandate, the applicability matrix, the debt-payoff efficacy curve, and the delta-first trigger/bypass rules for state-mutating code

## nw-tdd-methodology-walking-skeleton

- [nw-tdd-methodology-walking-skeleton](nw-tdd-methodology-walking-skeleton.md) — Building and validating a walking skeleton - the WS protocol, per-slice JIT E2E management, Mandate 5 adapter-strategy decision tree (A/B/C/D + resource table), and Mandate 6 adapter-integration real-I/O requirement

## nw-tdd-review-enforcement

- [nw-tdd-review-enforcement](nw-tdd-review-enforcement.md) — Test design mandate enforcement, test budget validation, TDD phase validation (3-phase canon per ADR-025), and external validity checks for the software crafter reviewer

## nw-test-design-mandates

- [nw-test-design-mandates](nw-test-design-mandates.md) — Design mandates for acceptance tests - hexagonal boundary, business language abstraction, user journey completeness, pure function extraction, 3 Pillars (domain language / chained narrative / production composition), and the layered ATD discipline (Universe-bound assertion, layer-dependent PBT mode, two-tier acceptance, example-based sad paths). Lean recomposing core - routes to three narrow mandate modules.

## nw-test-design-mandates-composition-contract

- [nw-test-design-mandates-composition-contract](nw-test-design-mandates-composition-contract.md) — Composition-root authoring-contract mandates for acceptance tests — SSOT + Zero Duplication via Types + Services + DSL, Driving-Port-Only Boundary (Farley four-layer protocol-driver contract, fixture-theater/tautological-test anti-pattern), Contract Shape Classification (@in-memory/@real-io tag-vs-composition), and Dormant-Seam Reconciliation (AT drives the DESIGN-declared seam, not the new component). Consult while composing the AT's driving surface, structuring step/type/service code, and tagging the contract shape. Canonical definitions; SSOT for these mandates.

## nw-test-design-mandates-layered-mechanics

- [nw-test-design-mandates-layered-mechanics](nw-test-design-mandates-layered-mechanics.md) — Layered test-mechanics mandates for acceptance tests — Universe-bound assertion at layers 1-3 (assert_state_delta), Mandate-9-v2 three-way treatment by mock-status, layer-dependent PBT input mode, two-tier acceptance (Tier A Gojko + optional Tier B state-machine PBT), example-based integration sad paths, the Layered Test Discipline table, and the Polyglot Adapter Matrix. Consult while choosing assertion style, PBT mode, tier, and sad-path treatment for a given layer and driven-adapter realness. Canonical definitions; SSOT for these mandates.

## nw-test-design-mandates-scenario-design

- [nw-test-design-mandates-scenario-design](nw-test-design-mandates-scenario-design.md) — Scenario-design mandates for acceptance tests — Hexagonal Boundary Enforcement (drive through driving ports, never internals), Business Language Abstraction (three abstraction layers), User Journey Completeness, Pure Function Extraction Before Fixtures, the 3 Pillars style backbone, and Walking Skeleton Strategy. Consult while shaping or judging a scenario's boundary, language, journey completeness, and fixture strategy. Canonical definitions; SSOT for these mandates.

## nw-test-optimization

- [nw-test-optimization](nw-test-optimization.md) — Methodology for minimizing test count while maximizing behavioral coverage - lean core composing behavior-counting, anti-patterns, consolidation, budget-gate, paradigm-match, coverage-validation, scope-selection modules

## nw-test-optimization-consolidation

- [nw-test-optimization-consolidation](nw-test-optimization-consolidation.md) — Coverage-preserving consolidation patterns applied in order - parametrize-collapse, dict-iteration, fixture-scope, xdist-group, migration-collapse lifecycle, cross-tier dedup, single-lifecycle consolidation, state-delta cross-ref

## nw-test-optimization-paradigm-match

- [nw-test-optimization-paradigm-match](nw-test-optimization-paradigm-match.md) — Decision rule matching test SHAPE to the right paradigm before authoring/migrating - closed-world vs multi-step-setup vs state-mutation vs unbounded-invariant vs few-examples, plus the falsifier-gate that blocks PBT on finite domains

## nw-test-organization-conventions

- [nw-test-organization-conventions](nw-test-organization-conventions.md) — Test directory structure patterns by architecture style, language conventions, naming rules, and fixture placement. Decision tree for selecting test organization strategy.

## nw-test-refactoring-catalog

- [nw-test-refactoring-catalog](nw-test-refactoring-catalog.md) — Detailed refactoring mechanics with step-by-step procedures, and test code smell catalog with detection patterns and before/after examples

## nw-throughput

- [nw-throughput](nw-throughput.md) — How to maximize delivery throughput while driving the nWave spine — the Theory-of-Constraints insight (the box, not the agents), the N-cloud-ONE-box resource-aware pipeline, and the re-runnable measure. Load when orchestrating multi-slice/multi-feature delivery.

## nw-tlaplus-verification

- [nw-tlaplus-verification](nw-tlaplus-verification.md) — TLA+ formal verification for design correctness and PBT pipeline integration

## nw-tr-review-criteria

- [nw-tr-review-criteria](nw-tr-review-criteria.md) — Review dimensions and scoring for root cause analysis quality assessment

## nw-update

- [nw-update](nw-update.md) — Queues a deferred self-update of nwave-ai. Writes a PendingUpdateFlag that the SessionStart hook replays on the next Claude Code launch, so the current session is not interrupted. Falls back to manual instructions when the package manager cannot be detected.

## nw-user-story-mapping

- [nw-user-story-mapping](nw-user-story-mapping.md) — User story mapping for backlog management and outcome-based prioritization. Load during Phase 2.5 (User Story Mapping) to produce story-map.md and prioritization.md.

## nw-ux-desktop-patterns

- [nw-ux-desktop-patterns](nw-ux-desktop-patterns.md) — Desktop application UI patterns for product owners. Load when designing native or cross-platform desktop applications, writing desktop-specific acceptance criteria, or evaluating panel layouts and keyboard workflows.

## nw-ux-emotional-design

- [nw-ux-emotional-design](nw-ux-emotional-design.md) — Emotional design and delight patterns for product owners. Load when designing onboarding flows, empty states, first-run experiences, or evaluating the emotional quality of an interface.

## nw-ux-principles

- [nw-ux-principles](nw-ux-principles.md) — Core UX principles for product owners. Load when evaluating interface designs, writing acceptance criteria with UX requirements, or reviewing wireframes and mockups.

## nw-ux-tui-patterns

- [nw-ux-tui-patterns](nw-ux-tui-patterns.md) — Terminal UI and CLI design patterns for product owners. Load when designing command-line tools, interactive terminal applications, or writing CLI-specific acceptance criteria.

## nw-ux-web-patterns

- [nw-ux-web-patterns](nw-ux-web-patterns.md) — Web UI design patterns for product owners. Load when designing web application interfaces, writing web-specific acceptance criteria, or evaluating responsive designs.

## nw-wizard-shared-rules

- [nw-wizard-shared-rules](nw-wizard-shared-rules.md) — Shared rules for feature ID derivation and wave detection used by /nw-new, /nw-continue, and /nw-fast-forward wizards
