# ADR-003: Full Replacement of PSR with Commitizen

## Status

Accepted

## Context

ADR-001 originally designed CZ for dev releases only, keeping PSR for stable releases via `release.yml`. After implementation planning, Mike decided to expand scope: **PSR must be fully replaced by CZ** across all stages.

Key drivers for this decision:
- PSR does not support PEP 440 (the versioning standard this project uses). Research Gap 3 confirmed this with no upstream fix timeline.
- Two version tools create contributor confusion ("which config do I modify?")
- `.releaserc` is a Node.js config file in a Python project, adding cognitive overhead
- `python-semantic-release` adds transitive dependencies to the lock file that serve no purpose since custom scripts handle all version calculations
- The 3-stage release train (release-dev.yml, release-rc.yml, release-prod.yml) already uses custom Python scripts, not PSR. PSR is only used by the legacy `release.yml` workflow.

## Decision

Fully replace PSR with CZ. Specifically:

1. Expand `[tool.commitizen]` with `version_files` and `changelog_file` to handle file updates PSR performed via `.releaserc` plugins
2. Delete `.releaserc` (Node.js PSR plugin config)
3. Remove `[tool.semantic_release]` and all sub-sections from pyproject.toml
4. Remove `python-semantic-release>=9.0.0` from dev dependencies
5. Migrate `release.yml` version-bump job from `semantic-release version` to `cz bump`
6. Update sync-public strip regex from `[tool.semantic_release]` to `[tool.commitizen]`
7. Clean up rsync excludes (`.releaserc` references) and CI/docs references

## Alternatives Considered

### Alternative 1: Keep PSR for stable releases (coexistence)

**Evaluation**: The original ADR-001 approach. CZ for dev analysis, PSR for stable release via `release.yml`. Both configs coexist in pyproject.toml.

**Rejection reason**: Perpetuates dual-tool confusion. PSR's lack of PEP 440 support means it cannot be extended to the 3-stage train. The coexistence cost (two configs, two tools to upgrade, contributor confusion) is ongoing, while the migration cost is one-time.

### Alternative 2: Replace PSR in release.yml with custom scripts (no CZ)

**Evaluation**: Instead of using `cz bump` in `release.yml`, write a custom Python script that bumps version, updates files, and generates changelog. No dependency on either PSR or CZ for stable releases.

**Rejection reason**: Reinvents what CZ already does. `cz bump` handles version bumping, file updates via `version_files`, and changelog generation via `--changelog`. Writing a custom script adds maintenance burden without benefit.

## Consequences

### Positive
- Single version tool: one config section, one mental model, one tool to upgrade
- `.releaserc` deletion removes Node.js config from Python project
- Smaller lock file (PSR transitive dependencies removed)
- `version_files` provides declarative file-update config (vs `.releaserc`'s imperative `sed` commands)
- Contributors see `[tool.commitizen]` as the sole version config

### Negative
- One-time migration effort for `release.yml` version-bump job
- `cz bump` command syntax differs from `semantic-release version` (team must update muscle memory and scripts)
- CZ's GitHub release integration is less mature than PSR's `@semantic-release/github` plugin; existing custom changelog generator in `release.yml` remains the approach

### Risks
- `cz bump` behavior in edge cases (no bump-worthy commits, force-bump) may differ from PSR. Mitigated by: dry-run testing, and the version-consistency check in the build job catches any discrepancy.
- `release.yml` is the only path for direct stable releases outside the 3-stage train. A broken migration blocks stable releases. Mitigated by: `cz bump --dry-run` for validation, rollback plan (revert commit + reinstall PSR).

## Traceability

- **User Story**: US-CZ-05 (PSR-to-CZ Migration)
- **Decision maker**: Mike (2026-02-26)
- **Supersedes**: ADR-001 coexistence clause ("Keep PSR for stable releases only")
