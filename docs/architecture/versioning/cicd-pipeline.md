# CI/CD Pipeline Design: Versioning and Release Management

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

## 1. Pipeline Architecture Overview

The CI/CD pipeline for versioning and release management extends the existing `ci-cd.yml` workflow with a dedicated release pipeline. The architecture follows a two-branch strategy with protected `main` and `development` branches.

### Pipeline Topology

```
                                    PR Pipeline
                                    (development -> main)
                                         |
    +------------------------------------v------------------------------------+
    |                                                                         |
    |  Stage 1: Fast Checks (parallel, ~1 min)                               |
    |  - commitlint, code-quality, file-quality, security                    |
    |                                                                         |
    +------------------------------------+------------------------------------+
                                         |
    +------------------------------------v------------------------------------+
    |                                                                         |
    |  Stage 2: Framework Validation (~2 min)                                |
    |  - YAML schema, docs validation, conflict detection                    |
    |                                                                         |
    +------------------------------------+------------------------------------+
                                         |
    +------------------------------------v------------------------------------+
    |                                                                         |
    |  Stage 3: Cross-Platform Tests (matrix, ~10 min)                       |
    |  - 3 OS x 2 Python = 6 parallel jobs                                   |
    |                                                                         |
    +------------------------------------+------------------------------------+
                                         |
    +------------------------------------v------------------------------------+
    |                                                                         |
    |  Stage 4: Agent Sync Validation (~1 min)                               |
    |  - Verify agent name synchronization                                   |
    |                                                                         |
    +------------------------------------+------------------------------------+
                                         |
                                    [PR STATUS]
                                         |
                          (requires repo owner approval)
                                         |
                                    [MERGE TO MAIN]
                                         |
    +------------------------------------v------------------------------------+
    |                                                                         |
    |  Release Pipeline (on push to main)                                    |
    |  Stage 5: Version Bump + Changelog                                     |
    |  Stage 6: Build Distribution                                           |
    |  Stage 7: Create Tag + GitHub Release                                  |
    |                                                                         |
    +------------------------------------------------------------------------+
```

---

## 2. PR Pipeline (development -> main)

### 2.1 Trigger Conditions

```yaml
on:
  pull_request:
    branches:
      - main
    types: [opened, synchronize, reopened]
```

### 2.2 Quality Gates

The PR pipeline reuses all existing stages from `ci-cd.yml`:

| Stage | Duration | Quality Gate | Blocking |
|-------|----------|--------------|----------|
| Commit Lint | ~30s | Conventional commits | Yes |
| Code Quality | ~1min | Ruff lint + format | Yes |
| File Quality | ~30s | YAML/JSON syntax, whitespace | Yes |
| Security | ~30s | No merge conflicts, no keys | Yes |
| Framework Validation | ~2min | Schema valid, docs fresh | Yes |
| Cross-Platform Tests | ~10min | All tests pass | Yes |
| Agent Sync | ~1min | Names synchronized | Yes |

### 2.3 PR Requirements

Before merge to `main`:

1. **All quality gates pass** - Pipeline status must be green
2. **Repo owner approval** - Manual approval required
3. **Branch up-to-date** - Must be rebased on latest `main`
4. **No unresolved conversations** - All review comments addressed

---

## 3. Release Pipeline (on merge to main)

### 3.1 Trigger Conditions

```yaml
on:
  push:
    branches:
      - main
    paths-ignore:
      - 'docs/**'
      - '*.md'
      - '.gitignore'
```

### 3.2 Stage 5: Version Bump + Changelog

**Duration**: ~2 minutes

**Actions**:
1. Extract current version from `pyproject.toml`
2. Determine version bump type from conventional commits:
   - `feat:` -> minor bump
   - `fix:` -> patch bump
   - `BREAKING CHANGE:` -> major bump
3. Update `pyproject.toml` with new version
4. Generate changelog from conventional commits
5. Commit version bump (bot commit)

**Version Bump Logic**:
```python
def determine_bump_type(commits: list[str]) -> str:
    """Analyze commits since last tag to determine bump type."""
    if any("BREAKING CHANGE" in c or "!:" in c for c in commits):
        return "major"
    if any(c.startswith("feat") for c in commits):
        return "minor"
    return "patch"
```

**Changelog Generation**:
```
## v{version} ({date})

### Features
- feat(scope): description (#PR)

### Bug Fixes
- fix(scope): description (#PR)

### Breaking Changes
- BREAKING CHANGE: description
```

### 3.3 Stage 6: Build Distribution

**Duration**: ~5 minutes

**Actions**:
1. Run `create_github_tarballs.py` to create release archives
2. Generate SHA256 checksums for all artifacts
3. Validate package structure

**Build Artifacts**:
```
dist/releases/
  nwave-{version}-claude-code.tar.gz
  nwave-{version}-codex.tar.gz
  install-nwave-claude-code.py
  install-nwave-codex.py
  SHA256SUMS.txt
```

### 3.4 Stage 7: Create Tag + GitHub Release

**Duration**: ~2 minutes

**Actions**:
1. Create annotated Git tag `v{version}`
2. Push tag to repository
3. Create GitHub Release with:
   - Release title: `nWave Framework v{version}`
   - Release notes from changelog
   - Attached assets from `dist/releases/`

---

## 4. Workflow Integration with Existing CI/CD

### 4.1 Reuse Strategy

The release pipeline **extends** the existing `ci-cd.yml` rather than replacing it:

| Existing Component | Reuse Strategy |
|-------------------|----------------|
| Stage 1-4 jobs | Reuse as-is for PR validation |
| Build job | Extend for release packaging |
| Release job | Extend for automated changelog |
| Caching | Reuse pip and npm caches |
| Matrix testing | Reuse 3x2 matrix configuration |

### 4.2 New Workflow File

Create `.github/workflows/release.yml` for release-specific logic:
- Version bump automation
- Changelog generation
- Tag creation
- GitHub Release publication

The existing `ci-cd.yml` continues to handle:
- PR validation
- Tag-triggered builds (manual releases)
- All quality gates

---

## 5. Pipeline Security

### 5.1 Permissions

```yaml
permissions:
  contents: write      # For tag creation, release publication
  pull-requests: read  # For PR information
```

### 5.2 Token Management

- **GITHUB_TOKEN**: Used for all GitHub API operations
- **No external secrets**: No third-party services required
- **gh CLI authentication**: Inherits from GITHUB_TOKEN

### 5.3 Branch Protection Rules

Configured in repository settings (not workflow):

| Rule | Setting |
|------|---------|
| Require PR | Yes |
| Required reviewers | 1 (repo owner) |
| Require status checks | Yes (all Stage 1-4 jobs) |
| Require linear history | Yes |
| Restrict force push | Yes |
| Restrict deletions | Yes |

---

## 6. Error Handling

### 6.1 Pipeline Failure Recovery

| Failure Point | Recovery Strategy |
|---------------|-------------------|
| Tests fail in PR | Block merge, fix and re-run |
| Version bump fails | Pipeline stops, no tag created |
| Build fails | Pipeline stops, no release |
| Release publish fails | Manual retry via re-run |

### 6.2 Rollback Strategy

If a release causes issues:
1. Create hotfix branch from `main`
2. Apply fix
3. Create PR to `main` with `fix:` commit
4. New patch release will be created on merge

---

## 7. DORA Metrics Alignment

### 7.1 Deployment Frequency

**Target**: Ad-hoc (release when ready)
**Measurement**: Count of GitHub Releases per month

### 7.2 Lead Time for Changes

**Target**: < 1 day from merge to release
**Measurement**: Time from PR merge to GitHub Release publication

### 7.3 Change Failure Rate

**Target**: < 15%
**Measurement**: Releases requiring hotfix within 7 days

### 7.4 Mean Time to Recovery

**Target**: < 1 hour
**Measurement**: Time from issue report to hotfix release

---

## 8. Pure Python Implementation

Per ADR-PLAT-001, all pipeline operations use pure Python:

| Operation | Traditional Tool | Python Alternative |
|-----------|------------------|-------------------|
| HTTP requests | curl/wget | `requests` library |
| Archive creation | tar | `tarfile` module |
| Checksum | shasum | `hashlib` module |
| JSON parsing | jq | `json` module |
| YAML parsing | yq | `pyyaml` library |

This ensures consistent behavior across Windows, macOS, and Linux runners.

---

## 9. Integration Points

### 9.1 With /nw:forge:release Command

The command creates a PR which triggers this pipeline:

```
/nw:forge:release
      |
      v
  gh pr create (development -> main)
      |
      v
  PR Pipeline runs (Stage 1-4)
      |
      v
  [Manual approval required]
      |
      v
  gh pr merge
      |
      v
  Release Pipeline runs (Stage 5-7)
      |
      v
  GitHub Release published
```

### 9.2 With /nw:update Command

Users consume releases via `/nw:update`:
- Queries GitHub API for latest release
- Downloads assets from GitHub Release
- Validates SHA256 checksum
- Installs to `~/.claude/`

---

## 10. Handoff to DISTILL Wave

This design provides the foundation for acceptance tests:

### Pipeline Behavior Scenarios

1. **PR with passing tests merges successfully**
2. **PR with failing tests blocks merge**
3. **Merge to main triggers release pipeline**
4. **Version bump follows conventional commits**
5. **Changelog includes all commit types**
6. **GitHub Release contains all artifacts**

### Quality Gate Verification

1. **All Stage 1-4 gates block PR on failure**
2. **Branch protection rules enforced**
3. **Only repo owner can approve PRs**

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-28 | Apex (platform-architect) | Initial platform design |
