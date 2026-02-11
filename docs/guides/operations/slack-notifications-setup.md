# Slack Notifications Setup Guide

**Version**: 1.0
**Date**: 2026-01-31
**Architecture Reference**: [docs/architecture/slack-notifications-architecture.md](../architecture/slack-notifications-architecture.md)

---

## Overview

This guide provides step-by-step instructions for configuring Slack notifications for CI/CD pipeline failures in the nWave Framework repository.

**What you'll get**:
- Real-time notifications when CI/CD pipeline fails
- Rich context including commit details, failed job, and direct links to logs
- Notifications only for `master` and `develop` branches
- Beautiful Slack Block Kit formatting with action buttons

**Estimated setup time**: 10 minutes

---

## Prerequisites

Before you begin, ensure you have:

- [ ] **Slack workspace admin access** (to create incoming webhooks)
- [ ] **GitHub repository admin access** (to add secrets)
- [ ] **Slack channel** for notifications (recommended: `#engineering-alerts`)

---

## Part 1: Create Slack Incoming Webhook

### Step 1: Create Slack App

1. Navigate to: https://api.slack.com/apps
2. Click **"Create New App"**
3. Select **"From scratch"**
4. Enter app details:
   - **App Name**: `GitHub CI/CD Alerts`
   - **Workspace**: Select your workspace
5. Click **"Create App"**

### Step 2: Enable Incoming Webhooks

1. In the app settings sidebar, click **"Incoming Webhooks"**
2. Toggle **"Activate Incoming Webhooks"** to **ON**
3. Scroll down and click **"Add New Webhook to Workspace"**
4. Select the channel where notifications should be posted:
   - Recommended: `#engineering-alerts`
   - Alternative: `#ci-cd-alerts`, `#devops-alerts`, or any team channel
5. Click **"Allow"**

### Step 3: Copy Webhook URL

1. The webhook URL will be displayed on the screen
2. **Copy the entire URL** (it should look like this):
   ```
   https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX
   ```
3. **Keep this URL secret** - treat it like a password

**Security Note**: This webhook URL allows anyone with it to post messages to your Slack channel. Never commit it to version control or share it publicly.

---

## Part 2: Configure GitHub Secret

### Step 1: Navigate to Repository Secrets

1. Go to: https://github.com/Undeadgrishnackh/crafter-ai/settings/secrets/actions
   - OR: Navigate to your repository → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**

### Step 2: Add Slack Webhook Secret

1. **Name**: Enter exactly `SLACK_WEBHOOK_URL` (case-sensitive)
2. **Secret**: Paste the webhook URL from Part 1, Step 3
3. Click **"Add secret"**

**Verification**: You should see `SLACK_WEBHOOK_URL` in the list of repository secrets with a green checkmark.

---

## Part 3: Verify Installation

The `notify-slack` job is already configured in `.github/workflows/ci-cd.yml` (no code changes needed).

### Test Method 1: Intentional Test Failure (Recommended)

1. Create a test branch:
   ```bash
   git checkout -b test-slack-notification
   ```

2. Intentionally break a test (example):
   ```python
   # In tests/test_nwave_core.py, add a failing test
   def test_slack_notification():
       assert False, "Testing Slack notification"
   ```

3. Commit and push to trigger CI/CD:
   ```bash
   git add tests/test_nwave_core.py
   git commit -m "test: verify Slack notification integration"
   git push -u origin test-slack-notification
   ```

4. Merge the PR to `develop` or `master` (notifications only trigger on these branches)

5. Check your Slack channel for the notification

6. **Cleanup**: Revert the failing test after verification

### Test Method 2: Simulate Pipeline Failure

Alternatively, temporarily break any quality gate:

**Option A: Break code formatting**
```python
# Add trailing whitespace to any Python file
def example_function():
    return True  # <- add spaces after True
```

**Option B: Break commit message format**
```bash
git commit -m "bad commit message format"  # Missing conventional commit type
```

---

## Part 4: Validation Checklist

After setup, verify the following:

- [ ] **Notification received in Slack**: Check the configured channel
- [ ] **All fields populated correctly**:
  - Repository name with clickable link
  - Branch name (should be `master` or `develop`)
  - Commit SHA with clickable link
  - Author name
  - Workflow name (should be "CI/CD Pipeline")
  - Event type (push, pull_request, etc.)
  - Commit message
- [ ] **Action buttons work**:
  - "View Logs" button redirects to GitHub Actions run
  - "View Commit" button redirects to commit page
- [ ] **Secret protected**: Check GitHub Actions logs - webhook URL should appear as `***`
- [ ] **Branch filtering works**: Push failing commit to feature branch - NO notification expected

---

## Part 5: Notification Message Format

**Example notification** (as it will appear in Slack):

```
🚨 CI/CD Pipeline Failed

Repository: Undeadgrishnackh/crafter-ai
Branch: master

Commit: a1b2c3d
Author: Alessandro

Workflow: CI/CD Pipeline
Event: push

Commit Message:
feat(agents): add new capability

[View Logs] [View Commit]

⏰ Workflow run #123
```

**Field Descriptions**:

| Field | Source | Description |
|-------|--------|-------------|
| Repository | `github.repository` | Full repository name with clickable link |
| Branch | `github.ref_name` | Branch or tag name |
| Commit | `github.sha` | Short commit SHA with clickable link |
| Author | `github.actor` | GitHub username who triggered the workflow |
| Workflow | `github.workflow` | Workflow name from YAML |
| Event | `github.event_name` | Trigger event (push, pull_request, etc.) |
| Commit Message | `github.event.head_commit.message` | Full commit message |
| Workflow run | `github.run_number` | Sequential run number |

---

## Troubleshooting

### Problem: No notification received

**Potential causes and solutions**:

1. **Secret not configured correctly**:
   - Verify secret name is exactly `SLACK_WEBHOOK_URL` (case-sensitive)
   - Verify webhook URL is complete and starts with `https://hooks.slack.com/services/`

2. **Workflow failed on feature branch**:
   - Notifications only trigger on `master` and `develop` branches
   - Solution: Merge to develop or master to test

3. **Webhook URL invalid or revoked**:
   - Regenerate webhook URL in Slack (see Maintenance section)
   - Update GitHub secret with new URL

4. **Slack API rate limit**:
   - Check GitHub Actions logs for rate limit error
   - Slack allows 600 messages/minute workspace-wide
   - Solution: Wait and retry, or reduce pipeline trigger frequency

5. **slackapi action failed**:
   - Check GitHub Actions logs for `notify-slack` job
   - Look for error messages from slackapi/slack-github-action
   - Verify webhook URL format is correct

### Problem: Notification received but formatting broken

**Solution**:
- Verify JSON payload is valid (check for syntax errors in workflow YAML)
- Test payload using Slack Block Kit Builder: https://app.slack.com/block-kit-builder
- Ensure all GitHub context variables are available (some may be null for certain events)

### Problem: Webhook URL exposed in logs

**Verification**:
1. Go to GitHub Actions run logs
2. Search for `hooks.slack.com`
3. Should appear as `***` (GitHub automatic sanitization)

**If exposed**:
1. Immediately revoke webhook in Slack
2. Generate new webhook URL
3. Update GitHub secret
4. Report security incident if URL was logged elsewhere

---

## Maintenance

### Quarterly Webhook Rotation (Recommended)

**Why**: Security best practice to rotate secrets regularly

**Procedure**:

1. **Generate new webhook URL** (Part 1: Create Slack Incoming Webhook)
2. **Update GitHub secret** (Part 2: Configure GitHub Secret)
3. **Test new webhook** (Part 3: Verify Installation)
4. **Revoke old webhook** in Slack:
   - Go to: https://api.slack.com/apps
   - Select app: "GitHub CI/CD Alerts"
   - Click "Incoming Webhooks"
   - Delete old webhook
5. **Document rotation** in changelog or security log

### Monitoring Notification Health

**Metrics to track**:

1. **Notification delivery rate**: Compare Slack messages to GitHub Actions failures
   - Target: >99.5% delivery rate
   - Check Slack audit logs and GitHub Actions history

2. **Notification latency**: Time from pipeline failure to Slack message
   - Target: <30 seconds
   - Use timestamp from GitHub Actions and Slack message

3. **False negatives**: Missed notifications
   - Target: 0 per month
   - Conduct monthly audit of pipeline failures vs Slack notifications

4. **Secret exposure incidents**: Webhook URL leaked
   - Target: 0 per year
   - Review GitHub audit logs and security alerts

### Incident Response

| Incident | Detection | Response | SLA |
|----------|-----------|----------|-----|
| Notification not received | Manual check after pipeline failure | Verify webhook URL, check GitHub logs | 1 hour |
| Secret exposed | GitHub security alert or audit | Revoke webhook, regenerate, update secret | 15 minutes |
| Rate limit exceeded | Error in GitHub Actions logs | Investigate trigger frequency, wait for reset | 2 hours |
| Action version deprecated | GitHub Dependabot alert | Update to latest slackapi action version | 1 week |

---

## Security Considerations

### Best Practices

1. **Principle of Least Privilege**:
   - Use Incoming Webhook (not Bot Token)
   - Webhook scoped to single channel only
   - No additional permissions granted

2. **Secret Management**:
   - Store webhook URL only in GitHub Secrets (encrypted at rest)
   - Never commit webhook URL to version control
   - Never share webhook URL via email or chat
   - Use environment-specific webhooks (dev, staging, prod)

3. **Access Control**:
   - Limit GitHub repository admin access
   - Limit Slack workspace admin access
   - Enable audit logging for both GitHub and Slack
   - Review access logs quarterly

4. **Rotation Strategy**:
   - Rotate webhook URL quarterly (minimum)
   - Rotate immediately if exposure suspected
   - Document all rotations in security log

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Webhook URL leaked | Low | Medium | Quarterly rotation, instant revocation capability |
| Unauthorized channel posts | Very Low | Low | Webhook scoped to single channel |
| Rate limit abuse | Very Low | Low | Slack rate limiting (600/min workspace) |
| GitHub secret exposure | Very Low | Low | GitHub automatic sanitization in logs |

---

## Advanced Configuration (Optional)

### Conditional Notifications by Branch

To customize notification behavior by branch, modify the `if` condition in `.github/workflows/ci-cd.yml`:

**Example: Add @channel mention for master failures only**

```yaml
notify-slack:
  if: |
    failure() &&
    (github.ref == 'refs/heads/master' || github.ref == 'refs/heads/develop')
  steps:
    - name: Send Slack notification
      uses: slackapi/slack-github-action@v2.0.0
      with:
        webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
        payload: |
          {
            "text": "${{ github.ref == 'refs/heads/master' && '<!channel> ' || '' }}🚨 CI/CD Pipeline Failed",
            "blocks": [ ... ]
          }
```

### Multiple Notification Channels

To send notifications to different channels based on failure type:

**Setup**:
1. Create multiple Slack webhooks (one per channel)
2. Store each as separate GitHub secret:
   - `SLACK_WEBHOOK_CRITICAL` → `#critical-alerts`
   - `SLACK_WEBHOOK_GENERAL` → `#engineering-alerts`
   - `SLACK_WEBHOOK_DEPLOY` → `#deployment-alerts`

**Usage**:
```yaml
- name: Notify critical channel
  if: github.ref == 'refs/heads/master'
  uses: slackapi/slack-github-action@v2.0.0
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK_CRITICAL }}
    payload: |
      { ... }

- name: Notify general channel
  if: github.ref == 'refs/heads/develop'
  uses: slackapi/slack-github-action@v2.0.0
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK_GENERAL }}
    payload: |
      { ... }
```

### Custom Notification Content

To include additional context (e.g., which tests failed):

```yaml
payload: |
  {
    "blocks": [
      {
        "type": "section",
        "text": {
          "type": "mrkdwn",
          "text": "*Failed Tests:*\n${{ steps.test-results.outputs.failed_tests }}"
        }
      }
    ]
  }
```

---

## Support and Documentation

**Related Documentation**:
- Architecture Design: [docs/architecture/slack-notifications-architecture.md](../architecture/slack-notifications-architecture.md)
- GitHub Actions Workflow: [.github/workflows/ci-cd.yml](../../.github/workflows/ci-cd.yml)
- Slack API Documentation: https://api.slack.com/messaging/webhooks
- slackapi/slack-github-action: https://github.com/slackapi/slack-github-action

**Getting Help**:
- GitHub Issues: https://github.com/Undeadgrishnackh/crafter-ai/issues
- Slack Support: https://slack.com/help
- GitHub Actions Support: https://docs.github.com/en/actions

**Security Concerns**:
- Report security vulnerabilities privately via GitHub Security Advisories
- Do NOT create public issues for exposed secrets

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-31 | Initial setup guide for Slack notifications |

---

**END OF SETUP GUIDE**
