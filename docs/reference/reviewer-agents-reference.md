# Reviewer Agents Reference

**Version**: 2.0.0
**Date**: 2026-02-13
**Status**: Production Ready

Quick reference for peer review agents - specifications, configuration, and lookup.

**Related Docs**:
- [How to invoke reviewers](../guides/invoke-reviewer-agents.md) (how-to)

---

## Reviewer Agents Matrix

| # | Primary Agent | Reviewer Agent | Focus |
|---|---------------|----------------|-------|
| 1 | product-discoverer | product-discoverer-reviewer | Discovery evidence quality, sample sizes, bias detection |
| 2 | product-owner | product-owner-reviewer | Requirements bias, completeness, testability |
| 3 | solution-architect | solution-architect-reviewer | Architectural bias, ADR quality, feasibility |
| 4 | platform-architect | platform-architect-reviewer | Deployment readiness, CI/CD quality, infrastructure |
| 5 | acceptance-designer | acceptance-designer-reviewer | Happy path bias, GWT quality, coverage |
| 6 | software-crafter | software-crafter-reviewer | Implementation bias, test coupling, complexity |
| 7 | researcher | researcher-reviewer | Source bias, evidence quality, replicability |
| 8 | troubleshooter | troubleshooter-reviewer | Causality logic, evidence quality, alternatives |
| 9 | data-engineer | data-engineer-reviewer | Performance claims, query optimization, security |
| 10 | documentarist | documentarist-reviewer | DIVIO compliance, classification accuracy, collapse detection |
| 11 | agent-builder | agent-builder-reviewer | Template compliance, framework completeness, design patterns |

---

## Reviewer by Wave

### DISCOVER Wave
| Reviewer | When to Use |
|----------|-------------|
| product-discoverer-reviewer | After discovery research and validation |

### DISCUSS Wave
| Reviewer | When to Use |
|----------|-------------|
| product-owner-reviewer | After requirements gathering |

### DESIGN Wave
| Reviewer | When to Use |
|----------|-------------|
| solution-architect-reviewer | After architecture design |

### DEVOP Wave
| Reviewer | When to Use |
|----------|-------------|
| platform-architect-reviewer | After platform/infrastructure design |

### DISTILL Wave
| Reviewer | When to Use |
|----------|-------------|
| acceptance-designer-reviewer | After acceptance tests written |

### DELIVER Wave
| Reviewer | When to Use |
|----------|-------------|
| software-crafter-reviewer | After implementation complete |
| data-engineer-reviewer | After database/query work |

### Cross-Wave
| Reviewer | When to Use |
|----------|-------------|
| researcher-reviewer | After research completed |
| troubleshooter-reviewer | After RCA investigation |
| documentarist-reviewer | After documentation created |
| agent-builder-reviewer | After agent creation |

---

## Agent Specification Files

**Location**: `~/.claude/agents/nw/`

```
~/.claude/agents/nw/
├── nw-acceptance-designer-reviewer.md
├── nw-agent-builder-reviewer.md
├── nw-data-engineer-reviewer.md
├── nw-documentarist-reviewer.md
├── nw-platform-architect-reviewer.md
├── nw-product-discoverer-reviewer.md
├── nw-product-owner-reviewer.md
├── nw-researcher-reviewer.md
├── nw-software-crafter-reviewer.md
├── nw-solution-architect-reviewer.md
└── nw-troubleshooter-reviewer.md
```

---

## Configuration Reference

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NWAVE_REVIEW_ENABLED` | Enable peer reviews | `true` |
| `NWAVE_MAX_ITERATIONS` | Maximum review iterations | `2` |
| `NWAVE_AUTO_TRIGGER` | Auto-trigger after wave completion | `true` |
| `NWAVE_BLOCK_HANDOFF` | Block handoff without approval | `true` |

### Configuration File

**Location**: `.nwave/review.yaml`

```yaml
review_config:
  enabled: true

  automation:
    auto_trigger_after_wave: true
    auto_iterate: true
    max_iterations: 2

  quality_gates:
    block_handoff_without_approval: true
    escalate_after_max_iterations: true

  reviewers:
    product-owner-reviewer:
      enabled: true
      auto_invoke_on: ["DISCUSS wave completion"]

    solution-architect-reviewer:
      enabled: true
      auto_invoke_on: ["DESIGN wave completion"]

    acceptance-designer-reviewer:
      enabled: true
      auto_invoke_on: ["DISTILL wave completion"]

    software-crafter-reviewer:
      enabled: true
      auto_invoke_on: ["DELIVER wave completion"]

  metrics:
    collect_review_metrics: true
    export_to: ["prometheus", "datadog"]

  escalation:
    human_facilitator_email: "team-lead@example.com"
    escalation_timeout: "5 minutes"
```

---

## Review Feedback Format

Reviewers output structured YAML feedback:

```yaml
review_id: "rev_{timestamp}_{artifact_name}"
reviewer: "product-owner-reviewer"
artifact: "docs/feature/{feature-name}/discuss/requirements.md"

strengths:
  - "Clear acceptance criteria for checkout flow"
  - "Well-defined user personas"

issues_identified:
  confirmation_bias:
    - issue: "Technology assumption without stakeholder requirement"
      impact: "May constrain solution options unnecessarily"
      recommendation: "Re-elicit deployment constraints from stakeholders"
      severity: "critical"

  completeness:
    - issue: "Missing error scenarios for payment failure"
      impact: "Incomplete test coverage"
      recommendation: "Add scenarios: card declined, timeout, fraud detection"
      severity: "high"

recommendations:
  - "Address critical issues before DESIGN wave"
  - "Quantify performance requirements"
  - "Add compliance requirements (PCI-DSS)"

approval_status: "rejected_pending_revisions"
iteration: 1
max_iterations: 2
```

### Approval Status Values

| Status | Meaning | Action |
|--------|---------|--------|
| `approved` | All quality criteria met | Proceed to handoff |
| `rejected_pending_revisions` | Issues require fixes | Revise and resubmit |
| `conditionally_approved` | Minor issues, can proceed | Document caveats |

### Severity Levels

| Severity | Definition | Action |
|----------|------------|--------|
| `critical` | Blocks progression, must fix | Fix before resubmission |
| `high` | Significant impact, should fix | Fix before resubmission |
| `medium` | Moderate impact | Fix if time permits |
| `low` | Minor improvement | Optional |

---

## Handoff Triggers

### Wave Completion Triggers

| Transition | Reviewer Required |
|------------|-------------------|
| DISCUSS -> DESIGN | product-owner-reviewer |
| DESIGN -> DISTILL | solution-architect-reviewer |
| DISTILL -> DELIVER | acceptance-designer-reviewer |
| DELIVER -> (done) | software-crafter-reviewer |

### Quality Gate Configuration

```yaml
handoff_quality_gate:
  condition: reviewer_approval_obtained == true
  on_failure:
    action: block_handoff
    message: "Artifact requires peer review approval before handoff"
    next_step: invoke_reviewer
```

---

## Metrics Reference

### Review Effectiveness

| Metric | Target | Description |
|--------|--------|-------------|
| Issues per review | > 3 | Reviewer finding value |
| First iteration approval | 40-60% | Balanced difficulty |
| Critical issues caught | > 0.5 per review | Preventing defects |

### Revision Cycle

| Metric | Target | Alert |
|--------|--------|-------|
| Iterations to approval | <= 1.5 | > 1.8 indicates problems |
| Revision cycle time | < 2 days | > 5 days is bottleneck |
| Issue resolution rate | > 90% | < 80% indicates quality problems |

### Quality Impact

| Metric | Target | Baseline |
|--------|--------|----------|
| Handoff rejection post-review | < 10% | 30-40% without review |
| Defect escape rate | < 5% | Issues missed by reviewer |

---

## Troubleshooting Quick Reference

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Reviewer not found" | Reviewers not in build | Use Task tool manual invocation |
| Review not triggered | Reviews disabled | Check `NWAVE_REVIEW_ENABLED` |
| Infinite loop | Max iterations not set | Set `max_iterations: 2` |
| No feedback | Wrong output format | Check YAML structure |

---

**Last Updated**: 2026-02-13
**Type**: Reference
**Purity**: 98%+
