# Plan: Replace hardcoded patch bump with Commitizen-based version calculation

**Status**: PENDING (to be discussed with Luna/Apex/Quinn after release train E2E)
**Date**: 2026-02-23

## Problem

`next_version.py` always calls `_bump_patch()` for dev releases, ignoring conventional commit types. With 4 `feat:` commits, the dev release was `v1.1.23.dev2` instead of `v1.2.0.dev1`. The version bump level should be driven by commit analysis, not hardcoded.

## Research

Full research at `docs/research/cicd/psr-version-calculation-for-release-trains.md`.

**Key findings**:
- PSR cannot produce PEP 440 prerelease versions (outputs `1.2.3-dev.1` not `1.2.3.dev1`)
- Commitizen natively supports PEP 440 via `version_scheme = "pep440"`
- `cz bump --get-next` outputs just the version string, no side effects
- `cz bump --get-next --devrelease N` produces `X.Y.Z.devN` directly
- CZ uses same conventional commit rules (feat→minor, fix→patch, !→major)
- Commitizen already installed as dev dependency (`commitizen>=3.12.0`)

## Design: Hybrid CZ + Floor Override

Mike's requirement: CZ manages the version bump, but trapped in a fallback system that allows manual baseline override via `[tool.nwave].public_version`.

**Key insight**: `project.version` stays at `1.1.22` (last stable) throughout the dev cycle because dev releases don't modify pyproject.toml. So `cz bump --get-next` always analyzes commits from the stable tag. Each dev release in the cycle shares the same base version.

**RC and Stable need no changes**: the base version propagates through tags (`v1.2.0.dev1` → `1.2.0rc1` → `1.2.0`).

### Version resolution priority

```
1. [tool.nwave].public_version floor  (highest priority: manual override)
2. Commitizen commit analysis          (primary: conventional commit → bump level)
3. _bump_patch fallback               (safety net: if CZ fails or returns empty)
```

Example scenarios:

| CZ says | Floor says | Result |
|---------|-----------|--------|
| 1.2.0 (feat commits) | 1.1.0 | 1.2.0.dev1 (CZ wins) |
| 1.1.23 (fix commits) | 1.1.0 | 1.1.23.dev1 (CZ wins) |
| 1.2.0 (feat commits) | 1.3.0 | 1.3.0.dev1 (floor wins) |
| empty (no commits) | 1.1.0 | 1.1.23.dev1 (fallback to patch) |
| empty (no commits) | 2.0.0 | 2.0.0.dev1 (floor wins over fallback) |

## Changes

### Step 1: Add `[tool.commitizen]` config to pyproject.toml

```toml
[tool.commitizen]
name = "cz_conventional_commits"
version_provider = "pep621"
version_scheme = "pep440"
tag_format = "v$version"
```

- `version_provider = "pep621"` reads from `[project].version` (anchored at last stable)
- `version_scheme = "pep440"` produces `1.2.0` not `1.2.0-rc.1`
- `tag_format = "v$version"` matches our existing tag convention
- Coexists with `[tool.semantic_release]` (different config sections, no conflict)

**File**: `pyproject.toml` (add after `[tool.nwave]` section, ~line 110)

### Step 2: Add `--base-version` and `--version-floor` args to next_version.py

New optional CLI args:

```
--base-version    Base version from external calculator (e.g. CZ). Overrides _bump_patch.
--version-floor   Minimum version floor. If higher than base, becomes the new base.
```

**File**: `scripts/release/next_version.py`

Changes to `parse_args()`:
- Add `--base-version` (default `""`)
- Add `--version-floor` (default `""`)

Changes to `calculate_dev()`:
```python
def calculate_dev(
    current_version: Version,
    existing_tags: list[Version],
    no_bump: bool,
    base_version: str = "",
    version_floor: str = "",
) -> None:
    if no_bump:
        _error_exit("No version bump needed.", code=1)

    # Base from external calculator (CZ) or fallback to patch bump
    if base_version:
        base = base_version
    else:
        base = _bump_patch(current_version)

    # Floor override: use floor if higher
    if version_floor:
        floor_v = Version(version_floor)
        base_v = Version(base)
        if floor_v > base_v:
            base = str(floor_v)

    highest = _highest_counter(existing_tags, base, "dev")
    next_dev = highest + 1
    version_str = f"{base}.dev{next_dev}"
    _success_output(version_str, base)
```

Changes to `main()`: pass `args.base_version` and `args.version_floor` to `calculate_dev()`.

### Step 3: Add tests for new args

**File**: `tests/release/test_next_version.py`

New class `TestDevBaseVersionAndFloor`:

| Test | Scenario |
|------|----------|
| `test_base_version_overrides_patch_bump` | `--base-version 1.2.0` → base is `1.2.0`, not `1.1.23` |
| `test_empty_base_version_falls_back_to_patch` | No `--base-version` → same as today (`_bump_patch`) |
| `test_version_floor_overrides_when_higher` | base `1.2.0` + floor `1.3.0` → `1.3.0.dev1` |
| `test_version_floor_ignored_when_lower` | base `1.2.0` + floor `1.1.0` → `1.2.0.dev1` |
| `test_floor_and_base_and_counter_combined` | base `1.2.0` + floor `1.3.0` + existing `v1.3.0.dev1` → `1.3.0.dev2` |

### Step 4: Wire CZ into release-dev.yml workflow

In the `version-calc` job, add CZ step and floor step, pass both to next_version.py:

```yaml
      - name: Install dependencies
        run: pip install packaging commitizen

      - name: Determine bump level via commitizen
        id: bump
        run: |
          BASE=$(cz bump --get-next 2>/dev/null) || BASE=""
          echo "base=$BASE" >> $GITHUB_OUTPUT

      - name: Read version floor
        id: floor
        run: |
          FLOOR=$(python scripts/release/read_toml_field.py \
            --file pyproject.toml --key tool.nwave.public_version)
          echo "floor=$FLOOR" >> $GITHUB_OUTPUT

      - name: Calculate next dev version
        id: calc
        run: |
          OUTPUT=$(python scripts/release/next_version.py \
            --stage dev \
            --current-version "${{ steps.current.outputs.version }}" \
            --existing-tags "${{ steps.tags.outputs.tags }}" \
            --base-version "${{ steps.bump.outputs.base }}" \
            --version-floor "${{ steps.floor.outputs.floor }}")
          ...
```

**No changes to release-rc.yml or release-prod.yml** — they inherit the base version from source tags.

## Files modified

| File | Change |
|------|--------|
| `pyproject.toml` | Add `[tool.commitizen]` section (4 lines) |
| `scripts/release/next_version.py` | Add `--base-version`, `--version-floor` args; refactor `calculate_dev()` |
| `tests/release/test_next_version.py` | Add `TestDevBaseVersionAndFloor` class (5 tests) |
| `.github/workflows/release-dev.yml` | Add CZ bump step, floor step, pass to next_version.py |

## Verification

1. `pytest tests/release/test_next_version.py -v` — all tests pass (20 existing + 5 new)
2. `pytest tests/release/ -v` — full suite passes (125+ tests)
3. Local smoke test: `cz bump --get-next` in repo → should output `1.2.0` (feat commits since v1.1.22)
4. After push: trigger dev release → should create `v1.2.0.dev1` (not `v1.1.24.dev1`)
5. Verify floor override: temporarily set `public_version = "2.0.0"`, run next_version.py locally, confirm `2.0.0.dev1`

## Open questions for DISCUSS wave

1. Should the floor also apply to RC stage as a safety net?
2. Should we remove `[tool.semantic_release]` config now that CZ handles version calculation?
3. Do we need a `--increment MAJOR/MINOR/PATCH` manual override flag alongside the floor?
4. Should the nwave-ai stage also use CZ instead of its own floor logic?
