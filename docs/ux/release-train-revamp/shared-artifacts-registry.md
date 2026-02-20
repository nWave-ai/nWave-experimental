# Shared Artifacts Registry: Release Train Revamp

**Epic**: release-train-revamp
**Last updated**: 2026-02-20

---

## Cross-Stage Artifacts

These artifacts are produced in one stage and consumed in another. Each must have a single source of truth.

| Artifact | Type | Source Stage | Source Step | Consumers | Format |
|----------|------|-------------|------------|-----------|--------|
| `source_commit_sha` | string | Stage 1 (Dev) | trigger (HEAD at dispatch) | All stages, cross-repo commits | Git SHA (40 chars) |
| `dev_version` | string | Stage 1 (Dev) | version-calc | Stage 1 tag, Stage 2 input | PEP 440: `X.Y.Z.devN` |
| `dev_tag` | string | Stage 1 (Dev) | tag-release | Stage 2 input, traceability | `vX.Y.Z.devN` |
| `rc_version` | string | Stage 2 (RC) | version-calc | Stage 2 tag/publish, Stage 3 input | PEP 440: `X.Y.ZrcN` |
| `rc_tag` | string | Stage 2 (RC) | tag-release | Stage 3 input, traceability | `vX.Y.ZrcN` |
| `stable_version` | string | Stage 3 (Stable) | validate-source | Version bump, PyPI, public repo | PEP 440: `X.Y.Z` |
| `stable_tag` | string | Stage 3 (Stable) | version-bump | GitHub Release, traceability | `vX.Y.Z` |
| `nwave_ai_version` | string | Stage 3 (Stable) | sync-public-repo | Public PyPI, marker tag | PEP 440: `X.Y.Z` |
| `nwave_dev_marker` | string | Stage 3 (Stable) | marker-tag | Reverse traceability | `vX.Y.Z` |
| `ci_check_status` | string | Each stage | ci-status-gate | Gate for build step in all stages | `green \| failed \| pending \| none` |
| `dist_artifacts` | files | Each stage | build step | Tag upload, PyPI, TestPyPI | wheel + sdist |
| `checksums` | file | Each stage | build step | GitHub Release assets | SHA256SUMS.txt |
| `workflow_run_url` | string | Each stage | GitHub context | Cross-repo commit messages | URL |

## Within-Stage Artifacts

| Artifact | Stage | Source Step | Consumers | Format |
|----------|-------|------------|-----------|--------|
| `ci_check_status` | Stage 1, 2, 3 | ci-status-gate | Gate for build/tag in all stages | green/failed/pending/none |
| `github_pre_release_url` | Stage 1, 2 | tag-release | Slack notification | URL |
| `github_release_url` | Stage 3 | version-bump | Slack notification | URL |
| `pypi_package_url` | Stage 2, 3 | pypi-publish | Slack, beta testers | URL |
| `beta_repo_release_url` | Stage 2 | sync-beta-repo | Slack, beta testers | URL |
| `public_repo_release_url` | Stage 3 | sync-public-repo | Slack notification | URL |
| `validated_commit_sha` | Stage 2, 3 | validate-source | Build, cross-repo commits | Git SHA |
| `public_version_floor` | Stage 3 | pyproject.toml [tool.nwave] | nwave-ai version calc | PEP 440: `X.Y.Z` |
| `current_public_version` | Stage 3 | pre-sync read of public repo | nwave-ai version calc | PEP 440: `X.Y.Z` |

## Version Naming Convention

| Context | Format | Example | Notes |
|---------|--------|---------|-------|
| Dev git tag | `vX.Y.Z.devN` | `v1.1.22.dev1` | Dot before dev required by PEP 440 |
| RC git tag | `vX.Y.ZrcN` | `v1.1.22rc1` | No dot before rc (PEP 440 normalized) |
| Stable git tag | `vX.Y.Z` | `v1.1.22` | Standard semver with v prefix |
| PyPI dev version | `X.Y.Z.devN` | `1.1.22.dev1` | No v prefix on PyPI |
| PyPI RC version | `X.Y.ZrcN` | `1.1.22rc1` | No v prefix on PyPI |
| PyPI stable version | `X.Y.Z` | `1.1.22` | No v prefix on PyPI |
| Public marker tag | `vX.Y.Z` | `v1.1.22` | On nwave-dev, tracks public release |

## Traceability Chain

```
Forward (source -> public):
  nwave-dev commit abc123d
    -> dev tag v1.1.22.dev3
    -> rc tag v1.1.22rc1
    -> stable tag v1.1.22
    -> nWave public v1.1.22
    -> nWave-beta v1.1.22rc1

Reverse (public -> source):
  nWave public v1.1.22
    -> commit message: "Source: nwave-dev@abc123d"
    -> nwave-dev marker tag: v1.1.22
    -> nwave-dev commit abc123d
```

## Integration Checkpoints

| Checkpoint | Between | Validates | Failure Action |
|------------|---------|-----------|----------------|
| IC-1 | Dev version-calc -> ci-status-gate | PEP 440 validity | STOP, report format error |
| IC-2 | Dev ci-status-gate -> build-dist | CI passed on commit SHA | STOP, report CI status |
| IC-3 | Dev build-dist -> tag-release | Build succeeded; artifacts exist | STOP, no tag |
| IC-4 | Dev tag -> RC validate-source | Dev tag exists at valid commit | STOP, list available tags |
| IC-5 | RC validate-source -> ci-status-gate | Source dev tag resolves to valid commit | STOP, list available tags |
| IC-6 | RC ci-status-gate -> build | CI passed on source commit SHA | STOP, report CI status |
| IC-7 | RC build -> pypi-publish | Wheel passes twine check | STOP, report build issue |
| IC-8 | RC pypi-publish -> sync-beta | Package on PyPI | STOP, report publish failure |
| IC-9 | RC tag -> Stable validate-source | RC tag exists | STOP, list available RCs |
| IC-10 | Stable validate-source -> ci-status-gate | RC tag resolves to valid commit | STOP, list available RCs |
| IC-11 | Stable ci-status-gate -> build | CI passed on source commit SHA | STOP, report CI status |
| IC-12 | Stable build -> pypi-publish | Build succeeded; wheel passes twine check | STOP, report build issue |
| IC-13 | Stable pypi-publish -> sync-public | Stable on PyPI | STOP, report publish failure |
| IC-14 | Stable sync-public -> marker-tag | Public version known | STOP, report sync failure |

## Secrets and Tokens

| Secret | Purpose | Current | Target | Used By |
|--------|---------|---------|--------|---------|
| `GH_TOKEN` | nwave-dev push + tag | PAT | PAT (fine-grained) | Stage 1, 3 version bump |
| `RELEASETRAIN` | Cross-repo push | Classic PAT | Fine-grained PAT (future: GitHub App) | Stage 2 beta sync, Stage 3 public sync |
| `PYPI_TOKEN` | PyPI upload | API token | Trusted Publisher (OIDC) | Stage 2, 3 PyPI publish |
| `SLACK_WEBHOOK_URL` | Notifications | Webhook URL | Webhook URL (no change) | All stages |
