# nWave Framework CI/CD Pipeline

Comprehensive continuous integration and automated release workflow for the nWave framework.

## Overview

The CI/CD pipeline automatically validates code quality, runs tests, and publishes releases through GitHub Actions.

### Workflow File

`.github/workflows/ci-cd.yml`

### Triggers

- **Push to master/develop**: Full CI validation
- **Pull requests**: Full CI validation
- **Version tags (v*)**: CI validation + automated release creation

## Pipeline Stages

### Stage 1: Continuous Integration (CI)

Runs on **every push and pull request** across multiple environments:

#### Test Matrix
- **Operating Systems**: Ubuntu, Windows, macOS
- **Python Versions**: 3.11, 3.12
- **Total Combinations**: 6 (3 OS × 2 Python versions)

#### Quality Gates

1. **Pre-commit Hooks**
   - YAML validation
   - Trailing whitespace removal
   - End-of-file fixing
   - Merge conflict detection
   - Private key detection
   - Ruff linting and formatting

2. **Agent Name Synchronization**
   ```bash
   python scripts/framework/sync_agent_names.py --verify
   ```

3. **Framework Catalog Validation**
   - YAML syntax validation
   - Required fields verification
   - Semantic versioning format check

4. **Documentation Version Consistency**
   - Cross-reference version markers
   - Ensure documentation matches catalog version

5. **Pytest Test Suite**
   - **246 tests** must pass (100%)
   - Coverage reporting (XML + HTML)
   - Test results uploaded as artifacts

#### Outputs

All CI runs produce:
- Test results (JUnit XML format)
- Coverage reports (XML + HTML)
- Downloadable artifacts (14-day retention)

### Stage 2: Build Framework (Tags Only)

Triggered **only when version tags are pushed** (e.g., `v1.4.8`).

#### Build Process

1. **Version Extraction**
   - Extract version from Git tag
   - Verify against `nWave/framework-catalog.yaml`
   - Fail if versions don't match

2. **Release Package Creation**
   - `nwave-claude-code-{version}.tar.gz`
   - `nwave-codex-{version}.tar.gz`
   - `install-nwave-claude-code.py`

4. **Checksum Generation**
   - SHA256 for all artifacts
   - `SHA256SUMS.txt` file

#### Outputs

- Release packages (90-day retention)
- Checksums for verification

### Stage 3: GitHub Release Creation (Tags Only)

Creates official GitHub release with auto-generated notes.

#### Release Contents

- **Name**: `nWave Framework v{version}`
- **Body**: Auto-generated release notes
- **Artifacts**:
  - Framework packages (tar.gz)
  - Installation script (Python)
  - Checksums (SHA256SUMS.txt)

#### Pre-release Detection

Tags containing `-beta`, `-rc`, or `-alpha` are marked as pre-releases automatically.

## Usage

### Running CI Locally

#### Install Pre-commit Hooks
```bash
pip install pre-commit
pre-commit install
```

#### Run All Pre-commit Checks
```bash
pre-commit run --all-files
```

#### Run Pytest Suite
```bash
pytest tests/ --verbose --cov=. --cov-report=term-missing
```

#### Verify Agent Synchronization
```bash
python scripts/framework/sync_agent_names.py --verify
```

### Creating a Release

#### 1. Update Version

Edit `nWave/framework-catalog.yaml`:
```yaml
version: "1.4.9"  # Increment according to semver
```

#### 2. Commit Version Change

```bash
git add nWave/framework-catalog.yaml
git commit -m "chore: bump version to 1.4.9"
git push origin master
```

#### 3. Create and Push Tag

```bash
# Create annotated tag
git tag -a v1.4.9 -m "Release version 1.4.9"

# Push tag (triggers release workflow)
git push origin v1.4.9
```

#### 4. Monitor Workflow

```bash
# Using GitHub CLI
gh run watch

# Or visit GitHub Actions page
# https://github.com/{owner}/{repo}/actions/workflows/ci-cd.yml
```

#### 5. Verify Release

Check the release page:
```
https://github.com/{owner}/{repo}/releases/tag/v1.4.9
```

## Status Badges

Add these badges to your README.md:

### CI Status Badge
```markdown
![CI Status](https://github.com/{owner}/{repo}/actions/workflows/ci-cd.yml/badge.svg)
```

### Latest Release Badge
```markdown
![Latest Release](https://img.shields.io/github/v/release/{owner}/{repo})
```

### Test Coverage Badge (optional)
After setting up Codecov or similar:
```markdown
![Coverage](https://codecov.io/gh/{owner}/{repo}/branch/master/graph/badge.svg)
```

## Troubleshooting

### CI Failures

#### Pre-commit Hook Failures
```bash
# Fix locally first
pre-commit run --all-files

# Common fixes
git add -u  # Stage fixes
git commit --amend --no-edit
git push --force-with-lease
```

#### Test Failures
```bash
# Run tests locally
pytest tests/ --verbose --tb=long

# Run specific test
pytest tests/test_specific.py::test_function -v
```

#### Agent Sync Failures
```bash
# Auto-fix synchronization
python scripts/framework/sync_agent_names.py --fix

# Verify fix
python scripts/framework/sync_agent_names.py --verify
```

### Release Failures

#### Version Mismatch
```
ERROR: Version mismatch!
  Tag version: 1.4.9
  framework-catalog.yaml version: 1.4.8
```

**Fix**:
```bash
# Delete the tag
git tag -d v1.4.9
git push origin :refs/tags/v1.4.9

# Update framework-catalog.yaml
# Commit and create tag again
```

#### Build Failures
```bash
# Test release packaging locally
python tools/create_release_packages.py

# Check for errors in output
```

#### Artifact Upload Failures

**Cause**: Missing files or incorrect paths

**Fix**:
1. Check workflow logs for specific error
2. Verify all expected files exist in `dist/releases/`
3. Re-tag and push if needed

## Advanced Configuration

### Custom Python Dependencies

If your project requires additional dependencies, create `requirements.txt`:

```txt
pytest>=7.0.0
pytest-cov>=4.0.0
pyyaml>=6.0
```

The workflow will automatically detect and install them.

### Timeout Adjustments

Default timeouts:
- CI jobs: 30 minutes
- Build job: 20 minutes
- Release job: 10 minutes

To adjust, edit `.github/workflows/ci-cd.yml`:
```yaml
jobs:
  ci:
    timeout-minutes: 45  # Increase if needed
```

### Matrix Customization

Add/remove Python versions or OS combinations:

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest, macos-latest]
    python-version: ['3.8', '3.10', '3.12', '3.13']  # Add 3.13
```

### Conditional Steps

Run steps only on specific conditions:

```yaml
- name: Run only on Linux
  if: runner.os == 'Linux'
  run: ./linux-specific-script.sh

- name: Run only on master branch
  if: github.ref == 'refs/heads/master'
  run: ./master-only-task.sh
```

## Security Considerations

### Secrets Management

The workflow uses `GITHUB_TOKEN` (automatically provided) for:
- Creating releases
- Uploading artifacts

No manual secrets configuration required.

### Permissions

Required permissions (already configured):
```yaml
permissions:
  contents: write  # For creating releases
  pull-requests: read  # For PR validation
```

### Private Key Detection

Pre-commit hook automatically scans for:
- SSH private keys
- API keys
- Authentication tokens
- Credentials

## Performance Optimization

### Caching Strategy

The workflow caches:
- Pip dependencies (per OS/Python version)
- Pre-commit environments
- Build artifacts

Cache invalidation:
- `CACHE_VERSION` environment variable (manual)
- `requirements.txt` changes (automatic)

### Parallel Execution

- **CI Matrix**: All 9 combinations run in parallel
- **Build**: Sequential (depends on CI)
- **Release**: Sequential (depends on Build)

### Artifact Retention

- **Test results**: 14 days
- **Coverage reports**: 14 days
- **Release packages**: 90 days

## Integration with Development Workflow

### Pre-commit Integration

```bash
# Automatic validation before every commit
git commit -m "fix: resolve issue"
# Pre-commit runs automatically

# Bypass (not recommended)
git commit -m "fix: urgent" --no-verify
```

### Pull Request Workflow

1. Create feature branch
2. Make changes
3. Commit (pre-commit runs)
4. Push to GitHub
5. Create PR
6. CI runs automatically
7. Review CI results
8. Merge when all checks pass

### Release Workflow

1. Ensure all tests pass on master
2. Update version in `framework-catalog.yaml`
3. Commit version bump
4. Create annotated tag
5. Push tag
6. CI/CD creates release automatically
7. Verify release artifacts
8. Announce release

## Monitoring and Notifications

### GitHub Actions Dashboard

View all workflow runs:
```
https://github.com/{owner}/{repo}/actions
```

### Email Notifications

GitHub sends emails for:
- Failed workflows (if you're the author)
- Successful releases (if subscribed)

Configure in GitHub Settings → Notifications.

### Slack/Discord Integration (Optional)

Add notification steps to workflow:

```yaml
- name: Notify Slack
  if: failure()
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## Continuous Improvement

### Metrics to Monitor

- **Test execution time**: Should remain < 5 minutes
- **Build time**: Should remain < 10 minutes
- **Cache hit rate**: Should be > 80%
- **Flaky tests**: Should be 0

### Regular Maintenance

- **Monthly**: Review and update Python versions
- **Quarterly**: Update GitHub Actions to latest versions
- **Annually**: Review caching strategy and retention policies

## Related Documentation

- [Release Guide](RELEASING.md)
- [Installation Guide](installation/INSTALL.md)
- [Contributing Guide](../CONTRIBUTING.md)

---

For issues with CI/CD pipeline, please open an issue on GitHub with:
- Workflow run URL
- Error messages
- Steps to reproduce
