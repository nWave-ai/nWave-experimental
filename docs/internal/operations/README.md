# Operations Documentation

**Purpose**: Operational guides for nWave Framework infrastructure and DevOps

---

## Available Guides

### 1. Slack Notifications for CI/CD Failures

**Status**: ✅ Implemented (2026-01-31)

**Description**: Real-time Slack notifications when GitHub Actions CI/CD pipeline fails, with rich context including commit details, failed job information, and direct links to logs.

**Documentation**:
- **Setup Guide**: [slack-notifications-setup.md](slack-notifications-setup.md) - Complete setup instructions
- **Testing Procedures**: [slack-notifications-testing.md](slack-notifications-testing.md) - Comprehensive test suite
- **Architecture**: [../architecture/slack-notifications-architecture.md](../architecture/slack-notifications-architecture.md) - Design decisions and technical details

**Quick Start**:
1. Create Slack incoming webhook → [Setup Guide Part 1](slack-notifications-setup.md#part-1-create-slack-incoming-webhook)
2. Add GitHub secret `SLACK_WEBHOOK_URL` → [Setup Guide Part 2](slack-notifications-setup.md#part-2-configure-github-secret)
3. Verify installation → [Setup Guide Part 3](slack-notifications-setup.md#part-3-verify-installation)

**Estimated Setup Time**: 10 minutes

---

## Operational Procedures

### Monitoring and Alerting

**Notification Health Metrics**:
- Notification delivery rate target: >99.5%
- Notification latency target: <30 seconds
- Secret exposure incidents target: 0 per year

**Monitoring Locations**:
- GitHub Actions: `.github/workflows/ci-cd.yml` - `notify-slack` job
- Slack Audit Logs: Webhook usage tracking
- GitHub Audit Logs: Secret access tracking

### Maintenance Schedule

**Quarterly Tasks** (Every 3 months):
- [ ] Rotate Slack webhook URL → [Maintenance Guide](slack-notifications-setup.md#quarterly-webhook-rotation-recommended)
- [ ] Run full test suite → [Testing Procedures](slack-notifications-testing.md#quarterly-full-test-suite)
- [ ] Review notification delivery metrics
- [ ] Update documentation if needed

**Monthly Tasks**:
- [ ] Validate notification system → [Monthly Validation](slack-notifications-testing.md#monthly-validation)
- [ ] Review failed notifications (if any)
- [ ] Check for slackapi action updates

### Incident Response

**Common Incidents**:

| Incident | Detection | First Response | SLA |
|----------|-----------|----------------|-----|
| Notification not received | Manual check after pipeline failure | Verify webhook URL and secret | 1 hour |
| Secret exposed | GitHub security alert | Revoke webhook, regenerate immediately | 15 minutes |
| Rate limit exceeded | Error in GitHub Actions logs | Investigate trigger frequency | 2 hours |
| Action deprecated | GitHub Dependabot alert | Update slackapi action version | 1 week |

**Escalation Path**:
1. DevOps Engineer → Review logs and attempt resolution
2. Security Team → If secret exposure suspected
3. GitHub Support → If platform issue
4. Slack Support → If Slack API issue

---

## Security Best Practices

### Secret Management

**Do**:
- ✅ Store webhook URL only in GitHub Secrets
- ✅ Rotate webhook URL quarterly
- ✅ Use incoming webhooks (not bot tokens)
- ✅ Limit webhook to single channel
- ✅ Monitor GitHub audit logs for secret access

**Don't**:
- ❌ Commit webhook URL to version control
- ❌ Share webhook URL via email/chat
- ❌ Use same webhook for multiple repositories
- ❌ Grant webhook broader permissions than needed

### Access Control

**Required Permissions**:
- GitHub repository admin: To manage secrets
- Slack workspace admin: To create webhooks
- CI/CD pipeline access: To view logs and diagnose issues

**Review Frequency**: Quarterly

---

## Troubleshooting Quick Reference

### No Notification Received

**Checklist**:
1. Is the failed job on `master` or `develop` branch? (Feature branches don't notify)
2. Is GitHub secret `SLACK_WEBHOOK_URL` configured correctly?
3. Is the webhook URL still valid in Slack? (Not revoked)
4. Check `notify-slack` job logs in GitHub Actions for errors

**Resolution**: [Setup Guide - Troubleshooting](slack-notifications-setup.md#troubleshooting)

### Notification Content Broken

**Checklist**:
1. Validate JSON payload syntax in workflow YAML
2. Check GitHub context variables availability
3. Test payload in Slack Block Kit Builder

**Resolution**: [Testing Guide - Content Validation](slack-notifications-testing.md#test-8-notification-content-validation)

### Secret Exposed in Logs

**CRITICAL - Immediate Action Required**:
1. Revoke webhook URL in Slack immediately
2. Generate new webhook URL
3. Update GitHub secret
4. Report to security team
5. Review audit logs

**Prevention**: [Setup Guide - Security](slack-notifications-setup.md#security-considerations)

---

## Contributing

### Adding New Operational Guides

**Template Structure**:
1. Overview (purpose, scope, estimated time)
2. Prerequisites (access requirements, tools)
3. Step-by-step procedures (numbered, actionable)
4. Validation checklist (how to verify success)
5. Troubleshooting (common issues and solutions)
6. Maintenance (ongoing tasks and schedule)

**Documentation Standards**:
- Use clear, concise language
- Include code examples with syntax highlighting
- Provide validation criteria for each step
- Include security considerations
- Link to related documentation

### Requesting Documentation

**Process**:
1. Create GitHub issue with label `documentation`
2. Describe operational procedure needed
3. Include use case and priority
4. DevOps team will prioritize and create guide

---

## Related Documentation

**Infrastructure**:
- CI/CD Pipeline: [.github/workflows/ci-cd.yml](../../.github/workflows/ci-cd.yml)
- Build System: [tools/](../../tools/)
- Testing Framework: [tests/](../../tests/)

**Architecture**:
- System Architecture: [../architecture/](../architecture/)
- Decision Records: [../architecture/](../architecture/)

**Development**:
- Contributing Guide: [../../CONTRIBUTING.md](../../CONTRIBUTING.md)
- Development Setup: [../../README.md](../../README.md)

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-31 | Initial operations documentation with Slack notifications |

---

**Maintained by**: DevOps Team
**Last Updated**: 2026-01-31
**Next Review**: 2026-04-30
