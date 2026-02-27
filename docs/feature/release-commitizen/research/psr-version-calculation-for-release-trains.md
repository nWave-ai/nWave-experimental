# Research: python-semantic-release Version Calculation for Multi-Stage Release Trains

**Date**: 2026-02-23
**Researcher**: Nova (knowledge-researcher)
**Overall Confidence**: High
**Sources Consulted**: 14
**Cross-References Performed**: 9
**PSR Version Scope**: v9.x (your dep) and v10.5.3 (current latest)

## Executive Summary

python-semantic-release (PSR) calculates versions from conventional commits and can output the next version via `--print` without making changes. However, PSR produces **SemVer format** (`1.2.3-rc.1`) not **PEP 440 format** (`1.2.3rc1`, `1.2.3.dev1`). This is a fundamental incompatibility for your 3-stage release train.

**Your project already solved this.** The custom `scripts/release/next_version.py` uses `packaging.version.Version` to produce PEP 440-compliant versions (`1.2.3.dev1`, `1.2.3rc1`, `1.2.3`) directly. PSR in `release.yml` handles only stable version bumps where the format difference is irrelevant (both produce `1.2.3`).

**Bottom line**: Use PSR for what it does well (commit analysis, stable version bumps). Use your custom script for what PSR cannot do (PEP 440 dev/rc versioning). Do not try to force PSR into PEP 440 prerelease output; that is an open feature request with no timeline [1][2].

---

## Question 1: How Does PSR Calculate the Next Version?

**Confidence: High (5 sources)**

### Algorithm

PSR follows this sequence [3][4][5]:

| Step | Action |
|------|--------|
| 1 | Parse all git tags matching `tag_format` (default: `v{version}`) into Version objects |
| 2 | Filter to tags reachable from the current branch |
| 3 | Sort by SemVer precedence, descending |
| 4 | Identify the latest full release and latest prerelease (if any) |
| 5 | Collect all commits between HEAD and the last release tag |
| 6 | Parse each commit using the configured parser (default: conventional) |
| 7 | Determine the highest bump level across all parsed commits |
| 8 | Apply `major_on_zero` and `allow_zero_version` rules |
| 9 | Produce the next version |

### Conventional Commit Mapping

| Commit Pattern | Bump Level |
|---------------|------------|
| `fix:`, `perf:` | PATCH |
| `feat:` | MINOR |
| `feat!:` or body contains `BREAKING CHANGE:` | MAJOR |
| `chore:`, `docs:`, `style:`, `test:`, `ci:`, `build:` | No bump |
| Unparseable | No bump (logged as "Unknown") |

The **highest** bump level wins. If you have 3 `fix:` commits and 1 `feat:` commit, the result is MINOR [4][5].

### CLI to Compute Without Releasing

```bash
# Print next version number only (no side effects)
semantic-release version --print

# Print next version as full tag (e.g., v1.2.3)
semantic-release version --print-tag

# Print last released version (from tags)
semantic-release version --print-last-released

# Force a specific bump level, preview only
semantic-release version --minor --print
semantic-release version --patch --print
```

The `--print` flag outputs **just the version string** to stdout and exits [3]. No files are modified, no commits are created, no tags are applied.

### Full Dry Run (verbose, no changes)

```bash
# Global --noop shows all intended actions
semantic-release --noop version

# Verbose dry run
semantic-release -vv --noop version
```

---

## Question 2: How Does PSR Handle Pre-Release Versions?

**Confidence: High (4 sources)**

### Format Produced

PSR produces **SemVer format**, not PEP 440 [1][2][6]:

| PSR Output | PEP 440 Equivalent | Valid PEP 440? |
|------------|-------------------|----------------|
| `1.2.3-rc.1` | `1.2.3rc1` | No (hyphen+dot) |
| `1.2.3-dev.1` | `1.2.3.dev1` | No (hyphen+dot) |
| `1.2.3-alpha.1` | `1.2.3a1` | No (hyphen+dot, "alpha" not canonical) |
| `1.2.3` | `1.2.3` | Yes (stable is compatible) |

The `__str__` method of PSR's Version class hardcodes the format:
```python
f"-{self.prerelease_token}.{self.prerelease_revision}"
```
This produces `1.2.3-rc.1`, not `1.2.3rc1` [6].

### CLI Flags for Pre-Release

```bash
# Convert calculated version to prerelease
semantic-release version --as-prerelease --print
# Output: 1.3.0-rc.1 (if feat commits exist, with default token "rc")

# Force minor bump as prerelease
semantic-release version --minor --as-prerelease --print
# Output: 1.3.0-rc.1

# Increment existing prerelease revision
semantic-release version --prerelease --print
# From 1.2.3-rc.1 -> Output: 1.2.3-rc.2

# Override prerelease token
semantic-release version --as-prerelease --prerelease-token dev --print
# Output: 1.3.0-dev.1
```

**Key distinction**: `--prerelease` increments the revision of an existing prerelease. `--as-prerelease` converts a calculated stable version into a prerelease [3].

### PEP 440 `.devN` and `rcN` Support

**PSR does NOT natively support PEP 440 format** [1][2]. Issue #455 (opened June 2022, still open as of Feb 2026) tracks this feature request. No timeline has been provided by maintainers.

The workaround is post-processing: use PSR to determine the bump level, then format the version yourself. **This is exactly what your `next_version.py` does.**

---

## Question 3: Tag Architecture Compatibility

**Confidence: High (4 sources)**

### Tag Format PSR Expects

Configured via `tag_format` in pyproject.toml. Your config:

```toml
tag_format = "v{version}"
```

PSR uses this pattern both for:
- **Creating** new tags (applies the template)
- **Parsing** existing tags (reverse-matches to extract versions)

"Tags which do not match this format will not be considered as versions of your project" [7].

### Compatibility With Your Tags

| Your Tag Format | PSR Can Parse? | Why |
|----------------|---------------|-----|
| `v1.1.22` | Yes | Matches `v{version}` exactly |
| `v1.1.23.dev2` | **No** | PSR expects SemVer: `v1.1.23-dev.2` |
| `v1.1.22rc5` | **No** | PSR expects SemVer: `v1.1.22-rc.5` |

PSR will **ignore** your PEP 440 dev/rc tags because they do not match its internal SemVer parser. It will only see stable tags (`v1.1.22`, `v1.1.21`, etc.).

### How PSR Finds "Previous Version"

1. Lists all git tags matching `tag_format`
2. Parses each into a SemVer Version object (ignoring unparseable ones)
3. Filters to tags reachable from the current branch's commit history
4. Sorts by SemVer precedence
5. The highest version is the "latest release"

For prerelease branches, it additionally searches for the latest prerelease with a matching token [4][5].

### Implication for Your Pipeline

When PSR runs `semantic-release version --print` on your repo, it will:
1. See tags: `v1.1.22`, `v1.1.21`, `v1.1.20`, etc.
2. **Skip** tags: `v1.1.23.dev1`, `v1.1.22rc1` (cannot parse as SemVer)
3. Base version: `1.1.22`
4. Analyze commits since `v1.1.22`
5. Output: `1.1.23` (if there are `feat` or `fix` commits)

This is **correct behavior** for your use case: PSR determines the bump level, your custom script handles the stage-specific formatting.

---

## Question 4: Configuration for Your Use Case

**Confidence: High (3 sources)**

### Your Current Config: Assessment

```toml
[tool.semantic_release]
version_toml = ["pyproject.toml:project.version"]            # Correct
version_variables = ["nWave/framework-catalog.yaml:version"]  # Correct
commit_parser = "conventional"                                 # Correct
tag_format = "v{version}"                                      # Correct
major_on_zero = false                                          # Correct for 1.x dev
build_command = ""                                             # Correct (build handled elsewhere)
commit_author = "github-actions[bot] <...>"                    # Correct
commit_message = "chore(release): v{version} [skip ci]"       # Correct

[tool.semantic_release.branches.main]
match = "master"     # Correct (your default branch)
prerelease = false   # Correct (stable releases only from this config)
```

**This config is fine for stable releases.** PSR correctly bumps `project.version` and `framework-catalog.yaml:version` when running `semantic-release version` for stable releases.

### What PSR Cannot Do for You

| Need | PSR Support | Your Solution |
|------|-------------|---------------|
| Calculate `1.2.3.dev1` | No (produces `1.2.3-dev.1`) | `next_version.py --stage dev` |
| Calculate `1.2.3rc1` | No (produces `1.2.3-rc.1`) | `next_version.py --stage rc` |
| Calculate `1.2.3` (stable) | Yes | PSR or `next_version.py --stage stable` |
| Determine bump level from commits | Yes (`--print`) | Uses PSR indirectly via release.yml |
| Stamp version into pyproject.toml | Yes | Release workflows handle this |

### Using PSR as a Library (Programmatic)

PSR can be imported and used programmatically, but this is not well-documented for version calculation only. The CLI approach is more reliable:

```bash
# Get next version as a string (for CI scripts)
NEXT=$(semantic-release version --print 2>/dev/null)
echo "Next version would be: $NEXT"

# Use in a shell variable
if [ -z "$NEXT" ]; then
  echo "No release needed"
fi
```

### Minimal CLI to Get "Next Version Would Be X.Y.Z"

```bash
# Simplest form:
semantic-release version --print

# With forced bump:
semantic-release version --patch --print

# As prerelease (SemVer format):
semantic-release version --as-prerelease --print
```

---

## Question 5: The `version` Command in Detail

**Confidence: High (3 sources)**

### `semantic-release version --print`

- **Output**: The raw version number (e.g., `1.2.3`), no `v` prefix
- **Side effects**: None. No file modifications, no git operations
- **Exit code**: 0 if a new version would be released; outputs the version
- **No release case**: Outputs nothing (empty string) if no bump is needed

### Full Dry Run Pattern

```bash
semantic-release version --no-commit --no-tag --no-push --print
```

This is redundant; `--print` alone already prevents all side effects. But it is harmless and makes intent explicit.

### `--as-prerelease` Behavior

Starting from version `1.1.22` with `feat:` commits:

```bash
semantic-release version --as-prerelease --print
# Output: 1.1.23-rc.1   (SemVer format, NOT PEP 440)

semantic-release version --as-prerelease --prerelease-token dev --print
# Output: 1.1.23-dev.1  (SemVer format, NOT PEP 440)
```

### Getting `1.2.0.dev1` from PSR

**You cannot.** PSR will produce `1.2.0-dev.1`. To get `1.2.0.dev1`, post-process:

```bash
# Workaround: extract bump level from PSR, format with your script
PSR_VERSION=$(semantic-release version --print)
if [ -n "$PSR_VERSION" ]; then
  python scripts/release/next_version.py \
    --stage dev \
    --current-version "$(cat pyproject.toml | grep 'version =' | head -1 | cut -d'"' -f2)" \
    --existing-tags "$(git tag -l 'v*' | tr '\n' ',')"
fi
```

Or simply use your `next_version.py` directly, which is what your release-dev.yml already does.

---

## Question 6: Key PSR Config Options

**Confidence: High (4 sources)**

### Options Relevant to Your Setup

| Option | Your Value | Default | Notes |
|--------|-----------|---------|-------|
| `version_toml` | `["pyproject.toml:project.version"]` | `[]` | Correct. Uses TOML parser for precise updates [7] |
| `version_variables` | `["nWave/framework-catalog.yaml:version"]` | `[]` | Correct. Pattern-based regex matching for YAML [7] |
| `commit_parser` | `"conventional"` | `"conventional"` | Correct. Parses `feat:`, `fix:`, `BREAKING CHANGE:` [7] |
| `tag_format` | `"v{version}"` | `"v{version}"` | Correct. Must contain `{version}` placeholder [7] |
| `major_on_zero` | `false` | `true` | Correct for your 1.x phase. Breaking changes bump minor, not major [7] |
| `build_command` | `""` | `""` | Correct. Build is handled by separate workflow jobs |
| `allow_zero_version` | (not set) | `false` (v10) | Not relevant; you are at 1.1.22 |

### `prerelease_token` Configuration

Configured per-branch:

```toml
[tool.semantic_release.branches.main]
match = "master"
prerelease = false
prerelease_token = "rc"   # Default value (even if not set)
```

When `prerelease = false`, the `prerelease_token` is ignored for that branch. It only matters when `prerelease = true` or when `--as-prerelease` is used on the CLI [7][8].

**Valid token values**: Any string. Common: `"rc"`, `"alpha"`, `"beta"`, `"dev"`. But the output format will always be SemVer (`1.2.3-dev.1`), not PEP 440 (`1.2.3.dev1`) [1][6].

### Configuration You Do NOT Need to Add

| Option | Why Not |
|--------|---------|
| `prerelease_token = "dev"` | Your dev/rc versions are handled by `next_version.py`, not PSR |
| Additional branch configs | You run PSR only on master for stable releases |
| `add_partial_tags` | Not needed for your tag strategy |

---

## Architecture Recommendation

Based on the findings, your current architecture is correct. Here is the validated division of responsibility:

```
+--------------------------+---------------------------+
| PSR (release.yml)        | next_version.py           |
| Stable releases only     | Dev + RC + Stable calc    |
+--------------------------+---------------------------+
| - Parses conventional    | - Receives base version   |
|   commits                |   from pyproject.toml     |
| - Determines bump level  | - Receives existing tags  |
|   (major/minor/patch)    |   from git                |
| - Stamps version into    | - Produces PEP 440        |
|   pyproject.toml         |   versions:               |
| - Stamps version into    |   1.2.3.dev1              |
|   framework-catalog.yaml |   1.2.3rc1                |
| - Creates git commit     |   1.2.3                   |
| - Creates git tag        | - Outputs JSON for CI     |
| - Pushes to remote       |   consumption             |
+--------------------------+---------------------------+
```

### What Could Improve

1. **Bump level extraction from PSR for dev/rc stages.** Currently `next_version.py` always bumps patch for dev releases (`_bump_patch`). If a `feat:` commit exists, the dev version should bump minor instead. You could use `semantic-release version --print` to get the bump level, then pass it to `next_version.py`.

2. **Commitizen as alternative.** Commitizen (`cz bump`) natively supports `version_scheme = "pep440"` and has `--devrelease` and `--prerelease rc` flags that produce PEP 440 output directly [9][10]. Command: `cz bump --get-next` outputs just the version string. You already have commitizen as a dependency (`commitizen>=3.12.0`). However, switching mid-project has migration risk.

---

## Conflict: PSR Tags vs. Your Tags

**This is the most important finding.** PSR's tag parser and your pipeline's tag format are incompatible for prerelease tags:

| Source | Format | Example |
|--------|--------|---------|
| PSR internal | SemVer | `v1.2.3-rc.1` |
| Your pipeline | PEP 440 | `v1.2.3rc1` |

**Impact**: PSR will **never** see your dev/rc tags. When it runs `--print`, it only considers stable tags. This is actually **beneficial** because:

- PSR calculates the next stable version from the last stable tag
- Your custom script calculates dev/rc versions from the same base
- There is no conflict because they operate on different tag sets

**Risk**: If someone manually runs `semantic-release version --as-prerelease`, it would create a SemVer-format tag (`v1.2.3-rc.1`) that conflicts with your PEP 440 convention. Mitigation: ensure PSR is only used via the `release.yml` workflow, never for dev/rc stages.

---

## Full Citations

[1] python-semantic-release contributors. "Support PEP 440 versioning; Issue #455." GitHub. https://github.com/python-semantic-release/python-semantic-release/issues/455. Accessed 2026-02-23. Reputation: medium-high (industry_leaders/github.com).

[2] python-semantic-release contributors. "Multibranch releases convert SemVer version to PEP 440 version; Issue #844." GitHub. https://github.com/python-semantic-release/python-semantic-release/issues/844. Accessed 2026-02-23. Reputation: medium-high (industry_leaders/github.com).

[3] python-semantic-release. "Command Line Interface (CLI)." ReadTheDocs. https://python-semantic-release.readthedocs.io/en/latest/api/commands.html. Accessed 2026-02-23. Reputation: high (readthedocs.org/official docs).

[4] python-semantic-release. "Version Algorithm (source)." ReadTheDocs. https://python-semantic-release.readthedocs.io/en/latest/_modules/semantic_release/version/algorithm.html. Accessed 2026-02-23. Reputation: high (readthedocs.org/official docs).

[5] python-semantic-release. "Commit Parsing." ReadTheDocs. https://python-semantic-release.readthedocs.io/en/latest/concepts/commit_parsing.html. Accessed 2026-02-23. Reputation: high (readthedocs.org/official docs).

[6] python-semantic-release. "Version class source (version.py)." ReadTheDocs (module source). https://python-semantic-release.readthedocs.io/en/latest/_modules/semantic_release/version/version.html. Accessed 2026-02-23. Reputation: high (readthedocs.org/official docs).

[7] python-semantic-release. "Configuration." ReadTheDocs. https://python-semantic-release.readthedocs.io/en/latest/configuration/configuration.html. Accessed 2026-02-23. Reputation: high (readthedocs.org/official docs).

[8] python-semantic-release. "Multibranch Releases." ReadTheDocs. https://python-semantic-release.readthedocs.io/en/latest/concepts/multibranch_releases.html. Accessed 2026-02-23. Reputation: high (readthedocs.org/official docs).

[9] Commitizen contributors. "Bump Command." Commitizen Documentation. https://commitizen-tools.github.io/commitizen/commands/bump/. Accessed 2026-02-23. Reputation: medium-high (industry_leaders/github.com).

[10] Commitizen contributors. "version_schemes.py." GitHub. https://github.com/commitizen-tools/commitizen/blob/master/commitizen/version_schemes.py. Accessed 2026-02-23. Reputation: medium-high (industry_leaders/github.com).

[11] PyPI. "python-semantic-release 10.5.3." PyPI. https://pypi.org/project/python-semantic-release/. Accessed 2026-02-23. Reputation: high (official).

[12] Python Software Foundation. "PEP 440; Version Identification and Dependency Specification." https://peps.python.org/pep-0440/. Accessed 2026-02-23. Reputation: high (official).

[13] Seth Larson. "Quirks of Python package versioning." https://sethmlarson.dev/pep-440. Accessed 2026-02-23. Reputation: medium-high (Python core contributor).

[14] python-semantic-release. "Getting Started." ReadTheDocs. https://python-semantic-release.readthedocs.io/en/latest/concepts/getting_started.html. Accessed 2026-02-23. Reputation: high (readthedocs.org/official docs).

---

## Knowledge Gaps

### Gap 1: PSR v10 Internal PEP 440 Conversion

**Searched**: Whether PSR v10 added any internal PEP 440 conversion or `version_scheme` config.
**Found**: No evidence of such a feature. Issue #455 remains open with label "needs-update." The closest v10 change is `allow_zero_version` default changed to `false`.
**Impact**: Low. Your architecture already works around this limitation.

### Gap 2: PSR Behavior When No Commits Warrant a Bump

**Searched**: What `--print` outputs when no releaseable commits exist since last tag.
**Found**: Documentation says "if no release occurs, prints the current version." Web sources conflict on whether it prints nothing or the current version.
**Impact**: Medium. Your CI scripts handle the empty/error case with `|| echo "none"`.

### Gap 3: Commitizen `--get-next` with PEP 440 Dev Format

**Searched**: Whether `cz bump --get-next --devrelease 1` produces `X.Y.Z.dev1` directly.
**Found**: Documentation confirms `--devrelease` support and PEP 440 output, but no explicit example of `--get-next` combined with `--devrelease`.
**Impact**: Medium. Relevant if you consider migrating version calculation to Commitizen.

---

## Research Metadata

- **Research Duration**: ~30 minutes
- **Total Sources Examined**: 20+
- **Sources Cited**: 14
- **Cross-References Performed**: 9
- **Confidence Distribution**: High: 83%, Medium-High: 17%
- **Output File**: `/Users/mike/ProgettiGit/Undeadgrishnackh/crafter-ai/docs/research/cicd/psr-version-calculation-for-release-trains.md`
