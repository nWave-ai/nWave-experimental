# US-CZ-05: Consolidate Versioning by Replacing PSR with Commitizen

## Problem (The Pain)
Mike Brissoni is a release engineer who maintains two version management tools in the same repo: python-semantic-release (PSR) and Commitizen (CZ). PSR does not support PEP 440 natively (it outputs SemVer `1.2.3-rc.1` instead of PEP 440 `1.2.3rc1`), which is why custom scripts already handle all version calculations. PSR remains only for its side effects: updating `nWave/VERSION` and `nWave/framework-catalog.yaml`, committing changes, and creating GitHub releases. Meanwhile, CZ already handles commit analysis (US-CZ-01) and natively supports PEP 440 via `version_scheme = "pep440"`. Having two tools creates confusion ("which one is the source of truth?"), duplicates configuration across `.releaserc` (Node.js) and `[tool.semantic_release]` (Python), and adds a `python-semantic-release` dev dependency that inflates the lock file with unused transitive packages.

## Who (The User)
- Release engineer (Mike) who must reason about which tool does what during stable releases
- Contributors who see two version tool configs in pyproject.toml and wonder which to modify
- CI/CD pipelines that install `python-semantic-release` despite not needing it for version calculation
- The nwave-dev repo maintenance burden: two configs to keep in sync, two tools to upgrade

## Solution (What We Build)
Expand CZ's `[tool.commitizen]` config with `version_files` and `changelog_file` to handle the file-update and changelog side effects PSR currently provides. Remove PSR's three footprints: `.releaserc` (Node.js config), `[tool.semantic_release]` section in pyproject.toml, and `python-semantic-release` from dev dependencies. Update the legacy `release.yml` workflow to use CZ instead of PSR for the version-bump job. Update CI comments and documentation that reference PSR.

## Domain Examples

### Example 1: Stable release with CZ handling file updates (happy path)
Mike promotes v1.2.0rc2 to stable via `release-prod.yml`. The pipeline calculates stable version "1.2.0" using `next_version.py` (unchanged). The `version-bump` job runs `bump_version.py` to update `pyproject.toml` and `nWave/framework-catalog.yaml` (unchanged). CZ's `version_files` config ensures `nWave/VERSION` is also updated when `cz bump` runs during dev releases. The `.releaserc` file no longer exists. The `[tool.semantic_release]` section is gone from pyproject.toml. Mike sees one version tool, one config section, one mental model.

### Example 2: Legacy release.yml uses CZ instead of PSR
Mike triggers the legacy `release.yml` workflow (used for direct stable releases without the 3-stage train). The `version-bump` job previously ran `pip install python-semantic-release` and `semantic-release version`. Now it runs `cz bump --changelog` instead. CZ reads `[tool.commitizen]` config, analyzes commits, bumps `pyproject.toml` version, updates `nWave/VERSION` and `nWave/framework-catalog.yaml` via `version_files`, generates `CHANGELOG.md`, and commits. Same observable outcome, one tool instead of two.

### Example 3: Contributor adds a new version-tracked file
Ale needs to add a version stamp to a new `nWave/manifest.json` file. With PSR, he would have to update both `.releaserc` (the `@semantic-release/exec` prepareCmd) AND `[tool.semantic_release].version_variables`. With CZ, he adds one line to `version_files` in `[tool.commitizen]`: `"nWave/manifest.json:version"`. Single place, single mental model.

### Example 4: Dev dependency cleanup after PSR removal
After removing `python-semantic-release>=9.0.0` from pyproject.toml dev dependencies and regenerating the lock file, the `requirements.lock` shrinks. The `python-semantic-release==10.5.3` line and its transitive dependencies disappear. `commitizen>=3.12.0` remains as the single version management tool.

### Example 5: CI version-drift check updated
The CI pipeline (`ci.yml`) currently prints "python-semantic-release keeps framework-catalog.yaml in sync automatically" when version drift is detected. After migration, this message changes to reference CZ: "commitizen version_files keeps framework-catalog.yaml in sync automatically." The check logic itself is unchanged (compare pyproject.toml version to framework-catalog.yaml version).

## UAT Scenarios (BDD)

### Scenario 1: CZ config includes version_files for all version-tracked files
Given the `[tool.commitizen]` section exists in pyproject.toml (from US-CZ-01)
When Mike reviews the CZ config
Then the `version_files` list includes "nWave/VERSION" and "nWave/framework-catalog.yaml:version"
And the `changelog_file` is set to "CHANGELOG.md"
And CZ handles all file updates that PSR previously handled

### Scenario 2: .releaserc file is removed
Given the `.releaserc` file currently exists at the repo root
When the PSR migration is complete
Then `.releaserc` no longer exists in the repo
And the rsync exclude lists in `release-rc.yml`, `release-prod.yml`, and `release.yml` no longer reference `.releaserc`

### Scenario 3: [tool.semantic_release] section removed from pyproject.toml
Given pyproject.toml currently contains a `[tool.semantic_release]` section (lines 272-292)
And pyproject.toml contains `[tool.semantic_release.branches.main]` and `[tool.semantic_release.changelog]` sub-sections
When the PSR migration is complete
Then none of these sections exist in pyproject.toml
And the `[tool.commitizen]` section is the sole version tool config

### Scenario 4: python-semantic-release removed from dev dependencies
Given pyproject.toml lists `"python-semantic-release>=9.0.0"` in `[project.optional-dependencies].dev`
And requirements.lock contains `python-semantic-release==10.5.3`
When the PSR migration is complete
Then `python-semantic-release` does not appear in pyproject.toml dependencies
And `python-semantic-release` does not appear in requirements.lock
And `commitizen>=3.12.0` remains as the version management dependency

### Scenario 5: Legacy release.yml workflow uses CZ instead of PSR
Given `release.yml` currently runs `pip install python-semantic-release` and `semantic-release version`
When the PSR migration is complete
Then the version-bump job uses `cz bump` instead of `semantic-release version`
And the `--changelog` flag is included to generate release notes
And the dry-run mode uses `cz bump --dry-run` instead of `semantic-release version --print`
And the force-bump mode uses `cz bump --increment {level}` instead of `semantic-release version --{level}`

### Scenario 6: CZ generates changelog on stable release
Given CZ config has `changelog_file = "CHANGELOG.md"`
And `.gitignore` already ignores `CHANGELOG.md`
When Mike runs a stable release via the legacy `release.yml`
Then CZ generates `CHANGELOG.md` from conventional commits
And the changelog groups commits by type (Features, Bug Fixes, etc.)
And the changelog is committed alongside version bumps

### Scenario 7: CI and documentation references updated
Given `ci.yml` references "python-semantic-release" in the version-drift check message
And `.github/workflows/README.md` references PSR in the version-bump description
When the PSR migration is complete
Then all workflow comments and messages reference "commitizen" instead of "python-semantic-release"
And the workflows README describes CZ as the version management tool

## Acceptance Criteria
- [ ] `[tool.commitizen]` section includes `version_files` with "nWave/VERSION" and "nWave/framework-catalog.yaml:version"
- [ ] `[tool.commitizen]` section includes `changelog_file = "CHANGELOG.md"`
- [ ] `.releaserc` file is deleted from the repository root
- [ ] `[tool.semantic_release]` and all its sub-sections removed from pyproject.toml
- [ ] `python-semantic-release>=9.0.0` removed from pyproject.toml dev dependencies
- [ ] `python-semantic-release` removed from requirements.lock (regenerated)
- [ ] `release.yml` version-bump job uses `cz bump` commands instead of `semantic-release version`
- [ ] rsync exclude lists in release workflows no longer reference `.releaserc`
- [ ] CI version-drift check message references commitizen instead of PSR
- [ ] Existing release-prod.yml and release-rc.yml pipelines are unaffected (they use next_version.py, not PSR)
- [ ] The pyproject.toml strip logic in release.yml (sync-public job) removes `[tool.commitizen]` instead of `[tool.semantic_release]`

## Technical Notes
- **release-prod.yml is unaffected**: The 3-stage release train (release-dev.yml, release-rc.yml, release-prod.yml) already uses custom Python scripts (`next_version.py`, `bump_version.py`, `discover_tag.py`) for all version calculations. PSR is NOT used in these workflows. This story only affects the legacy `release.yml` and repo-wide config cleanup.
- **CZ version_files config**: CZ's `version_files` handles regex-based file updates during `cz bump`. For `nWave/VERSION` (plain text file), CZ writes the version directly. For `nWave/framework-catalog.yaml:version`, CZ updates the YAML `version:` field.
- **Changelog**: `.gitignore` already ignores `CHANGELOG.md`. CZ can generate it with `cz bump --changelog` or `cz changelog` standalone. The changelog format follows conventional commits grouping (Features, Bug Fixes, etc.).
- **release.yml sync-public job**: Lines 758-762 currently strip `[tool.semantic_release]` from pyproject.toml before syncing to the public repo. After migration, this regex should strip `[tool.commitizen]` instead (CZ config is dev-only, not needed in the public package).
- **Backward compatibility**: The `release-prod.yml` version-bump job uses `bump_version.py` (a custom script), not PSR. CZ's `version_files` is an additional mechanism for dev-stage file updates via `cz bump`. Both can coexist during transition.
- **rsync excludes**: `.releaserc` appears in rsync exclude lists in 3 workflows (release.yml, release-rc.yml, release-prod.yml). After deleting the file, these exclude entries become harmless no-ops but should be cleaned up for clarity.
- **Dependency**: US-CZ-01 must be implemented first (CZ config must exist before expanding it with `version_files`).

## Traceability
- **Journey**: `docs/ux/release-commitizen/journey-dev-release.feature` section "US-CZ-05"
- **Visual**: `docs/ux/release-commitizen/journey-dev-release-visual.md` (Coexistence with PSR section to be replaced)
- **Registry**: `docs/ux/release-commitizen/shared-artifacts-registry.md` (Coexistence section to be updated)
- **Research**: `docs/research/cicd/psr-version-calculation-for-release-trains.md` (Gap 3: PSR does not support PEP 440)
- **ADR**: `docs/features/release-train-revamp/02-design/architecture.md` (ADR-RTR-004: Custom Version Scripts over PSR)
