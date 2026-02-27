# Architecture: Release Train Tag Auto-Discovery

**Author**: Morgan (nw-solution-architect)
**Date**: 2026-02-23
**Status**: DESIGN wave (review-updated 2026-02-23)
**Reviewer**: Eclipse (nw-solution-architect-reviewer)
**Review status**: APPROVED after addressing 6 findings
**Input**: `docs/release/ux-auto-discovery-analysis.md` (APPROVED by Eclipse)

## 1. System Context

```
+------------------+     workflow_dispatch      +----------------------+
|  Release Engineer| --------------------------> | GitHub Actions UI    |
|  (Alessandro)    |  source_dev_tag: ""        | release-rc.yml       |
+------------------+  (or explicit tag)         | release-prod.yml     |
                                                +----------+-----------+
                                                           |
                                    +----------------------v-----------+
                                    |  validate-source job             |
                                    |  +---------------------------+   |
                                    |  | discover_tag.py           |   |
                                    |  | (new: tag auto-discovery) |   |
                                    |  +-------------+-------------+   |
                                    |                |                  |
                                    |  output: resolved_tag            |
                                    +--+-------------+-----------------+
                                       |             |
                      +----------------v--+   +------v-----------+
                      | ci-gate           |   | version-calc     |
                      | (unchanged)       |   | (uses resolved)  |
                      +-------------------+   +------------------+
                                       |             |
                      +----------------v--+   +------v-----------+
                      | build, tag,       |   | changelog, trace |
                      | pypi, sync, slack |   | (uses resolved)  |
                      +-------------------+   +------------------+
```

**One new component**: `discover_tag.py`. Everything else is wiring changes to existing jobs.

## 2. Existing System Analysis

| Existing Component | Reuse? | Rationale |
|---|---|---|
| `scripts/release/next_version.py` | **Pattern reuse** | Same CLI+JSON+subprocess pattern, same `packaging.Version` import |
| `scripts/release/ci_gate.py` | No change | Receives `commit_sha` from validate-source (already indirected) |
| `scripts/release/trace_message.py` | **Wiring only** | Currently receives `inputs.source_dev_tag`; will receive `resolved_tag` instead |
| `scripts/release/patch_pyproject.py` | No change | Not affected |
| `tests/release/conftest.py` | **Extend** | Add fixtures for tag discovery test data |
| `tests/release/test_next_version.py` | **Pattern reuse** | Same subprocess-based testing pattern for new script |

No new component is needed beyond `discover_tag.py`. The tag cleanup utility (`scripts/release/cleanup/cleanup_tags.py`) uses `git tag --list` and subprocess patterns we can reference but not import.

## 3. Component Design: `scripts/release/discover_tag.py`

### 3.1 Responsibility

Single responsibility: given a tag pattern, discover the highest semantic version tag and report staleness.

### 3.2 CLI Interface

```
python scripts/release/discover_tag.py \
    --pattern "dev" \
    [--validate "v1.1.23.dev1"] \
    [--tag-list "v1.1.22.dev1,v1.1.23.dev1,..."]
```

| Argument | Required | Description |
|---|---|---|
| `--pattern` | Yes | `"dev"` or `"rc"` |
| `--validate` | No | Explicit tag to validate. When provided, checks tag exists in list and outputs it directly. Skips discovery sort. |
| `--tag-list` | No | Comma-separated tag list. When omitted, runs `git tag -l` internally |

**Why `--tag-list`**: Enables pure-unit testing without git. Workflow passes live tags; tests pass synthetic lists.

**Why `--pattern` not the raw glob**: The script owns the mapping (`dev` -> `v*.dev*`, `rc` -> `v*rc*`). This prevents inconsistency between workflows and ensures the glob is correct.

### 3.3 JSON Output Schema

**Success**:
```json
{
    "tag": "v1.1.23.dev1",
    "version": "1.1.23.dev1",
    "found": true,
    "commits_behind": 0
}
```

**No tags found**:
```json
{
    "tag": null,
    "found": false,
    "error": "No dev tags found matching pattern 'v*.dev*'. Run Stage 1 (Dev Release) first."
}
```

| Field | Type | Description |
|---|---|---|
| `tag` | `string / null` | Full tag name with `v` prefix |
| `version` | `string / null` | PEP 440 version (no `v` prefix) |
| `found` | `boolean` | Whether a matching tag was discovered |
| `commits_behind` | `integer / null` | Result of `git rev-list --count <tag>..HEAD`. Null when `--tag-list` is provided (no git context) |
| `error` | `string` | Present only on `found: false` |

### 3.4 Exit Codes

| Code | Meaning | Consistent with |
|---|---|---|
| 0 | Tag found | `next_version.py` success |
| 1 | No matching tags | `next_version.py` "no bump needed" |
| 2 | Invalid input | `next_version.py` validation errors |

### 3.5 Internal Behavior (What, Not How)

- Accepts comma-separated tag list OR fetches via `git tag -l <glob>`
- Filters tags that parse as valid `packaging.Version`
- Sorts using `packaging.Version` comparison (guarantees dev10 > dev9, rc10 > rc9)
- Selects highest version
- When git is available (no `--tag-list`), computes `commits_behind` via `git rev-list --count <tag>..HEAD`
- Outputs JSON to stdout

### 3.6 Technology

| Choice | License | Rationale |
|---|---|---|
| `packaging` (PyPI) | Apache-2.0 / BSD-2 | Already in project. PEP 440 sort is the core requirement |
| Python 3.12 stdlib | PSF | `argparse`, `json`, `subprocess`, `sys` |

No new dependencies required.

## 4. Workflow Modification Design

### 4.1 Changes to `release-rc.yml` (Stage 2)

**Input section**:
```yaml
source_dev_tag:
    description: "Source dev tag (leave empty for latest, or enter e.g. v1.1.23.dev1)"
    required: false
    type: string
    default: ""
```

**Run-name**:
```yaml
run-name: "RC Release from ${{ inputs.source_dev_tag || '(auto-latest)' }}${{ inputs.dry_run == true && ' (dry run)' || '' }}"
```

**validate-source job**: New outputs and new step.

```
outputs:
    commit_sha: (unchanged)
    resolved_tag: <-- NEW (replaces source_dev_tag output)

steps:
    1. actions/checkout (fetch-depth: 0)
    2. setup-python + pip install packaging
    3. NEW STEP: Auto-discover or validate tag
       - If input is empty/whitespace: run discover_tag.py --pattern dev
       - If input is explicit: run discover_tag.py --pattern dev --validate <input>
       - Set resolved_tag from script's JSON tag field (with v prefix)
    4. Resolve tag to commit SHA (existing logic, now uses resolved_tag)
    5. NEW STEP: Staleness warning (when auto-discovered)
       - Read commits_behind from discover_tag.py JSON output (script computes it once; no recomputation in workflow)
       - If commits_behind > 0: emit ::warning:: annotation
```

**Downstream rewiring** (11 total references to `inputs.source_dev_tag`; L14 run-name and L60 validate-source handled above; 9 downstream):

| Line | Current | New |
|---|---|---|
| L50 (output) | `source_dev_tag: ${{ inputs.source_dev_tag }}` | `resolved_tag: ${{ steps.discover.outputs.resolved_tag }}` |
| L166 (version-calc) | `--current-version "${{ inputs.source_dev_tag }}"` | `--current-version "${{ needs.validate-source.outputs.resolved_tag }}"` |
| L243 (tag message) | `promoted from ${{ inputs.source_dev_tag }}` | `promoted from ${{ needs.validate-source.outputs.resolved_tag }}` |
| L336 (changelog env) | `SOURCE_TAG: ${{ inputs.source_dev_tag }}` | `SOURCE_TAG: ${{ needs.validate-source.outputs.resolved_tag }}` |
| L517 (trace_message) | `--dev-tag "${{ inputs.source_dev_tag }}"` | `--dev-tag "${{ needs.validate-source.outputs.resolved_tag }}"` |
| L590 (dry-run trace) | `--dev-tag "${{ inputs.source_dev_tag }}"` | `--dev-tag "${{ needs.validate-source.outputs.resolved_tag }}"` |
| L603 (dry-run table) | `${{ inputs.source_dev_tag }}` | `${{ needs.validate-source.outputs.resolved_tag }}` |
| L659 (Slack success) | `${{ inputs.source_dev_tag }}` | `${{ needs.validate-source.outputs.resolved_tag }}` |
| L690 (Slack failure) | `${{ inputs.source_dev_tag }}` | `${{ needs.validate-source.outputs.resolved_tag }}` |

### 4.2 Changes to `release-prod.yml` (Stage 3)

Identical pattern to 4.1 but with:
- `source_rc_tag` instead of `source_dev_tag`
- `--pattern rc` instead of `--pattern dev`
- Glob `v*rc*` instead of `v*.dev*`

**Downstream rewiring** (12 total references to `inputs.source_rc_tag`; L15 run-name and L62 validate-source handled above; 10 downstream):

| Line | Current | New |
|---|---|---|
| L51 (output) | `source_rc_tag: ${{ inputs.source_rc_tag }}` | `resolved_tag: ${{ steps.discover.outputs.resolved_tag }}` |
| L174 (version-calc) | `--current-version "${{ inputs.source_rc_tag }}"` | `--current-version "${{ needs.validate-source.outputs.resolved_tag }}"` |
| L393 (changelog env) | `SOURCE_RC: ${{ inputs.source_rc_tag }}` | `SOURCE_RC: ${{ needs.validate-source.outputs.resolved_tag }}` |
| L400 (tag message) | `promoted from ${{ inputs.source_rc_tag }}` | `promoted from ${{ needs.validate-source.outputs.resolved_tag }}` |
| L625 (trace_message) | `--rc-tag "${{ inputs.source_rc_tag }}"` | `--rc-tag "${{ needs.validate-source.outputs.resolved_tag }}"` |
| L734 (dry-run trace) | `--rc-tag "${{ inputs.source_rc_tag }}"` | `--rc-tag "${{ needs.validate-source.outputs.resolved_tag }}"` |
| L748 (dry-run table) | `${{ inputs.source_rc_tag }}` | `${{ needs.validate-source.outputs.resolved_tag }}` |
| L765 (dry-run summary) | `${{ inputs.source_rc_tag }}` | `${{ needs.validate-source.outputs.resolved_tag }}` |
| L809 (Slack success) | `${{ inputs.source_rc_tag }}` | `${{ needs.validate-source.outputs.resolved_tag }}` |
| L840 (Slack failure) | `${{ inputs.source_rc_tag }}` | `${{ needs.validate-source.outputs.resolved_tag }}` |

### 4.3 Data Flow: resolved_tag Propagation

```
                    validate-source
                    +---------------------------------+
 input: ""          | 1. discover_tag.py --pattern dev |
 ------------------>| 2. output: resolved_tag          |
                    | 3. output: commit_sha            |
                    +---------+---------+--------------+
                              |         |
               resolved_tag   |         |  commit_sha
          +-------------------+         +------------------+
          |                   |                            |
+---------v------+  +---------v------+  +---------v-------+
| version-calc   |  | tag-release    |  | ci-gate         |
| --current-     |  | tag message    |  | (uses sha only) |
|  version uses  |  | changelog      |  +-----------------+
|  resolved_tag  |  | trace_message  |
+--------+-------+  +-------+--------+
         |                   |
         v                   v
+------------------+  +-----------------+
| build            |  | sync repos      |
| (uses sha)       |  | (uses resolved) |
+------------------+  +-----------------+
         |                   |
         v                   v
+------------------+  +-----------------+
| pypi-publish     |  | slack notify    |
| (uses version)   |  | (uses resolved) |
+------------------+  +-----------------+
```

**Field mapping**: The workflow's `resolved_tag` output is set from the JSON `tag` field (with `v` prefix). Example: JSON `{"tag": "v1.1.23.dev1", ...}` maps to `resolved_tag=v1.1.23.dev1`.

**Critical invariant**: After validate-source, no job references `inputs.source_dev_tag` or `inputs.source_rc_tag`. All use `needs.validate-source.outputs.resolved_tag`.

## 5. Test Strategy

### 5.1 New Test File: `tests/release/test_discover_tag.py`

**Pattern**: Same subprocess-based testing as `test_next_version.py`. Run `discover_tag.py` as a subprocess, parse JSON output.

**Test categories and behavioral scenarios**:

| Category | Scenario | Key Assertion |
|---|---|---|
| **Dev happy path** | `--pattern dev --tag-list "v1.1.22.dev1,v1.1.23.dev1"` | Returns `v1.1.23.dev1` |
| **Dev digit transition** | `--pattern dev --tag-list "v1.1.23.dev1,...,v1.1.23.dev11"` (11 tags) | Returns `v1.1.23.dev11` (not dev9) |
| **No dev tags** | `--pattern dev --tag-list ""` | Exit 1, `found: false`, error mentions Stage 1 |
| **RC happy path** | `--pattern rc --tag-list "v1.1.22rc1,v1.1.23rc1"` | Returns `v1.1.23rc1` |
| **RC digit transition** | `--pattern rc --tag-list "v1.1.23rc1,...,v1.1.23rc11"` (11 tags) | Returns `v1.1.23rc11` (not rc9) |
| **No RC tags** | `--pattern rc --tag-list ""` | Exit 1, error mentions Stage 2 |
| **Mixed base versions** | `--pattern dev --tag-list "v1.1.22.dev1,v1.1.22.dev2,v1.1.23.dev1"` | Returns `v1.1.23.dev1` (highest semantic) |
| **Validate existing** | `--pattern dev --validate v1.1.23.dev1 --tag-list "v1.1.23.dev1,..."` | Returns `v1.1.23.dev1` directly (skips sort) |
| **Validate missing** | `--pattern dev --validate v9.9.9.dev1 --tag-list "v1.1.23.dev1"` | Exit 1, error: tag not found |
| **Invalid pattern** | `--pattern stable` | Exit 2, error message |
| **Invalid tags filtered** | `--pattern dev --tag-list` with mix of valid and non-PEP-440 tags | Invalid tags skipped, valid ones sorted |

**commits_behind**: Not tested at unit level (requires git repo). Tested via workflow integration or a dedicated integration test with `tmp_path` git init.

### 5.2 Existing Tests: No Changes

No existing test files require modification. The new test file follows the same conventions.

### 5.3 Test Fixtures (conftest.py extension)

Add sample tag lists for discovery tests:

| Fixture | Content |
|---|---|
| `dev_tags_mixed_versions` | `["v1.1.22.dev1", "v1.1.22.dev2", "v1.1.23.dev1"]` |
| `dev_tags_digit_transition` | `["v1.1.23.dev1", "v1.1.23.dev2", ..., "v1.1.23.dev11"]` (11 entries: proves dev10 > dev9, dev11 > dev10) |
| `rc_tags_mixed` | `["v1.1.22rc1", "v1.1.22rc2", "v1.1.23rc1"]` |
| `rc_tags_digit_transition` | `["v1.1.23rc1", "v1.1.23rc2", ..., "v1.1.23rc11"]` (11 entries: proves rc10 > rc9, rc11 > rc10) |

## 6. Files Changed Summary

| File | Action | Scope |
|---|---|---|
| `scripts/release/discover_tag.py` | **NEW** | ~80-120 lines. CLI, JSON output, `packaging.Version` sort |
| `tests/release/test_discover_tag.py` | **NEW** | ~120-160 lines. 9+ test cases |
| `tests/release/conftest.py` | **EXTEND** | Add 4 tag-list fixtures |
| `.github/workflows/release-rc.yml` | **MODIFY** | Input optional, add discover step, rewire 10 references |
| `.github/workflows/release-prod.yml` | **MODIFY** | Input optional, add discover step, rewire 12 references |

**Production files**: 3 (discover_tag.py, release-rc.yml, release-prod.yml)
**Test files**: 2 (test_discover_tag.py, conftest.py)

## 7. ADRs

### ADR-001: Tag Discovery as Standalone Script

**Status**: Accepted

**Context**: Auto-discovery logic must sort PEP 440 versions correctly. This requires `packaging.Version`. We need this logic in two workflows (RC and Stable).

**Decision**: Create `scripts/release/discover_tag.py` as a standalone Python CLI script.

**Alternatives Considered**:
- **Inline bash in workflow**: Rejected. Cannot use `packaging.Version` for sort. Bash `sort -V` fails on `dev9 vs dev10`. The UX analysis (section 4.1) explicitly flags this as a critical trap and mandates `packaging.Version`.
- **Extend `next_version.py` with a `--discover` flag**: Rejected. Different responsibility (discovery vs calculation). Would complicate an already multi-branching script. Violates single-responsibility.

**Consequences**:
- Positive: Testable in isolation; reusable across both workflows; consistent with existing script patterns
- Negative: One more file in `scripts/release/`

### ADR-002: `--tag-list` Parameter for Testability

**Status**: Accepted

**Context**: Discovery needs `git tag -l` to list tags. Unit tests should not require a real git repository.

**Decision**: Accept `--tag-list` as optional comma-separated input. When provided, skip `git tag -l`. When omitted, fetch from git.

**Alternatives Considered**:
- **Mock subprocess in tests**: Rejected. The existing test pattern (`test_next_version.py`) uses subprocess-based testing (run script as child process). Mocking subprocess inside a subprocess is fragile.
- **Always require `--tag-list`**: Rejected. Workflow would need an extra step to gather tags and pass them. Unnecessary complexity when the script can call git directly.

**Consequences**:
- Positive: Clean unit tests with synthetic tag lists; workflow just calls `--pattern dev` with no extra steps
- Negative: Two code paths (git vs tag-list) that must stay consistent

### ADR-003: Staleness via `git rev-list --count`, Not Calendar Days

**Status**: Accepted

**Context**: The UX analysis (section 4.4) reframes staleness from "days old" to "unreleased commits after the tag." A tag created yesterday with 0 commits after it is not stale. A tag from 1 hour ago with 12 commits after it is stale.

**Decision**: Compute `git rev-list --count <tag>..HEAD` inside `discover_tag.py`. Report as `commits_behind` in JSON. Workflow emits `::warning::` annotation when `commits_behind > 0`.

**Alternatives Considered**:
- **Calendar-based staleness (days since tag)**: Rejected. Per UX analysis, misleading. A recent tag with no new commits is not stale.
- **Staleness check in workflow bash**: Rejected. The script already has git access; computing it there keeps logic in one testable place.

**Consequences**:
- Positive: Accurate staleness signal; actionable warning message
- Negative: `commits_behind` is null when `--tag-list` is used (no git context). Integration tests needed for staleness behavior.

## 8. Roadmap

### Step 1: `discover_tag.py` with unit tests

**Description**: Create tag discovery script with `--pattern` and `--tag-list` args. JSON output. `packaging.Version` sort. Unit tests via subprocess.

**Acceptance criteria**:
- `--pattern dev` with tag list returns highest semantic dev tag
- `--pattern rc` with tag list returns highest semantic RC tag
- dev11 sorts higher than dev10, dev10 higher than dev9 (integer sort, not string)
- `--validate <tag>` returns that tag if found, exit 1 if missing
- No matching tags returns exit 1 with actionable error
- Mixed base versions return globally highest version

**Architectural constraints**:
- Uses `packaging.Version` for all sorting (MUST)
- JSON output to stdout, errors to stdout as JSON
- Exit codes: 0=found, 1=not-found, 2=invalid-input

### Step 2: `discover_tag.py` staleness detection (integration test)

**Description**: Add `commits_behind` via `git rev-list --count`. Integration test with temp git repo.

**Acceptance criteria**:
- `commits_behind` is 0 when tag points at HEAD
- `commits_behind` reflects commit count when tag is behind
- `commits_behind` is null when `--tag-list` is provided
- Staleness does not affect exit code

### Step 3: Workflow integration (both RC and Stable)

**Description**: Wire `discover_tag.py` into validate-source job of both workflows. Rewire all downstream references.

**Acceptance criteria**:
- Empty input triggers auto-discovery; explicit input uses that tag
- `resolved_tag` output replaces all `inputs.source_*_tag` references downstream
- Run-name shows "(auto-latest)" when input was empty
- Staleness warning annotation emitted when `commits_behind > 0`
- No downstream job references raw input directly

**Architectural constraints**:
- validate-source MUST output `resolved_tag`
- All downstream jobs MUST use `needs.validate-source.outputs.resolved_tag`
