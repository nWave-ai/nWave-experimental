<!-- version: 1.4.5 -->

# nWave Framework Release Guide

This guide explains how to create new releases of the nWave framework.

## Release Process Overview

The release process is **fully automated** via GitHub Actions. When you push a version tag, the CI/CD pipeline automatically:

1. Builds the nWave framework
2. Creates distributable packages (Claude Code + Codex)
3. Generates release notes
4. Creates a GitHub release
5. Uploads release artifacts

## Creating a New Release

### 1. Update Version Number

Update the version in [`nWave/framework-catalog.yaml`](../nWave/framework-catalog.yaml):

```yaml
version: "1.2.71"  # Increment according to semver
```

### 2. Commit Version Change

```bash
git add nWave/framework-catalog.yaml
git commit -m "chore: bump version to 1.2.71"
git push origin master
```

### 3. Create and Push Version Tag

```bash
# Create annotated tag
git tag -a v1.2.71 -m "Release version 1.2.71"

# Push the tag to trigger release workflow
git push origin v1.2.71
```

### 4. Monitor Release Creation

The GitHub Actions workflow will automatically:
- Build the framework
- Create packages
- Publish the release

Watch the workflow progress at:
```
https://github.com/nWave-ai/nWave/actions/workflows/release.yml
```

### 5. Verify Release

Once the workflow completes, verify the release:
- Visit: https://github.com/nWave-ai/nWave/releases
- Check that artifacts are attached:
  - `nwave-claude-code-{version}.tar.gz`
  - `nwave-codex-{version}.tar.gz`
  - `install-nwave-claude-code.py`

## Semantic Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** version (X.0.0): Incompatible API changes
- **MINOR** version (0.X.0): New functionality (backward compatible)
- **PATCH** version (0.0.X): Bug fixes (backward compatible)

### Examples

- `v1.2.70` → `v1.2.71`: Patch release (bug fixes)
- `v1.2.70` → `v1.3.0`: Minor release (new features)
- `v1.2.70` → `v2.0.0`: Major release (breaking changes)

## Release Artifacts

Each release includes:

### Claude Code Package
- **File**: `nwave-claude-code-{version}.tar.gz`
- **Size**: ~1.5 MB
- **Contents**: 23+ agents, 21+ commands, scripts, templates

### Codex Package
- **File**: `nwave-codex-{version}.tar.gz`
- **Size**: ~1.5 MB
- **Contents**: Same as Claude Code (alternative format)

### Standalone Installer
- **File**: `install-nwave-claude-code.py`
- **Size**: ~13 KB
- **Purpose**: Download and install framework without cloning repo

## Testing Before Release

### Local Package Test

Before creating a release tag, test the release packaging locally:

```bash
# Clean previous packages
rm -rf dist/

# Create packages
python tools/create_release_packages.py

# Verify packages
ls -lh dist/releases/
```

### Local Installation Test

Test the installer with the local package:

```bash
cd dist/releases
python install-nwave-claude-code.py --local nwave-claude-code-{version}.tar.gz
```

## Hotfix Releases

For urgent bug fixes:

1. Create hotfix branch from master:
   ```bash
   git checkout -b hotfix/1.2.71 master
   ```

2. Apply fixes and update version

3. Merge to master:
   ```bash
   git checkout master
   git merge hotfix/1.2.71
   ```

4. Create tag and push:
   ```bash
   git tag -a v1.2.71 -m "Hotfix: critical bug fix"
   git push origin master v1.2.71
   ```

## Pre-releases

For beta/RC versions, use pre-release tags:

```bash
# Create pre-release tag
git tag -a v1.3.0-beta.1 -m "Beta release for v1.3.0"
git push origin v1.3.0-beta.1
```

The workflow will create a pre-release on GitHub (marked as "Pre-release").

## Rollback a Release

If a release has critical issues:

### 1. Delete the Release (GitHub UI)
- Go to: https://github.com/nWave-ai/nWave/releases
- Edit the problematic release
- Delete the release

### 2. Delete the Tag (Local and Remote)

```bash
# Delete local tag
git tag -d v1.2.71

# Delete remote tag
git push origin :refs/tags/v1.2.71
```

### 3. Fix Issues and Re-release

```bash
# Fix the issues
git commit -m "fix: resolve critical issue"

# Create new tag
git tag -a v1.2.71 -m "Re-release v1.2.71 with fixes"
git push origin master v1.2.71
```

## Release Checklist

Before creating a release:

- [ ] All tests passing in CI
- [ ] Version bumped in `framework-catalog.yaml`
- [ ] Breaking changes documented (if major version)
- [ ] Migration guide created (if needed)
- [ ] Local build tested successfully
- [ ] Local installation tested successfully
- [ ] CHANGELOG reviewed (if manually maintained)

## Troubleshooting

### Workflow Fails on Build

**Cause**: Build errors in framework code

**Solution**:
1. Check workflow logs: https://github.com/nWave-ai/nWave/actions
2. Fix build errors locally
3. Delete failed tag: `git push origin :refs/tags/v1.2.71`
4. Commit fixes and re-tag

### Workflow Fails on Package Creation

**Cause**: Missing dependencies or invalid package structure

**Solution**:
1. Test locally: `python tools/create_release_packages.py`
2. Fix issues
3. Delete tag and re-release

### Release Created but Artifacts Missing

**Cause**: Upload step failed

**Solution**:
1. Check workflow permissions (needs `contents: write`)
2. Manually upload artifacts to existing release
3. Or delete release, fix, and re-tag

## Advanced: Manual Release

If CI/CD is unavailable, create release manually:

```bash
# Create release packages
python tools/create_release_packages.py

# Create release using GitHub CLI
gh release create v1.2.71 \
  --title "nWave Framework v1.2.71" \
  --notes-file dist/releases/RELEASE_NOTES_1.2.71.md \
  dist/releases/nwave-claude-code-1.2.71.tar.gz \
  dist/releases/nwave-codex-1.2.71.tar.gz \
  dist/releases/install-nwave-claude-code.py
```

## Release Announcement

After release:

1. Update [README.md](../README.md) if needed
2. Announce in GitHub Discussions
3. Update external documentation (if any)
4. Notify users of breaking changes (if major version)

## Related Documentation

- [Installation Guide](installation/INSTALL.md)
- [CI/CD Documentation](CI-CD-README.md)
- [Contributing Guide](../CONTRIBUTING.md) (if exists)

---

For questions or issues with the release process, please open an issue on GitHub.
