# CI/CD Notification Journey - Visual Design

**Goal**: Stay informed about pipeline health without alarm fatigue
**Persona**: Developer (Mike, Alessandro) working on master/develop/installer branches
**Emotional Arc**: Urgent concern → Focused action → Relief + Celebration

---

## SCENARIO A: Developer Breaks Build, Then Fixes It

### Context
Mike pushes a commit to `installer` branch. The CI pipeline fails. He context switches to other work but notices the Slack menubar badge.

---

### Step 1: Pipeline Failure Detected

**Trigger**: GitHub Actions workflow completes with status=failure

**What Dakota's system does**:
- Checks previous run status (was: success)
- Detects state transition: GREEN → RED
- Prepares notification payload

---

┌─ Step 1: RED Notification Appears ─────────────────────────┐  Emotion: URGENT
│                                                             │  "I broke it!"
│ #cicd channel (Slack)                                       │
│                                                             │
│ 🔴 Pipeline Failed: CI Pipeline                            │
│                                                             │
│ Branch: installer                                           │
│ Author: @michele.brissoni                                   │
│                                                             │
│ 📝 Fix authentication bug                                  │
│ Commit: a1b2c3d                                             │
│                                                             │
│ ❌ Failed Jobs:                                             │
│   • test (exit code 1)                                      │
│   • lint (ruff formatting)                                  │
│                                                             │
│ [View Run] [View Commit]                                    │
│                                                             │
│ ⏱️ Failed at: 2:34 PM                                       │
└─────────────────────────────────────────────────────────────┘
          │
          │ Mike sees menubar badge (🔴 1)
          │ Clicks Slack → Sees his @mention
          │ Emotional state: "Damn, I need to fix this NOW"
          ▼

┌─ Step 2: Mike Investigates ────────────────────────────────┐  Emotion: FOCUSED
│                                                             │  "Let me see what
│ Mike clicks [View Run] → Opens GitHub Actions              │   broke"
│                                                             │
│ Sees test failure:                                          │
│   AssertionError: Expected 200, got 401                     │
│                                                             │
│ Mike realizes: "I forgot to mock the auth token"           │
└─────────────────────────────────────────────────────────────┘
          │
          │ Mike fixes the code locally
          │ Runs tests → Pass ✓
          │ Commits: "Fix auth mock in tests"
          │ Pushes to installer branch
          ▼

┌─ Step 3: Pipeline Recovers ────────────────────────────────┐  Emotion: ANXIOUS
│                                                             │  "Please work..."
│ GitHub Actions re-runs tests                                │
│ Mike context switches to Slack, watching for result        │
│                                                             │
│ ⏱️ Time since failure: 18 minutes                           │
└─────────────────────────────────────────────────────────────┘
          │
          │ Pipeline completes: status=success
          │ Dakota detects: RED → GREEN transition
          ▼

┌─ Step 4: GREEN Notification Appears ───────────────────────┐  Emotion: RELIEF
│                                                             │  + CELEBRATION
│ #cicd channel (Slack)                                       │  "I fixed it!"
│                                                             │
│ ✅ Pipeline Recovered: CI Pipeline                          │
│                                                             │
│ Branch: installer                                           │
│ Fixed by: @michele.brissoni                                 │
│                                                             │
│ 📝 Fix auth mock in tests                                  │
│ Commit: b2c3d4e                                             │
│                                                             │
│ 🎉 Back to green after 18 minutes                          │
│ Recovery commits: 1                                         │
│                                                             │
│ Previously failed:                                          │
│   • test ✓ now passing                                     │
│   • lint ✓ now passing                                     │
│                                                             │
│ [View Run] [View Commit]                                    │
│                                                             │
│ 🟢 All systems healthy                                      │
└─────────────────────────────────────────────────────────────┘
          │
          │ Mike sees notification
          │ Team sees "all clear" signal
          │ Emotional state: "Phew! Crisis averted"
          ▼

┌─ INTEGRATION CHECKPOINT ───────────────────────────────────┐
│ ✓ Author attribution consistent (git → Slack)              │
│ ✓ Branch matches filtered list (installer)                 │
│ ✓ State transition tracked (GREEN → RED → GREEN)           │
│ ✓ Time-since-failure calculated (18 minutes)               │
│ ✓ Failed jobs mapped to recovery jobs                      │
└─────────────────────────────────────────────────────────────┘

---

## SCENARIO B: Developer Returns After Auto-Recovery

### Context
Mike pushed a commit before lunch. Pipeline failed while he was away. Another commit (from auto-merge or teammate) fixed it. Mike returns to see GREEN notification.

---

┌─ Step 1: RED Notification (Mike missed this) ──────────────┐  Emotion: N/A
│                                                             │  (Mike is at lunch)
│ 🔴 Pipeline Failed: CI Pipeline                            │
│ Author: @michele.brissoni                                   │
│ ...                                                         │
└─────────────────────────────────────────────────────────────┘
          │
          │ Mike is away (no immediate action)
          │ Alessandro sees the failure
          │ Alessandro pushes a fix
          ▼

┌─ Step 2: GREEN Notification (Mike returns) ────────────────┐  Emotion: RELIEVED
│                                                             │  "Someone handled
│ #cicd channel (Slack)                                       │   it, good"
│                                                             │
│ ✅ Pipeline Recovered: CI Pipeline                          │
│                                                             │
│ Branch: installer                                           │
│ Fixed by: @alessandro.digioia                               │
│                                                             │
│ 📝 Fix Mike's auth issue                                   │
│ Commit: c3d4e5f                                             │
│                                                             │
│ 🎉 Back to green after 2h 34m                              │
│ Recovery commits: 3                                         │
│                                                             │
│ Previously failed:                                          │
│   • test ✓ now passing                                     │
│                                                             │
│ [View Run] [View Commit]                                    │
│                                                             │
│ 🟢 All systems healthy                                      │
└─────────────────────────────────────────────────────────────┘
          │
          │ Mike sees: "Oh, Alessandro fixed my issue"
          │ Team sees: "Build is healthy again"
          │ Emotional state: "Thanks Alessandro, I owe you coffee"
          ▼

---

## DESIGN RATIONALE: Anti-Alarm-Fatigue Patterns

### 1. **Visual Hierarchy**
- **RED**: 🔴 emoji + bold "Pipeline Failed" (impossible to miss)
- **GREEN**: ✅ emoji + "Pipeline Recovered" (positive closure)
- **Color contrast**: Red for urgency, green for celebration

### 2. **Ownership Signal**
- **RED**: `@mention` author immediately (clear responsibility)
- **GREEN**: `@mention` whoever fixed it (credit where due)
- **No orphan failures**: Every RED has a responsible party

### 3. **Actionable Information**
- **Failed jobs listed** (not just "it failed")
- **Direct links** to run and commit (one click to context)
- **Time-since-failure** (builds urgency: "18 min ago" vs "2h 34m ago")

### 4. **Closure Signal**
- **GREEN shows what was broken** ("Previously failed: test ✓ now passing")
- **Celebration tone** (🎉 emoji, "Back to green", "All systems healthy")
- **Team reassurance** ("No stress fellas, we're good")

### 5. **Cognitive Load Management**
- **Minimal blocks** (RED: 8 elements, GREEN: 9 elements)
- **Scannable structure** (emoji markers, clear labels)
- **No @channel** (only individual @mentions, respects focus)

### 6. **Notification Batching** (Future Enhancement)
- If multiple failures in 5 min → Thread subsequent failures
- If recovery in <5 min → Edit RED to GREEN (no spam)

---

## SHARED ARTIFACTS TRACKED

| Artifact | Source | Displayed As | Consumers |
|----------|--------|--------------|-----------|
| `author` | Git commit author | `@michele.brissoni` | RED notification, GREEN notification |
| `branch` | Git branch name | `installer` | Both notifications, routing logic |
| `commit_sha` | Git commit hash | `a1b2c3d` | Both notifications, links |
| `commit_message` | Git commit message | "Fix authentication bug" | Both notifications |
| `workflow_name` | GitHub Actions workflow | "CI Pipeline" | Both notifications |
| `failed_jobs` | GitHub Actions job status | "test, lint" | RED notification, GREEN "Previously failed" |
| `run_url` | GitHub Actions run URL | `[View Run]` link | Both notifications |
| `time_since_failure` | Dakota's state tracking | "18 minutes" | GREEN notification only |
| `previous_run_id` | Dakota's state tracking | Used for comparison | Internal (not displayed) |

**Integration Risk**: HIGH
- If `author` mapping breaks (git → Slack), ownership fails
- If `previous_run_id` tracking breaks, GREEN detection fails
- If `failed_jobs` parsing breaks, actionable info lost

---

## EMOTIONAL ARC VALIDATION

### RED Notification Journey
- **Entry emotion**: Productive flow
- **Notification hits**: Urgent concern ("I broke it!")
- **After investigation**: Focused action ("I know what to fix")
- **No jarring transitions**: ✓ (urgent but not panic)

### GREEN Notification Journey
- **Entry emotion**: Anxious waiting ("Did my fix work?")
- **Notification hits**: Relief + celebration ("Yes!")
- **After reading**: Confidence + closure ("All good")
- **Team reassurance**: ✓ ("Everyone can relax")

### Transition Coherence
- RED → Action → GREEN is natural flow ✓
- No "radio silence" after RED (closure guaranteed) ✓
- Celebration tone appropriate (not over-the-top) ✓
- Team culture respected (high urgency + accountability) ✓

---

## NEXT STEPS

1. **Implement Slack Block Kit messages** (see journey-cicd-notifications.yaml)
2. **Test author mapping** (git username → Slack user ID)
3. **Validate with real failures** (staging environment)
4. **Iterate based on team feedback** (too much? too little?)

**Handoff to**: Dakota (DevOps) for implementation
