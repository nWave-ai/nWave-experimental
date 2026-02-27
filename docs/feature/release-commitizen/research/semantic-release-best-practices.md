# Research: Semantic-Release Best Practices for CI/CD Integration

**Date**: 2026-01-23
**Researcher**: researcher (Nova)
**Overall Confidence**: High
**Sources Consulted**: 12

## Executive Summary

Semantic-release automates version management and package publishing by analyzing conventional commits. For nWave's open-source release flow, the recommended approach combines GitHub Actions with a carefully ordered plugin chain. Key findings:

1. **Plugin order matters critically** - changelog must run before git/npm plugins
2. **CHANGELOG.md is optional but valuable** - GitHub Releases alone may suffice for GitHub-centric projects
3. **Branch protection creates complexity** - the default `GITHUB_TOKEN` cannot push to protected branches
4. **Manual triggers via `workflow_dispatch`** - enables your future `/nw:release` command pattern

---

## Research Methodology

**Search Strategy**: Official semantic-release documentation, GitHub repositories, and community best practices from 2025-2026

**Source Selection Criteria**:
- Source types: official, technical_docs, industry
- Reputation threshold: high/medium-high minimum
- Verification method: Cross-referencing across official docs and community implementations

---

## Findings

### Finding 1: Recommended Plugin Chain

**Evidence**: The plugin execution order is critical. Plugins run in series, in the order defined.

**Source**: [semantic-release/changelog GitHub](https://github.com/semantic-release/changelog) - Accessed 2026-01-23

**Recommended Plugin Order**:

```json
{
  "plugins": [
    "@semantic-release/commit-analyzer",
    "@semantic-release/release-notes-generator",
    "@semantic-release/changelog",
    "@semantic-release/exec",
    "@semantic-release/npm",
    "@semantic-release/git",
    "@semantic-release/github"
  ]
}
```

| Plugin | Purpose |
|--------|---------|
| `@semantic-release/commit-analyzer` | Analyzes commits to determine version bump (major/minor/patch) |
| `@semantic-release/release-notes-generator` | Generates release notes from commits |
| `@semantic-release/changelog` | Updates CHANGELOG.md file |
| `@semantic-release/exec` | Runs custom commands (e.g., update version in source files) |
| `@semantic-release/npm` | Updates package.json version, publishes to npm |
| `@semantic-release/git` | Commits changelog/version changes back to repo |
| `@semantic-release/github` | Creates GitHub Release with notes, comments on issues/PRs |

**Confidence**: High

---

### Finding 2: @semantic-release/changelog Configuration

**Evidence**: "The release notes that would be added to a changelog file are likely redundant with the release notes added as GitHub releases."

**Source**: [semantic-release/changelog](https://github.com/semantic-release/changelog) - Accessed 2026-01-23

**Configuration Options**:

| Option | Purpose | Default |
|--------|---------|---------|
| `changelogFile` | Path to changelog file | `CHANGELOG.md` |
| `changelogTitle` | First line header in file | (none) |

**Best Configuration**:

```json
["@semantic-release/changelog", {
  "changelogFile": "CHANGELOG.md",
  "changelogTitle": "# Changelog\n\nAll notable changes to nWave are documented here."
}]
```

**Critical**: Must run BEFORE `@semantic-release/git` so the updated changelog is committed.

**GitHub Native Changelog Integration**: GitHub's auto-generated release notes are separate from this. The `@semantic-release/github` plugin creates GitHub Releases with the generated notes. There is no direct integration between CHANGELOG.md and GitHub's "Generate release notes" button - they serve different purposes.

**Confidence**: High

---

### Finding 3: GitHub Actions Integration

**Evidence**: Minimum required permissions are `contents: write` and `issues: write`.

**Source**: [semantic-release GitHub Actions Recipe](https://semantic-release.gitbook.io/semantic-release/recipes/ci-configurations/github-actions) - Accessed 2026-01-23

**Recommended Workflow**:

```yaml
name: Release
on:
  push:
    branches:
      - master
  workflow_dispatch:  # Enables manual trigger

permissions:
  contents: read  # Default for checkout

jobs:
  release:
    name: Release
    runs-on: ubuntu-latest
    permissions:
      contents: write       # Publish GitHub release, push tags
      issues: write         # Comment on released issues
      pull-requests: write  # Comment on released PRs
      id-token: write       # OIDC for npm provenance (if publishing)
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          persist-credentials: false  # Required if using PAT for protected branches

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "lts/*"

      - name: Install dependencies
        run: npm clean-install

      - name: Release
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: npx semantic-release
```

**Branch Protection Considerations**:

| Scenario | Token | Works? |
|----------|-------|--------|
| No branch protection | `GITHUB_TOKEN` | Yes |
| Branch protection enabled | `GITHUB_TOKEN` | No - cannot push |
| Branch protection + need commits | Personal Access Token (PAT) | Yes - security risk |
| Branch protection + security | GitHub App installation token | Yes - recommended |

**Key Warning**: Using PAT in workflows accessible from non-protected branches is a security risk. All branches can access secrets, potentially exposing elevated permissions.

**Confidence**: High

---

### Finding 4: CHANGELOG.md vs GitHub Releases

**Evidence**: "Consider whether committing release notes to a file is worth the added complexity compared to other available options."

**Source**: [semantic-release FAQ](https://semantic-release.gitbook.io/semantic-release/support/faq) - Accessed 2026-01-23

**Decision Matrix**:

| Approach | Pros | Cons |
|----------|------|------|
| **GitHub Releases only** | Simple, no commits needed, native integration | Not portable, less discoverable |
| **CHANGELOG.md only** | Portable, discoverable, version-controlled | Requires git commits, more complexity |
| **Both** | Best of both worlds | Redundant, maximum complexity |
| **CHANGELOG.md with link** | Simple file, full history on GitHub | Compromise approach |

**Recommendation for nWave**: Use both. As an open-source ATDD framework:
- CHANGELOG.md provides portability for users who clone/fork without visiting GitHub
- GitHub Releases enables watchers and provides downloadable artifacts
- The complexity cost is minimal with proper configuration

**Middle-ground Alternative**: Create a CHANGELOG.md containing only a link to GitHub Releases:

```markdown
# Changelog

For the complete changelog, see [GitHub Releases](https://github.com/swcraftsmanshipdojo/nWave/releases).
```

**Confidence**: High

---

### Finding 5: Manual Release Trigger (workflow_dispatch)

**Evidence**: "You can create workflows that are manually triggered with the `workflow_dispatch` event."

**Source**: [GitHub Blog - Manual Triggers](https://github.blog/changelog/2020-07-06-github-actions-manual-triggers-with-workflow_dispatch/) - Accessed 2026-01-23

**Pattern for `/nw:release` Command**:

```yaml
name: Release
on:
  push:
    branches: [master]
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Run in dry-run mode (no actual release)'
        required: false
        default: 'false'
        type: boolean

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-node@v4
        with:
          node-version: 'lts/*'

      - run: npm ci

      - name: Release
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          if [ "${{ inputs.dry_run }}" = "true" ]; then
            npx semantic-release --dry-run
          else
            npx semantic-release
          fi
```

**CLI Trigger via GitHub CLI**:

```bash
# Trigger release workflow manually
gh workflow run release.yml

# Trigger with dry-run
gh workflow run release.yml -f dry_run=true
```

This pattern enables your future `/nw:release` command to call `gh workflow run` programmatically.

**Confidence**: High

---

### Finding 6: Updating Version in Source Files

**Evidence**: "Use `@semantic-release/exec` plugin with the `prepareCmd` option."

**Source**: [semantic-release FAQ](https://semantic-release.gitbook.io/semantic-release/support/faq) - Accessed 2026-01-23

**Configuration for Version File Updates**:

```json
["@semantic-release/exec", {
  "prepareCmd": "echo ${nextRelease.version} > VERSION",
  "successCmd": "echo 'Released version ${nextRelease.version}'"
}]
```

**For nWave (updating multiple files)**:

```json
["@semantic-release/exec", {
  "prepareCmd": "./scripts/update-version.sh ${nextRelease.version}"
}]
```

Where `update-version.sh` might:
```bash
#!/bin/bash
VERSION=$1
# Update package.json (if not using @semantic-release/npm)
# Update pyproject.toml for Python components
# Update version constants in source code
sed -i "s/VERSION = .*/VERSION = \"$VERSION\"/" src/version.py
```

**Important**: Commit these changes via `@semantic-release/git`:

```json
["@semantic-release/git", {
  "assets": ["VERSION", "src/version.py", "CHANGELOG.md"],
  "message": "chore(release): ${nextRelease.version} [skip ci]\n\n${nextRelease.notes}"
}]
```

**Confidence**: High

---

## Recommended `.releaserc` Configuration for nWave

```json
{
  "branches": ["master"],
  "tagFormat": "v${version}",
  "plugins": [
    ["@semantic-release/commit-analyzer", {
      "preset": "conventionalcommits",
      "releaseRules": [
        {"type": "feat", "release": "minor"},
        {"type": "fix", "release": "patch"},
        {"type": "perf", "release": "patch"},
        {"type": "docs", "scope": "README", "release": "patch"},
        {"breaking": true, "release": "major"}
      ]
    }],
    ["@semantic-release/release-notes-generator", {
      "preset": "conventionalcommits",
      "presetConfig": {
        "types": [
          {"type": "feat", "section": "Features"},
          {"type": "fix", "section": "Bug Fixes"},
          {"type": "perf", "section": "Performance"},
          {"type": "refactor", "section": "Code Refactoring"},
          {"type": "docs", "section": "Documentation"},
          {"type": "chore", "hidden": true}
        ]
      }
    }],
    ["@semantic-release/changelog", {
      "changelogFile": "CHANGELOG.md",
      "changelogTitle": "# Changelog\n\nAll notable changes to nWave are documented here.\nThis project adheres to [Semantic Versioning](https://semver.org/)."
    }],
    ["@semantic-release/git", {
      "assets": ["CHANGELOG.md", "package.json"],
      "message": "chore(release): ${nextRelease.version} [skip ci]\n\n${nextRelease.notes}"
    }],
    ["@semantic-release/github", {
      "successComment": "This ${issue.pull_request ? 'PR is included' : 'issue has been resolved'} in version ${nextRelease.version}",
      "releasedLabels": ["released"]
    }]
  ]
}
```

---

## Recommended GitHub Actions Workflow

**File**: `.github/workflows/release.yml`

```yaml
name: Release

on:
  push:
    branches:
      - master
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Dry run (preview without releasing)'
        required: false
        default: false
        type: boolean

permissions:
  contents: read

jobs:
  release:
    name: Release
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
      pull-requests: write

    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 'lts/*'
          cache: 'npm'

      - name: Install dependencies
        run: npm clean-install

      - name: Verify dependency integrity
        run: npm audit signatures

      - name: Semantic Release
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          if [ "${{ inputs.dry_run }}" = "true" ]; then
            echo "Running in dry-run mode..."
            npx semantic-release --dry-run
          else
            npx semantic-release
          fi
```

---

## Gotchas and Antipatterns to Avoid

### 1. Tag Format Mismatch
**Problem**: Existing tags like `3.1.2` won't be recognized if semantic-release expects `v3.1.2`.
**Solution**: Set `tagFormat` in config to match existing convention.

### 2. Plugin Order Errors
**Problem**: Changelog not included in release because `@semantic-release/git` runs before `@semantic-release/changelog`.
**Solution**: Always order: commit-analyzer, release-notes-generator, changelog, exec, npm, git, github.

### 3. Branch Protection + GITHUB_TOKEN
**Problem**: Release workflow fails silently - cannot push tags/commits.
**Solution**: Either disable branch protection OR use GitHub App token OR accept GitHub Releases-only (no changelog commits).

### 4. Missing `fetch-depth: 0`
**Problem**: Shallow clone prevents semantic-release from analyzing commit history.
**Solution**: Always set `fetch-depth: 0` in checkout action.

### 5. Releases Not Triggering Other Workflows
**Problem**: `GITHUB_TOKEN` releases don't trigger `on: release` workflows.
**Solution**: Use a PAT or GitHub App token if downstream workflows are needed.

### 6. Pre-commit Hooks Blocking Release Commits
**Problem**: Husky/commitlint blocks the automated release commit.
**Solution**: Add `[skip ci]` to release commit message, or configure hooks to skip on CI.

### 7. Removing Tags to "Fix" Bad Releases
**Problem**: Deleting a tag causes semantic-release to re-release the same version.
**Solution**: Never delete tags. Publish a patch release instead.

### 8. Starting at v0.0.1
**Problem**: Semantic-release doesn't support `0.0.x` versions well.
**Solution**: Start at `1.0.0` or use pre-release branches (`beta`, `alpha`).

---

## Installation Commands

```bash
# Core semantic-release
npm install --save-dev semantic-release

# Recommended plugins for nWave
npm install --save-dev \
  @semantic-release/changelog \
  @semantic-release/git \
  @semantic-release/github \
  conventional-changelog-conventionalcommits
```

---

## Full Citations

[1] semantic-release. "GitHub Actions Recipe". semantic-release Documentation. 2025. https://semantic-release.gitbook.io/semantic-release/recipes/ci-configurations/github-actions. Accessed 2026-01-23.

[2] semantic-release. "@semantic-release/changelog". GitHub. 2025. https://github.com/semantic-release/changelog. Accessed 2026-01-23.

[3] semantic-release. "@semantic-release/github". GitHub. 2025. https://github.com/semantic-release/github. Accessed 2026-01-23.

[4] semantic-release. "@semantic-release/exec". GitHub. 2025. https://github.com/semantic-release/exec. Accessed 2026-01-23.

[5] semantic-release. "Frequently Asked Questions". semantic-release Documentation. 2025. https://semantic-release.gitbook.io/semantic-release/support/faq. Accessed 2026-01-23.

[6] GitHub. "Manual triggers with workflow_dispatch". GitHub Changelog. 2020. https://github.blog/changelog/2020-07-06-github-actions-manual-triggers-with-workflow_dispatch/. Accessed 2026-01-23.

[7] Shine Solutions. "Learning to Use Semantic-Release the Hard Way". 2021. https://shinesolutions.com/2021/07/21/learning-to-use-semantic-release-the-hard-way/. Accessed 2026-01-23.

[8] cycjimmy. "semantic-release-action". GitHub Marketplace. 2025. https://github.com/cycjimmy/semantic-release-action. Accessed 2026-01-23.

[9] semantic-release. "Configuration". semantic-release Documentation. 2025. https://semantic-release.gitbook.io/semantic-release/usage/configuration. Accessed 2026-01-23.

[10] Gonzalo Hirsch. "Semantic Release and Branch Protection Rules". 2024. https://gonzalohirsch.com/blog/semantic-release-and-branch-protection-rules/. Accessed 2026-01-23.

[11] MerginIT. "semantic-release Guide 2025". https://merginit.com/blog/29062025-automated-multi-platform-releases. Accessed 2026-01-23.

[12] Keep a Changelog. https://keepachangelog.com/en/1.0.0/. Accessed 2026-01-23.

---

## Research Metadata

- **Research Duration**: ~15 minutes
- **Total Sources Examined**: 15+
- **Sources Cited**: 12
- **Cross-References Performed**: 8
- **Confidence Distribution**: High: 100%
- **Output File**: data/research/cicd/semantic-release-best-practices.md
