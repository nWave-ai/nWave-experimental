# Infrastructure Architect Agent Proposal

**Author:** Vera (Orchestrator)
**Date:** 2026-01-27
**Status:** Proposal for Review

---

## Executive Summary

**Recommendation: Create a new `platform-architect` agent.**

Following SOLID principles at the agent design level, the current `solution-architect` agent has a clear Single Responsibility: **software architecture**. Adding DevOps/infrastructure concerns would violate SRP and dilute expertise in both domains.

The gap is visible in recent work: the version-update-experience architecture document contains 1500 lines of comprehensive software architecture (hexagonal design, ADRs, component boundaries, ports/adapters) but only ~35 lines of superficial CI/CD notes (a basic GitHub Actions workflow snippet with no failure handling, no branch protection, no rollback strategy).

**The solution:** A specialized `platform-architect` agent that owns **delivery infrastructure architecture**. It works sequentially after `solution-architect` in the DESIGN wave, consuming deployment unit specifications and producing CI/CD, infrastructure, and observability designs.

---

## Analysis: Why Separation, Not Expansion

### The SOLID Argument

**Single Responsibility Principle applied to agents:**
- An agent should have one domain of expertise
- One "reason to change"
- One set of core competencies

**solution-architect's domain:** Software architecture
- How code is *structured* (hexagonal, DDD, layers)
- How components *interact* (ports, adapters, contracts)
- How business logic is *protected* (domain isolation)
- What technologies *implement* the design (language, frameworks, databases)

**platform-architect's domain:** Delivery infrastructure
- How code is *built* (CI pipelines, test automation)
- How code is *deployed* (containers, orchestration, GitOps)
- How code is *operated* (observability, alerting, SLOs)
- How infrastructure is *provisioned* (IaC, cloud resources)

These are genuinely different cognitive modes:
- solution-architect thinks in: components, interfaces, patterns, domain models
- platform-architect thinks in: pipelines, containers, metrics, infrastructure graphs

### The Risk of Expansion

If we added DevOps to solution-architect:
1. **Context bloat:** The agent's system prompt would grow significantly, diluting focus
2. **Expertise dilution:** Jack of all trades, master of none
3. **Maintenance burden:** Updates to either domain require touching the same agent
4. **Testing complexity:** Adversarial validation becomes harder with mixed concerns
5. **Cognitive overload:** Users would need to context-switch when engaging the agent

### Evidence from Current Gap

The version-update-experience architecture document demonstrates this:
- Software architecture: Detailed hexagonal design, 10 ADRs, quality attributes, component protocols
- CI/CD section: A 30-line workflow snippet with TODO placeholders

This is not a failure of Morgan (solution-architect persona). It's the expected behavior of a software architecture specialist who correctly focuses on their domain.

---

## The Platform Architect Agent

### Identity

```yaml
name: platform-architect
persona_name: Apex
title: Platform & Delivery Infrastructure Architect
icon: "cloud"
wave: DESIGN (sequential after solution-architect)
whenToUse: |
  Use when you need to design CI/CD pipelines, container orchestration,
  infrastructure as code, observability stacks, or deployment strategies.
  Invoked after solution-architect defines software architecture.
```

### Core Responsibility

**Single Responsibility:** Design and document the platform and delivery infrastructure that enables software to be built, deployed, and operated.

### Domain Expertise Areas

```yaml
expertise:
  ci_cd_pipeline_design:
    description: "Design automated build, test, and deployment pipelines"
    technologies:
      - GitHub Actions (primary)
      - GitLab CI
      - Azure DevOps Pipelines
      - Jenkins (legacy migration)
    patterns:
      - Pipeline-as-code
      - Trunk-based development
      - Feature flag deployments
      - Semantic versioning automation

  container_orchestration:
    description: "Design containerized deployments and orchestration"
    technologies:
      - Docker (containerization)
      - Kubernetes (orchestration)
      - Helm (package management)
      - Docker Compose (local development)
    patterns:
      - Multi-stage builds
      - Distroless images
      - Pod security policies
      - Resource quotas and limits

  infrastructure_as_code:
    description: "Design reproducible, version-controlled infrastructure"
    technologies:
      - Terraform (primary)
      - Pulumi
      - CloudFormation
      - Ansible (configuration management)
    patterns:
      - Modular infrastructure
      - Remote state management
      - Drift detection
      - Environment parity

  observability:
    description: "Design monitoring, logging, tracing, and alerting"
    technologies:
      - Prometheus + Grafana (metrics)
      - Loki (logs)
      - Jaeger/Tempo (tracing)
      - PagerDuty/OpsGenie (alerting)
    patterns:
      - RED metrics (Rate, Errors, Duration)
      - USE metrics (Utilization, Saturation, Errors)
      - SLO-based alerting
      - Distributed tracing propagation

  gitops_workflows:
    description: "Design declarative, Git-driven deployment workflows"
    technologies:
      - ArgoCD
      - Flux
      - Kustomize
    patterns:
      - Pull-based deployment
      - Environment promotion
      - Drift remediation
      - Config sync

  deployment_strategies:
    description: "Design safe, reversible deployment approaches"
    patterns:
      - Blue-green deployment
      - Canary releases
      - Rolling updates
      - Progressive delivery
      - Feature flags (LaunchDarkly, Unleash)

  pipeline_security:
    description: "Design security controls in the delivery pipeline"
    patterns:
      - SAST (Static Application Security Testing)
      - DAST (Dynamic Application Security Testing)
      - SCA (Software Composition Analysis)
      - Container scanning
      - SBOM generation
      - Secrets management (Vault, AWS Secrets Manager)
      - Signed commits and artifacts

  branch_and_release_strategy:
    description: "Design branching models and release workflows"
    patterns:
      - Trunk-based development
      - GitFlow (when necessary)
      - Branch protection rules
      - Required reviewers and status checks
      - Release train cadence
```

### What Platform Architect Does NOT Do

```yaml
not_responsible_for:
  - Software architecture (hexagonal, DDD, layers) - solution-architect
  - Business domain modeling - solution-architect
  - Database schema design - solution-architect
  - API contract design - solution-architect
  - Technology selection for application logic - solution-architect
  - Writing implementation code - software-crafter
  - Production deployment execution - devop (DELIVER wave)
  - Incident response coordination - devop (DELIVER wave)
```

---

## Collaboration Model

### Sequential Flow in DESIGN Wave

```
DISCUSS Wave
    |
    v
business-analyst produces requirements
    |
    v
DESIGN Wave
    |
    +---> solution-architect (FIRST)
    |         |
    |         v
    |     Produces:
    |     - docs/design/{feature}/architecture.md
    |     - docs/design/{feature}/component-boundaries.md
    |     - docs/design/{feature}/technology-stack.md
    |     - ADRs for software design decisions
    |     - Deployment units definition
    |         |
    |         v
    +---> solution-architect-reviewer validates
    |         |
    |         v
    +---> platform-architect (SECOND)
    |         |
    |         v
    |     Consumes:
    |     - Deployment units from solution-architect
    |     - Non-functional requirements (SLOs, scaling, availability)
    |     - Security requirements
    |     - Technology stack (what needs CI/CD support)
    |         |
    |         v
    |     Produces:
    |     - docs/design/{feature}/cicd-pipeline.md
    |     - docs/design/{feature}/infrastructure.md
    |     - docs/design/{feature}/deployment-strategy.md
    |     - docs/design/{feature}/observability.md
    |     - .github/workflows/{feature}.yml (design)
    |     - ADRs for platform decisions
    |         |
    |         v
    +---> platform-architect-reviewer validates
    |         |
    |         v
    +---> (Optional) Feedback loop if platform raises concerns
              |
              v
DISTILL Wave
    |
    v
acceptance-designer creates tests for BOTH
software behavior AND deployment behavior
```

### Handover Contracts

**solution-architect -> platform-architect:**

```yaml
handover_contract:
  from: solution-architect
  to: platform-architect

  required_artifacts:
    architecture_document:
      path: "docs/design/{feature}/architecture.md"
      must_contain:
        - deployment_units: "Named components that will be deployed independently"
        - technology_stack: "Languages, frameworks, databases requiring CI/CD support"
        - external_integrations: "Services that need deployment configuration"

    component_boundaries:
      path: "docs/design/{feature}/component-boundaries.md"
      must_contain:
        - port_definitions: "What adapters need infrastructure support"
        - data_flows: "What needs monitoring/observability"

  required_metadata:
    non_functional_requirements:
      - availability_target: "99.9%, 99.99%, etc."
      - latency_slos: "p50, p95, p99 targets"
      - scaling_requirements: "Expected load, burst capacity"
      - recovery_objectives: "RTO, RPO targets"

    security_requirements:
      - authentication_method: "OAuth, API keys, mTLS"
      - compliance_constraints: "SOC2, GDPR, HIPAA"
      - data_classification: "Public, internal, confidential"

  validation:
    - deployment_units_identifiable: true
    - nfrs_quantified: true
    - security_requirements_explicit: true
```

**platform-architect -> acceptance-designer:**

```yaml
handover_contract:
  from: platform-architect
  to: acceptance-designer

  required_artifacts:
    cicd_pipeline_design:
      path: "docs/design/{feature}/cicd-pipeline.md"
      must_contain:
        - pipeline_stages: "Build, test, security scan, deploy stages"
        - failure_handling: "What happens on each failure type"
        - rollback_triggers: "Automatic and manual rollback conditions"
        - quality_gates: "Required checks before promotion"

    deployment_strategy:
      path: "docs/design/{feature}/deployment-strategy.md"
      must_contain:
        - deployment_method: "Blue-green, canary, rolling"
        - promotion_criteria: "What metrics gate promotion"
        - rollback_procedure: "How to revert safely"

    observability_design:
      path: "docs/design/{feature}/observability.md"
      must_contain:
        - key_metrics: "What to measure (RED, USE, custom)"
        - alerting_thresholds: "When to alert, to whom"
        - dashboard_design: "What operators need to see"

  testable_scenarios:
    - "Pipeline failure recovery is testable"
    - "Deployment rollback is testable"
    - "Alert thresholds are verifiable"
    - "SLO compliance is measurable"
```

### Feedback Loop: Platform Raises Concerns

Sometimes platform constraints affect software architecture. The platform-architect may raise concerns that require solution-architect revision:

```yaml
feedback_scenarios:
  cost_concerns:
    example: "Microservices design will cost $50k/month to run on Kubernetes"
    action: "platform-architect returns feedback to solution-architect"
    outcome: "Consider consolidating to fewer deployment units"

  complexity_concerns:
    example: "This architecture requires 15 separate pipelines to maintain"
    action: "platform-architect proposes monorepo or shared pipeline strategy"
    outcome: "solution-architect may revise component boundaries"

  security_concerns:
    example: "External integration requires compliance certification we don't have"
    action: "platform-architect flags blocker for security team"
    outcome: "May require architecture change or timeline adjustment"

  operational_concerns:
    example: "No team has Kubernetes expertise for this complexity"
    action: "platform-architect proposes simpler deployment model"
    outcome: "solution-architect may adjust technology choices"
```

This is healthy tension, not a problem. The feedback loop ensures architecture is both elegant AND deployable.

---

## Example: Versioning and Release Management Feature

### Current State (Gap Visible)

The solution-architect produced:
- Comprehensive hexagonal architecture (1400+ lines)
- 10 ADRs for software design decisions
- Component boundaries with ports and adapters
- Quality attribute scenarios

But CI/CD section was superficial:
- 35 lines of basic GitHub Actions workflow
- No failure handling strategy
- No branch protection design
- No rollback mechanism
- No observability integration

### With Platform Architect

**Step 1: solution-architect produces (already done)**

```markdown
# Architecture Design (summary)
- Hexagonal architecture with VersionManager, BackupManager, UpdateOrchestrator
- Ports: CLI Command Port, Version Source Port, File System Port
- Adapters: GitHub API, Local File System, Git Config, Console UI
- Deployment unit: Single Python package installed to ~/.claude/
- NFRs: Version check < 3s, update < 60s, 99.9% reliability
```

**Step 2: platform-architect receives handover and produces**

```markdown
# docs/design/version-update-experience/cicd-pipeline.md

## CI/CD Pipeline Architecture

### Pipeline Philosophy
- **Trunk-based development:** All commits to main trigger pipeline
- **Semantic versioning:** Automated via semantic-release
- **Quality gates:** Each stage must pass before next

### Pipeline Stages

```yaml
stages:
  1_validation:
    name: "Validate"
    jobs:
      - lint: "Python linting (ruff, mypy)"
      - format: "Code formatting (black, isort)"
      - commit: "Conventional commit validation"
    failure_action: "Block merge, notify author"
    parallelization: true

  2_test:
    name: "Test"
    jobs:
      - unit: "Unit tests with pytest (80% coverage gate)"
      - integration: "Integration tests with real adapters"
      - acceptance: "Acceptance tests (Given-When-Then)"
    failure_action: "Block merge, create failure issue"
    parallelization: true
    timeout: 10 minutes

  3_security:
    name: "Security Scan"
    jobs:
      - sast: "Static analysis (bandit, semgrep)"
      - sca: "Dependency scan (safety, pip-audit)"
      - secrets: "Secrets detection (gitleaks)"
    failure_action: "Block merge, notify security team"
    parallelization: true

  4_build:
    name: "Build"
    jobs:
      - package: "Build distribution package"
      - checksum: "Generate SHA256 checksums"
    artifacts:
      - "dist/nwave-*.tar.gz"
      - "dist/checksums.txt"

  5_release:
    name: "Release"
    trigger: "merge to main"
    jobs:
      - semantic: "Analyze commits, determine version bump"
      - changelog: "Generate changelog from commits"
      - tag: "Create git tag"
      - github: "Create GitHub release with artifacts"
    failure_action: "Alert maintainers, no partial release"
```

### Failure Recovery Strategy

```yaml
failure_recovery:
  validation_failure:
    automatic: true
    action: "Block PR, notify author via GitHub comment"
    recovery: "Author fixes, pushes new commit"

  test_failure:
    automatic: true
    action: "Block PR, create issue if flaky test detected"
    flaky_detection: "3 failures in 24h = flaky, skip for investigation"
    recovery: "Author fixes or marks flaky for investigation"

  security_failure:
    automatic: false
    action: "Block PR, notify security team"
    escalation: "24h response SLA"
    recovery: "Security team approves exception or fix required"

  build_failure:
    automatic: true
    action: "Retry once, then block with detailed logs"
    recovery: "Debug from logs, fix build script"

  release_failure:
    automatic: true
    action: "Alert maintainers via PagerDuty, no partial state"
    rollback: "Delete partial tag if created, cleanup artifacts"
    recovery: "Manual re-run after investigation"
```

### Branch Protection

```yaml
branch_protection:
  main:
    require_pull_request: true
    required_reviewers: 1
    dismiss_stale_reviews: true
    require_status_checks:
      - "validate"
      - "test"
      - "security"
    require_linear_history: true
    restrict_force_push: true
    restrict_deletions: true

  release/*:
    require_pull_request: true
    required_reviewers: 2
    require_status_checks:
      - "validate"
      - "test"
      - "security"
      - "build"
```
```

```markdown
# docs/design/version-update-experience/observability.md

## Observability Architecture

### Key Metrics (RED Method)

```yaml
metrics:
  rate:
    - name: "pipeline_executions_total"
      type: counter
      labels: [stage, status]

    - name: "releases_total"
      type: counter
      labels: [version_type, status]

  errors:
    - name: "pipeline_failures_total"
      type: counter
      labels: [stage, failure_type]

    - name: "security_findings_total"
      type: counter
      labels: [severity, tool]

  duration:
    - name: "pipeline_duration_seconds"
      type: histogram
      labels: [stage]
      buckets: [30, 60, 120, 300, 600]

    - name: "release_duration_seconds"
      type: histogram
      labels: []
      buckets: [60, 120, 300, 600, 900]
```

### Alerting

```yaml
alerts:
  critical:
    - name: "ReleaseFailure"
      condition: "releases_total{status='failed'} increase > 0"
      for: "0m"
      action: "PagerDuty to maintainers"

    - name: "SecurityCritical"
      condition: "security_findings_total{severity='critical'} increase > 0"
      for: "0m"
      action: "PagerDuty to security team"

  warning:
    - name: "PipelineSlow"
      condition: "pipeline_duration_seconds{stage='test'} p95 > 600"
      for: "1h"
      action: "Slack notification to team"

    - name: "FlakyTestDetected"
      condition: "test_retries_total > 3 in 24h for same test"
      for: "0m"
      action: "Create GitHub issue, tag flaky"
```

### Dashboard Design

```yaml
dashboards:
  pipeline_health:
    panels:
      - "Pipeline success rate (24h)"
      - "Average pipeline duration by stage"
      - "Test coverage trend"
      - "Security findings by severity"

  release_status:
    panels:
      - "Releases this week (success/failed)"
      - "Time since last release"
      - "Changelog entries per release"
      - "Breaking changes frequency"
```
```

**Step 3: acceptance-designer includes deployment tests**

```gherkin
# tests/acceptance/features/cicd.feature

Feature: CI/CD Pipeline Behavior
  As a maintainer
  I want the pipeline to enforce quality gates
  So that only valid code reaches production

  Scenario: Conventional commit enforcement
    Given a developer has made changes
    When they commit with message "fixed the bug"
    Then the commit-msg hook should reject with error
    And the error should explain conventional commit format

  Scenario: Pipeline blocks on test failure
    Given a pull request with failing unit tests
    When the pipeline runs
    Then the "test" stage should fail
    And the PR should be blocked from merge
    And the author should receive a GitHub comment

  Scenario: Release rollback on partial failure
    Given a release pipeline in progress
    And the GitHub release creation fails mid-process
    When the failure is detected
    Then any created git tag should be deleted
    And no partial release should be visible
    And maintainers should receive PagerDuty alert
```

---

## Alternative Considered: Hybrid Approach

**Pattern:** solution-architect drafts CI/CD, platform-architect enriches

### Analysis

**Pros:**
- Fewer handoffs
- Single document per concern
- Faster for simple features

**Cons:**
- Blurs responsibility boundaries
- "Enrichment" feels like patch work
- Review becomes murky (who reviews what?)
- Drafting agent may constrain enriching agent's thinking
- When things fail, "who's responsible?" is unclear

### Verdict: Sequential is Superior

The sequential approach with clear handover contracts is superior because:
1. Each agent owns their domain completely
2. Review is straightforward (each reviewer knows their scope)
3. Artifacts are clearly attributed
4. Handover contracts force explicit communication
5. Easier to maintain and evolve each agent independently
6. Clean separation aligns with nWave methodology

---

## Implementation Recommendation

### Phase 1: Agent Creation

1. Create `platform-architect.md` agent specification
   - Follow AGENT_TEMPLATE.yaml structure exactly
   - Include all 5 production frameworks (contract, safety, testing, observability, error recovery)
   - Define expertise areas as documented above

2. Create `platform-architect-reviewer.md` for peer review
   - Focus on infrastructure best practices validation
   - Check for security, reliability, and maintainability concerns

### Phase 2: Integration

1. Update `solution-architect.md` handoff section
   - Add explicit handoff to platform-architect
   - Define deployment unit output requirements

2. Update nWave workflow documentation
   - Document sequential DESIGN wave flow
   - Add platform-architect to agent catalog

### Phase 3: Validation

1. Test with real feature (version-update-experience)
   - Have platform-architect design CI/CD for existing architecture
   - Validate handover contracts work in practice

2. Adversarial review of agent outputs
   - Verify platform designs are actionable
   - Verify solution-architect can provide required inputs

---

## Risk Assessment

### Risk 1: Handoff Friction

**Probability:** Medium
**Impact:** Medium

**Mitigation:**
- Clear handover contract schema
- Validation tooling (check required fields)
- Feedback loop when inputs insufficient

### Risk 2: Scope Creep Between Agents

**Probability:** Low
**Impact:** High

**Mitigation:**
- Clear "NOT responsible for" sections in both agents
- Reviewer agents enforce boundaries
- Documentation of edge cases

### Risk 3: Increased Cycle Time

**Probability:** Medium
**Impact:** Low

**Mitigation:**
- Sequential but focused (each agent does one thing well)
- Parallelization where possible (both reviewers can work simultaneously)
- Skip platform-architect for trivial features (Mike's decision)

---

## Conclusion

The evidence is clear: software architecture and platform/infrastructure architecture are distinct domains requiring separate expertise. The current `solution-architect` correctly focuses on software design, leaving a gap in delivery infrastructure.

Creating a specialized `platform-architect` agent:
- Follows SOLID principles (SRP at agent level)
- Maintains the quality that Morgan (solution-architect) provides for software design
- Fills the documented gap in CI/CD, observability, and deployment design
- Integrates cleanly with existing nWave workflow (sequential in DESIGN wave)
- Enables comprehensive acceptance testing of both code behavior AND deployment behavior

**Recommendation:** Proceed with platform-architect agent creation using this specification.

---

## Appendix: Quick Reference Comparison

| Aspect | solution-architect (Morgan) | platform-architect (Apex) |
|--------|----------------------------|---------------------------|
| Wave | DESIGN (first) | DESIGN (second) |
| Focus | Software architecture | Delivery infrastructure |
| Thinks in | Components, interfaces, patterns | Pipelines, containers, metrics |
| Produces | Architecture.md, ADRs, component boundaries | CI/CD design, IaC, observability |
| Consumes | Requirements from business-analyst | Deployment units from solution-architect |
| Hands off to | platform-architect | acceptance-designer |
| Key question | "How is the code structured?" | "How is the code delivered?" |
| Reviewer | solution-architect-reviewer | platform-architect-reviewer |
