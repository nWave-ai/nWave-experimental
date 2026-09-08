# Agents

## DESIGN

| Name | Description | Preloaded skills |
| --- | --- | --- |
| [nw-ddd-architect](nw-ddd-architect.md) | Use for DESIGN wave domain modeling. Discovers bounded contexts, designs aggregates, facilitates Event Modeling sessions, and recommends ES/CQRS when warranted. Writes to architecture SSOT. | 7 |
| [nw-ddd-architect-reviewer](nw-ddd-architect-reviewer.md) | Use for reviewing DDD domain models. Validates bounded context boundaries, aggregate design, context mapping, ES/CQRS recommendations, and ubiquitous language consistency. | 1 |
| [nw-platform-architect](nw-platform-architect.md) | Use for DESIGN wave (infrastructure design) and DEVOPS wave (deployment execution, production readiness, stakeholder sign-off). Transforms architecture into deployable infrastructure, then coordinates production delivery and outcome measurement. | 8 |
| [nw-platform-architect-reviewer](nw-platform-architect-reviewer.md) | Use for review and critique tasks - Platform design, CI/CD pipeline, infrastructure, observability, deployment readiness, and production handoff review specialist. Runs on Haiku for cost efficiency. | 0 |
| [nw-system-designer](nw-system-designer.md) | Use for DESIGN wave infrastructure-level architecture. Designs distributed systems, scalability strategies, load balancing, caching, database sharding, message queues, back-of-envelope estimation, and trade-off analysis. Complements solution-architect (application-level) with infrastructure-level depth. | 6 |
| [nw-system-designer-reviewer](nw-system-designer-reviewer.md) | Use to review system design architecture outputs. Validates trade-off analysis, estimation accuracy, pattern applicability, SPOF detection, and scalability claims. Pairs with system-designer. | 3 |

## Other

| Name | Description | Preloaded skills |
| --- | --- | --- |
| [nw-acceptance-designer](nw-acceptance-designer.md) | Authors the public executable oracle when required. | 0 |
| [nw-acceptance-designer-reviewer](nw-acceptance-designer-reviewer.md) | Independently approves or finds defects in the consolidated public oracle. | 0 |
| [nw-agent-builder](nw-agent-builder.md) | Use when creating new AI agents, validating agent specifications, optimizing requested existing SKILL.md assets, optimizing command definitions, or ensuring compliance with Claude Code best practices. Creates focused, research-validated agents (200-400 lines) with Skills for domain knowledge. | 18 |
| [nw-agent-builder-reviewer](nw-agent-builder-reviewer.md) | Use for review and critique tasks - Agent design and quality review specialist. Runs on Haiku for cost efficiency. | 5 |
| [nw-data-engineer](nw-data-engineer.md) | Use for database technology selection, data architecture design, query optimization, schema design, security implementation, and governance guidance. Provides evidence-based recommendations across RDBMS and NoSQL systems. | 4 |
| [nw-data-engineer-reviewer](nw-data-engineer-reviewer.md) | Use for review and critique tasks - Data architecture and pipeline review specialist. Runs on Haiku for cost efficiency. | 1 |
| [nw-diverger](nw-diverger.md) | Use before DISCUSS — runs JTBD analysis, competitive research, structured brainstorming, and taste-filtered evaluation to produce 3-5 design directions before the team converges on one. Use when the team has a validated problem but hasn't chosen a solution approach. | 3 |
| [nw-diverger-reviewer](nw-diverger-reviewer.md) | Use as peer reviewer for nw-diverger outputs — validates JTBD rigor, research evidence quality, option structural diversity, taste application correctness, and recommendation coherence. Runs on Haiku for cost efficiency. | 1 |
| [nw-documentarist](nw-documentarist.md) | Use for documentation quality enforcement using DIVIO/Diataxis principles. Classifies documentation type, validates against type-specific criteria, detects collapse patterns, and provides actionable improvement guidance. | 3 |
| [nw-documentarist-reviewer](nw-documentarist-reviewer.md) | Use for reviewing documentarist assessments. Validates classification accuracy, validation completeness, collapse detection, and recommendation quality using Haiku model. | 2 |
| [nw-functional-software-crafter](nw-functional-software-crafter.md) | Implements the functional change for one ready ordered batch. | 1 |
| [nw-nwave-buddy](nw-nwave-buddy.md) | Use for any nWave question — methodology, project navigation, command help, wave status, migration, and troubleshooting. The first agent to consult when unsure about anything in nWave. | 4 |
| [nw-plugin-validator](nw-plugin-validator.md) | Use to validate Claude Code plugin structure and schema during DISTILL/DELIVER verification when deliverable_type is `plugin`. Validates plugin manifest, directory layout, hook/command/agent registration, and Claude Code plugin schema compliance. No existing agent knows the plugin schema. Runs on Haiku for cost efficiency. | 1 |
| [nw-product-discoverer](nw-product-discoverer.md) | Conducts evidence-based product discovery through customer interviews, assumption testing, and opportunity validation. Use when validating problems exist, prioritizing opportunities, or confirming market viability before writing requirements. | 3 |
| [nw-product-discoverer-reviewer](nw-product-discoverer-reviewer.md) | Use as peer reviewer for product-discoverer outputs -- validates evidence quality, sample sizes, decision gate compliance, bias detection, and discovery anti-patterns. Runs on Haiku for cost efficiency. | 1 |
| [nw-product-owner](nw-product-owner.md) | Classifies one Request into its ephemeral observable value projection. | 0 |
| [nw-product-owner-reviewer](nw-product-owner-reviewer.md) | Reviews every direct expectation-charter namespace member for value-side independence, completeness, and executable human observability. | 1 |
| [nw-researcher](nw-researcher.md) | Use for evidence-driven research with source verification. Gathers knowledge from web and files, cross-references across multiple sources, and produces cited research documents. | 4 |
| [nw-researcher-reviewer](nw-researcher-reviewer.md) | Use for review and critique tasks - Research quality and evidence review specialist. Runs on Haiku for cost efficiency. | 1 |
| [nw-skill-reviewer](nw-skill-reviewer.md) | Use to review SKILL.md quality during DISTILL/DELIVER verification when deliverable_type is `plugin` or `skill`. Validates skill structure, scope discipline, frontmatter, and domain-knowledge quality. Thin reviewer — reuses nw-agent-builder skill assets. Runs on Haiku for cost efficiency. | 2 |
| [nw-software-crafter](nw-software-crafter.md) | Implements the OO change for one ready ordered batch. | 1 |
| [nw-software-crafter-reviewer](nw-software-crafter-reviewer.md) | Independently reviews the whole candidate with captured native evidence. | 0 |
| [nw-solution-architect](nw-solution-architect.md) | Returns typed design facts consumed by one DES run. | 0 |
| [nw-solution-architect-reviewer](nw-solution-architect-reviewer.md) | Reviews durable architecture decisions for evidence, reuse, boundaries, cross-layer algebra, residual stress behavior, test substrate, and absence of drift. | 1 |
| [nw-test-optimizer](nw-test-optimizer.md) | Minimize test cost while preserving observable behavior and coverage. Reads production code but modifies tests only. | 1 |
| [nw-test-optimizer-reviewer](nw-test-optimizer-reviewer.md) | Independently reviews test optimization. Read-only; vetoes production drift, behavior or coverage loss, and unmapped deletion. | 1 |
| [nw-troubleshooter](nw-troubleshooter.md) | Use for investigating system failures, recurring issues, unexpected behaviors, or complex bugs requiring systematic root cause analysis with evidence-based investigation. | 4 |
| [nw-troubleshooter-reviewer](nw-troubleshooter-reviewer.md) | Independently falsifies root-cause analyses and their prevention claims. | 1 |
| [nw-user-examiner](nw-user-examiner.md) | Source-blind judge of supplied installed-observation evidence. | 0 |

## All Agents

| Name | Wave | Description | Preloaded skills |
| --- | --- | --- | --- |
| [nw-acceptance-designer](nw-acceptance-designer.md) | Other | Authors the public executable oracle when required. | 0 |
| [nw-acceptance-designer-reviewer](nw-acceptance-designer-reviewer.md) | Other | Independently approves or finds defects in the consolidated public oracle. | 0 |
| [nw-agent-builder](nw-agent-builder.md) | Other | Use when creating new AI agents, validating agent specifications, optimizing requested existing SKILL.md assets, optimizing command definitions, or ensuring compliance with Claude Code best practices. Creates focused, research-validated agents (200-400 lines) with Skills for domain knowledge. | 18 |
| [nw-agent-builder-reviewer](nw-agent-builder-reviewer.md) | Other | Use for review and critique tasks - Agent design and quality review specialist. Runs on Haiku for cost efficiency. | 5 |
| [nw-data-engineer](nw-data-engineer.md) | Other | Use for database technology selection, data architecture design, query optimization, schema design, security implementation, and governance guidance. Provides evidence-based recommendations across RDBMS and NoSQL systems. | 4 |
| [nw-data-engineer-reviewer](nw-data-engineer-reviewer.md) | Other | Use for review and critique tasks - Data architecture and pipeline review specialist. Runs on Haiku for cost efficiency. | 1 |
| [nw-ddd-architect](nw-ddd-architect.md) | DESIGN | Use for DESIGN wave domain modeling. Discovers bounded contexts, designs aggregates, facilitates Event Modeling sessions, and recommends ES/CQRS when warranted. Writes to architecture SSOT. | 7 |
| [nw-ddd-architect-reviewer](nw-ddd-architect-reviewer.md) | DESIGN | Use for reviewing DDD domain models. Validates bounded context boundaries, aggregate design, context mapping, ES/CQRS recommendations, and ubiquitous language consistency. | 1 |
| [nw-diverger](nw-diverger.md) | Other | Use before DISCUSS — runs JTBD analysis, competitive research, structured brainstorming, and taste-filtered evaluation to produce 3-5 design directions before the team converges on one. Use when the team has a validated problem but hasn't chosen a solution approach. | 3 |
| [nw-diverger-reviewer](nw-diverger-reviewer.md) | Other | Use as peer reviewer for nw-diverger outputs — validates JTBD rigor, research evidence quality, option structural diversity, taste application correctness, and recommendation coherence. Runs on Haiku for cost efficiency. | 1 |
| [nw-documentarist](nw-documentarist.md) | Other | Use for documentation quality enforcement using DIVIO/Diataxis principles. Classifies documentation type, validates against type-specific criteria, detects collapse patterns, and provides actionable improvement guidance. | 3 |
| [nw-documentarist-reviewer](nw-documentarist-reviewer.md) | Other | Use for reviewing documentarist assessments. Validates classification accuracy, validation completeness, collapse detection, and recommendation quality using Haiku model. | 2 |
| [nw-functional-software-crafter](nw-functional-software-crafter.md) | Other | Implements the functional change for one ready ordered batch. | 1 |
| [nw-nwave-buddy](nw-nwave-buddy.md) | Other | Use for any nWave question — methodology, project navigation, command help, wave status, migration, and troubleshooting. The first agent to consult when unsure about anything in nWave. | 4 |
| [nw-platform-architect](nw-platform-architect.md) | DESIGN | Use for DESIGN wave (infrastructure design) and DEVOPS wave (deployment execution, production readiness, stakeholder sign-off). Transforms architecture into deployable infrastructure, then coordinates production delivery and outcome measurement. | 8 |
| [nw-platform-architect-reviewer](nw-platform-architect-reviewer.md) | DESIGN | Use for review and critique tasks - Platform design, CI/CD pipeline, infrastructure, observability, deployment readiness, and production handoff review specialist. Runs on Haiku for cost efficiency. | 0 |
| [nw-plugin-validator](nw-plugin-validator.md) | Other | Use to validate Claude Code plugin structure and schema during DISTILL/DELIVER verification when deliverable_type is `plugin`. Validates plugin manifest, directory layout, hook/command/agent registration, and Claude Code plugin schema compliance. No existing agent knows the plugin schema. Runs on Haiku for cost efficiency. | 1 |
| [nw-product-discoverer](nw-product-discoverer.md) | Other | Conducts evidence-based product discovery through customer interviews, assumption testing, and opportunity validation. Use when validating problems exist, prioritizing opportunities, or confirming market viability before writing requirements. | 3 |
| [nw-product-discoverer-reviewer](nw-product-discoverer-reviewer.md) | Other | Use as peer reviewer for product-discoverer outputs -- validates evidence quality, sample sizes, decision gate compliance, bias detection, and discovery anti-patterns. Runs on Haiku for cost efficiency. | 1 |
| [nw-product-owner](nw-product-owner.md) | Other | Classifies one Request into its ephemeral observable value projection. | 0 |
| [nw-product-owner-reviewer](nw-product-owner-reviewer.md) | Other | Reviews every direct expectation-charter namespace member for value-side independence, completeness, and executable human observability. | 1 |
| [nw-researcher](nw-researcher.md) | Other | Use for evidence-driven research with source verification. Gathers knowledge from web and files, cross-references across multiple sources, and produces cited research documents. | 4 |
| [nw-researcher-reviewer](nw-researcher-reviewer.md) | Other | Use for review and critique tasks - Research quality and evidence review specialist. Runs on Haiku for cost efficiency. | 1 |
| [nw-skill-reviewer](nw-skill-reviewer.md) | Other | Use to review SKILL.md quality during DISTILL/DELIVER verification when deliverable_type is `plugin` or `skill`. Validates skill structure, scope discipline, frontmatter, and domain-knowledge quality. Thin reviewer — reuses nw-agent-builder skill assets. Runs on Haiku for cost efficiency. | 2 |
| [nw-software-crafter](nw-software-crafter.md) | Other | Implements the OO change for one ready ordered batch. | 1 |
| [nw-software-crafter-reviewer](nw-software-crafter-reviewer.md) | Other | Independently reviews the whole candidate with captured native evidence. | 0 |
| [nw-solution-architect](nw-solution-architect.md) | Other | Returns typed design facts consumed by one DES run. | 0 |
| [nw-solution-architect-reviewer](nw-solution-architect-reviewer.md) | Other | Reviews durable architecture decisions for evidence, reuse, boundaries, cross-layer algebra, residual stress behavior, test substrate, and absence of drift. | 1 |
| [nw-system-designer](nw-system-designer.md) | DESIGN | Use for DESIGN wave infrastructure-level architecture. Designs distributed systems, scalability strategies, load balancing, caching, database sharding, message queues, back-of-envelope estimation, and trade-off analysis. Complements solution-architect (application-level) with infrastructure-level depth. | 6 |
| [nw-system-designer-reviewer](nw-system-designer-reviewer.md) | DESIGN | Use to review system design architecture outputs. Validates trade-off analysis, estimation accuracy, pattern applicability, SPOF detection, and scalability claims. Pairs with system-designer. | 3 |
| [nw-test-optimizer](nw-test-optimizer.md) | Other | Minimize test cost while preserving observable behavior and coverage. Reads production code but modifies tests only. | 1 |
| [nw-test-optimizer-reviewer](nw-test-optimizer-reviewer.md) | Other | Independently reviews test optimization. Read-only; vetoes production drift, behavior or coverage loss, and unmapped deletion. | 1 |
| [nw-troubleshooter](nw-troubleshooter.md) | Other | Use for investigating system failures, recurring issues, unexpected behaviors, or complex bugs requiring systematic root cause analysis with evidence-based investigation. | 4 |
| [nw-troubleshooter-reviewer](nw-troubleshooter-reviewer.md) | Other | Independently falsifies root-cause analyses and their prevention claims. | 1 |
| [nw-user-examiner](nw-user-examiner.md) | Other | Source-blind judge of supplied installed-observation evidence. | 0 |
