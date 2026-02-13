# Slack Notifications Testing Procedures

**Version**: 2.0
**Date**: 2026-01-31
**Feature**: RED (failure) + GREEN (recovery) Notifications
**Related**: [slack-notifications-setup.md](slack-notifications-setup.md)

---

## Testing Overview

This document provides comprehensive testing procedures for validating the "Back to Green" notification system.

**Test Objectives**:
- Verify RED notification on pipeline failure
- Verify GREEN notification on pipeline recovery (failure → success)
- Verify NO notification when staying green (success → success)
- Validate state tracking across workflow runs
- Confirm author mapping (git username → Slack user ID)
- Test failed jobs parsing and display
- Validate recovery time calculation
- Confirm security measures (secret sanitization)

---

## Test Suite

### Test 1: Fast Checks Failure (Code Quality)

**Purpose**: Verify notification for early-stage pipeline failures

**Test Procedure**:

1. Create test branch:
   ```bash
   git checkout -b test/slack-notification-code-quality
   ```

2. Introduce code formatting issue:
   ```bash
   # Add trailing whitespace to any Python file
   echo "def example():    " >> scripts/test_file.py
   ```

3. Commit and push:
   ```bash
   git add scripts/test_file.py
   git commit -m "test: verify Slack notification for code quality failure"
   git push -u origin test/slack-notification-code-quality
   ```

4. Merge to develop:
   ```bash
   gh pr create --base develop --title "Test Slack Notification" --body "Testing notification"
   gh pr merge --merge
   ```

**Expected Result**:
- ✅ Slack notification received in configured channel
- ✅ Failed job shows as "Code Quality (Ruff)"
- ✅ Branch shows as "develop"
- ✅ "View Logs" button links to failed workflow run

**Cleanup**:
```bash
git checkout develop
git pull
git branch -D test/slack-notification-code-quality
```

---

### Test 2: Test Suite Failure (pytest)

**Purpose**: Verify notification for test failures with detailed context

**Test Procedure**:

1. Create test branch:
   ```bash
   git checkout -b test/slack-notification-test-failure
   ```

2. Add failing test:
   ```python
   # In tests/test_slack_notification.py (create new file)
   def test_intentional_failure():
       """Temporary test to verify Slack notification system."""
       assert False, "Intentional failure for Slack notification testing"
   ```

3. Commit and push:
   ```bash
   git add tests/test_slack_notification.py
   git commit -m "test: add intentional failure for notification testing"
   git push -u origin test/slack-notification-test-failure
   ```

4. Merge to master:
   ```bash
   gh pr create --base master --title "Test Slack Notification - Test Failure" --body "Testing notification"
   gh pr merge --merge
   ```

**Expected Result**:
- ✅ Slack notification received
- ✅ Failed job shows as "Test - Py3.12 / ubuntu-latest" (or similar)
- ✅ Branch shows as "master"
- ✅ Commit message includes "test: add intentional failure"
- ✅ All metadata fields populated correctly

**Cleanup**:
```bash
git checkout master
git pull
rm tests/test_slack_notification.py
git add tests/test_slack_notification.py
git commit -m "test: remove temporary test for Slack notification"
git push
```

---

### Test 3: Build Failure (Version Tags Only)

**Purpose**: Verify notification for build stage failures

**Test Procedure**:

1. Create tag with version mismatch:
   ```bash
   # Ensure framework-catalog.yaml version doesn't match tag
   git tag v99.99.99
   git push origin v99.99.99
   ```

**Expected Result**:
- ✅ Slack notification received (if build fails due to version mismatch)
- ✅ Failed job shows as "Build Distribution"
- ✅ Branch shows tag name "v99.99.99"

**Cleanup**:
```bash
git tag -d v99.99.99
git push origin :refs/tags/v99.99.99
```

**Note**: This test only applies if version validation fails. If builds are disabled on your repository, skip this test.

---

### Test 4: Branch Filtering Validation

**Purpose**: Verify notifications ONLY trigger on master/develop branches

**Test Procedure**:

1. Create feature branch:
   ```bash
   git checkout -b feature/no-notification-expected
   ```

2. Introduce failing test:
   ```python
   # In tests/test_branch_filter.py
   def test_feature_branch_failure():
       assert False, "This should NOT trigger Slack notification"
   ```

3. Commit and push:
   ```bash
   git add tests/test_branch_filter.py
   git commit -m "test: verify branch filtering for notifications"
   git push -u origin feature/no-notification-expected
   ```

**Expected Result**:
- ❌ NO Slack notification received (feature branch excluded)
- ✅ GitHub Actions shows failure
- ✅ Pipeline fails as expected

**Cleanup**:
```bash
git checkout develop
git branch -D feature/no-notification-expected
git push origin --delete feature/no-notification-expected
```

---

### Test 5: Secret Sanitization Verification

**Purpose**: Ensure webhook URL is never exposed in logs

**Test Procedure**:

1. Trigger any pipeline failure (use Test 1 or Test 2)

2. Navigate to failed GitHub Actions run

3. Open `notify-slack` job logs

4. Search for sensitive strings:
   - Search for: `hooks.slack.com`
   - Search for: `services/T`
   - Search for: `SLACK_WEBHOOK_URL`

**Expected Result**:
- ✅ All webhook URL occurrences appear as `***`
- ✅ No plaintext webhook URL visible anywhere in logs
- ✅ Environment variable section shows `SLACK_WEBHOOK_URL: ***`

**Validation Script**:
```bash
# Download logs and verify sanitization
gh run view <run-id> --log | grep -i "slack" | grep -i "webhook"
# Should show no plaintext URLs, only ***
```

---

### Test 6: Network Failure Simulation

**Purpose**: Verify graceful error handling when Slack API is unreachable

**Test Procedure**:

1. Temporarily revoke webhook URL:
   - Go to: https://api.slack.com/apps
   - Select "GitHub CI/CD Alerts"
   - Click "Incoming Webhooks"
   - Delete webhook

2. Trigger pipeline failure (use Test 1)

3. Observe `notify-slack` job behavior

**Expected Result**:
- ✅ `notify-slack` job fails gracefully
- ✅ Error message logged: "Invalid webhook URL" or "404 Not Found"
- ✅ Pipeline overall status shows failure (original failure + notification failure)
- ✅ No infinite retries or hanging

**Cleanup**:
- Recreate webhook URL
- Update GitHub secret `SLACK_WEBHOOK_URL`
- Re-run Test 1 to verify restoration

---

### Test 7: Multiple Failure Stages

**Purpose**: Verify notification summarizes all failed jobs

**Test Procedure**:

1. Create test branch:
   ```bash
   git checkout -b test/multi-stage-failure
   ```

2. Introduce multiple failures:
   ```bash
   # Break code quality
   echo "def bad_format():    " >> scripts/test_multi.py

   # Break test
   echo "def test_fail(): assert False" >> tests/test_multi.py
   ```

3. Commit and push to develop:
   ```bash
   git add scripts/test_multi.py tests/test_multi.py
   git commit -m "test: verify multi-stage failure notification"
   git push -u origin test/multi-stage-failure
   gh pr create --base develop --title "Multi-Stage Failure Test" --body "Test"
   gh pr merge --merge
   ```

**Expected Result**:
- ✅ Single Slack notification received (not multiple)
- ✅ Notification sent after first job failure
- ✅ Subsequent job failures do not trigger duplicate notifications

**Cleanup**:
```bash
git checkout develop
git pull
git branch -D test/multi-stage-failure
```

---

### Test 8: Notification Content Validation

**Purpose**: Verify all message fields are populated correctly

**Test Procedure**:

1. Trigger any pipeline failure

2. Review Slack notification and validate:

**Checklist**:
- [ ] **Header**: "🚨 CI/CD Pipeline Failed" (emoji renders)
- [ ] **Repository**: Link to GitHub repository works
- [ ] **Branch**: Correct branch name (master or develop)
- [ ] **Commit**: Short SHA with working link to commit page
- [ ] **Author**: GitHub username of committer
- [ ] **Workflow**: "CI/CD Pipeline" (matches workflow name)
- [ ] **Event**: "push" or "pull_request" (correct event type)
- [ ] **Commit Message**: Full commit message displayed
- [ ] **View Logs Button**: Links to correct GitHub Actions run
- [ ] **View Commit Button**: Links to correct commit page
- [ ] **Workflow Run Number**: Displays correct run number
- [ ] **Timestamp**: Workflow run metadata present

**Validation Screenshot**:
Take screenshot of Slack notification for documentation.

---

### Test 9: Rate Limit Handling

**Purpose**: Verify behavior under high notification volume

**Test Procedure**:

1. Trigger multiple rapid failures:
   ```bash
   # Push multiple failing commits in quick succession
   for i in {1..10}; do
     echo "def fail_$i(): assert False" >> tests/test_rate_limit.py
     git add tests/test_rate_limit.py
     git commit -m "test: rate limit test $i"
   done
   git push
   ```

**Expected Result**:
- ✅ All notifications delivered (Slack rate limit: 600/min)
- ✅ No notification errors in GitHub Actions logs
- ✅ If rate limit hit, slackapi action retries automatically

**Cleanup**:
```bash
rm tests/test_rate_limit.py
git add tests/test_rate_limit.py
git commit -m "test: cleanup rate limit test"
git push
```

**Note**: Slack workspace rate limit is 600 messages/minute. CI/CD failures typically won't hit this limit.

---

## Validation Criteria Summary

| Test | Validation Criteria | Pass Threshold |
|------|---------------------|----------------|
| Test 1 | Notification delivered for code quality failure | 100% |
| Test 2 | Notification delivered for test failure | 100% |
| Test 3 | Notification delivered for build failure | 100% |
| Test 4 | NO notification for feature branches | 100% |
| Test 5 | Webhook URL sanitized in logs | 100% |
| Test 6 | Graceful error handling | Job fails with clear error |
| Test 7 | Single notification for multi-stage failure | 100% |
| Test 8 | All message fields populated correctly | 100% |
| Test 9 | Rate limit handling | >99.5% delivery |

**Overall Pass Criteria**: All tests must pass with 100% success rate (except Test 9: >99.5%).

---

## Continuous Testing Recommendations

### Monthly Validation

**Schedule**: First Monday of each month

**Procedure**:
1. Run Test 1 (Fast Checks Failure)
2. Run Test 5 (Secret Sanitization)
3. Run Test 8 (Content Validation)

**Documentation**: Record results in operations log.

### Quarterly Full Test Suite

**Schedule**: End of each quarter (March, June, September, December)

**Procedure**:
1. Run all tests (Test 1-9)
2. Review failure trends (if any)
3. Update documentation if behavior changes
4. Rotate webhook URL (security best practice)

**Report Template**:
```markdown
## Quarterly Slack Notification Test Report

**Date**: YYYY-MM-DD
**Tester**: [Name]
**Environment**: Production

### Test Results
- Test 1 (Code Quality): ✅ PASS
- Test 2 (Test Failure): ✅ PASS
- Test 3 (Build Failure): ⏭️ SKIPPED (no tags created)
- Test 4 (Branch Filtering): ✅ PASS
- Test 5 (Secret Sanitization): ✅ PASS
- Test 6 (Network Failure): ✅ PASS
- Test 7 (Multi-Stage): ✅ PASS
- Test 8 (Content Validation): ✅ PASS
- Test 9 (Rate Limit): ✅ PASS

### Issues Identified
- None

### Actions Taken
- Webhook URL rotated as scheduled
- Documentation updated with new webhook creation date
```

---

## Automated Testing (Future Enhancement)

**Proposed**: GitHub Actions workflow to validate notification system

**Workflow**:
```yaml
name: Validate Slack Notifications

on:
  schedule:
    - cron: '0 9 1 * *'  # First day of month at 9 AM
  workflow_dispatch:

jobs:
  test-notification:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Trigger test failure
        run: |
          # Create temporary failing test
          echo "def test_notification(): assert False" > tests/test_notification_validation.py

      - name: Run pytest
        run: pytest tests/test_notification_validation.py || true

      - name: Verify notification sent
        run: |
          # Check Slack API for recent message
          # Requires additional Slack API integration

      - name: Cleanup
        if: always()
        run: rm tests/test_notification_validation.py
```

**Status**: Not implemented (manual testing sufficient for current needs).

---

## Troubleshooting Test Failures

### Test 1-3 Fail: No notification received

**Diagnosis**:
1. Check GitHub secret `SLACK_WEBHOOK_URL` exists and is correct
2. Verify branch is `master` or `develop` (not feature branch)
3. Check Slack webhook is active (not revoked)
4. Review GitHub Actions logs for `notify-slack` job errors

**Resolution**:
- Recreate webhook URL
- Update GitHub secret
- Re-run test

### Test 4 Fails: Notification received on feature branch

**Diagnosis**:
1. Check workflow YAML `if` condition
2. Verify branch name filtering logic

**Resolution**:
- Update `.github/workflows/ci-cd.yml` if condition
- Ensure: `(github.ref == 'refs/heads/master' || github.ref == 'refs/heads/develop')`

### Test 5 Fails: Webhook URL exposed in logs

**CRITICAL SECURITY ISSUE**

**Immediate Actions**:
1. Revoke webhook URL in Slack immediately
2. Generate new webhook URL
3. Update GitHub secret
4. Report to security team
5. Review GitHub audit logs for secret access

**Root Cause Analysis**:
- GitHub automatic sanitization failed (investigate why)
- Possible cause: Webhook URL passed outside environment variable context

### Test 8 Fails: Missing or incorrect fields

**Diagnosis**:
1. Check GitHub context variables availability
2. Verify Slack Block Kit JSON syntax
3. Test payload in Slack Block Kit Builder

**Resolution**:
- Update workflow YAML payload JSON
- Ensure all `${{ github.* }}` variables are available for current event type
- Test with: https://app.slack.com/block-kit-builder

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-31 | Initial testing procedures document |

---

**END OF TESTING PROCEDURES**
