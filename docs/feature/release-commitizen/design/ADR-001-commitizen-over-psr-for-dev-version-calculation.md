# ADR-001: Full Replacement of PSR with Commitizen for All Version Management

## Status

Accepted (updated 2026-02-26: expanded from "dev only" to full PSR replacement per Mike's decision)

## Context

`next_version.py` hardcodes `_bump_patch()` for dev releases, ignoring conventional commit semantics. 4 `feat:` commits produce `v1.1.23.dev2` (patch) instead of `v1.2.0.dev1` (minor). The version bump level must be derived from commit analysis.

Two tools are available as dev dependencies:
- **python-semantic-release (PSR)** v9.x (`python-semantic-release>=9.0.0`)
- **Commitizen (CZ)** v3.x (`commitizen>=3.12.0`)

Both parse conventional commits. The original question was which one drives dev release version calculation. Mike's subsequent decision expanded the scope: **CZ fully replaces PSR across all stages**, because PSR does not support PEP 440 (the versioning standard this project uses). Maintaining two tools creates confusion ("which one is the source of truth?"), duplicates configuration across `.releaserc` (Node.js) and `[tool.semantic_release]` (Python), and adds unused transitive dependencies.

## Decision

Use **Commitizen** as the sole version management tool across all release stages:

1. **Dev releases**: `cz bump --get-next` provides base version to `next_version.py` via `--base-version` (unchanged from original design)
2. **Stable releases**: `release.yml` version-bump job uses `cz bump` instead of `semantic-release version`
3. **Config consolidation**: `[tool.commitizen]` expanded with `version_files` and `changelog_file` to handle file updates PSR previously performed
4. **PSR removal**: `.releaserc` deleted, `[tool.semantic_release]` removed from pyproject.toml, `python-semantic-release` removed from dev dependencies
5. **Sync-public job**: Strip regex updated from `[tool.semantic_release]` to `[tool.commitizen]`

The 3-stage release train (release-dev.yml, release-rc.yml, release-prod.yml) is **unaffected**; it already uses custom Python scripts for all version calculations. Only the legacy `release.yml` workflow migrates from PSR to CZ.

## Alternatives Considered

### Alternative 1: PSR for stable, CZ for dev (coexistence)

**Evaluation**: The original ADR-001 design. CZ drives dev release analysis; PSR remains for stable releases via `release.yml`. Two tools coexist.

**Rejection reason**: PSR does not support PEP 440 (Gap 3 from research). Two version tool configs create contributor confusion. Two tools to upgrade and maintain. Mike decided the coexistence cost outweighs the migration effort.

### Alternative 2: PSR `semantic-release version --print`

**Evaluation**: PSR produces SemVer format (`1.2.0-dev.1`), not PEP 440 (`1.2.0.dev1`). Issue #455 (opened June 2022) tracks PEP 440 support with no timeline. The `--print` flag outputs the base version correctly (`1.2.0`), but PSR ignores PEP 440 dev/rc tags when scanning, which means it only sees stable tags.

**Rejection reason**: No native PEP 440 scheme. CZ has `version_scheme = "pep440"` built-in. Since CZ can handle all stages, there is no reason to keep PSR for any stage.

### Alternative 3: Custom commit parser in next_version.py

**Evaluation**: Build conventional commit parsing directly into `next_version.py` using `subprocess` + regex on `git log`. No external tool dependency.

**Rejection reason**: Reinvents commit parsing that CZ already does well. Conventional commit spec has edge cases (body `BREAKING CHANGE:`, multi-line footers, `feat!:` shorthand) that a custom parser would need to handle. Maintenance burden without benefit. CZ is already installed and MIT-licensed.

## Consequences

### Positive
- Single version tool across all stages; one mental model for contributors
- CZ `--get-next` outputs just the base version string (clean integration for dev)
- `cz bump --changelog` handles stable release version bumps, file updates, and changelog generation
- `version_scheme = "pep440"` ensures CZ internal logic aligns with PEP 440
- `|| BASE=""` fallback pattern makes CZ optional (dev pipeline never breaks)
- `.releaserc` (Node.js config) deleted; no more cross-language config duplication
- `python-semantic-release` removed from dev dependencies; smaller lock file
- Zero new dependencies (CZ already installed)

### Negative
- `release.yml` version-bump job must be rewritten from PSR commands to CZ commands (one-time migration effort)
- CZ `--get-next` behavior with `--devrelease` flag is not fully documented (research Gap 3). We avoid this by using `--get-next` for base version only, not full dev version string.
- Teams familiar with PSR's GitHub release integration (`@semantic-release/github`) must use the existing custom changelog generator in `release.yml` instead

### Risks
- CZ `--get-next` may change behavior in future versions. Mitigated by: pinned minimum version, `|| BASE=""` fallback, and the fact that we only consume the base version string.
- Developers may accidentally run `cz bump` (without `--get-next`) and modify pyproject.toml. Mitigated by: CZ is a dev dependency only, and `cz bump` requires explicit invocation.
- `release.yml` migration must be tested thoroughly; the legacy workflow is the only path for direct stable releases outside the 3-stage train. Mitigated by: dry-run mode (`cz bump --dry-run`) and the existing version-consistency check in the build job.
