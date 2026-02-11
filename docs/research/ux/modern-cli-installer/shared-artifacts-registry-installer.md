# Shared Artifacts Registry - modern_CLI_installer

**Epic**: modern_CLI_installer
**Last Updated**: 2026-02-01
**Owner**: leanux-designer (Luna)

This document tracks all shared data artifacts that appear across multiple journeys in the modern_CLI_installer epic. Each artifact must have a **single source of truth** to prevent integration failures.

---

## Glossary

### Version Terminology

| Term | Definition | Example |
|------|------------|---------|
| `${version}` | Base semantic version from pyproject.toml | `1.3.0` |
| `${candidate_version}` | Development candidate version with date and sequence | `1.3.0-dev-20260201-001` |

### Candidate Version Format

```
Format: M.m.p-dev-YYYYMMDD-seq

Components:
  M.m.p      Base semantic version from pyproject.toml [project.version]
  dev        Fixed literal indicating development candidate
  YYYYMMDD   Build date (e.g., 20260201 for February 1, 2026)
  seq        Daily build sequence number (001, 002, etc.)

Examples:
  1.3.0-dev-20260201-001   First build on Feb 1, 2026
  1.3.0-dev-20260201-002   Second build on Feb 1, 2026
  1.3.0-dev-20260202-001   First build on Feb 2, 2026

Notes:
  - NO branch name in version (not PEP 440 compliant with branch names)
  - Final release versions (no suffix) only come from CI/CD on main branch
  - This format is PEP 440 compatible (dev release identifier)
```

---

## Artifact Index

| Artifact | Integration Risk | Source | Consumers |
|----------|------------------|--------|-----------|
| `${version}` | HIGH | pyproject.toml [project.version] | All three journeys |
| `${candidate_version}` | HIGH | Generated: M.m.p-dev-YYYYMMDD-seq | forge:build-local, forge:install-local-candidate |
| `${wheel_path}` | HIGH | dist/nwave-${candidate_version}-py3-none-any.whl | forge:build-local, forge:install-local-candidate |
| `${install_path}` | MEDIUM | NWAVE_INSTALL_PATH or config or default | All three journeys |
| `${agent_count}` | LOW | Runtime count | All three journeys |
| `${command_count}` | LOW | Runtime count | All three journeys |
| `${template_count}` | LOW | Runtime count | All three journeys |
| `${branch}` | LOW | git branch --show-current | Informational only |

---

## Standardized Example Values

All journey files must use these example values for horizontal consistency:

```yaml
version: "1.3.0"
candidate_version: "1.3.0-dev-20260201-001"
wheel_path: "dist/nwave-1.3.0-dev-20260201-001-py3-none-any.whl"
install_path: "~/.claude/agents/nw/"
agent_count: 47
command_count: 23
template_count: 12
date: "20260201"
sequence: "001"
```

---

## Artifact Details

### `${version}` - HIGH RISK

**Source of Truth**: pyproject.toml [project.version]

**Displayed As**:
- install-nwave: `nwave-${version}.tar.gz`, `nWave v${version}`
- forge:build-local: Pre-flight check, summary header
- forge:install-local-candidate: Changelog check, release command

**Consumers**:
1. install-nwave Steps 2, 4, 6, 7
2. forge:build-local Steps 1, 5
3. forge:install-local-candidate Steps 2, 5

**Integration Risk**: HIGH
- Version mismatch breaks user trust
- All displays must show same version

**Validation**:
- Read from pyproject.toml [project.version]
- Must be valid semver format (M.m.p)
- Same value used across all three journeys

---

### `${candidate_version}` - HIGH RISK

**Source of Truth**: Generated from M.m.p-dev-YYYYMMDD-seq

**Displayed As**:
- forge:build-local: `Candidate: 1.3.0-dev-20260201-001`
- forge:install-local-candidate: Wheel filename, doctor output, release report

**Consumers**:
1. forge:build-local Steps 2, 4, 5, 6
2. forge:install-local-candidate Steps 2, 4, 5

**Integration Risk**: HIGH
- Flows through all build/install steps
- Must match wheel filename exactly

**Validation**:
- Format must be: M.m.p-dev-YYYYMMDD-seq
- NO branch name in version
- Sequence padded to 3 digits (001, 002, etc.)

---

### `${wheel_path}` - HIGH RISK

**Source of Truth**: Generated from dist/nwave-${candidate_version}-py3-none-any.whl

**Example**: `dist/nwave-1.3.0-dev-20260201-001-py3-none-any.whl`

**Consumers**:
1. forge:build-local Steps 5, 6
2. forge:install-local-candidate Steps 1, 2, 3

**Integration Risk**: HIGH
- Must exist after build
- Must match candidate_version
- Used in pipx install command

---

### `${install_path}` - MEDIUM RISK

**Source of Truth**: Resolution order:
1. NWAVE_INSTALL_PATH environment variable (highest priority)
2. config/installer.yaml [paths.install_dir]
3. Default: ~/.claude/agents/nw/ (fallback)

**Example**: `~/.claude/agents/nw/`

**Consumers**:
1. install-nwave Steps 3, 4, 5, 7
2. forge:install-local-candidate Steps 4, 5

**Integration Risk**: MEDIUM
- Invalid path causes doctor failures
- Must be writable

---

### `${agent_count}` - LOW RISK

**Source of Truth**: Runtime count of installed/bundled agents

**Example**: `47`

**Consumers**:
1. install-nwave Steps 4, 5, 7
2. forge:build-local Steps 4, 5
3. forge:install-local-candidate Steps 4, 5

**Validation**:
- Must match actual files bundled/installed
- Same value across validation and summary steps

---

### `${command_count}` - LOW RISK

**Source of Truth**: Runtime count of installed/bundled commands

**Example**: `23`

**Consumers**: Same as agent_count

---

### `${template_count}` - LOW RISK

**Source of Truth**: Runtime count of installed/bundled templates

**Example**: `12`

**Consumers**: Same as agent_count

---

### `${branch}` - LOW RISK

**Source of Truth**: git branch --show-current

**Example**: `installer`

**Consumers**:
1. forge:install-local-candidate Step 5 (informational only)

**Integration Risk**: LOW
- Informational only
- NOT part of candidate_version

**Important**: Branch is NOT included in the candidate version format.

---

## Integration Checkpoints

### Checkpoint 1: Version Consistency (All Journeys)

**What**: Version must be consistent across all three journeys

**Artifacts Involved**:
- `${version}` from pyproject.toml
- All display locations in all three journeys

**Validation**:
- Same version shown in: download, pre-flight, summary, welcome, /nw:version

---

### Checkpoint 2: Wheel Path Derivation (forge:build-local -> forge:install-local-candidate)

**What**: Wheel path must be derived consistently from candidate_version

**Artifacts Involved**:
- `${candidate_version}` (e.g., 1.3.0-dev-20260201-001)
- `${wheel_path}` (e.g., dist/nwave-1.3.0-dev-20260201-001-py3-none-any.whl)

**Validation**:
- Wheel file must exist at derived path
- Path must be passed correctly to install command

---

### Checkpoint 3: Count Consistency (All Journeys)

**What**: Agent, command, and template counts must match

**Artifacts Involved**:
- `${agent_count}` in wheel validation, summary, doctor, /nw:version
- `${command_count}` same locations
- `${template_count}` same locations

**Validation**:
- Counts in build validation = counts in summary
- Counts in doctor = counts in install manifest
- Counts in /nw:version = counts in doctor

---

### Checkpoint 4: Install Path Resolution (All Journeys)

**What**: Install path must be resolved consistently

**Validation**:
- Path resolved once in pre-flight
- Same path used in all subsequent steps
- Path displayed correctly in doctor and summary

---

## Cross-Journey Integration

### forge:build-local -> forge:install-local-candidate

```yaml
handoff_artifacts:
  - wheel_path: "Passed to install command"
  - candidate_version: "Used for version verification"
  - agent_count: "Used for doctor validation"
  - command_count: "Used for doctor validation"
  - template_count: "Used for doctor validation"
```

### forge:install-local-candidate shares with install-nwave

```yaml
shared_patterns:
  - doctor_verification: "Same health check format"
  - install_path_resolution: "Same resolution order"
  - count_validation: "Same validation approach"
```

---

## Bug Detection Patterns

### Pattern 1: Multiple Version Sources

**Symptom**: Version shows "2.1.0" in build but "1.3.0" in install

**Root Cause**: Different journeys reading from different sources

**Fix**: All journeys read from pyproject.toml [project.version]

---

### Pattern 2: Branch in Version Format

**Symptom**: Version shows "1.3.0-feature-new-agent-20260201-001" (not PEP 440 compliant)

**Root Cause**: Old format included branch name

**Fix**: Use M.m.p-dev-YYYYMMDD-seq format (no branch)

---

### Pattern 3: Inconsistent Example Data

**Symptom**: Build uses agent_count=30, install uses agent_count=47

**Root Cause**: Example values not standardized

**Fix**: All journeys use same example values (47, 23, 12)

---

### Pattern 4: Wheel Path Mismatch

**Symptom**: Build creates "dist/nwave-1.3.0.whl" but install looks for "dist/nwave-1.3.0-dev-20260201-001.whl"

**Root Cause**: Candidate version not used consistently in wheel filename

**Fix**: Wheel path must include full candidate_version

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-01 | Initial creation for modern_CLI_installer epic | Luna (leanux-designer) |
| 2026-02-01 | Aligned candidate version format to M.m.p-dev-YYYYMMDD-seq | Luna (per Eclypse review) |
| 2026-02-01 | Standardized example values across all journeys | Luna (per Eclypse review) |

---

*Registry maintained by Luna (leanux-designer) for horizontal coherence across modern_CLI_installer epic.*
