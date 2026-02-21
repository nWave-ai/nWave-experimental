# Release Train: How-To Guide

How to ship a release using the three-stage promotion pipeline.

## Overview

```
Stage 1: Dev          Stage 2: RC (Beta)       Stage 3: Stable (Prod)
─────────────────     ─────────────────────     ──────────────────────
master HEAD           v1.1.22.dev7              v1.1.22rc5
    │                     │                         │
    ▼                     ▼                         ▼
CI gate               CI gate                   CI gate
version calc          version calc              version calc
build wheel           build wheel               build wheel
tag + pre-release     tag + pre-release         version bump on master
Slack                 PyPI publish (pre)        tag + GitHub Release
                      sync nWave-beta           PyPI publish (stable)
                      Slack                     sync nWave public repo
                                                marker tag
                                                Slack
```

Each stage promotes the output of the previous one. Nothing reaches production without passing through all three gates.

## Prerequisites

- Push access to `nwave-dev` (master branch)
- GitHub CLI (`gh`) authenticated
- CI Pipeline must be green on HEAD before any stage will proceed

## Stage 1: Dev Release

Creates a dev snapshot from the current master HEAD.

**Trigger:**

```bash
gh workflow run "Release: Dev (Stage 1)" --ref master
```

**What it does:**
1. Checks CI is green on HEAD
2. Calculates next dev version (e.g. `v1.1.22.dev7`)
3. Builds wheel + sdist
4. Creates GitHub pre-release with tag

**Output:** A dev tag like `v1.1.22.dev7`

## Stage 2: RC / Beta Release

Promotes a dev release to release candidate status.

**Trigger:**

```bash
# Find the latest dev tag
git fetch --tags && git tag --sort=-creatordate | head -3

# Promote it
gh workflow run "Release: RC (Stage 2)" --ref master \
  -f source_dev_tag=v1.1.22.dev7
```

**What it does:**
1. Validates the source dev tag exists
2. Checks CI is green on that commit
3. Calculates next RC version (e.g. `v1.1.22rc5`)
4. Builds wheel + sdist
5. Creates GitHub pre-release with tag
6. Publishes to PyPI as pre-release (`pipx install nwave-ai==1.1.22rc5 --pip-args="--pre"`)
7. Syncs to nWave-beta repository

**Output:** An RC tag like `v1.1.22rc5`, published to PyPI and nWave-beta

## Stage 3: Stable / Production Release

Promotes a validated RC to stable production status.

**Trigger (dry run first):**

```bash
# Always dry run first
gh workflow run "Release: Stable (Stage 3)" --ref master \
  -f source_rc_tag=v1.1.22rc5 -f dry_run=true

# Watch it
gh run list --workflow="Release: Stable (Stage 3)" --limit 1
gh run watch <run-id> --exit-status

# If clean, fire the real release
gh workflow run "Release: Stable (Stage 3)" --ref master \
  -f source_rc_tag=v1.1.22rc5
```

**What it does:**
1. Validates the source RC tag exists
2. Traces promotion chain back to the source dev tag
3. Checks CI is green on that commit
4. Calculates stable version (e.g. `v1.1.22`)
5. Builds wheel + sdist
6. Bumps version in `pyproject.toml` and `framework-catalog.yaml` on master
7. Creates GitHub Release (not pre-release) with full changelog
8. Publishes to PyPI as stable (`pipx install nwave-ai`)
9. Syncs to nWave public repository with matching tag + release
10. Creates marker tag on nwave-dev

**Output:** Stable tag `v1.1.22` on both repos, published to PyPI, Slack notified

## Typical Flow

```bash
# 1. Push your changes to master, wait for CI green

# 2. Dev release
gh workflow run "Release: Dev (Stage 1)" --ref master
# wait ~1 min

# 3. Beta release
git fetch --tags
gh workflow run "Release: RC (Stage 2)" --ref master \
  -f source_dev_tag=v1.1.22.dev7
# wait ~2 min, verify with: pipx install nwave-ai==1.1.22rc5 --pip-args="--pre"

# 4. Prod release (dry run)
gh workflow run "Release: Stable (Stage 3)" --ref master \
  -f source_rc_tag=v1.1.22rc5 -f dry_run=true
# verify all jobs pass

# 5. Prod release (for real)
gh workflow run "Release: Stable (Stage 3)" --ref master \
  -f source_rc_tag=v1.1.22rc5
# wait ~2 min, verify with: pipx upgrade nwave-ai
```

## Dry Run Mode

All three stages support `dry_run=true`. In dry run mode:
- All validation and build steps execute normally
- No tags, releases, or publishes are created
- A summary job reports what would have happened

Always dry run Stage 3 before the real release.

## Traceability

Every release carries a full promotion chain:

```
PyPI: nwave-ai==1.1.22
  └── GitHub Release: v1.1.22 (nwave-dev + nWave)
       └── Promoted from: v1.1.22rc5
            └── Promoted from: v1.1.22.dev7
                 └── Commit: 41c56c47 on master
```

## Troubleshooting

**"CI Pipeline status not found"**
The CI Pipeline workflow must have run on the exact commit being promoted. Push to master and wait for CI to complete before triggering a dev release.

**"pipx installs old version"**
pipx caches aggressively. Use `pipx upgrade nwave-ai` instead of `pipx install`.

**"Release Pipeline" (old workflow)**
The legacy single-stage workflow (`release.yml`) is disabled. Do not re-enable it. Use the three-stage train instead.
