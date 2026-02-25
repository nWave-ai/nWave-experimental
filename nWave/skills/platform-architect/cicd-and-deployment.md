---
name: cicd-and-deployment
description: CI/CD pipeline design methodology, deployment strategies, GitHub Actions patterns, and branch/release strategies. Load when designing pipelines or deployment workflows.
---

# CI/CD Pipeline Design and Deployment Strategies

## Pipeline Stages

### Commit Stage (target: < 10 minutes)
Compile/build | Run unit tests (fast, isolated) | Static code analysis (linting, formatting) | Security scanning (SAST, secrets detection) | Generate build artifacts.
Quality gates: build success | 100% unit test pass rate | coverage threshold (e.g., > 80%) | no critical vulnerabilities | no secrets in code.

### Acceptance Stage (target: < 30 minutes)
Deploy to test environment | Run acceptance/integration/contract tests | Security scanning (DAST).
Quality gates: 100% acceptance/integration pass rate | no high/critical security findings | API contracts validated.

### Capacity Stage (target: < 60 minutes, can run parallel)
Performance, load, and stress testing | Chaos engineering experiments.
Quality gates: performance within SLO thresholds | load test pass (expected traffic + margin) | resilience under failure.

### Production Stage
Progressive deployment (canary/blue-green) | Health checks and smoke tests | SLO monitoring during rollout | Automatic rollback on degradation.
Quality gates: health checks pass | SLOs maintained | no error rate increase | latency within bounds.

## GitHub Actions Patterns

### Workflow Structure
Triggers: push to main/develop | pull_request | release tags | manual workflow_dispatch.
Jobs flow: build -> security -> deploy_staging -> deploy_production. Each with appropriate `needs` dependencies and environment gates.

### Quality Gate Pattern
```yaml
- name: Quality Gate
  run: |
    COVERAGE=$(jq '.totals.percent_covered' coverage.json)
    if (( $(echo "$COVERAGE < 80" | bc -l) )); then
      echo "Coverage $COVERAGE% is below 80% threshold"
      exit 1
    fi
```

### Caching Pattern
```yaml
- uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

### Matrix Testing Pattern
```yaml
strategy:
  matrix:
    python-version: ['3.10', '3.11', '3.12']
    os: [ubuntu-latest, macos-latest]
```

## Deployment Strategies

### Rolling Deployment
Gradual replacement of instances. Kubernetes config: `type: RollingUpdate`, `maxSurge: 25%`, `maxUnavailable: 0`.
- Pros: zero downtime | simple | efficient resources
- Cons: slow rollback | mixed versions during deployment
- Use when: stateless services | no breaking API changes | low-risk changes

### Blue-Green Deployment
Two identical environments, instant switch: Blue (current) serves traffic -> Deploy new to Green -> Smoke tests on Green -> Switch load balancer -> Blue becomes standby/rollback.
- Pros: instant rollback | easy pre-switch testing | clean version separation
- Cons: requires 2x resources | database migrations need care
- Use when: instant rollback needed | critical services | regulated environments

### Canary Deployment
Gradual traffic shift: 5% -> 25% -> 50% -> 100%, monitoring metrics at each step.

Argo Rollouts config:
```yaml
spec:
  strategy:
    canary:
      steps:
      - setWeight: 5
      - pause: {duration: 10m}
      - setWeight: 25
      - pause: {duration: 10m}
      - setWeight: 50
      - pause: {duration: 10m}
      - setWeight: 100
      analysis:
        templates:
        - templateName: success-rate
```

- Pros: low blast radius | real traffic validation | automatic rollback
- Cons: more complex | requires good observability
- Use when: high-traffic services | real-world validation needed | risk-sensitive

### Progressive Delivery
Feature flags + canary + automatic rollback. Components: feature flags for gradual rollout | canary analysis for automatic decisions | SLO monitoring for health validation.
Tools: Argo Rollouts | Flagger | LaunchDarkly/Flagsmith.

## Branch and Release Strategies

Select branching strategy matching team maturity, release cadence, and risk profile. Shapes pipeline triggers, environment promotion, and release automation.

### Trunk-Based Development
Single main branch, short-lived feature branches (< 1 day). Direct commits to main allowed with protection. Releases from main via tags.
- **CI/CD**: Every commit to main triggers full pipeline. Requires robust automated gates since main always releasable. Feature flags manage incomplete work.
- **Triggers**: `push: [main]`, `tags: ['v*']`
- Use when: high-performing teams | continuous deployment | mature test suites.

### GitHub Flow
Feature branches from main, PRs with review, merge to main after approval. Releases from main.
- **CI/CD**: PR-triggered pipelines run commit + acceptance stages. Merge to main triggers deployment. Requires PR quality gates.
- **Triggers**: `pull_request: [main]`, `push: [main]`
- Use when: teams practicing continuous delivery with code review culture.

### GitFlow
Structured branches: main (production) | develop (integration) | feature/* | release/* | hotfix/*.
- **CI/CD**: Branch-specific pipelines. Feature branches: commit stage only. Develop: commit + acceptance. Release: full pipeline. Hotfix: commit + acceptance with fast-track to production.
- **Triggers**: `push: [main, develop, 'release/**', 'hotfix/**']`, `pull_request: [develop]`
- Use when: scheduled releases | multiple versions in production | regulated environments.

### Release Branching
Long-lived release branches (e.g., `release/1.x`, `release/2.x`), cherry-pick fixes between branches.
- **CI/CD**: Per-branch pipelines with independent deployment targets. Cross-branch validation when cherry-picking.
- **Triggers**: `push: [main, 'release/**']`
- Use when: supporting multiple product versions | enterprise software with customer-specific releases.

### Branch Protection Rules (main)
Require PR reviews (2+ approvers) | Require status checks to pass | Require signed commits | Require linear history | Restrict force pushes and deletions.

### Release Workflow
Semantic versioning (MAJOR.MINOR.PATCH): Create release branch -> Bump version -> Update CHANGELOG -> Run full test suite -> Create release tag -> Deploy to production -> Merge back to main.

## Simplest Solution Check for Infrastructure

Before proposing multi-service infrastructure (>3 components), document rejected simple alternatives:
- Single-service deployment (no orchestration) | Managed services instead of self-hosted
- Simple CI/CD (no canary/blue-green) | Monolithic deployment (no microservices infrastructure)

Format:
```markdown
## Rejected Simple Alternatives

### Alternative 1: {Simplest possible approach}
- **What**: {description}
- **Expected Impact**: {what % of requirements this meets}
- **Why Insufficient**: {specific, evidence-based reason}
```
