# nw-platform-architect

Use for DESIGN wave (infrastructure design) and DEVOPS wave (deployment execution, production readiness, stakeholder sign-off). Transforms architecture into deployable infrastructure, then coordinates production delivery and outcome measurement.

**Wave:** DESIGN
**Model:** sonnet
**Max turns:** 45
**Tools:** Read, Write, Edit, Bash, Glob, Grep, Task, Skill

## Commands

- [`/nw-design`](../commands/index.md)
- [`/nw-devops`](../commands/index.md)
- [`/nw-discuss`](../commands/index.md)
- [`/nw-finalize`](../commands/index.md)

## Preloaded skills

- [nw-cicd-and-deployment](../skills/nw-cicd-and-deployment.md) — CI/CD pipeline design methodology, deployment strategies, GitHub Actions patterns, and branch/release strategies. Load when designing pipelines or deployment workflows.
- [nw-cross-cutting-invariants](../skills/nw-cross-cutting-invariants.md) — Cross-cutting normative invariants — paradigm-independent and role-independent rules that bind every architect and crafter (data justification, gate design GDP-1..9, self-explaining surfaces). SHIPPED home of these definitions; cite by clause id, never re-declare.
- [nw-deliver](../skills/nw-deliver.md) — Orchestrates the current DELIVER wave end-to-end. Use when all prior waves are complete and the feature is ready for implementation.
- [nw-deployment-strategies](../skills/nw-deployment-strategies.md) — Rollback procedures, risk assessment, pre/post-deployment validation, and contingency planning. Load when orchestrating deployment or preparing rollback plans. For deployment strategy details (canary, blue-green, rolling), see `cicd-and-deployment` skill.
- [nw-infrastructure-and-observability](../skills/nw-infrastructure-and-observability.md) — Infrastructure as Code patterns (Terraform, Kubernetes), observability design (SLOs, metrics, alerting, dashboards), and pipeline security stages. Load when designing infrastructure, observability, or security scanning.
- [nw-platform-engineering-foundations](../skills/nw-platform-engineering-foundations.md) — Foundational platform engineering knowledge from key references -- Continuous Delivery, SRE, Accelerate, Team Topologies, Chaos Engineering, and Secure Delivery. Load when contextual grounding in platform engineering theory is needed.
- [nw-production-readiness](../skills/nw-production-readiness.md) — Monitoring, observability, operational procedures, CI/CD lessons learned, and quality gate definitions. Load when assessing production readiness or validating operational excellence.
- [nw-stakeholder-engagement](../skills/nw-stakeholder-engagement.md) — Demonstration preparation, audience-tailored presentations, feedback collection, and business outcome measurement. Load when preparing demos or measuring business value delivery.
