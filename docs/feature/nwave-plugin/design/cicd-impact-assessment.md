# CI/CD Impact Assessment: nWave Plugin Marketplace

**Date**: 2026-02-27
**Author**: Apex (Platform Architect)
**Status**: Assessment complete
**Scope**: CI pipeline (ci.yml), Release pipeline (release.yml), plugin repository, version sync, test integration

---

## Executive Summary

The nWave Plugin Marketplace feature requires **targeted extensions** to both CI and Release pipelines. The existing infrastructure is well-structured with clear stage boundaries, making integration low-risk. The primary changes are:

1. **CI**: Add plugin build verification as a new step within the existing test stage (Stage 3)
2. **Release**: Add a new `build-plugin` job between `build` and `github-release`, plus a new `publish-to-plugin-repo` job after `github-release`
3. **Version sync**: Enforced by existing `pyproject.toml` single-source-of-truth pattern -- minimal new work
4. **Test integration**: Plugin acceptance tests run within the existing pytest matrix -- no special CI configuration needed

Estimated CI/CD effort: **3-5 hours** of workflow modifications, after `build_plugin.py` is implemented.

---

## 1. CI Pipeline Changes (ci.yml)

### Current State

```
Stage 1: Fast Checks (parallel) ---- commitlint, code-quality, file-quality, security
Stage 2: Framework Validation ------- catalog schema, version consistency, docs freshness
Stage 3: Cross-Platform Tests ------- Ubuntu x Python 3.11/3.12 matrix (pytest)
Stage 4: Agent Validation ----------- agent-sync
```

### Recommended Changes

**No new stages needed.** The plugin build tests integrate into the existing test matrix at Stage 3.

#### Change 1: Plugin acceptance tests run automatically via pytest

The tests at `tests/build/acceptance/plugin/` are pytest-bdd scenarios with standard conftest.py fixtures. They use `tmp_path` for output isolation and reference the real nWave source tree. The existing CI test command already runs `pipenv run pytest tests/` which discovers all tests including plugin acceptance tests.

**Action required**: None for test discovery. The tests are auto-discovered by pytest. The `@skip` markers on milestone-4 and milestone-5 scenarios will prevent them from running until implementation is complete.

**Risk**: LOW. Tests use temp directories and do not modify the source tree.

#### Change 2: Plugin build smoke test in Framework Validation (optional)

Add a plugin build verification step to Stage 2 (framework-validation) that verifies `build_plugin.py` runs without error. This catches build script regressions early.

```yaml
# Addition to framework-validation job (Stage 2)
- name: Verify plugin build script
  run: |
    pipenv run python3 scripts/build_plugin.py --output-dir /tmp/plugin-verify
    # Validate output structure
    test -f /tmp/plugin-verify/.claude-plugin/plugin.json
    test -d /tmp/plugin-verify/agents
    test -d /tmp/plugin-verify/commands
    test -d /tmp/plugin-verify/skills
    test -d /tmp/plugin-verify/hooks
    echo "::notice::Plugin build verification passed"
```

**Risk**: LOW. Runs in temp directory, fails fast (<10s), no side effects.
**Recommendation**: Add this in Phase 02-01 (release pipeline extension), not during Phase 01 (build pipeline implementation).

#### Change 3: JSON syntax validation covers plugin output (already handled)

The existing `file-quality` job validates all JSON files in the repository. Generated plugin files (plugin.json, hooks.json) in the `plugin/` directory would be validated if committed. Since plugin output is a build artifact (not committed to nwave-dev), this is only relevant for the `nwave-plugin` repo.

**Action required**: None for ci.yml.

### CI Changes Summary

| Change | Stage | Effort | Risk | When |
|--------|-------|--------|------|------|
| Plugin acceptance tests auto-discovery | Stage 3 (test) | None | LOW | Automatic |
| Plugin build smoke test | Stage 2 (framework-validation) | 30 min | LOW | Phase 02-01 |
| JSON validation | Stage 1 (file-quality) | None | N/A | Already covered |

---

## 2. Release Pipeline Changes (release.yml)

### Current State

```
Job 1: version-bump ---------- Calculate semver, update files, create tag
Job 2: build ----------------- build_dist.py, tarballs, SHA256SUMS
Job 3: github-release -------- Changelog, GitHub Release with assets
Job 4: publish-to-nwave ------ rsync to nwave-ai/nwave, auto-bump version
Job 5: publish-to-pypi ------- Build wheel, twine upload, smoke test
Job 6: notify-slack ---------- Success/failure notification
```

### New Release Flow

```
Job 1: version-bump ---------- (unchanged)
Job 2: build ----------------- (unchanged)
Job 3: build-plugin ---------- NEW: build_plugin.py, upload artifact
Job 4: github-release -------- (unchanged, + plugin tarball as asset)
Job 5: publish-to-nwave ------ (unchanged)
Job 6: publish-to-plugin-repo  NEW: commit plugin to nwave-ai/nwave-plugin
Job 7: publish-to-pypi ------- (unchanged)
Job 8: notify-slack ---------- (updated needs list)
```

### Sequence Diagram

```
version-bump
     |
     v
   build  (dist/ artifacts)
     |
     +---> build-plugin  (plugin/ artifact)  [NEW - parallel with github-release]
     |          |
     v          v
github-release (includes plugin tarball from build-plugin)
     |
     +---> publish-to-nwave (unchanged)
     |          |
     |          v
     +---> publish-to-plugin-repo [NEW - after github-release]
     |
     v
publish-to-pypi (unchanged)
     |
     v
notify-slack (updated)
```

### New Job: build-plugin

```yaml
build-plugin:
  name: "Build Plugin"
  runs-on: ubuntu-latest
  timeout-minutes: 10
  needs: [version-bump]
  if: |
    always() &&
    (needs.version-bump.outputs.tag_created == 'true' || startsWith(github.ref, 'refs/tags/v'))

  steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0
        ref: ${{ needs.version-bump.outputs.new_version && format('v{0}', needs.version-bump.outputs.new_version) || github.ref }}

    - uses: actions/setup-python@v5
      with:
        python-version: ${{ env.PYTHON_DEFAULT }}

    - name: Build plugin
      run: |
        python3 scripts/build_plugin.py --output-dir plugin/

    - name: Verify plugin version matches tag
      run: |
        TAG_VERSION="${{ needs.version-bump.outputs.new_version || github.ref_name }}"
        TAG_VERSION="${TAG_VERSION#v}"
        PLUGIN_VERSION=$(python3 -c "
        import json
        with open('plugin/.claude-plugin/plugin.json') as f:
            print(json.load(f)['version'])
        ")
        if [ "$TAG_VERSION" != "$PLUGIN_VERSION" ]; then
          echo "::error::Plugin version ($PLUGIN_VERSION) != tag version ($TAG_VERSION)"
          exit 1
        fi

    - name: Create plugin tarball
      run: |
        VERSION="${{ needs.version-bump.outputs.new_version || github.ref_name }}"
        VERSION="${VERSION#v}"
        tar -czf "nwave-plugin-${VERSION}.tar.gz" -C plugin/ .
        sha256sum "nwave-plugin-${VERSION}.tar.gz" > "nwave-plugin-${VERSION}.tar.gz.sha256"

    - name: Upload plugin artifact
      uses: actions/upload-artifact@v4
      with:
        name: plugin-package
        path: |
          nwave-plugin-*.tar.gz
          nwave-plugin-*.sha256
        retention-days: 90
```

**Risk**: LOW. Pure build step with no external dependencies. Fails fast. Does not affect existing dist/ build.

**Rollback**: Remove the job. Existing release pipeline continues to work without it.

### New Job: publish-to-plugin-repo

```yaml
publish-to-plugin-repo:
  name: "Publish to nwave-ai/nwave-plugin"
  needs: [version-bump, github-release, build-plugin]
  if: |
    always() &&
    needs.github-release.result == 'success' &&
    needs.build-plugin.result == 'success' &&
    (github.event_name != 'workflow_dispatch' || inputs.dry_run != true)
  runs-on: ubuntu-latest
  timeout-minutes: 10

  steps:
    - uses: actions/checkout@v4

    - uses: actions/download-artifact@v4
      with:
        name: plugin-package
        path: plugin-artifacts/

    - name: Checkout nwave-ai/nwave-plugin (target)
      uses: actions/checkout@v4
      with:
        repository: nwave-ai/nwave-plugin
        token: ${{ secrets.RELEASETRAIN }}
        path: plugin-target

    - name: Extract and sync plugin
      run: |
        VERSION="${{ needs.version-bump.outputs.new_version }}"
        # Clear target (except .git)
        find plugin-target -maxdepth 1 -not -name '.git' -not -name 'plugin-target' -exec rm -rf {} +
        # Extract plugin tarball
        tar -xzf "plugin-artifacts/nwave-plugin-${VERSION}.tar.gz" -C plugin-target/

    - name: Commit and push
      working-directory: plugin-target
      run: |
        VERSION="${{ needs.version-bump.outputs.new_version }}"
        git config user.name "nWave Release Train"
        git config user.email "noreply@nwave.ai"
        git add -A
        if git diff --cached --quiet; then
          echo "No changes to publish"
        else
          git commit -m "chore(release): v${VERSION}"
          git push
        fi

    - name: Create tag and release
      working-directory: plugin-target
      env:
        GH_TOKEN: ${{ secrets.RELEASETRAIN }}
      run: |
        VERSION="${{ needs.version-bump.outputs.new_version }}"
        TAG="v${VERSION}"
        if ! git rev-parse "$TAG" >/dev/null 2>&1; then
          git tag -a "$TAG" -m "Release ${TAG}"
          git push origin "$TAG"
          gh release create "$TAG" --title "nWave Plugin ${TAG}" --notes "Plugin release for nWave v${VERSION}"
        fi
```

**Risk**: MEDIUM. Writes to an external repository. Requires `RELEASETRAIN` secret (already configured for nwave-ai/nwave). Requires `nwave-ai/nwave-plugin` repository to exist.

**Rollback**: Job is isolated. If it fails, the main release (GitHub Release, PyPI, nwave-ai/nwave) is unaffected.

### Modifications to Existing Jobs

#### github-release: Add plugin tarball as release asset

```yaml
# In github-release job, add download of plugin artifact
- uses: actions/download-artifact@v4
  with:
    name: plugin-package
    path: dist/releases/

# The existing softprops/action-gh-release step already uploads dist/releases/*.tar.gz
# Plugin tarball (nwave-plugin-*.tar.gz) is automatically included
```

**Risk**: LOW. Adds files to an existing upload pattern. If build-plugin job fails, the tarball is absent but the release still succeeds.

#### notify-slack: Update needs list

```yaml
needs: [version-bump, build, build-plugin, github-release, publish-to-nwave, publish-to-plugin-repo, publish-to-pypi]
```

**Risk**: LOW. Cosmetic change to include new jobs in failure detection.

### Release Changes Summary

| Change | Type | Effort | Risk | Rollback |
|--------|------|--------|------|----------|
| build-plugin job | New job | 1-2 hours | LOW | Delete job |
| publish-to-plugin-repo job | New job | 2-3 hours | MEDIUM | Delete job |
| github-release asset addition | Modify existing | 15 min | LOW | Remove download step |
| notify-slack needs update | Modify existing | 5 min | LOW | Revert line |

---

## 3. Plugin Repository Configuration

### Repository: nwave-ai/nwave-plugin

**Purpose**: Standalone repository containing the built plugin artifact. Used as:
1. Direct installation source (`claude plugin install github@nwave-ai/nwave-plugin`)
2. Self-hosted marketplace source (`extraKnownMarketplaces` in enterprise settings)
3. Marketplace submission source (Anthropic reviews this repo)

**Setup requirements**:

| Requirement | Action | Status |
|-------------|--------|--------|
| Create `nwave-ai/nwave-plugin` repo | GitHub UI or `gh repo create` | NOT YET CREATED |
| Grant `RELEASETRAIN` token access | Token already has nwave-ai org access | LIKELY READY |
| Add repo description | "nWave AI Plugin for Claude Code" | Manual |
| Set default branch | `main` | Manual |
| Add LICENSE | Copy from nwave-dev | Manual |
| Add README.md | Plugin-specific installation instructions | Manual |

**Risk**: LOW. Repository creation is a one-time manual step. The `RELEASETRAIN` personal access token already has `nwave-ai` organization access (used for `nwave-ai/nwave` sync).

**Verification**: Before the first release with plugin publishing, run:
```bash
# Verify token has access
gh repo view nwave-ai/nwave-plugin --json name 2>/dev/null || echo "REPO NOT CREATED"
```

---

## 4. Version Synchronization

### Current Version Flow

```
pyproject.toml [project.version] = "X.Y.Z"
  |
  +---> framework-catalog.yaml (enforced by CI Stage 2)
  +---> nWave/VERSION (synced by commitizen)
  +---> git tag vX.Y.Z (created by version-bump job)
  +---> nwave-ai/nwave pyproject.toml (auto-bumped patch from public_version floor)
```

### Extended Version Flow (with plugin)

```
pyproject.toml [project.version] = "X.Y.Z"
  |
  +---> (existing: framework-catalog.yaml, nWave/VERSION, git tag)
  +---> NEW: plugin/.claude-plugin/plugin.json { "version": "X.Y.Z" }
  +---> NEW: nwave-ai/nwave-plugin tag vX.Y.Z
```

### Enforcement Mechanisms

| Check | Where | How |
|-------|-------|-----|
| pyproject.toml == framework-catalog.yaml | CI Stage 2 | Existing Python script |
| pyproject.toml == plugin.json | build-plugin job | Version comparison step (see Job spec above) |
| tag == plugin.json | build-plugin job | Same step |
| nwave-plugin repo tag matches | publish-to-plugin-repo job | Tag created from version-bump output |

**Key design decision**: The plugin version always matches `pyproject.toml` exactly (no separate version track like nwave-ai). This is correct because the plugin IS the nWave framework -- it is not a thin wrapper like `nwave-ai`.

**Risk**: LOW. Version is read from `pyproject.toml` by `build_plugin.py` and injected into `plugin.json`. The same single-source-of-truth pattern already proven in the existing pipeline.

---

## 5. Marketplace Submission

### First Submission (Manual)

Anthropic's Plugin Marketplace requires manual initial submission. The CI/CD pipeline prepares the artifact but does not submit it.

**Pre-submission checklist** (manual, one-time):
- [ ] Plugin builds correctly from release pipeline
- [ ] Plugin installs via `claude plugin install github@nwave-ai/nwave-plugin`
- [ ] All hook registrations work (PreToolUse, PostToolUse, SubagentStop, SessionStart, SubagentStart)
- [ ] `/nw:deliver` command discovered and executable
- [ ] Submit to Anthropic via their plugin submission process

### Auto-update After Submission

Once accepted in the marketplace, Claude Code auto-updates plugins when new versions are detected. The `version` field in `plugin.json` triggers this.

**CI/CD support needed for auto-update**: None beyond what is already described. The `publish-to-plugin-repo` job pushes new versions with updated `plugin.json`, which the marketplace polls.

### Future: Automated Submission (Phase 2+)

If Anthropic provides a CLI or API for marketplace submission, add a step to `publish-to-plugin-repo`:

```yaml
- name: Submit to Anthropic Marketplace (future)
  if: false  # Enable when API available
  run: |
    claude marketplace submit --plugin-dir plugin-target/
```

**Risk**: N/A (future work). No CI/CD changes needed now.

---

## 6. Test Integration

### Current Test Architecture

```
tests/
  des/           -- DES tests (unit/, integration/, acceptance/, e2e/)
  installer/     -- Installer tests (unit/, acceptance/, e2e/)
  plugins/       -- Plugin system tests
  bugs/          -- Regression tests
  build/         -- Build script tests
    acceptance/
      plugin/    -- NEW: Plugin build acceptance tests (pytest-bdd)
  conftest.py    -- Root fixtures, auto-marking by directory
```

### Plugin Test Files (Already Created)

| File | Type | CI Behavior |
|------|------|-------------|
| `tests/build/acceptance/plugin/conftest.py` | Fixtures | Auto-loaded by pytest |
| `milestone-1-plugin-assembler.feature` | BDD scenarios | Discovered by pytest-bdd |
| `milestone-2-des-bundle.feature` | BDD scenarios | Discovered by pytest-bdd |
| `milestone-3-plugin-validation.feature` | BDD scenarios | Discovered by pytest-bdd |
| `milestone-4-release-pipeline.feature` | BDD scenarios | All `@skip` -- not run until implemented |
| `milestone-5-coexistence.feature` | BDD scenarios | All `@skip` -- not run until implemented |
| `walking-skeleton.feature` | BDD scenarios | Discovered by pytest-bdd |
| `steps/test_plugin_build_steps.py` | Step implementations | Discovered by pytest |
| `steps/test_des_bundle_steps.py` | Step implementations | Discovered by pytest |
| `steps/test_validation_steps.py` | Step implementations | Discovered by pytest |
| `steps/test_release_pipeline_steps.py` | Step implementations | All `@skip` steps |
| `steps/test_coexistence_steps.py` | Step implementations | All `@skip` steps |

### Special CI Configuration Needed?

**No.** The tests integrate cleanly into the existing pytest matrix:

1. **Discovery**: pytest auto-discovers `tests/build/acceptance/plugin/` via directory traversal
2. **Dependencies**: pytest-bdd >= 7.0.0 is already in `pyproject.toml` (dev dependencies)
3. **Fixtures**: `conftest.py` uses `tmp_path` (stdlib) and `Path` references to the real source tree
4. **Markers**: `@skip` prevents premature execution of unimplemented scenarios
5. **Performance**: Plugin build tests are fast (<10s total) -- no timeout concerns
6. **Isolation**: All output goes to `tmp_path` -- no filesystem side effects

### Test Coverage Gate

The plugin build tests will add to the overall test count. Current coverage threshold is 60% (`--cov` with `fail_under=60` in pyproject.toml). The new test files test a new module (`build_plugin.py`), so coverage impact is neutral (new tests + new code).

**Risk**: LOW. If `build_plugin.py` is partially implemented, uncovered code could lower the coverage percentage. Mitigation: implement tests and code together (TDD, as per nWave methodology).

---

## 7. Risk Assessment Summary

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Plugin build fails in release pipeline | Release completes without plugin artifact | LOW | build-plugin job is isolated; existing release unaffected |
| nwave-ai/nwave-plugin repo not created before first release | publish-to-plugin-repo job fails | MEDIUM | Create repo before first release with plugin publishing |
| RELEASETRAIN token lacks nwave-plugin repo access | publish-to-plugin-repo job fails | LOW | Token already has nwave-ai org access |
| Plugin acceptance tests slow down CI | Longer Stage 3 execution | LOW | Tests are <10s; negligible impact on ~10min matrix |
| Version mismatch between tag and plugin.json | Plugin publishes with wrong version | LOW | Explicit version check in build-plugin job |
| Plugin tarball missing from GitHub Release | Users cannot download plugin from release page | LOW | build-plugin job uploads artifact; github-release downloads it |
| Marketplace rejection on first submission | Plugin not available via marketplace | MEDIUM | Manual testing before submission; marketplace is secondary to direct GitHub install |

---

## 8. Effort Estimate

| Task | Effort | Dependency |
|------|--------|------------|
| Create `nwave-ai/nwave-plugin` repository | 15 min | None (manual) |
| Add `build-plugin` job to release.yml | 1-2 hours | `build_plugin.py` implemented |
| Add `publish-to-plugin-repo` job to release.yml | 1-2 hours | `nwave-plugin` repo exists |
| Add plugin tarball to github-release job | 15 min | `build-plugin` job exists |
| Update notify-slack needs | 5 min | New jobs exist |
| Add plugin build smoke test to ci.yml (optional) | 30 min | `build_plugin.py` implemented |
| **Total** | **3-5 hours** | After `build_plugin.py` |

**Sequencing**: All CI/CD changes are in Phase 02-01 of the roadmap. They depend on Phase 01 (build pipeline implementation) being complete. The CI/CD work should be the last implementation step before the first plugin-enabled release.

---

## 9. Recommendations

1. **Do NOT modify CI/CD until Phase 01 is complete.** The build pipeline (`build_plugin.py`) must exist and pass acceptance tests before integrating into release workflows.

2. **Create `nwave-ai/nwave-plugin` repository early.** This is a zero-risk manual step that unblocks Phase 02-01 testing.

3. **Keep plugin publishing as a non-blocking job.** If `build-plugin` or `publish-to-plugin-repo` fails, the existing release pipeline (dist, GitHub Release, PyPI, nwave-ai/nwave) must still succeed. Use `if: always()` patterns already established in the pipeline.

4. **Version sync is already solved.** The `pyproject.toml` single-source-of-truth pattern plus explicit version checks in the build-plugin job is sufficient. No new version-sync infrastructure needed.

5. **Test integration requires zero CI changes.** Plugin acceptance tests at `tests/build/acceptance/plugin/` are auto-discovered by pytest and use `@skip` markers for unimplemented scenarios.

6. **Defer marketplace submission automation.** First submission is manual. Add automation only when Anthropic provides a submission API/CLI.
