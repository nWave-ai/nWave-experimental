# Shared Artifacts Registry: Release Commitizen

**Epic**: release-commitizen
**Last updated**: 2026-02-26

---

## New Artifacts (introduced by this feature)

| Artifact | Type | Source Step | Consumers | Format |
|----------|------|------------|-----------|--------|
| `cz_base_version` | string | CZ analysis (`cz bump --get-next`) | next_version.py `--base-version` arg | PEP 440 base version or empty string |
| `version_floor` | string | pyproject.toml `[tool.nwave].public_version` | next_version.py `--version-floor` arg | PEP 440 base version or empty string |
| `tool_commitizen_config` | TOML section | pyproject.toml `[tool.commitizen]` | `cz bump --get-next`, `cz bump --changelog` | Expanded TOML config (US-CZ-05 adds version_files + changelog_file) |
| `cz_version_files` | string list | `[tool.commitizen].version_files` | `cz bump` (file updates during version bump) | `["nWave/VERSION", "nWave/framework-catalog.yaml:version"]` |
| `cz_changelog_file` | string | `[tool.commitizen].changelog_file` | `cz bump --changelog`, `cz changelog` | `"CHANGELOG.md"` |

## Existing Artifacts (consumed but not changed)

| Artifact | Type | Source | Consumers | Format |
|----------|------|--------|-----------|--------|
| `pyproject_toml_version` | string | `[project].version` | CZ analysis (anchor), next_version.py fallback | PEP 440: `X.Y.Z` |
| `existing_dev_tags` | string list | `git tag -l "v*.dev*"` | next_version.py sequential counter, discover_tag.py (RC promotion) | CSV of `vX.Y.Z.devN` tags |
| `dev_version` | string | next_version.py output | tag-release, notify, Stage 2 RC promotion | PEP 440: `X.Y.Z.devN` |
| `dev_tag` | string | next_version.py output | GitHub tag, Stage 2 RC promotion input | `vX.Y.Z.devN` |

## Stage 2 Artifacts (RC Promotion)

| Artifact | Type | Source | Consumers | Format |
|----------|------|--------|-----------|--------|
| `resolved_dev_tag` | string | discover_tag.py `--pattern dev` | calculate_rc `--current-version` | `vX.Y.Z.devN` (highest by packaging.Version) |
| `existing_rc_tags` | string list | `git tag -l "v*rc*"` | next_version.py `--existing-tags` (RC counter) | CSV of `vX.Y.ZrcN` tags |
| `rc_version` | string | calculate_rc output | tag-release (RC), notify, Stage 3 stable promotion | PEP 440: `X.Y.ZrcN` |
| `rc_tag` | string | calculate_rc output | GitHub pre-release tag, nWave-beta sync, Stage 3 stable input | `vX.Y.ZrcN` |
| `rc_base_version` | string | calculate_rc output (JSON `base_version`) | Traceability; confirms base stripped from dev tag | PEP 440: `X.Y.Z` |

## Stage 3 Artifacts (Stable Promotion)

| Artifact | Type | Source | Consumers | Format |
|----------|------|--------|-----------|--------|
| `resolved_rc_tag` | string | discover_tag.py `--pattern rc` | calculate_stable `--current-version` | `vX.Y.ZrcN` (highest by packaging.Version) |
| `stable_version` | string | calculate_stable output | pyproject.toml bump, tag-release, PyPI publish, public repo sync | PEP 440: `X.Y.Z` |
| `stable_tag` | string | calculate_stable output | GitHub Release tag, marker tag on nwave-dev, Slack | `vX.Y.Z` |
| `traced_dev_tag` | string | git tag -l "v*.dev*" --points-at (commit SHA) | Traceability commit message on public repo | `vX.Y.Z.devN` or "unknown" |

## New CLI Arguments

| Argument | Script | Default | Source | Validation |
|----------|--------|---------|--------|------------|
| `--base-version` | next_version.py | `""` (empty) | CZ analysis output | Must be valid PEP 440 or empty |
| `--version-floor` | next_version.py | `""` (empty) | `[tool.nwave].public_version` | Must be valid PEP 440 or empty |

## Configuration Added

### `[tool.commitizen]` in pyproject.toml

```toml
[tool.commitizen]
name = "cz_conventional_commits"
version_provider = "pep621"
version_scheme = "pep440"
tag_format = "v$version"
```

| Field | Value | Why |
|-------|-------|-----|
| `name` | `cz_conventional_commits` | Standard conventional commit parser |
| `version_provider` | `pep621` | Reads version from `[project].version` (last stable) |
| `version_scheme` | `pep440` | Produces `1.2.0` not `1.2.0-rc.1` |
| `tag_format` | `v$version` | Matches existing tag convention `v{version}` |

## Version Resolution Priority Chain

```
Input: --base-version (from CZ), --version-floor (from pyproject.toml)

1. If --base-version is non-empty:
     base = --base-version
   Else:
     base = _bump_patch(current_version)    # fallback

2. If --version-floor is non-empty AND Version(floor) > Version(base):
     base = floor                           # floor override

3. dev_version = f"{base}.dev{next_counter}"
```

## Mid-Cycle Escalation: Artifact Behavior

When a higher bump type appears mid-cycle (e.g., `feat:` after `fix:`-only releases):

| Artifact | Before Escalation | After Escalation | Notes |
|----------|-------------------|------------------|-------|
| `pyproject_toml_version` | `1.1.25` | `1.1.25` (unchanged) | Stable anchor never moves during dev cycle |
| `cz_base_version` | `1.1.26` | `1.2.0` | CZ re-scans all commits, highest bump wins |
| `existing_dev_tags` | `v1.1.26.dev1..dev8` | `v1.1.26.dev1..dev8, v1.2.0.dev1` | Both bases coexist |
| `dev_version` | `1.1.26.dev8` | `1.2.0.dev1` | Counter resets (new base has no matching tags) |
| `dev_tag` | `v1.1.26.dev8` | `v1.2.0.dev1` | New tag series starts |

**Key mechanism**: `_highest_counter` (next_version.py lines 124-135) matches `v_base != base` to filter. When base changes from `1.1.26` to `1.2.0`, old tags are invisible.

**De-escalation is impossible**: CZ scans all commits since the stable anchor. A `feat:` commit stays in history even after `revert:`. Only a new stable release resets the scan window.

**RC promotion path**: After escalation, RC inherits from the highest base version's latest dev tag. Example: `v1.2.0.dev2` -> `v1.2.0rc1` -> `v1.2.0`.

## PSR-to-CZ Migration (US-CZ-05)

**Status**: PSR to be fully replaced by CZ.

| Artifact | Before (PSR) | After (CZ) | Notes |
|----------|-------------|------------|-------|
| `.releaserc` | Node.js semantic-release config | **Deleted** | CZ does not need a separate config file |
| `[tool.semantic_release]` | pyproject.toml section (lines 272-292) | **Deleted** | Replaced by expanded `[tool.commitizen]` |
| `python-semantic-release` dep | `>=9.0.0` in dev dependencies | **Removed** | `commitizen>=3.12.0` is the sole version tool |
| `version_files` | PSR: `version_toml`, `version_variables` | CZ: `version_files` list | CZ handles nWave/VERSION and framework-catalog.yaml |
| Changelog | PSR: `@semantic-release/release-notes-generator` | CZ: `changelog_file = "CHANGELOG.md"` | CZ generates from conventional commits |
| `release.yml` version-bump | `semantic-release version` | `cz bump --changelog` | Legacy workflow updated |
| CI drift message | References PSR | References CZ | ci.yml version-drift check |

### CZ Config After Migration

```toml
[tool.commitizen]
name = "cz_conventional_commits"
version_provider = "pep621"
version_scheme = "pep440"
tag_format = "v$version"
version_files = [
    "nWave/VERSION",
    "nWave/framework-catalog.yaml:version"
]
changelog_file = "CHANGELOG.md"
```

### Files Affected by PSR Removal

| File | Change |
|------|--------|
| `.releaserc` | Delete |
| `pyproject.toml` | Remove `[tool.semantic_release]` and sub-sections; remove PSR from dev deps; expand `[tool.commitizen]` |
| `requirements.lock` | Regenerate (PSR and transitive deps removed) |
| `.github/workflows/release.yml` | Replace `semantic-release version` with `cz bump`; remove PSR install step |
| `.github/workflows/release.yml` | Update sync-public regex to strip `[tool.commitizen]` instead of `[tool.semantic_release]` |
| `.github/workflows/release-rc.yml` | Remove `.releaserc` from rsync exclude |
| `.github/workflows/release-prod.yml` | Remove `.releaserc` from rsync exclude |
| `.github/workflows/ci.yml` | Update version-drift message to reference CZ |
| `.github/workflows/README.md` | Update version-bump description to reference CZ |

### What Is NOT Affected

The 3-stage release train workflows (release-dev.yml, release-rc.yml, release-prod.yml) use custom Python scripts for version calculation. They do not invoke PSR and require no changes for this migration (beyond removing `.releaserc` from rsync excludes).

## Integration Checkpoints

| ID | Between | Validates | Failure Action |
|----|---------|-----------|----------------|
| IC-CZ-1 | CZ analysis -> version-calc | CZ output is valid PEP 440 base or empty | Use empty (triggers fallback) |
| IC-CZ-2 | Floor read -> version-calc | Floor is valid PEP 440 base or empty | Use empty (no override) |
| IC-CZ-3 | version-calc -> tag-release | Output is valid PEP 440 devN format | STOP, report error |
| IC-CZ-4 | discover_tag (dev) -> calculate_rc | Resolved dev tag is valid PEP 440 dev pre-release | STOP: "No dev tags found. Run Stage 1 first." |
| IC-CZ-5 | calculate_rc -> tag-release (RC) | Output is valid PEP 440 rcN format | STOP, report error |
| IC-CZ-6 | discover_tag (rc) -> calculate_stable | Resolved RC tag is valid PEP 440 rc pre-release | STOP: "No rc tags found. Run Stage 2 first." |
| IC-CZ-7 | calculate_stable -> tag-release (stable) | Output is valid PEP 440 base version (no suffix) | STOP, report error |

## Promotion Chain: Artifact Flow

```
Stage 1 (Dev)                    Stage 2 (RC)                     Stage 3 (Stable)
=============                    ============                     ================
cz_base_version -.               resolved_dev_tag -.              resolved_rc_tag -.
version_floor ---+-> dev_version   (from discover_tag)             (from discover_tag)
                 |-> dev_tag ------+-> calculate_rc -.             calculate_stable -.
                                   |   rc_version ---+-> rc_tag ---+-> stable_version
                                   |   rc_base       |             |-> stable_tag
                                   |                 |             |-> pyproject_toml_version (bumped)
                                   |                 |
                           existing_rc_tags ---------+      resolved_rc_tag has no floor applied
                           (for counter)                    (floor is dev-stage only)
```
