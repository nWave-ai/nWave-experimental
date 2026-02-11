# ADR-PLAT-003: Branch Protection and Approval Workflow

## Status

**Accepted**

## Context

The release management feature requires a controlled workflow for publishing official releases to GitHub. This involves:

1. **Branch strategy**: How code flows from development to production
2. **Protection rules**: Who can merge and under what conditions
3. **Approval workflow**: Required reviews before merge
4. **Pipeline integration**: How CI/CD validates changes

### Mike's Decisions

| Decision | Value |
|----------|-------|
| Branch strategy | Protected `main` + `development` branch with PR pipeline |
| PR pipeline | Auto-runs on PR to main, requires green status + repo owner approval |
| Main pipeline | On merge to main builds distribution and creates GitHub Release |

## Decision

**Implement a two-branch strategy with protected main and automated release on merge.**

### Branch Architecture

```
main (protected, releases only)
  ^
  |  PR required + owner approval + green pipeline
  |
development (integration branch)
  ^
  |  direct push allowed
  |
feature/*, fix/*, chore/* (short-lived branches)
```

### Branch Roles

| Branch | Purpose | Protection Level |
|--------|---------|------------------|
| `main` | Production releases | Full (see rules below) |
| `development` | Integration, testing | Partial (optional protection) |
| `feature/*` | Feature development | None |
| `fix/*` | Bug fixes | None |
| `chore/*` | Maintenance | None |

## Branch Protection Rules

### Main Branch Protection

| Rule | Setting | Rationale |
|------|---------|-----------|
| **Require pull request** | Yes | All changes must be reviewed |
| **Required reviewers** | 1 | Repo owner must approve |
| **Dismiss stale reviews** | Yes | Changes after approval require re-review |
| **Require status checks** | Yes | CI must pass before merge |
| **Required checks** | `test`, `agent-sync` | Critical quality gates |
| **Require branches up-to-date** | Yes | No stale merges |
| **Require linear history** | Yes | Clean git history (no merge commits) |
| **Include administrators** | Yes | Admins follow same rules |
| **Restrict push** | Yes | Only via PR, no direct push |
| **Restrict force push** | Yes | Prevent history rewrite |
| **Restrict deletions** | Yes | Branch permanence |

### Repository Settings Configuration

```yaml
# .github/settings.yml (if using probot/settings)
branches:
  - name: main
    protection:
      required_pull_request_reviews:
        required_approving_review_count: 1
        dismiss_stale_reviews: true
        require_code_owner_reviews: true
      required_status_checks:
        strict: true
        contexts:
          - "Test - Py3.12 / ubuntu-latest"
          - "Test - Py3.12 / windows-latest"
          - "Test - Py3.12 / macos-latest"
          - "Agent Sync Validation"
      enforce_admins: true
      required_linear_history: true
      restrictions: null
```

## Workflow Integration

### PR Pipeline (development -> main)

Triggered on: `pull_request` to `main`

```yaml
on:
  pull_request:
    branches: [main]

jobs:
  # All quality gates from ci-cd.yml run here
  # PR is blocked until all pass
```

### Release Pipeline (on merge to main)

Triggered on: `push` to `main`

```yaml
on:
  push:
    branches: [main]

jobs:
  version-bump:
    # Bumps version based on conventional commits

  build:
    # Creates release packages

  release:
    # Creates GitHub Release
```

### Workflow Sequence

```
1. Developer works on development branch
          |
          v
2. /nw:forge:release creates PR (development -> main)
          |
          v
3. PR Pipeline runs automatically
   - Stage 1: Fast checks (lint, format, security)
   - Stage 2: Framework validation
   - Stage 3: Cross-platform tests (6 matrix jobs)
   - Stage 4: Agent sync validation
          |
          v
4. All checks must pass (status: green)
          |
          v
5. Repo owner reviews and approves
          |
          v
6. PR is merged (squash or rebase for linear history)
          |
          v
7. Release Pipeline triggers on push to main
   - Version bump from conventional commits
   - Build distribution packages
   - Generate changelog
   - Create Git tag
   - Publish GitHub Release
```

## Consequences

### Positive

1. **Quality enforcement**: No code reaches main without passing tests
2. **Review requirement**: Human approval required for every release
3. **Audit trail**: PR history documents all changes
4. **Clean history**: Linear history makes debugging easier
5. **Automation**: Release happens automatically on merge

### Negative

1. **Process overhead**: Every release requires PR + approval
2. **Single approver bottleneck**: Only repo owner can approve
3. **No hotfix shortcut**: Even urgent fixes need PR process

### Neutral

1. **Ad-hoc releases**: Works well for our non-scheduled release cadence
2. **Small team fit**: Single approver is appropriate for small teams

## Merge Strategies

### Recommended: Squash Merge

```
development: A -- B -- C -- D
                          \
main:        X -- Y -- Z -- [ABCD squashed]
```

**Advantages**:
- Clean history on main
- Single commit per feature/fix
- Easy to revert entire feature

### Alternative: Rebase Merge

```
development: A -- B -- C -- D
                          \
main:        X -- Y -- Z -- A' -- B' -- C' -- D'
```

**Advantages**:
- Preserves individual commits
- More detailed history

### Not Recommended: Merge Commit

Creates non-linear history, blocked by protection rules.

## Emergency Procedures

### Hotfix Process

Even hotfixes follow the PR process:

```
1. Create fix/critical-issue branch from main
2. Apply fix
3. Create PR to main
4. Fast-track review (repo owner online)
5. Merge triggers release pipeline
6. Patch version released
```

### If Owner Unavailable

For true emergencies when repo owner cannot approve:

1. **Temporarily disable protection** (admin access required)
2. Direct push the fix
3. **Re-enable protection immediately**
4. Document the bypass in issue tracker

This should be extremely rare (<1/year).

## CODEOWNERS Configuration

```
# .github/CODEOWNERS

# Default owner for all files
*                       @repo-owner

# Specific ownership if needed
/nWave/                 @repo-owner
/.github/workflows/     @repo-owner
```

This ensures the repo owner is automatically requested for review on all PRs.

## Alternatives Considered

### Alternative 1: Single Branch (Trunk-Based)

All commits go directly to main with post-commit validation.

**Rejected because**: Too risky for releases, no pre-merge validation.

### Alternative 2: GitFlow

Full GitFlow with develop, release branches, etc.

**Rejected because**: Overkill for ad-hoc releases, adds complexity.

### Alternative 3: Multiple Approvers

Require 2+ approvers for releases.

**Rejected because**: Small team, would create bottleneck.

### Alternative 4: Auto-Merge on Green

Automatically merge when all checks pass, no human approval.

**Rejected because**: Mike wants manual approval as safety gate.

## References

- GitHub Branch Protection: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches
- GitHub CODEOWNERS: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
- Trunk-Based Development: https://trunkbaseddevelopment.com/

## Decision Record

| Field | Value |
|-------|-------|
| Decision | ADR-PLAT-003 |
| Date | 2026-01-28 |
| Author | Apex (platform-architect) |
| Status | Accepted |
| Deciders | Mike (stakeholder) |
