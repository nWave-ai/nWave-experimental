---
name: nw-post-mortem-framework
description: Blameless post-mortem structure, incident timeline reconstruction, response evaluation, and organizational learning
user-invocable: false
disable-model-invocation: true
---

# Post-Mortem Framework

## Principles

- **Blameless**: focus on systems/processes, not individuals. People make reasonable decisions given available info.
- **Evidence-based**: every finding backed by logs, metrics, or documented actions
- **Action-oriented**: every finding produces concrete, assigned action item
- **Learning-focused**: capture what worked alongside what failed

## Post-Mortem Document Structure

```markdown
# Post-Mortem: [Incident Title]

**Date**: [incident date]
**Duration**: [start to resolution]
**Severity**: [P0-P3]
**Author**: [analyst]

## Summary
[2-3 sentence overview: what happened, impact, resolution]

## Timeline
| Time | Event | Source |
|------|-------|--------|
| HH:MM | [event] | [log/metric/report] |

## Impact
- Users affected: [number/percentage]
- Duration of impact: [time]
- Business impact: [quantified if possible]
- Systems affected: [list]

## Root Cause Analysis
[5 Whys analysis with evidence at each level]

## Detection and Response
- Time to detect: [duration] -- [how detected]
- Time to respond: [duration] -- [first action]
- Time to mitigate: [duration] -- [mitigation applied]
- Time to resolve: [duration] -- [permanent fix]

## What Went Well
- [positive observations about detection, response, recovery]

## What Could Be Improved
- [areas where detection, response, recovery fell short]

## Action Items
| ID | Action | Owner | Priority | Due Date |
|----|--------|-------|----------|----------|
| 1 | [specific action] | [team/person] | [P0-P3] | [date] |

## Lessons Learned
- [key takeaways for the organization]

## Machine-consumable section (des compile-contract)

ARCHITECTURE-COVERED: docs/analysis/root-cause-analysis-{problem}.md#machine-consumable-section-des-compile-contract

Paradigm: [functional or object-oriented, established above]

| Obligation | Transcribed from (fact already established above) |
|---|---|
| **TOKEN** | "[verbatim quote]" -- [section of this document] |
```

### The terminal section is not optional, and its rules live with the producer

The post-mortem is one SHAPE of RCA document, not a separate class: this template ends
with the same terminal section every RCA document ends with, so the two shapes cannot
contradict each other. The binding rules -- the closed seven-token vocabulary, the
accepted bold label shapes, and the transcription-not-inference discipline with its
self-audit question -- are stated ONCE, in `nw-troubleshooter`'s §Terminal
machine-consumable section, which is resident whenever this skill is loaded. Do not
restate them here; a drifted copy would teach a false contract.

**Does this post-mortem's obligation list quote a fact established in the timeline,
impact, or root-cause analysis above -- or was it filled in because the template shows a
row?** A row you cannot quote is template-following, not a declaration: delete it.

## Incident Timeline Reconstruction

### Sources
1. Monitoring alerts/dashboards (timestamps) | 2. Deployment logs/CI-CD records
3. Communication channels (Slack, email, incident) | 4. VCS (commits, merges, deploys) | 5. User reports/support tickets

### Quality Checks
Events chronological with verified timestamps | gaps >5 min noted/explained | decision points identified with available info | causal relationships noted

## Response Effectiveness Evaluation

### Detection
Detected by monitoring or users? | Duration onset-to-detection? | Existing alerts relevant? Missing?

### Escalation
Right team at right time? | Procedures followed? | Communication clear to stakeholders?

### Resolution
Mitigation effective? | Rollback considered/viable? | Duration mitigation-to-permanent-fix?

## Organizational Learning

### Knowledge Capture
Document root causes as reusable patterns | update runbooks | share in retrospectives

### Process Improvements
Update monitoring/alerting per detection gaps | revise deployment per rollback effectiveness | strengthen testing for failure scenario

### Action Item Tracking
Every item has owner + due date | track in standups/sprint reviews | verify effectiveness post-deployment
