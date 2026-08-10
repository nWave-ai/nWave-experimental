# nw-agent-builder

Use when creating new AI agents, validating agent specifications, optimizing command definitions, or ensuring compliance with Claude Code best practices. Creates focused, research-validated agents (200-400 lines) with Skills for domain knowledge. Also optimizes bloated command files into lean declarative definitions.

**Wave:** Other
**Model:** inherit
**Max turns:** 30
**Tools:** Read, Write, Edit, Glob, Grep, Task

## Commands

- [`/nw-forge`](../commands/index.md)

## Preloaded skills

- [nw-ab-agent-template](../skills/nw-ab-agent-template.md) — KNOWLEDGE — the canonical agent-spec template (frontmatter + body skeleton). Reference loaded by the create/migrate procedures; no sequence.
- [nw-ab-anti-patterns](../skills/nw-ab-anti-patterns.md) — KNOWLEDGE — agent/skill/command anti-pattern catalog with fixes. Reference scanned by validate-spec; no sequence.
- [nw-ab-create-agent](../skills/nw-ab-create-agent.md) — PROCEDURE — create a NEW agent via the 5-phase workflow (ANALYZE→DESIGN→CREATE→VALIDATE→REFINE). Trigger: build a new AI agent. Composes nw-ab-validate-spec.
- [nw-ab-critique-dimensions](../skills/nw-ab-critique-dimensions.md) — Review dimensions for validating agent quality - template compliance, safety, testing, and priority validation
- [nw-ab-examples](../skills/nw-ab-examples.md) — KNOWLEDGE — canonical worked examples for agent creation, migration, and command optimization. Reference for the relevant procedures; no sequence.
- [nw-ab-house-style](../skills/nw-ab-house-style.md) — KNOWLEDGE — caveman-native authoring house style + by-construction guarantees (Reasoning Mandate injection, A05/A06 anchors, measured-gain compression). Reference for create/migrate; no sequence.
- [nw-ab-merge-agents](../skills/nw-ab-merge-agents.md) — PROCEDURE — merge agent B into agent A, relocating skills and cleaning up all references. Trigger: two agents must become one. Composes nw-ab-validate-spec.
- [nw-ab-migrate-monolith](../skills/nw-ab-migrate-monolith.md) — PROCEDURE — migrate a legacy monolithic agent (>400L / embedded config / aggressive language) to lean core + skills, RECURSING into oversized referenced skills. Trigger: a bloated legacy agent spec, or a monolithic skill (>250L bundling >1 job). Composes nw-ab-validate-spec.
- [nw-ab-optimize-command](../skills/nw-ab-optimize-command.md) — PROCEDURE — optimize a bloated command file to a lean declarative definition (forge.md pattern). Trigger: a command file over its size target with reducible content.
- [nw-ab-todoify-file](../skills/nw-ab-todoify-file.md) — PROCEDURE — convert an agent/skill/command file's prose workflow + prose success-criteria to numbered task lists. Trigger: a file with prose workflow or prose success-criteria sections.
- [nw-ab-validate-spec](../skills/nw-ab-validate-spec.md) — PROCEDURE — validate an EXISTING agent spec against the 19-item checklist. Trigger: checking a spec for compliance (also the shared composition target create/migrate/merge invoke). One job: run the checklist, report pass/fail.
- [nw-ab-validation-checklist](../skills/nw-ab-validation-checklist.md) — KNOWLEDGE (data) — the 19-item agent-spec validation checklist. The item definitions the validate-spec / todoify procedures RUN against. No sequence of its own.
- [nw-agent-creation-workflow](../skills/nw-agent-creation-workflow.md) — Detailed 5-phase workflow for creating agents - from requirements analysis through validation and iterative refinement
- [nw-agent-evals](../skills/nw-agent-evals.md) — Lightweight eval method for testing nWave AGENTS and SKILLS (LLM behavior) as a lean alternative to heavy BDD/ATD. An eval = one prompt -> one captured run (trace + artifacts) -> a small set of checks -> a comparable score over time. Load when validating agent behavior, building a regression net for an agent/skill, or reducing agent-test bloat.
- [nw-agent-testing](../skills/nw-agent-testing.md) — 5-layer testing approach for agent validation including adversarial testing, security validation, and prompt injection resistance
- [nw-command-design-patterns](../skills/nw-command-design-patterns.md) — Best practices for command definition files - size targets, declarative template, anti-patterns, and canonical examples based on research evidence
- [nw-command-optimization-workflow](../skills/nw-command-optimization-workflow.md) — Step-by-step workflow for converting bloated command files to lean declarative definitions
- [nw-cross-cutting-invariants](../skills/nw-cross-cutting-invariants.md) — Cross-cutting normative invariants — paradigm-independent and role-independent rules that bind every architect and crafter (data justification, gate design GDP-1..9, self-explaining surfaces). SHIPPED home of these definitions; cite by clause id, never re-declare.
- [nw-design-patterns](../skills/nw-design-patterns.md) — 7 agentic design patterns with decision tree for choosing the right pattern for each agent type
