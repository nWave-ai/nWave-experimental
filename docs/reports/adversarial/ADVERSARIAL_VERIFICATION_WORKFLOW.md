# Layer 4 Adversarial Verification Workflow
**Version**: 1.5.2
**Date**: 2026-01-22
**Status**: Production Ready

## Executive Summary

Layer 4 Adversarial Verification is a **peer review workflow** where an equal-expertise agent reviews outputs from a primary agent to reduce confirmation bias, identify completeness gaps, and improve quality through independent critique. This layer is **distinct from Layer 3 adversarial output validation** (which challenges output validity through adversarial scrutiny like source verification and edge case testing).

### Key Innovation

This is a **NOVEL contribution** to AI agent testing frameworks. While Layer 3 focuses on adversarial challenges to output quality (source credibility, bias detection in outputs, edge cases, security vulnerabilities), Layer 4 introduces **collaborative peer review** for bias reduction and quality improvement through fresh perspective.

### Universal Application

Layer 4 applies to **ALL agents** (document-producing, code-producing, tool agents, orchestrators) with reviewer implementations adapted to agent output types.

---

## Table of Contents

1. [Workflow Overview](#workflow-overview)
2. [5-Phase Review Process](#5-phase-review-process)
3. [Reviewer Agent Specifications](#reviewer-agent-specifications)
4. [Review Output Format](#review-output-format)
5. [Automation Triggers](#automation-triggers)
6. [Integration with Other Layers](#integration-with-other-layers)
7. [Quality Gates](#quality-gates)
8. [Metrics and Monitoring](#metrics-and-monitoring)

---

## Workflow Overview

### Purpose

**Reduce Confirmation Bias**: Primary agents may miss issues due to cognitive biases (confirmation bias, anchoring bias, availability bias). Independent peer review provides fresh perspective.

**Improve Quality**: Peer reviewers identify:
- Completeness gaps (missing scenarios, stakeholders, requirements)
- Clarity issues (ambiguous requirements, unmeasurable criteria)
- Bias patterns (technology bias, happy path bias, selection bias)
- Feasibility concerns (implementation challenges, resource constraints)

### Distinction from Layer 3

| Aspect | Layer 3: Adversarial Output Validation | Layer 4: Adversarial Verification |
|--------|----------------------------------------|-----------------------------------|
| **Purpose** | Challenge output validity | Quality validation through peer review |
| **Validator** | Adversarial challenges to outputs | Equal agent (same expertise) |
| **Validates** | Source credibility, bias in OUTPUT, edge cases, security | Bias, completeness, quality, assumptions |
| **Approach** | Systematic adversarial questioning | Constructive critique and improvement |
| **Example** | "Can all cited sources be verified?" | "Are requirements reflecting stakeholder needs or analyst assumptions?" |

Both validate **OUTPUT quality**, but through different mechanisms:
- **Layer 3**: Stress testing, attack scenarios, validity challenges
- **Layer 4**: Collaborative peer review, constructive feedback, iteration

---

## 5-Phase Review Process

### Phase 1: Artifact Production

**Actor**: Primary agent (e.g., business-analyst, solution-architect, software-crafter)

**Process**:
1. Primary agent executes command (e.g., `*gather-requirements`)
2. Agent produces artifact (e.g., requirements.md, architecture.md, source code)
3. Artifact passes **Layer 1 Unit Tests** (structural and quality validation)

**Outputs**:
- Artifact file(s) meeting Layer 1 quality gates
- Metadata: creation timestamp, agent ID, command executed

**Quality Gate**: All Layer 1 unit tests must pass before Layer 4 review begins

---

### Phase 2: Peer Review

**Actor**: Reviewer agent (e.g., business-analyst-reviewer, solution-architect-reviewer)

**Process**:

1. **Load Artifact**: Reviewer loads output from Phase 1
2. **Analyze for Bias**: Apply critique dimensions specific to agent type
3. **Validate Completeness**: Check coverage across dimensions (stakeholders, scenarios, requirements)
4. **Assess Clarity**: Identify ambiguity, vagueness, unmeasurable criteria
5. **Verify Quality**: Apply domain-specific quality standards
6. **Generate Structured Feedback**: YAML format with strengths, issues, recommendations

**Critique Dimensions by Agent Type**:

| Agent Type | Critique Focus | Example Issue |
|------------|----------------|---------------|
| business-analyst | Confirmation bias, completeness, testability | "Requirements assume cloud deployment without stakeholder requirement" |
| solution-architect | Architectural bias, ADR quality, feasibility | "Technology choices driven by preference vs requirements" |
| acceptance-designer | Happy path bias, GWT quality, coverage | "8/10 scenarios test success, only 2/10 test errors" |
| software-crafter | Implementation bias, test coupling, complexity | "Caching implemented without caching requirement" |
| knowledge-researcher | Source bias, evidence quality, replicability | "Sources cherry-picked to support predetermined narrative" |

**Outputs**:
- Structured review feedback (YAML format)
- Issues categorized by severity (critical, high, medium, low)
- Specific, actionable recommendations
- Approval status (approved, rejected_pending_revisions, conditionally_approved)

**Review Criteria**:
- `no_critical_bias_detected`: Confirmation, availability, technology bias
- `completeness_validated`: All dimensions covered (stakeholders, scenarios, requirements)
- `clarity_confirmed`: Unambiguous, measurable, specific
- `quality_standards_met`: Domain-specific quality gates passed

---

### Phase 3: Revision

**Actor**: Primary agent (original agent)

**Process**:

1. **Review Feedback**: Load structured review from Phase 2
2. **Prioritize Issues**: Address critical and high severity issues first
3. **Re-elicit Information**: Gather missing information from stakeholders/sources
4. **Clarify Ambiguities**: Make vague requirements specific and measurable
5. **Revise Artifact**: Produce version 2 (v2) addressing feedback
6. **Document Changes**: Track how each issue was addressed for traceability

**Addressing Issue Examples**:

**Issue**: "Requirements assume cloud deployment without stakeholder requirement"
**Resolution**:
- Re-interview Infrastructure Lead and CTO
- Document deployment constraints: "Deployment-agnostic, supports cloud and on-premise per CTO requirement"
- Add constraint rationale to requirements.md Section 3.2

**Issue**: "Performance requirement 'System should be fast' is vague"
**Resolution**:
- Elicit specific latency requirements: "API responds to search queries within 2 seconds (p95) under 1000 concurrent users"
- Update acceptance criterion AC-3 with quantitative threshold

**Outputs**:
- Revised artifact (v2)
- Revision notes documenting issue resolution
- Traceability links from issues to resolutions

---

### Phase 4: Approval Validation

**Actor**: Reviewer agent (same as Phase 2)

**Process**:

1. **Load Revised Artifact**: Reviewer loads v2 from Phase 3
2. **Verify Issue Resolution**: Check critical and high issues addressed
3. **Check for New Issues**: Ensure revision didn't introduce new problems
4. **Decide Approval**: Approve OR request second iteration (max 2 total iterations)

**Approval Criteria**:
- `all_critical_issues_resolved`: true
- `all_high_issues_addressed`: true (or explicitly accepted as won't-fix with justification)
- `no_new_critical_issues`: true
- `quality_standards_met`: true

**Decision Outcomes**:

| Outcome | Condition | Next Step |
|---------|-----------|-----------|
| **Approved** | All criteria met | Phase 5: Handoff |
| **Conditionally Approved** | Medium issues remain, critical/high resolved | Phase 5 with caveats documented |
| **Rejected** | Critical/high issues unresolved, iteration < 2 | Return to Phase 3 (second iteration) |
| **Escalated** | Critical issues unresolved after 2 iterations | Human facilitator review required |

**Outputs**:
- Approval decision with rationale
- Final review feedback
- Iteration count (1 or 2)

**Iteration Limit**: Maximum 2 iterations. If quality standards not met after 2 iterations, escalate to human facilitator for workshop/collaboration session.

---

### Phase 5: Handoff

**Actor**: Primary agent (with reviewer approval)

**Condition**: `reviewer_approval_obtained: true`

**Process**:

1. **Package Artifacts**: Collect all deliverables
2. **Include Review History**: Attach peer review approval and feedback
3. **Add Traceability**: Link revision notes for transparency
4. **Handoff to Next Agent**: Transfer package to next wave (e.g., DESIGN → DISTILL)

**Handoff Package Contents**:

```yaml
handoff_package:
  deliverables:
    - artifact: "requirements.md (approved version v2)"
    - peer_review_approval: "review_20251006_requirements_approved.yaml"
    - revision_notes: "revision_notes_v1_to_v2.md"

  validation_status:
    layer_1_unit_tests: "passed"
    layer_4_peer_review: "approved"
    critical_issues_resolved: true
    iteration_count: 1

  next_agent: "solution-architect"
  wave_transition: "DISCUSS → DESIGN"
```

**Quality Gate**: Handoff only occurs when Layer 4 approval obtained. No exceptions.

---

## Reviewer Agent Specifications

### Complete Reviewer Agent List

| Primary Agent | Reviewer Agent | Persona Name | Focus |
|---------------|----------------|--------------|-------|
| business-analyst | business-analyst-reviewer | Scout | Requirements bias, completeness, testability |
| solution-architect | solution-architect-reviewer | Atlas | Architectural bias, ADR quality, feasibility |
| acceptance-designer | acceptance-designer-reviewer | Sentinel | Happy path bias, GWT quality, coverage |
| software-crafter | software-crafter-reviewer | Mentor | Implementation bias, test coupling, complexity |
| knowledge-researcher | knowledge-researcher-reviewer | Scholar | Source bias, evidence quality, replicability |
| data-engineer | data-engineer-reviewer | Validator | Performance claims, query optimization, security |
| architecture-diagram-manager | architecture-diagram-manager-reviewer | Clarity | Visual clarity, consistency, stakeholder accessibility |
| visual-2d-designer | visual-2d-designer-reviewer | Critic | 12 principles compliance, timing, readability |
| feature-completion-coordinator | feature-completion-coordinator-reviewer | Auditor | Handoff completeness, phase validation, traceability |
| root-cause-analyzer | root-cause-analyzer-reviewer | Logician | Causality logic, evidence quality, alternatives |
| walking-skeleton-helper | walking-skeleton-helper-reviewer | Minimalist | Minimal scope, E2E completeness, deployment viability |
| agent-forger | agent-forger-reviewer | Inspector | Template compliance, framework completeness, design patterns |

### Reviewer Agent Capabilities

All reviewer agents implement:

1. **Independent Critique**: Not invested in original approach
2. **Structured Feedback**: YAML format for consistency and machine parsing
3. **Severity Classification**: Critical, high, medium, low
4. **Actionable Recommendations**: Specific guidance for addressing issues
5. **Approval Decision**: Approved, rejected, conditionally approved
6. **Iteration Management**: Track iteration count (max 2)

---

## Review Output Format

### Structured YAML Format

All reviewer agents produce feedback in consistent YAML format for machine parsing and traceability:

```yaml
review_id: "rev_{YYYYMMDD_HHMMSS}_{artifact_name}"
artifact_reviewed: "{path/to/artifact.md}"
reviewer: "{reviewer-agent-id}"
review_date: "{ISO 8601 timestamp}"

strengths:
  - "{Positive aspect 1 with specific example from artifact}"
  - "{Positive aspect 2 with specific example from artifact}"

issues_identified:
  {critique_dimension_1}:
    - issue: "{Specific issue detected}"
      impact: "{Business or technical consequence}"
      recommendation: "{Specific, actionable improvement}"
      severity: "{critical | high | medium | low}"
      location: "{Section reference or line number in artifact}"

  {critique_dimension_2}:
    - issue: "{Another specific issue}"
      impact: "{Consequence of issue}"
      recommendation: "{How to address issue}"
      severity: "{severity_level}"

recommendations:
  1: "{Highest priority action}"
  2: "{Second priority action}"
  3: "{Third priority action}"

approval_status: "{approved | rejected_pending_revisions | conditionally_approved}"
critical_issues_count: {number}
high_issues_count: {number}
iteration_number: {1 or 2}
next_steps: "{Guidance for original agent on how to address feedback}"
```

### Severity Definitions

| Severity | Definition | Impact on Approval |
|----------|------------|-------------------|
| **Critical** | Blocks handoff - must be resolved before next wave | Approval impossible until resolved |
| **High** | Significant quality concern - strongly recommend addressing | Approval unlikely without resolution or explicit won't-fix justification |
| **Medium** | Quality improvement opportunity - should address if time permits | Conditional approval possible |
| **Low** | Minor enhancement suggestion - optional | Does not affect approval |

---

## Automation Triggers

### When Layer 4 is Triggered

Layer 4 Adversarial Verification can be triggered in multiple ways:

#### 1. Automatic Trigger (Recommended)

**Condition**: Automatically after Layer 1 unit tests pass

**Workflow**:
```
Primary Agent → Artifact → Layer 1 Unit Tests → PASS → Auto-trigger Layer 4 Review
```

**Configuration**:
```yaml
automation:
  trigger: "on_layer_1_pass"
  reviewer_agent: "{agent-id}-reviewer"
  async: false  # Wait for approval before proceeding
```

#### 2. Critical Handoff Points

**Condition**: Before critical wave transitions

**Critical Handoffs**:
- DISCUSS → DESIGN: Requirements → Architecture
- DESIGN → DISTILL: Architecture → Acceptance Tests
- DEVOP → DISTILL: Acceptance Tests → Implementation
- DISTILL → DELIVER: Implementation → Production Deployment

**Workflow**:
```
Wave Completion → Handoff Preparation → Layer 4 Review → Approval → Handoff
```

#### 3. On-Demand by User Request

**Condition**: User explicitly requests peer review

**Commands**:
- `*request-peer-review {artifact_path}`
- `*review-requirements docs/requirements/requirements.md`
- `*validate-architecture docs/architecture/architecture.md`

#### 4. CI/CD Pipeline Integration

**Condition**: As part of continuous integration pipeline

**Pipeline Stage**:
```yaml
stages:
  - build
  - test_layer_1_unit
  - test_layer_2_integration
  - test_layer_3_adversarial_security
  - test_layer_4_peer_review  # ← Layer 4 Verification
  - deploy
```

**Failure Handling**: Pipeline fails if Layer 4 approval not obtained, blocking deployment.

---

## Integration with Other Layers

### Layer 1: Unit Testing

**Relationship**: Layer 4 review occurs **AFTER** Layer 1 passes

**Rationale**: No point in peer reviewing structurally invalid artifacts. Layer 1 validates basic quality before human-equivalent peer review.

**Flow**:
```
Artifact → Layer 1 Unit Tests → FAIL → Fix → Retry
                               → PASS → Layer 4 Peer Review
```

### Layer 2: Integration Testing

**Relationship**: Layer 4 approval **ENABLES** Layer 2 handoff validation

**Rationale**: Peer-reviewed artifacts have higher handoff success rate. Next agent can consume outputs without re-elicitation.

**Flow**:
```
Layer 4 Approval → Handoff → Layer 2 Integration Test (Next Agent Consumption)
```

### Layer 3: Adversarial Security Testing

**Relationship**: Layer 3 validates **AGENT security**, Layer 4 validates **OUTPUT quality**

**Distinction**:
- **Layer 3**: Prompt injection, jailbreak, credential access, tool misuse (AGENT attacks)
- **Layer 4**: Bias detection, completeness gaps, quality issues (OUTPUT quality)

**Independence**: Layers 3 and 4 validate different aspects and can run in parallel:

```
Artifact Production
    ↓
    ├─→ Layer 3: Adversarial Security (Agent Attack Testing)
    └─→ Layer 4: Peer Review (Output Quality Validation)
            ↓
         Both Pass → Proceed
```

---

## Quality Gates

### Reviewer Quality Gates

Reviewers themselves must meet quality standards:

#### Review Completeness

- ✅ All critique dimensions evaluated (bias, completeness, clarity, testability)
- ✅ Specific examples provided (all issues reference artifact locations)
- ✅ Actionable recommendations (clear guidance for addressing each issue)
- ✅ Severity assigned (all issues classified)

#### Objectivity Validation

- ✅ Evidence-based critique (all feedback backed by artifact evidence)
- ✅ Balanced feedback (strengths and issues both documented)
- ✅ Constructive tone (critique is actionable, not destructive)
- ✅ No reviewer bias (reviewer not introducing own technology/approach bias)

#### Standards Enforcement

- ✅ Critical issues blocking (critical issues must be resolved before approval)
- ✅ Quality threshold maintained (high standards consistently applied)
- ✅ Iteration limit enforced (max 2 iterations, escalate if needed)

### Approval Quality Gates

Primary agent revision must meet:

- ✅ All critical issues resolved
- ✅ All high issues addressed (or explicit won't-fix with justification)
- ✅ No new critical issues introduced
- ✅ Quality standards met (domain-specific metrics)

---

## Metrics and Monitoring

### Review Effectiveness Metrics

```yaml
metrics:
  issues_identified_per_review:
    calculation: "count(issues) by severity"
    dimensions: [critical, high, medium, low]
    target: "> 3 issues per review (indicating value add)"

  approval_rate_first_iteration:
    calculation: "count(approved_iteration_1) / count(total_reviews)"
    target: "40-60% (balance: not too easy, not too hard)"

  critical_issues_caught:
    calculation: "count(critical_issues_identified)"
    target: "> 0.5 critical issues per review"
    note: "Critical issues prevent production defects"
```

### Revision Cycle Metrics

```yaml
metrics:
  average_iterations_to_approval:
    calculation: "mean(iteration_count)"
    target: "≤ 1.5 iterations"
    alert: "> 1.8 iterations indicates quality problems in primary agent"

  revision_cycle_time:
    calculation: "time(approval) - time(initial_review)"
    target: "< 2 days (business days)"
    alert: "> 5 days indicates bottleneck"

  issue_resolution_rate:
    calculation: "count(resolved_issues) / count(identified_issues)"
    target: "> 90%"
    alert: "< 80% indicates revision quality problems"
```

### Quality Impact Metrics

```yaml
metrics:
  handoff_rejection_rate_post_review:
    calculation: "count(rejected_handoffs) / count(total_handoffs)"
    target: "< 10% (peer review reduces handoff failures)"
    baseline: "30-40% without peer review"

  defect_escape_rate:
    calculation: "count(issues_found_in_next_wave) / count(total_reviews)"
    target: "< 5% (reviewer should catch most issues)"
    note: "Issues found in DESIGN wave that business-analyst-reviewer missed"

  stakeholder_satisfaction:
    measurement: "Qualitative feedback on artifact quality improvement"
    target: "Positive feedback trend"
```

---

## Benefits Summary

### Bias Reduction

1. **Confirmation Bias**: Reviewer not invested in original approach
2. **Availability Bias**: Fresh perspective on alternatives
3. **Anchoring Bias**: Not anchored to initial assumptions
4. **Technology Bias**: Detects premature solution choices

### Quality Improvement

1. **Completeness**: Identifies gaps original agent missed
2. **Clarity**: Validates understandability by independent reader
3. **Robustness**: Challenges assumptions and edge cases
4. **Testability**: Ensures acceptance criteria truly measurable

### Knowledge Transfer

1. **Best Practices**: Reviewer shares alternative approaches
2. **Pattern Recognition**: Identifies anti-patterns
3. **Continuous Improvement**: Feedback loop improves both agents
4. **Organizational Learning**: Review history builds knowledge base

### Stakeholder Confidence

1. **Independent Validation**: Not self-review, peer-reviewed
2. **Quality Assurance**: Multi-agent validation before production
3. **Audit Trail**: Documented review process for compliance
4. **Reduced Defect Escape**: Catches issues before handoff

---

## Escalation Procedures

### When to Escalate

Escalate to human facilitator when:

1. **Iteration Limit Reached**: 2 iterations complete, quality standards still not met
2. **Critical Issue Deadlock**: Disagreement on critical issue resolution approach
3. **Scope Ambiguity**: Fundamental misunderstanding of requirements needing stakeholder clarification
4. **Resource Constraints**: Technical/budget constraints making requirements unachievable

### Escalation Process

```yaml
escalation:
  trigger: "iteration_count >= 2 AND approval_status != approved"

  action:
    1: "Pause workflow - no further automated iterations"
    2: "Generate escalation report with issue history"
    3: "Notify human facilitator (email, Slack, PagerDuty)"
    4: "Recommend live collaboration session (workshop, meeting)"

  escalation_report:
    - unresolved_critical_issues: "List with rationale for non-resolution"
    - iteration_history: "Review feedback from iteration 1 and 2"
    - recommended_next_steps: "Workshop agenda, stakeholder involvement needed"

  resolution:
    - live_session: "Human facilitator leads workshop to resolve issues"
    - explicit_acceptance: "Critical issues documented as won't-fix with business justification"
    - requirements_change: "Fundamental requirements revision needed"
```

---

## Conclusion

Layer 4 Adversarial Verification is a production-ready peer review workflow that:

1. **Reduces Bias**: Independent perspective catches confirmation bias, availability bias, technology bias
2. **Improves Quality**: Identifies completeness gaps, clarity issues, testability concerns
3. **Enables Handoffs**: Peer-reviewed artifacts have higher handoff success rate
4. **Builds Confidence**: Independent validation provides stakeholder assurance
5. **Transfers Knowledge**: Review feedback improves both primary and reviewer agents

**Status**: Ready for implementation across all 12 primary agents with corresponding reviewer agents.

**Next Steps**: See LAYER_4_INTEGRATION_GUIDE.md for developer, user, and CI/CD integration instructions.
