# Shared Artifacts Registry - CI/CD Notifications

**Journey**: cicd-notifications
**Last Updated**: 2026-01-31
**Owner**: leanux-designer (Luna)

This document tracks all shared data artifacts that appear across multiple steps in the CI/CD notification journey. Each artifact must have a **single source of truth** to prevent integration failures.

---

## Artifact Index

| Artifact | Integration Risk | Source | Consumers |
|----------|------------------|--------|-----------|
| `author` | 🔴 HIGH | Git commit author | RED @mention, GREEN @mention, Slack pings |
| `branch` | 🟢 LOW | Git branch name | Both notifications, routing filter |
| `commit_sha` | 🟢 LOW | Git commit hash | Both notifications, GitHub links |
| `commit_message` | 🟢 LOW | Git commit message | Both notifications |
| `workflow_name` | 🟢 LOW | GitHub Actions workflow file | Both notifications (header) |
| `failed_jobs` | 🟡 MEDIUM | GitHub Actions job status API | RED actionable info, GREEN recovery proof |
| `run_url` | 🟢 LOW | GitHub Actions webhook payload | [View Run] buttons |
| `time_since_failure` | 🔴 HIGH | Dakota's state tracking | GREEN notification (recovery speed) |
| `previous_run_id` | 🔴 CRITICAL | Dakota's state tracking | State transition detection (RED→GREEN) |
| `recovery_commit_count` | 🟡 MEDIUM | Dakota's state tracking | GREEN notification (fix complexity) |

---

## Artifact Details

### `author` 🔴 HIGH RISK

**Source of Truth**: Git commit author (mapped to Slack user ID via configuration)

**Displayed As**:
- RED: `Author: <@U01234ABCD>`
- GREEN: `Fixed by: <@U01234ABCD>`

**Consumers**:
1. RED notification (ownership assignment)
2. GREEN notification (credit attribution)
3. Slack notification system (triggers user ping)

**Owner**: Dakota's notification service (mapping logic)

**Integration Risk**: HIGH
- If git username → Slack user ID mapping breaks, ownership/accountability fails
- If mapping is missing for a user, notification degrades to plaintext username

**Validation**:
- Test with known git usernames: `undeadgrishnackh`, `11PJ11`
- Verify Slack user ID format: `<@U[A-Z0-9]+>`
- Edge case: Unknown users should log warning but still post notification

**Failure Impact**:
- No @mention = No Slack ping = Developer misses critical failure
- Breaks alarm fatigue prevention (ownership pattern)

---

### `branch` 🟢 LOW RISK

**Source of Truth**: Git branch name from GitHub Actions webhook

**Displayed As**: `Branch: installer`

**Consumers**:
1. RED notification (context)
2. GREEN notification (context)
3. Dakota's routing filter (only master/develop/installer notify)

**Owner**: GitHub Actions webhook payload (`workflow_run.head_branch`)

**Integration Risk**: LOW
- Branch name is stable and provided by GitHub
- Filter logic is simple string comparison

**Validation**:
- Verify only filtered branches trigger notifications
- Test with feature branch (should NOT notify)

**Failure Impact**:
- Wrong branch name = Context confusion
- Filter bypass = Noise (alarm fatigue)

---

### `commit_sha` 🟢 LOW RISK

**Source of Truth**: Git commit hash (SHA-1 or SHA-256)

**Displayed As**:
- RED: `Commit: a1b2c3d` (truncated to 7 chars)
- GREEN: `Commit: b2c3d4e`

**Consumers**:
1. RED notification (failure commit)
2. GREEN notification (recovery commit)
3. GitHub commit links (`https://github.com/.../commit/{sha}`)

**Owner**: Git commit object (immutable)

**Integration Risk**: LOW
- SHA is cryptographically unique and immutable
- GitHub API accepts both full and short SHAs

**Validation**:
- Links to commit pages work correctly
- Short SHA (7 chars) is unambiguous in repo

**Failure Impact**:
- Wrong SHA = Wrong commit linked (investigation failure)

---

### `commit_message` 🟢 LOW RISK

**Source of Truth**: Git commit message (first line only)

**Displayed As**: `📝 Fix authentication bug`

**Consumers**:
1. RED notification (context)
2. GREEN notification (context)

**Owner**: Git commit object (immutable)

**Integration Risk**: LOW
- Commit message is immutable once committed
- Only display concern: length truncation

**Validation**:
- Truncate to 100 characters if longer
- Add "..." if truncated
- Handle multi-line messages (show only first line)

**Failure Impact**:
- Long message = Slack block overflow (breaks layout)
- Empty message = Less context (but not critical)

---

### `workflow_name` 🟢 LOW RISK

**Source of Truth**: GitHub Actions workflow file (`.github/workflows/*.yml`)

**Displayed As**:
- RED: `🔴 Pipeline Failed: CI Pipeline`
- GREEN: `✅ Pipeline Recovered: CI Pipeline`

**Consumers**:
1. RED notification header
2. GREEN notification header

**Owner**: GitHub Actions configuration (`workflow.name` field)

**Integration Risk**: LOW
- Workflow name rarely changes
- GitHub provides via webhook payload

**Validation**:
- Display human-readable name (not filename)
- Fallback to filename if `name` field missing

**Failure Impact**:
- Wrong name = Confusion about which workflow failed

---

### `failed_jobs` 🟡 MEDIUM RISK

**Source of Truth**: GitHub Actions job status API (`workflow_run.jobs`)

**Displayed As**:
- RED: `❌ Failed Jobs: test (exit code 1), lint (ruff formatting)`
- GREEN: `Previously failed: test ✅ now passing, lint ✅ now passing`

**Consumers**:
1. RED notification (actionable information)
2. GREEN notification (recovery proof)

**Owner**: GitHub Actions job execution

**Integration Risk**: MEDIUM
- If job status parsing breaks, actionable info is lost
- If job data is not persisted, GREEN can't show recovery proof
- Job names must match exactly between RED and GREEN

**Validation**:
- Parse job names from `jobs` array
- Filter to only failed jobs (`conclusion: failure`)
- Persist failed job list from RED for GREEN reference
- Handle multiple jobs gracefully

**Failure Impact**:
- No job list in RED = Developer can't triage (just "it failed")
- No job list in GREEN = No proof of recovery (trust erosion)
- Breaks alarm fatigue prevention (actionability pattern)

---

### `run_url` 🟢 LOW RISK

**Source of Truth**: GitHub Actions run URL from webhook (`workflow_run.html_url`)

**Displayed As**: `[View Run]` button linking to GitHub Actions page

**Consumers**:
1. RED notification [View Run] button
2. GREEN notification [View Run] button

**Owner**: GitHub Actions webhook payload

**Integration Risk**: LOW
- URL structure is stable and provided by GitHub
- Direct link to workflow run page

**Validation**:
- Links open directly to run page (no 404s)
- Handle private repos (user must be authenticated)

**Failure Impact**:
- Broken link = Developer can't investigate (friction)

---

### `time_since_failure` 🔴 HIGH RISK

**Source of Truth**: Dakota's state tracking (`current_timestamp - failure_timestamp`)

**Displayed As**:
- GREEN: `🎉 Back to green after 18 minutes`
- GREEN: `🎉 Back to green after 2h 34m`

**Consumers**:
1. GREEN notification (recovery speed)
2. MTTR metrics (future enhancement)

**Owner**: Dakota's notification service

**Integration Risk**: HIGH
- Requires persisting failure timestamp across workflow runs
- If state storage fails, time calculation impossible
- If timezone handling is wrong, time is meaningless

**Validation**:
- Persist `failure_timestamp` when RED notification posted
- Calculate `time_since_failure = recovery_timestamp - failure_timestamp`
- Format duration human-readable (18 minutes, 2h 34m, 1d 3h)
- Handle edge case: recovery in <1 minute

**Failure Impact**:
- No time calculation = Less context in GREEN (less satisfying)
- Wrong time = Misleading metrics (MTTR tracking broken)

---

### `previous_run_id` 🔴 CRITICAL RISK

**Source of Truth**: Dakota's state tracking (previous workflow run ID)

**Displayed As**: Not displayed (internal only)

**Consumers**:
1. State transition detection (GREEN→RED, RED→GREEN, GREEN→GREEN)
2. Time-since-failure calculation (links to failure timestamp)

**Owner**: Dakota's notification service

**Integration Risk**: CRITICAL
- Without this, Dakota cannot detect GREEN→RED or RED→GREEN transitions
- Without this, GREEN notifications are impossible to generate
- Failure here breaks the entire notification system

**Validation**:
- Persist `previous_run_id` after EVERY workflow run
- Store in durable storage (database, file, Redis)
- Handle edge case: First run on a branch (no previous run)
- Verify state persistence survives Dakota service restart

**Failure Impact**:
- No state tracking = No GREEN notifications (alarm fatigue guaranteed)
- All failures appear orphaned (no closure)
- Breaks core value proposition of the feature

---

### `recovery_commit_count` 🟡 MEDIUM RISK

**Source of Truth**: Dakota's state tracking (commits between failure SHA and recovery SHA)

**Displayed As**: `Recovery commits: 3`

**Consumers**:
1. GREEN notification (fix complexity indicator)

**Owner**: Dakota's notification service

**Integration Risk**: MEDIUM
- Nice-to-have context, not critical for functionality
- Requires Git API access to count commits between SHAs
- Edge case: Force push or rebase may break commit ancestry

**Validation**:
- Query GitHub API: `GET /repos/{owner}/{repo}/compare/{base}...{head}`
- Count commits in `commits` array
- Handle edge case: Rebase/force push (ancestry broken)

**Failure Impact**:
- No commit count = Slightly less context (but GREEN still works)
- Wrong count = Misleading (but not critical)

---

## Integration Checkpoints

These are the critical validation points where multiple artifacts must align:

### Checkpoint 1: Author Attribution (RED → GREEN)

**What**: Git author must map consistently to Slack user across RED and GREEN

**Artifacts Involved**:
- `author` (git username → Slack user ID)
- `commit_sha` (different SHAs for failure vs recovery)

**Validation**:
- RED: `undeadgrishnackh` (commit a1b2c3d) → `<@U01234ABCD>`
- GREEN: `11PJ11` (commit b2c3d4e) → `<@U56789EFGH>` (if different person fixed it)

**Failure Mode**:
- If mapping breaks, @mentions fail → no Slack pings → developers miss alerts

---

### Checkpoint 2: Failed Jobs Persistence (RED → GREEN)

**What**: Failed jobs listed in RED must match "Previously failed" jobs in GREEN

**Artifacts Involved**:
- `failed_jobs` (RED snapshot)
- `failed_jobs` (GREEN reference to RED snapshot)

**Validation**:
- RED: `❌ Failed Jobs: test, lint`
- GREEN: `Previously failed: test ✅, lint ✅`
- Job names must match exactly (string equality)

**Failure Mode**:
- If jobs don't match, GREEN can't prove recovery → trust erosion

---

### Checkpoint 3: State Transition Detection (previous_run_id → current_run_id)

**What**: Dakota must correctly detect workflow state changes

**Artifacts Involved**:
- `previous_run_id` (run 122)
- `current_run_id` (run 123)
- `previous_status` (success)
- `current_status` (failure)

**Validation**:
- Run 122: success
- Run 123: failure → Transition: GREEN→RED → Post RED notification
- Run 124: success → Transition: RED→GREEN → Post GREEN notification
- Run 125: success → Transition: GREEN→GREEN → Post NOTHING (silence)

**Failure Mode**:
- If state tracking breaks, GREEN detection fails → no closure → alarm fatigue

---

### Checkpoint 4: Time-Since-Failure Calculation

**What**: GREEN notification must show accurate recovery time

**Artifacts Involved**:
- `failure_timestamp` (from RED event)
- `recovery_timestamp` (from GREEN event)
- `time_since_failure` (calculated delta)

**Validation**:
- Failure at: 2026-01-31 14:34:00
- Recovery at: 2026-01-31 14:52:00
- Delta: 18 minutes
- Display: "Back to green after 18 minutes"

**Failure Mode**:
- Wrong time = Misleading context
- No time = Less satisfying GREEN notification

---

## Bug Detection Patterns

These are the integration bugs that journey design helps catch:

### Pattern 1: Multiple Author Sources

**Symptom**: Git username shows in RED, but Slack user ID shows in GREEN

**Root Cause**: Inconsistent author data source (one uses git, other uses Slack API)

**Journey Evidence**:
- RED: `Author: undeadgrishnackh` (plaintext)
- GREEN: `Fixed by: <@U01234ABCD>` (Slack ID)

**Fix**: Use single mapping function for both notifications

---

### Pattern 2: Failed Jobs Not Persisted

**Symptom**: GREEN says "Previously failed: (none)" even though RED showed failures

**Root Cause**: Failed jobs not saved to state storage when RED posted

**Journey Evidence**:
- RED: `❌ Failed Jobs: test, lint`
- GREEN: `Previously failed: ` (empty)

**Fix**: Persist `failed_jobs` array when posting RED notification

---

### Pattern 3: State Tracking Database Failure

**Symptom**: Every workflow triggers RED notification (even when already red)

**Root Cause**: `previous_run_id` not persisting (always null)

**Journey Evidence**:
- Run 123 fails → RED ✓
- Run 124 fails again → RED again ✗ (should be silent or thread)

**Fix**: Verify state persistence survives Dakota restart, use durable storage

---

### Pattern 4: Timezone Issues

**Symptom**: "Back to green after -5 hours" (negative time)

**Root Cause**: Failure timestamp in UTC, recovery timestamp in local time

**Journey Evidence**:
- Failure: 2026-01-31 19:34:00 UTC
- Recovery: 2026-01-31 14:52:00 EST
- Calculation: 14:52 - 19:34 = -5 hours

**Fix**: Normalize all timestamps to UTC before calculation

---

## Handoff Checklist

Before passing to Dakota for implementation:

- [ ] All artifacts have documented source of truth
- [ ] All integration checkpoints are testable
- [ ] All failure modes have remediation guidance
- [ ] Slack Block Kit JSON validates against schema
- [ ] Gherkin scenarios cover happy path + edge cases
- [ ] Journey validates against alarm fatigue prevention patterns

**Next Agent**: Dakota (devops-specialist)
**Deliverables**: This registry + journey YAML + Gherkin scenarios
**Validation**: Quinn (acceptance-designer) will create E2E tests from Gherkin
