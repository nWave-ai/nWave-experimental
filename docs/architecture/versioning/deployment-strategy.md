# Deployment Strategy: Versioning and Release Management

## Document Metadata

| Field | Value |
|-------|-------|
| Feature | nWave Versioning and Release Management |
| Wave | DESIGN (Platform) |
| Status | Platform Design Complete |
| Author | Apex (platform-architect) |
| Created | 2026-01-28 |
| Version | 1.0.0 |

---

## 1. Release Strategy Overview

nWave follows an **ad-hoc release** strategy - releases are published when features are ready, not on a fixed schedule. This provides flexibility while maintaining quality through automated pipelines.

### Release Channels

| Channel | Purpose | Version Format | Distribution |
|---------|---------|----------------|--------------|
| **Stable** | Official releases | `MAJOR.MINOR.PATCH` | GitHub Releases |
| **RC (Local)** | Custom local builds | `{base}-rc.{branch}.{date}.{N}` | Local `dist/` only |

Note: RC versions are **never** published to GitHub Releases. They exist only for local testing via `/nw:forge`.

---

## 2. Branch Strategy

### 2.1 Branch Topology

```
main (protected)
  ^
  |  PR + approval
  |
development
  ^
  |  feature branches
  |
feature/*, fix/*, etc.
```

### 2.2 Branch Roles

| Branch | Purpose | Protection | Direct Push |
|--------|---------|------------|-------------|
| `main` | Production releases | Full | Forbidden |
| `development` | Integration branch | Partial | Allowed |
| `feature/*` | Feature development | None | Allowed |
| `fix/*` | Bug fixes | None | Allowed |

### 2.3 Branch Protection Rules for `main`

| Rule | Setting | Rationale |
|------|---------|-----------|
| Require pull request | Yes | All changes reviewed |
| Required approving reviews | 1 | Repo owner approval |
| Dismiss stale reviews | Yes | Re-review after changes |
| Require status checks | Yes | CI must pass |
| Required status checks | `test`, `agent-sync` | Critical gates |
| Require linear history | Yes | Clean git history |
| Include administrators | Yes | No bypass for admins |
| Restrict push | Yes | Only via PR |
| Restrict force push | Yes | Prevent history rewrite |
| Restrict deletions | Yes | Branch permanence |

---

## 3. Release Workflow

### 3.1 Complete Release Flow

```
Developer                    GitHub                      Users
    |                           |                           |
    |  1. /nw:forge:release     |                           |
    |-------------------------->|                           |
    |                           |                           |
    |  2. PR created            |                           |
    |     (dev -> main)         |                           |
    |                           |                           |
    |  3. Pipeline runs         |                           |
    |     (Stage 1-4)           |                           |
    |                           |                           |
    |  4. Review & approve      |                           |
    |-------------------------->|                           |
    |                           |                           |
    |  5. Merge PR              |                           |
    |-------------------------->|                           |
    |                           |                           |
    |                           |  6. Release pipeline      |
    |                           |     - Version bump        |
    |                           |     - Build dist/         |
    |                           |     - Generate changelog  |
    |                           |     - Create tag          |
    |                           |     - Publish release     |
    |                           |                           |
    |                           |  7. GitHub Release        |
    |                           |-------------------------->|
    |                           |                           |
    |                           |                           |  8. /nw:update
    |                           |                           |<---
```

### 3.2 Step-by-Step Process

#### Step 1: Initiate Release

Developer runs `/nw:forge:release` from `development` branch:

```python
def create_release() -> ReleaseResult:
    # Validate preconditions
    if git.get_current_branch() != "development":
        raise Error("Must run from development branch")

    if git.has_uncommitted_changes():
        raise Error("Uncommitted changes detected")

    # Create PR
    pr = gh.create_pr(
        base="main",
        head="development",
        title=f"Release: {get_next_version()}",
        body=generate_pr_body()
    )

    return ReleaseResult(pr_number=pr.number)
```

#### Step 2: PR Validation

Pipeline runs automatically on PR creation:
- All quality gates must pass
- Cross-platform tests on 6 configurations
- Agent synchronization verified

#### Step 3: Manual Approval

Repo owner reviews and approves:
- Code changes reviewed
- Test coverage adequate
- No security concerns
- Release notes accurate

#### Step 4: Merge to Main

After approval, PR is merged (squash or rebase):
- Linear history maintained
- Merge commit links to PR

#### Step 5: Release Pipeline Triggers

On push to `main`, release pipeline executes:

```yaml
jobs:
  release:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Version bump
        # Determines bump type from commits

      - name: Build distribution
        # Creates release packages

      - name: Generate changelog
        # Extracts from conventional commits

      - name: Create tag
        # Creates annotated tag v{version}

      - name: Publish release
        # Creates GitHub Release with assets
```

#### Step 6: GitHub Release Published

Release includes:
- Version tag (e.g., `v1.3.0`)
- Changelog in release notes
- Distribution archives
- Installation scripts
- SHA256 checksums

---

## 4. Version Bump Automation

### 4.1 Bump Type Detection

```python
def determine_version_bump(commits: list[Commit]) -> BumpType:
    """Analyze commits to determine version bump type."""

    for commit in commits:
        # Breaking changes -> major
        if "BREAKING CHANGE" in commit.body:
            return BumpType.MAJOR
        if commit.type.endswith("!"):
            return BumpType.MAJOR

    for commit in commits:
        # New features -> minor
        if commit.type == "feat":
            return BumpType.MINOR

    # Bug fixes, docs, etc. -> patch
    return BumpType.PATCH
```

### 4.2 Version Update Locations

| File | Field | Update Method |
|------|-------|---------------|
| `pyproject.toml` | `version` | Python script |
| `nWave/framework-catalog.yaml` | `version` | Python script |

### 4.3 Commit Message

Version bump creates a bot commit:

```
chore(release): bump version to 1.3.0

Automated version bump from release pipeline.

Co-authored-by: github-actions[bot] <github-actions[bot]@users.noreply.github.com>
```

---

## 5. Changelog Generation

### 5.1 Conventional Commits Mapping

| Commit Type | Changelog Section | Example |
|-------------|------------------|---------|
| `feat` | Features | `feat(agents): add researcher agent` |
| `fix` | Bug Fixes | `fix(update): handle network timeout` |
| `docs` | Documentation | `docs(readme): update install instructions` |
| `perf` | Performance | `perf(build): optimize bundle size` |
| `refactor` | Code Refactoring | `refactor(core): simplify version logic` |
| `test` | Tests | `test(update): add rollback tests` |
| `chore` | Maintenance | `chore(deps): update dependencies` |
| `BREAKING CHANGE` | Breaking Changes | `feat!: rename command` |

### 5.2 PR Reference in Changelog

**Requirement**: Changelog entries should include PR references for traceability.

**Current Implementation**: The release pipeline generates changelog entries using the commit short hash as the reference (e.g., `feat(agents): add researcher agent (abc1234)`).

**PR Number Injection**: PR numbers are automatically available when using GitHub's squash merge, as the default squash commit message includes the PR number. For repositories using this pattern, the changelog will naturally include PR references.

**Alternative Approaches**:
1. **Squash merge default**: GitHub automatically appends `(#PR)` to squash commit messages
2. **Commit message convention**: Contributors can manually include `(#PR)` in commit messages
3. **Future enhancement**: GitHub API lookup during release to inject PR numbers (not implemented in v1.0)

**Note**: The commitlint configuration should validate conventional commit format. PR number inclusion is recommended but not enforced at the commit level to avoid friction for contributors.

### 5.3 Changelog Format

```markdown
## v1.3.0 (2026-01-28)

### Features
- **agents**: add researcher agent for deep analysis (#123)
- **commands**: implement /nw:version command (#124)

### Bug Fixes
- **update**: handle network timeout gracefully (#125)
- **backup**: fix retention policy edge case (#126)

### Breaking Changes
- **commands**: rename /nw:build to /nw:forge (#127)

### Documentation
- **readme**: update installation instructions (#128)

### Full Changelog
https://github.com/owner/repo/compare/v1.2.0...v1.3.0
```

---

## 6. GitHub Release Structure

### 6.1 Release Title

```
nWave Framework v1.3.0
```

### 6.2 Release Body

```markdown
# nWave Framework v1.3.0

## Release Information

- **Version**: 1.3.0
- **Release Date**: 2026-01-28
- **Methodology**: DISCUSS > DESIGN > DISTILL > DEVELOP > DELIVER

## Installation

### Quick Install (Claude Code)
```bash
curl -O https://github.com/owner/repo/releases/download/v1.3.0/install-nwave-claude-code.py
python3 install-nwave-claude-code.py
```

### Update Existing Installation
Run `/nw:update` in Claude Code.

## What's New

{changelog content}

## Quality Assurance

This release passed all quality gates:
- Conventional commit validation
- Ruff lint and format checks
- Cross-platform tests (Linux, Windows, macOS)
- Multi-Python version tests (3.11, 3.12)
- Agent synchronization verification

## Checksums

SHA256 checksums are available in `SHA256SUMS.txt` for verification.
```

### 6.3 Release Assets

| Asset | Description |
|-------|-------------|
| `nwave-1.3.0-claude-code.tar.gz` | Claude Code bundle |
| `nwave-1.3.0-codex.tar.gz` | Codex bundle |
| `install-nwave-claude-code.py` | Claude Code installer |
| `install-nwave-codex.py` | Codex installer |
| `SHA256SUMS.txt` | Checksums for all assets |

---

## 7. Rollback Strategy

### 7.1 User Rollback (via /nw:update)

If a user encounters issues after updating:

1. **Manual rollback from backup**:
   ```bash
   # List available backups
   ls -la ~/.claude.backup.*

   # Restore from backup
   rm -rf ~/.claude
   cp -r ~/.claude.backup.20260128143022 ~/.claude
   ```

2. **Wait for hotfix release**: Report issue, dev team releases fix

### 7.2 Developer Rollback (via Git)

If a release causes widespread issues:

1. **Create hotfix branch**:
   ```bash
   git checkout main
   git checkout -b fix/critical-issue
   ```

2. **Apply fix and create PR**:
   ```bash
   git commit -m "fix: critical issue from v1.3.0"
   git push origin fix/critical-issue
   gh pr create --base main
   ```

3. **Fast-track merge**: Repo owner approves immediately

4. **New patch release**: Pipeline creates v1.3.1

### 7.3 Release Reversion (Emergency Only)

In extreme cases (security vulnerability):

1. Delete the GitHub Release (hides from users)
2. Delete the Git tag
3. Users running `/nw:update` will see previous version

This is a last resort - prefer hotfix releases.

---

## 8. Safety Mechanisms

### 8.1 Pre-Release Validation

| Check | Enforcement |
|-------|-------------|
| Tests pass | Pipeline blocks merge |
| Code review | Required approval |
| Branch up-to-date | GitHub enforces |
| Conventional commits | commitlint validates |

### 8.2 Post-Release Validation

| Check | Method |
|-------|--------|
| Assets uploaded | Pipeline verification |
| Checksums valid | Automated validation |
| Download works | Smoke test in pipeline |

### 8.3 User-Side Validation

| Check | Implementation |
|-------|---------------|
| Checksum verification | `/nw:update` validates SHA256 |
| Atomic installation | Download-then-install |
| Backup before install | Automatic backup creation |

---

## 9. Integration with Commands

### 9.1 /nw:forge:release

Initiates release workflow:
- Validates branch and state
- Creates PR with generated title/body
- Displays PR URL and instructions

### 9.2 /nw:update

Consumes releases:
- Queries GitHub API for latest release
- Downloads appropriate asset
- Validates checksum
- Installs with backup

### 9.3 /nw:version

Checks release status:
- Compares installed vs latest
- Uses watermark for caching
- Graceful offline handling

---

## 10. Handoff to DISTILL Wave

This deployment strategy provides scenarios for acceptance tests:

### Release Workflow Scenarios

1. **/nw:forge:release creates PR from development**
2. **PR blocked when not on development branch**
3. **Pipeline runs on PR creation**
4. **Merge blocked until pipeline passes**
5. **Release pipeline triggers on merge**
6. **Version bumped based on commits**
7. **Changelog generated correctly**
8. **GitHub Release created with assets**

### Rollback Scenarios

1. **User can restore from backup**
2. **Hotfix release workflow works**
3. **Emergency release deletion possible**

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-28 | Apex (platform-architect) | Initial platform design |
| 1.1.0 | 2026-01-28 | Apex (platform-architect) | Added PR reference documentation (PLAT-MAJOR-004) |
