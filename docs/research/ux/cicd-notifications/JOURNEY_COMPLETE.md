# CI/CD Notification Journey - COMPLETE ✅

**Journey**: cicd-notifications
**Designer**: Luna (leanux-designer)
**Date**: 2026-01-31
**Status**: ✅ READY FOR HANDOFF TO DAKOTA

---

## Summary

Designed the complete user experience for "back to green" CI/CD Slack notifications that prevent alarm fatigue through:

1. **Clear ownership** - Every RED notification @mentions the commit author
2. **Emotional closure** - GREEN notifications celebrate recovery and reassure team
3. **Actionable information** - Failed jobs listed with error types, one-click investigation
4. **Visual distinction** - RED (danger) vs GREEN (primary) instantly recognizable
5. **Noise reduction** - Only critical branches (master/develop/installer) trigger notifications

---

## Deliverables

### 1. Visual Journey Map
**File**: `journey-cicd-notifications-visual.md`

**Contents**:
- Complete ASCII journey for Scenario A (developer breaks/fixes build)
- Complete ASCII journey for Scenario B (teammate fixes build while developer away)
- Design rationale for anti-alarm-fatigue patterns
- Integration checkpoints
- Emotional arc validation

**Key Insights**:
- Recovery notification must provide both celebration (developer pride) AND team reassurance (all clear signal)
- Time-since-failure creates urgency context (18 min = responsive, 2h 34m = long wait)
- "Previously failed" jobs in GREEN prove recovery (builds trust)

---

### 2. Structured Journey Schema
**File**: `journey-cicd-notifications.yaml`

**Contents**:
- Complete step-by-step journey with emotional states
- Slack Block Kit JSON for RED and GREEN notifications
- Shared artifact tracking (10 artifacts with sources)
- Integration validation checkpoints
- Anti-alarm-fatigue design patterns
- Future enhancement ideas

**Critical Artifacts**:
- `author` (git → Slack user ID) - HIGH RISK if mapping breaks
- `previous_run_id` - CRITICAL for state transition detection
- `failed_jobs` - MEDIUM RISK, must persist from RED to GREEN
- `time_since_failure` - HIGH RISK, requires state persistence

---

### 3. Acceptance Test Scenarios
**File**: `journey-cicd-notifications.feature`

**Contents**:
- 20+ Gherkin scenarios covering:
  - Happy paths (developer fixes own build, teammate fixes build)
  - Integration validation (author mapping, job persistence, state tracking)
  - Edge cases (unknown author, long messages, multiple jobs)
  - Anti-alarm-fatigue validation (ownership, closure, actionability)
  - Technical validation (Slack Block Kit limits, API constraints)

**Test Coverage**:
- @horizontal @e2e - End-to-end user journeys
- @integration - Shared artifact validation
- @edge_case - Error handling and graceful degradation
- @alarm_fatigue - Prevention pattern validation
- @technical - Slack API compliance

---

### 4. Shared Artifacts Registry
**File**: `shared-artifacts-registry.md`

**Contents**:
- All 10 shared artifacts with sources, consumers, and integration risks
- 4 integration checkpoints (author attribution, job persistence, state transitions, time calculation)
- 4 bug detection patterns journey design catches
- Handoff checklist for Dakota

**High-Risk Artifacts**:
1. `previous_run_id` (CRITICAL) - Without this, GREEN detection impossible
2. `author` (HIGH) - If mapping breaks, ownership/accountability fails
3. `time_since_failure` (HIGH) - Requires state persistence across runs

---

### 5. Slack Block Kit Examples
**File**: `slack-block-kit-examples.json`

**Contents**:
- Ready-to-use Slack Block Kit JSON templates:
  - RED notification (6 blocks, ~350 chars)
  - GREEN notification (7 blocks, ~420 chars)
  - GREEN with teammate fix (7 blocks)
- Variable substitution guide (all ${placeholders} documented)
- State storage requirements (5 required fields)
- Notification logic (state transition table)
- Error handling (4 fallback scenarios)
- Python template example for Dakota

**Implementation Ready**:
- Well within Slack limits (max 50 blocks, max 3000 chars)
- All placeholders mapped to GitHub webhook payload fields
- Graceful degradation for missing data

---

## Journey Quality Gates - ALL PASSED ✅

### Discovery Complete ✅
- [x] All readiness criteria met
- [x] No vague or unclear steps
- [x] User mental model understood (Mike's answers guide design)

### Journey Completeness ✅
- [x] All steps from push → failure → fix → recovery defined
- [x] All steps have clear actions (push commit, click button, see notification)
- [x] No orphan steps disconnected from flow

### Emotional Coherence ✅
- [x] Emotional arc defined:
  - Start: Productive flow
  - RED: Urgent concern ("I must fix this NOW")
  - Investigation: Focused action
  - Fix: Anxious waiting
  - GREEN: Relief + Celebration ("I fixed it!")
  - End: Confidence + Closure
- [x] All steps have emotional annotations
- [x] No jarring transitions
- [x] Confidence builds progressively (RED guides to action, GREEN validates success)

### Shared Artifact Tracking ✅
- [x] All ${variables} have documented source
- [x] All sources are SINGLE source of truth
- [x] Integration risks assessed (3 HIGH, 1 CRITICAL, 3 MEDIUM, 3 LOW)

### Example Data Quality ✅
- [x] Data is realistic (actual commit messages, real job names)
- [x] Data reveals integration dependencies (git author → Slack ID mapping)

---

## Anti-Alarm-Fatigue Design Validation ✅

### Pattern 1: Ownership ✅
**Problem**: Failures with no owner lead to diffusion of responsibility
**Solution**: @mention author in RED notification
**Validation**: Every RED has exactly one @mention, triggers Slack ping

### Pattern 2: Closure ✅
**Problem**: Channel full of RED with no resolution creates despair
**Solution**: GREEN notification provides emotional closure
**Validation**: Every RED→GREEN transition creates GREEN notification

### Pattern 3: Actionability ✅
**Problem**: Generic "it failed" messages don't help developers act
**Solution**: List failed jobs with error types in RED
**Validation**: Developers can triage without opening GitHub

### Pattern 4: Celebration ✅
**Problem**: Only negative feedback creates demoralizing environment
**Solution**: GREEN uses celebration tone (🎉, positive language, "All systems healthy")
**Validation**: Team feels good about resolving issues

### Pattern 5: Noise Reduction ✅
**Problem**: Too many notifications create spam
**Solution**: Filter to critical branches only (master/develop/installer)
**Validation**: Feature branch failures don't spam #cicd

### Pattern 6: Visual Distinction ✅
**Problem**: All notifications look the same, critical ones get lost
**Solution**: RED=danger style, GREEN=primary style, emoji markers
**Validation**: Developers can triage at a glance (🔴 vs ✅)

---

## Integration Checkpoints - ALL DEFINED ✅

### Checkpoint 1: Author Attribution (RED → GREEN) ✅
- Git author maps consistently to Slack user across notifications
- Handles teammate fixes (different author in GREEN)
- Graceful degradation for unknown authors

### Checkpoint 2: Failed Jobs Persistence (RED → GREEN) ✅
- Failed jobs in RED match "Previously failed" in GREEN
- Job names string-equal validation
- Proves recovery (trust building)

### Checkpoint 3: State Transition Detection ✅
- Dakota correctly detects GREEN→RED, RED→GREEN, GREEN→GREEN
- `previous_run_id` persistence is critical
- Silence when GREEN→GREEN (no spam)

### Checkpoint 4: Time-Since-Failure Calculation ✅
- Accurate time delta between failure and recovery
- Human-readable format (18 min, 2h 34m, 1d 3h)
- Timezone normalization (all UTC internally)

---

## Bug Detection Patterns - IDENTIFIED ✅

The journey design process revealed these potential integration bugs:

### Pattern 1: Multiple Author Sources
**Symptom**: Inconsistent author display (plaintext vs Slack ID)
**Prevention**: Single mapping function for both RED and GREEN

### Pattern 2: Failed Jobs Not Persisted
**Symptom**: GREEN can't show "Previously failed" list
**Prevention**: Persist `failed_jobs` array in state storage when posting RED

### Pattern 3: State Tracking Database Failure
**Symptom**: Every workflow triggers RED (even when already red)
**Prevention**: Verify state persistence survives Dakota restart, use durable storage

### Pattern 4: Timezone Issues
**Symptom**: Negative time-since-failure calculation
**Prevention**: Normalize all timestamps to UTC before calculation

---

## Team Culture Alignment ✅

Design matches Mike's stated team culture:

| Requirement | Design Solution |
|-------------|-----------------|
| High urgency - "Drop everything, fix this now" | RED uses danger style, urgent language, immediate @mention |
| Developer accountability | Every notification tags the responsible developer |
| Team reassurance after fix | GREEN says "All systems healthy" (team all-clear signal) |
| Celebration of fixes | GREEN uses 🎉 emoji, positive language, validates effort |
| No spam tolerance | Only master/develop/installer notify, GREEN→GREEN is silent |

---

## Future Enhancements (Optional) 🚀

These ideas came up during design but are NOT required for MVP:

### 1. Notification Batching
- If multiple failures in 5 min, thread subsequent ones
- Reduces spam during flaky periods

### 2. Edit-in-place Recovery
- If recovery in <5 min, edit RED to GREEN (no new message)
- Ultra-fast fixes don't need separate GREEN

### 3. Thread Context
- GREEN notification replies to RED in thread
- Keeps recovery history connected to original failure

### 4. MTTR Metrics
- Weekly summary: avg time-to-recovery, failure rate
- Team visibility into CI health trends

### 5. Smart @channel
- @channel only for master branch failures
- Escalate critical failures to whole team

### 6. Flaky Test Detection
- If same job fails 3x then passes, mark as flaky
- Differentiate intermittent failures from real bugs

---

## Handoff to Dakota (DevOps) 🔄

### What Dakota Gets
1. Complete journey map with emotional design
2. Slack Block Kit JSON templates (ready to use)
3. Shared artifact registry (what to track, where it comes from)
4. Gherkin acceptance tests (validation criteria)
5. Implementation notes (Python example, error handling)

### What Dakota Must Implement
1. **GitHub webhook handler** - Receive `workflow_run` events
2. **State storage** - Persist `previous_run_id`, `failed_jobs`, `failure_timestamp`
3. **Author mapping** - Config file: git username → Slack user ID
4. **Notification logic** - Detect state transitions (GREEN→RED, RED→GREEN)
5. **Slack API client** - Post Block Kit messages to #cicd
6. **Error handling** - Graceful degradation for missing data

### Critical Success Factors
- ✅ State persistence must survive Dakota service restarts (use durable storage)
- ✅ Author mapping must be maintained (add new team members to config)
- ✅ Timezone handling must be UTC-normalized (prevent negative time calculations)
- ✅ Failed jobs must persist from RED to GREEN (enables recovery proof)

### Testing Checklist
- [ ] Test RED notification with real failure (verify @mention pings user)
- [ ] Test GREEN notification with real recovery (verify time calculation)
- [ ] Test author mapping for both users (undeadgrishnackh, 11PJ11)
- [ ] Test unknown author fallback
- [ ] Test long commit message truncation
- [ ] Test multiple failed jobs
- [ ] Test state persistence across Dakota restart
- [ ] Test timezone handling
- [ ] Test branch filter (feature branch should NOT notify)
- [ ] Test GREEN→GREEN silence (no spam)

---

## Journey Artifacts Location

All artifacts are in `/Users/mike/ProgettiGit/Undeadgrishnackh/crafter-ai/docs/ux/`:

```
docs/ux/
├── journey-cicd-notifications-visual.md      # ASCII journey map
├── journey-cicd-notifications.yaml           # Structured schema
├── journey-cicd-notifications.feature        # Gherkin acceptance tests
├── shared-artifacts-registry.md              # Integration tracking
├── slack-block-kit-examples.json             # Ready-to-use templates
└── JOURNEY_COMPLETE.md                       # This summary
```

---

## Next Steps

1. **Mike reviews journey** - Validate design matches vision
2. **Handoff to Dakota** - Implement notification service
3. **Quinn creates E2E tests** - Transform Gherkin to executable tests
4. **Staging validation** - Test with real failures in non-prod
5. **Production deployment** - Monitor #cicd for alarm fatigue signals

---

## Success Metrics (Post-Deployment)

Track these to validate alarm fatigue prevention:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Time to first investigation | <5 min | Time from RED notification to first GitHub run click |
| Resolution rate | >95% | % of RED notifications followed by GREEN within 24h |
| Team satisfaction | >4/5 | Weekly survey: "Are #cicd notifications helpful?" |
| Notification volume | <10/day | Count of RED+GREEN notifications (branch filter working) |
| False ignore rate | <5% | % of RED notifications with no action (alarm fatigue indicator) |

---

**Journey Design Status**: ✅ COMPLETE AND READY FOR IMPLEMENTATION

**Designer**: Luna 🌙 (leanux-designer)
**Date**: 2026-01-31
**Next Agent**: Dakota (devops-specialist)
